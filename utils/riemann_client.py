# -*- coding: utf-8 -*-
"""
filedesc: riemann reporter
@author: Yura A
"""

import bernhard
import gevent
from noodles.utils.logger import log
from gevent.queue import JoinableQueue
from config import RIEMANN_SOURCE, RIEMANN_ARGS, RIEMANN_CLIENTS


RIEMANN_QUEUE = JoinableQueue()


def worker(n):
    cli = bernhard.Client(**RIEMANN_ARGS)
    while True:
        try:
            target, metric = RIEMANN_QUEUE.get()
            target = target.partition('?')[0]
            target = target.replace('/', '.')
            event = {'service': target,
                     'metric': metric}
            event.update(RIEMANN_SOURCE)
            result = cli.send(event=event)
            log.debug("Sent %s result %s", target, result)
        except Exception as e:
            log.error(e)

for n in xrange(RIEMANN_CLIENTS):
    gevent.spawn(worker, n)
