# -*- coding: utf-8 -*-
"""
filedesc: base websocket implementation on top of gevent
"""
import gevent
import sys
import traceback

from datetime import datetime
from gevent.pywsgi import WSGIServer
from socket import error

from noodles.apisocket.handler import ApiSocketHandler
from config import USE_ALCHEMY_MW


if USE_ALCHEMY_MW:
    from noodles.middleware.alchemy import greenlet_spawn
    SPAWN = greenlet_spawn
else:
    SPAWN = 'default'


assert gevent.version_info >= (0, 13, 2),\
    'Newer version of gevent is required to run websocket.server'


__all__ = ['ApiSocketServer']


class ApiSocketServer(WSGIServer):

    def __init__(self, listener, application=None,
                 backlog=None, spawn=SPAWN, log='default',
                 handler_class=None, environ=None, namespace='api',
                 **ssl_args):
        self.namespace = namespace

        if handler_class is None:
            handler_class = ApiSocketHandler

        super(ApiSocketServer, self).__init__(
            listener, application,
            backlog=backlog, spawn=spawn, log=log, handler_class=handler_class,
            environ=environ, **ssl_args)

    def start_accepting(self):
        super(ApiSocketServer, self).start_accepting()
        self.log_message('%s accepting connections on %s',
                         self.__class__.__name__, _format_address(self))

    def kill(self):
        super(ApiSocketServer, self).kill()

    def log_message(self, message, *args):
        log = self.log
        if log is not None:
            try:
                message = message % args
            except Exception:
                traceback.print_exc()
                try:
                    message = '%r %r' % (message, args)
                except Exception:
                    traceback.print_exc()
            log.write('%s %s\n'
                      % (datetime.now().replace(microsecond=0), message))


def _format_address(server):
    try:
        if server.server_host == '0.0.0.0':
            return ':%s' % server.server_port
        return '%s:%s' % (server.server_host, server.server_port)
    except Exception:
        traceback.print_exc()
