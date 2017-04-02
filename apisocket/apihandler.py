# -*- coding: utf-8 -*-
"""
Base handler class is defined from which a web socket channel
implementation is derived
"""
import json
import sys
import time
from logging import Formatter
from collections import deque

import gevent
import re
from gevent.event import Event
from mako.filters import xml_escape
from noodles.utils.helpers import is_ws_error_abnormal

from noodles.utils.mailer import report_exception, format_exception
from config import WS_CHANNELS, DEBUG, USE_ALCHEMY_MW
from geventwebsocket.websocket import WebSocketError
from noodles.redisconn import RedisConn
from noodles.websocket.wssession import WSSession
from noodles.utils.datahandler import datahandler
from noodles.utils.logger import log


TEST_DATA_KEYS = ('timestamp',
                  'testname',
                  'method',
                  'job',
                  'suite_id',
                  'test_id',
                  'class')


if USE_ALCHEMY_MW:
    from noodles.middleware.alchemy import session_handler

from config import EXCEPTION_FLAVOR

try:
    from config import ENCODING
except ImportError:
    ENCODING = 'utf-8'

try:
    from config import RIEMANN_USE
except ImportError:
    RIEMANN_USE = False

if RIEMANN_USE:
    from noodles.utils.riemann_client import RIEMANN_QUEUE


class ApiSocketSendError(Exception):
    pass


class ApiSocketError(Exception):
    pass


class MultiChannelWSError(Exception):
    pass


def action(func):
    """decorator to mark permitted actions as such.
    """
    def action_wrapper(*args, **kw):
        return func(*args, **kw)
    return action_wrapper


class ApiSocketMessage(object):
    def __init__(self, data):
        if type(data) == dict:
            self.data = data
            return
        # TODO: check lib: https://bitbucket.org/Jeffrey/gevent-websocket/
        # issue/5/encoding-issue-when-sending-non-ascii
        self.raw_data = str(data.decode('utf-8')).encode(ENCODING)
        try:
            self.data = json.loads(self.raw_data)
        except ApiSocketError as e:
            self.data = self.raw_data
            extra = {'request': self.data}
            log.error(format_exception(e, None), extra=extra)
            report_exception(e, extra=extra)

    def __getattr__(self, name):
        if name == 'raw_data':
            self.raw_data = self.data
            return self.raw_data


