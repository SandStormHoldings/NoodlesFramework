# -*- coding: utf-8 -*-
"""
filedesc: Riemann support
@author: Yura A
"""
import os
import time
import gevent
import logging
import copy

from noodles.middleware import BaseMiddleware
from noodles.utils.riemann_client import RIEMANN_QUEUE
from noodles.utils.helpers import get_config


class RiemannMiddleware(BaseMiddleware):
    def run(self, producer, req):
        req.processing_started_at = time.time()
        return self.link(producer, req)

    def end(self, producer, req):
        path = copy.copy(req.path)
        if path == '/':
            path = 'index'
        f = 1 if path.startswith('/') else 0
        t = -1 if path.endswith('/') else None
        RIEMANN_QUEUE.put(('http.%s' % path[f:t],
                           time.time() - req.processing_started_at))
        return self.link(producer, req)


def infinite_control():
    """
    * VmPeak: Peak virtual memory size.
    * VmSize: Virtual memory size.
    * VmLck:  Locked memory size (see mlock(3)).
    * VmHWM:  Peak resident set size ("high water mark").
    * VmRSS:  Resident set size.
              http://en.wikipedia.org/wiki/Resident_set_size
    * VmData, VmStk, VmExe:
              Size of data, stack, and text segments.
    """
    pid = os.getpid()
    _proc_fname = '/proc/%d/status' % pid
    status = None
    mb = 1024 * 1024 * 1024
    try:
        status = open(_proc_fname, mode='r')
        while True:
            status.seek(0)
            content = status.read()
            for key in ['VmSize', 'VmRSS', 'VmStk']:
                i = content.index(key)
                portion = content[i:].split(None, 3)
                metric = portion[2]
                data = float(portion[1])
                if metric in ['kB', 'KB']:
                    data /= 1024.0
                    metric = 'mb'
                riemann_key = 'internal.%d.%s_%s' % (pid, key, metric)
                RIEMANN_QUEUE.put((riemann_key, data))
            gevent.sleep(10)
    except Exception as e:
        logging.error(e)
    finally:
        if status:
            status.close()


if get_config('RIEMANN_USE'):
    gevent.spawn(infinite_control)
