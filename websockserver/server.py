'''
filedesc: base websocket implementation on top of gevent
'''
import sys
import traceback
from datetime import datetime
from socket import error

import gevent
from gevent.pywsgi import WSGIServer
from noodles.apisocket import handler
from noodles.websockserver.policyserver import FlashPolicyServer
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

    handler_class = handler.ApiSocketHandler

    def __init__(
            self, listener, application=None, policy_server=True,
            flash_policy=True, backlog=None, spawn=SPAWN, log='default',
            handler_class=None, environ=None, namespace='api', **ssl_args):
        self.namespace = namespace
        if flash_policy is True:
            self.flash_policy = FlashPolicyServer.policy
        else:
            self.flash_policy = flash_policy
        if policy_server is True:
            self.policy_server = FlashPolicyServer(policy=self.flash_policy)
        elif hasattr(policy_server, 'start'):
            self.policy_server = policy_server
        elif policy_server:
            self.policy_server = FlashPolicyServer(policy_server,
                                                   policy=self.flash_policy)
        else:
            self.policy_server = None
        super(ApiSocketServer, self).__init__(
            listener, application,
            backlog=backlog, spawn=spawn, log=log, handler_class=handler_class,
            environ=environ, **ssl_args)

    def start_accepting(self):
        self._start_policy_server()
        super(ApiSocketServer, self).start_accepting()
        self.log_message('%s accepting connections on %s',
                         self.__class__.__name__, _format_address(self))

    def _start_policy_server(self):
        server = self.policy_server
        if server is not None:
            try:
                server.start()
                self.log_message('%s accepting connections on %s',
                                 server.__class__.__name__,
                                 _format_address(server))
            except error, ex:
                sys.stdout.write('FAILED to start %s on %s: %s\n'
                                 % (server.__class__.__name__,
                                    _format_address(server), ex))
            except Exception:
                traceback.print_exc()
                sys.stdout.write('FAILED to start %s on %s\n'
                                 % (server.__class__.__name__,
                                    _format_address(server)))

    def kill(self):
        if self.policy_server is not None:
            self.policy_server.kill()
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