class MultiSocketHandler(object):
    """Abstract class for implementing server side web socket logic.
    """
    def __init__(self, request, transport='ws'):
        self.check_permissions = True
        self.is_auth = False
        self.request = request
        self.transport = transport
        self.channel_history = {'request': request,
                                'transport': transport,
                                'messages': deque([], 20)}
        self.ws = None

    def propagate_greenlet_data(self, data):
        pass

    def pre_open(self):
        pass

    def after_open(self):
        pass

    def onopen(self):
        pass

    def onclose(self):
        pass

    def send(self, response):
        raise NotImplementedError

    def channel_404(self, channel):
        try:
            return self.ws.send(json.dumps({'channel': channel,
                                            'action': 'no-such-channel',
                                            'note': 'Channel with ID=%s not '
                                                    'found' % channel,
                                            }))
        except WebSocketError as e:
            if is_ws_error_abnormal(e):
                log.error('WebSocket fault: %s' % e.message,
                          extra=self.channel_history)

    def run_callback(self, obj, args=None):
        try:
            assert hasattr(self, 'on%s' % obj)
            f = getattr(self, 'on%s' % obj)
            if args is not None:
                return f(args)
            else:
                return f()
        except WebSocketError as e:
            if is_ws_error_abnormal(e):
                log.warn('WebSocket fault: %s' % e.message)
                log.error(format_exception(e, None),
                          extra=self.channel_history)
                report_exception(e, extra=self.channel_history)
        except Exception as e:
            self.onerror(e)
            if not self.ws.closed:
                try:
                    self.ws.close()
                except WebSocketError as e:
                    if is_ws_error_abnormal(e):
                        log.error('WebSocket fault: %s' % e.message,
                                  extra=self.channel_history)
        finally:
            if USE_ALCHEMY_MW:
                session_handler.close()

    def action_parser(self, act):
        """
        parse api action to callable name
        Example: getApiMethod -> get_api_method
        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', act)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def onmessage(self, msg):
        if type(msg) != dict:
            raise TypeError("Request object type is %s not dict!"
                            % type(msg.data))
        act = self.action_parser(msg['pkg'].get('action', False))
        assert not act.startswith('_'), "security violation"

        if not action:
            raise ValueError("Action not defined, error!")
        handler = getattr(self, act)
        if not handler:
            raise ValueError("Handler not defined, error!")

        assert handler.__name__ == "action_wrapper", \
            "%s is not allowed to be executed externally." % act

        self.send(handler(msg['pkg'].get('data', None)))

    def onerror(self, e):
        """Send here Exception and traceback by Error channel
        """
        f = Formatter()
        history = json.dumps(self.channel_history,
                             indent=2,
                             default=datahandler)
        data = (history, xml_escape(f.formatException(sys.exc_info())),)
        if EXCEPTION_FLAVOR == 'html':
            traceback = '<pre>%s\n\n%s</pre>' % data
        else:
            traceback = '%s\n%s' % data
        if DEBUG:
            err_message = {'channel': WS_CHANNELS['ERROR_CHID'],
                           'pkg': {'exception': repr(e), 'tb': traceback}}
        else:
            err_message = {'channel': WS_CHANNELS['ERROR_CHID'],
                           'pkg': {'exception': 'error 500',
                                   'tb': 'an error occurred'}}
        log.error(format_exception(e, None), extra=self.channel_history)
        report_exception(e, extra=self.channel_history)
        if not self.ws.closed:
            try:
                self.ws.send(json.dumps(err_message, separators=(', ', ':')))
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)

    def bad_request(self, message="Bad request"):
        if not self.ws.closed:
            try:
                self.ws.send(
                    json.dumps({'pkg': {'action': 'open',
                                        'data': {'result': 400,
                                                 'message': message,
                                                 },
                                        },
                                }))
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)

    def send_error_code(self, code, act, channel):
        if not self.ws.closed:
            try:
                self.ws.send(json.dumps({'pkg': {'action': act,
                                         'data': {'channel': channel,
                                                  'result': code,
                                                  },
                                                 },
                                         }))
                self.ws.close()
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)


class MultiChannelSocket(MultiSocketHandler):
    """
    Use this class to implement virtual channels over web socket.
    To use it, inherit class from this and override init_channel function,
    where you can register all channel handlers by register_channel function

    Example:
    class MyWebSocket(MultiChannelWS):
        def init_channels(self):
            self.register_channel(0, NullChannelHandler)
            self.register_channel(1, FirstChannelHandler)
            ...
    """

    def __init__(self, request, transport):
        super(MultiChannelSocket, self).__init__(request, transport)
        self.session = WSSession()
        self.channel_handlers = {}
        self.permissions = None
        self.allowed_channels = None
        self.access_token = None
        self.close_event = Event()

    def clear_test_data(self):
        for key in TEST_DATA_KEYS:
            if self.channel_history.get(key):
                del self.channel_history[key]

    def write_test_data(self, test_data):
        for key in TEST_DATA_KEYS:
            self.channel_history[key] = test_data[key]

    # noinspection PyUnusedLocal
    def __call__(self, env, start_response):
        websocket = env.get('wsgi.websocket')
        if not websocket:
            self.bad_request()
        self.ws = websocket
        # Endless event loop
        while 1:
            try:
                data = self.ws.receive()
                self.clear_test_data()
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)
                break
            except Exception:
                f = Formatter()
                traceback = f.formatException(sys.exc_info())
                log.error('Servlet fault: \n%s' % traceback,
                          extra=self.channel_history)
                break

            if data:
                jd = json.loads(data)
                if jd.get('pkg') \
                        and jd['pkg'].get('data') \
                        and isinstance(jd['pkg']['data'], dict)\
                        and jd['pkg']['data'].get('testData'):
                    self.write_test_data(jd['pkg']['data']['testData'])
                    del jd['pkg']['data']['testData']
                self.channel_history['messages'].append(jd)
                if hasattr(self.session, 'sess') and self.session.sess:
                    self.channel_history['session_id'] = self.session.sess.id
                    self.channel_history['user_id'] = self.session.sess.user_id
                if not jd.get('channel') and jd.get('pkg'):
                    act = jd['pkg'].get('action')
                    assert not act.startswith('_'), "security violation"
                    try:
                        handler = getattr(self, act)
                    except WebSocketError as e:
                        if is_ws_error_abnormal(e):
                            f = Formatter()
                            traceback = f.formatException(sys.exc_info())
                            log.error('Global channel action error: \n%s'
                                      % traceback, extra=self.channel_history)
                        break
                    assert handler.__name__ == "action_wrapper", \
                        "%s is not allowed to be executed externally." % act
                    handler(jd['pkg']['data'])
                    continue
                if self.check_permissions \
                        and not self.validate_send(jd.get('channel')):
                    jd['result'] = 403
                    if not self.ws.closed:
                        try:
                            self.ws.send(json.dumps(jd))
                        except WebSocketError as e:
                            if is_ws_error_abnormal(e):
                                log.error('WebSocket fault: %s' % e.message,
                                          extra=self.channel_history)
                    continue
                else:
                    self.run_callback('message', ApiSocketMessage(data))
            else:
                log.debug('Web Socket is disconnected')
                self.close_event.set()
            if self.close_event.is_set():
                break
        self.run_callback('close')

    @action
    def open(self, data):
        self.propagate_greenlet_data(data)
        if not data.get('token'):
            self.bad_request(message='No access token, exit')
            return

        if not data.get('channel'):
            self.bad_request(message='No channel name')
            return

        self.access_token = data.get('token')
        self.reopen = data.get('reopen', False)
        self.pre_open()
        handler = self.allowed_channels.get(data.get('channel'))
        if not handler:
            return self.channel_404(data['channel'])

        if self.check_permissions \
                and not self.validate_open(data.get('channel')):
            return self.send_error_code(403, 'open', data.get('channel'))
        if not self.is_auth:
            return self.send_error_code(403, 'open', data.get('channel'))

        handler = self.register_channel(data.get('channel'), handler)
        self.run_callback('open')
        pkg = {'action': 'open',
               'data': {'closable': handler.closable,
                        'result': 200},
               }
        package_to_send = {'channel': data.get('channel'),
                           'pkg': pkg,
                           'session_params': self.session.params}
        raw_data = json.dumps(package_to_send, default=datahandler)
        self.after_open()
        try:
            self.ws.send(raw_data)
        except WebSocketError as e:
            if is_ws_error_abnormal(e):
                log.error('WebSocket fault: %s' % e.message,
                          extra=self.channel_history)

    @action
    def close(self, data):
        if not data.get('channel'):
            raise Exception('No channel name, exit')

        handler = self.channel_handlers.get(data['channel'])

        if not handler:
            return self.channel_404(data['channel'])

        if self.check_permissions and not self.validate_close(data['channel']):
            return self.send_error_code(403, 'open', data['channel'])

        if not handler.closable and not self.ws.closed:
            try:
                self.ws.send(
                    json.dumps({'pkg': {'action': 'close',
                                        'data': {'channel': data['channel'],
                                                 'result': 501},
                                        },
                                }))
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)
            return

        handler.onclose()
        del self.channel_handlers[data['channel']]

        if not self.ws.closed:
            try:
                self.ws.send(
                    json.dumps({'pkg': {'action': 'close',
                                        'data': {'channel': data['channel'],
                                                 'result': 200},
                                        },
                                }))
            except WebSocketError as e:
                if is_ws_error_abnormal(e):
                    log.error('WebSocket fault: %s' % e.message,
                              extra=self.channel_history)

    def onopen(self):
        for channel_handler in self.channel_handlers.values():
            channel_handler.onopen()

    def onclose(self):
        for channel_handler in self.channel_handlers.values():
            channel_handler.onclose()

    def onmessage(self, msg):
        channel = msg.data.get('channel')
        if channel is None:
            raise MultiChannelWSError('No such channel ID in request')
        channel_handler = self.channel_handlers.get(channel)
        if not channel_handler:
            return self.channel_404(channel)
        if RIEMANN_USE:
            start = time.time()
            act = 'unknown'
            if 'action' in msg.data['pkg']:
                act = msg.data['pkg']['action']
            elif 'Action' in msg.data['pkg']:
                if 'name' in msg.data['pkg']['Action']:
                    act = msg.data['pkg']['Action']['name']
            channel_handler.onmessage(msg.data)
            RIEMANN_QUEUE.put(("ws.%s.%s" % (channel, act),
                               time.time() - start))
        else:
            channel_handler.onmessage(msg.data)

    def validate(self, permission_name):
        if self.permissions:
            return bool(self.permissions.get_perm(permission_name))
        return False

    def validate_open(self, channel):
        return self.validate('%s.ws.open' % channel)

    def validate_close(self, channel):
        return self.validate('%s.ws.close' % channel)

    def validate_send(self, channel):
        return self.validate('%s.ws.send' % channel)

    def register_channel(self, channel, channel_handler_class):
        """Registers new channel with channel id - channel and channel handler
           class - channel_handler_class
        """
        channel_handler = channel_handler_class(self.request,
                                                channel,
                                                self.ws,
                                                self.session,
                                                self.permissions,
                                                self.channel_history)
        self.channel_handlers[channel] = channel_handler
        return channel_handler


class VirtualChannelHandler(MultiSocketHandler):
    def __init__(self, request, channel, websocket, session, permission,
                 channel_history):
        super(VirtualChannelHandler, self).__init__(request)
        self.closable = False
        self.session = session
        self.permission = permission
        self.channel = channel
        self.ws = websocket
        self.subscribe_name = None
        self.dispatcher = None
        self.channel_history = channel_history

    def _send_ws(self, data):
        if type(data) != dict:
            raise TypeError("data is %s not dict" % type(data))
        package_to_send = {'channel': self.channel,
                           'pkg': data,
                           'session_params': self.session.params,
                           }
        data = json.dumps(package_to_send, default=datahandler)
        try:
            self.ws.send(data)
        except WebSocketError as e:
            if is_ws_error_abnormal(e):
                log.error('WebSocket fault: %s' % e.message,
                          extra=self.channel_history)
            self.onclose()

    def send(self, data):
        has_send_hook = bool(self.ws.environ) and '__on_send' in self.ws.environ
        if has_send_hook:
            fn_ = self.ws.environ['__on_send']
            fn_()
        self._send_ws(data)

    def dispatcher_routine(self):
        """This listens dispatcher redis channel and send data through channel
        """
        sub = RedisConn.pubsub()
        log.info('subscribing to %s' % self.subscribe_name)
        sub.subscribe(self.subscribe_name)
        for msg in sub.listen():
            if not 'type' in msg:
                continue

            if msg['type'] != 'message':
                continue

            log.info('CHANNEL %s < DISPATCHER MESSAGE %s' % (self, msg))
            self._send_ws(json.loads(msg['data']))
