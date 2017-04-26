"""
Base handler class is defined from which a web socket channel
implementation is derived
"""
import time
import json
import re
import sys
from config import WS_CHANNELS, DEBUG, USE_ALCHEMY_MW
from logging import Formatter
from mako.filters import xml_escape

import gevent
from gevent.event import Event
from noodles.apisocket.handler import ApiSocketHandler
from noodles.utils.datahandler import datahandler
from noodles.utils.logger import log
from noodles.utils.mailer import MailMan
from noodles.websocket.wssession import WSSession
from noodles.geventwebsocket.websocket import WebSocketError
from noodles.redisconn import RedisConn
if USE_ALCHEMY_MW:
    from noodles.middleware.alchemy import SESSION as sa_session


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
    "decorator to mark permitted actions as such."
    def action_wrapper(*args, **kw):
        return func(*args, **kw)
    return action_wrapper


class ApiSocketMessage(object):
    def __init__(self, data):
        if type(data) == dict:
            self.data = data
            return
        self.raw_data = data.encode(ENCODING)
        try:
            self.data = json.loads(self.raw_data)
        except:
            self.data = self.raw_data

    def __getattr__(self, name):
        if name == 'raw_data':
            self.raw_data = self.data
            return self.raw_data


class MultiSocketHandler(ApiSocketHandler):
    """
    Abstract class for implementing server side web socket logic.

    Usage:
    1) Inherit your handler from WebSocketHandler class and override
        onopen, onmessage, onclose functions in controllers module

        class MyHandler(WebSocketHandler):

            def onopen(self):
                #some onopen logic

            def onmessage(self):
                #some onmessage logic

            def onclose(self):
                #some onclose logic

    2) Then urlmap this class in urls module
        urlmap(map, [
            ...
            ('/wsurl', 'controllers.MyHandler'),
            ...
        ])
    That's all!
    """
    check_permissions = False
    is_auth = True

    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])
        self.close_event = Event()
        self.channel_history = [kwargs]

    @action
    def open(self, data):
        if not data.get('token'):
            self.bad_request(message='No access token, exit')
            return

        if not data.get('channel'):
            self.bad_request(message='No channel name')
            return

        self.access_token = data.get('token')
        self.pre_open()
        handler = self.allowed_channels.get(data.get('channel'))

        if not handler:
            return self.channel_404(data['channel'])

        if self.check_permissions and not self.validate_open(data.get('channel')):
            return self.send_error_code(403, 'open', data.get('channel'))
        if not self.is_auth:
            return self.send_error_code(403, 'open', data.get('channel'))

        self.register_channel(data.get('channel'), handler)
        self.run_callback('open')
        pkg = {'action': 'open',
               'data': {
                    'closable': handler.closable,
                    'result': 200
                        },
               }
        package_to_send = {'channel': data.get('channel'),
                           'pkg': pkg,
                           'session_params': self.session.params,
                           }
        raw_data = json.dumps(package_to_send, default=datahandler)
        self.transport.send(raw_data)

    @action
    def close(self, data):
        if not data.get('channel'):
            raise Exception('No channel name, exit')

        handler = self.channel_handlers.get(data['channel'])

        if not handler:
            return self.channel_404(data['channel'])

        if self.check_permissions and not self.validate_close(data['channel']):
            return self.send_error_code(403, 'open', data['channel'])

        if not handler.closable:
            self.transport.send(json.dumps({
                'pkg': {
                    'action': 'close',
                    'data': {
                        'channel': data['channel'],
                        'result': 501,
                    },
                },
            }))
            return

        handler.onclose()
        del self.channel_handlers[data['channel']]

        self.transport.send(json.dumps({
            'pkg': {
                'action': 'close',
                'data': {
                    'channel': data['channel'],
                    'result': 200,
                },
            },
        }))

    def validate_open(self, channel):
        if not self.permissions.get_perm('%s.ws.open' % channel):
            return False
        return True

    def validate_close(self, channel):
        if not self.permissions.get_perm('%s.ws.close' % channel):
            return False
        return True

    def validate_send(self, channel):
        if not self.permissions.get_perm('%s.ws.send' % channel):
            return False
        return True

    def __call__(self, env, start_response):
        transport = env.get('wsgi.transport')
        if not transport:
            self.handle_bad_request()

        self.transport = transport
        # Endless event loop
        while 1:
            try:
                data = self.transport.receive()
            except WebSocketError as e:
                log.warn('WebSocket fault: %s' % e.message)
                break
            except Exception:
                f = Formatter()
                traceback = f.formatException(sys.exc_info())
                log.error('Servlet fault: \n%s' % traceback)
                break

            if data:
                jd = json.loads(data)
                self.channel_history.append(jd)
                if not jd.get('channel') and jd.get('pkg'):
                    action = jd['pkg'].get('action')
                    assert not action.startswith('_'), "security violation"
                    try:
                        handler = getattr(self, action)
                    except Exception:
                        f = Formatter()
                        traceback = f.formatException(sys.exc_info())
                        log.error('Global channel action error: \n%s'
                                      % traceback)
                        break
                    assert handler.__name__ == "action_wrapper", \
                        "%s is not allowed to be executed externally." \
                        % (action)
                    handler(jd['pkg']['data'])
                    continue
                if self.check_permissions \
                        and not self.validate_send(jd.get('channel')):
                    jd['result'] = 403
                    self.transport.send(json.dumps(jd))
                    continue
                else:
                    self.run_callback('message', ApiSocketMessage(data))
            else:
                log.debug('Web Socket is disconnected')
                self.close_event.set()
            if self.close_event.is_set():
                break
        self.run_callback('close')

    def run_callback(self, obj, args=None):
        try:
            assert hasattr(self, 'on%s' % obj)
            f = getattr(self, 'on%s' % obj)
            if args:
                return f(args)
            else:
                return f()
        except WebSocketError as e:
            log.warn('WebSocket fault: %s' % e.message)
        except Exception as e:
            log.exception('Handler fault:')
            rt = self.onerror(json.dumps(str(e), separators=(', ', ':')))
            self.transport.close()
            return rt
        finally:
            if USE_ALCHEMY_MW:
                gevent.sleep(0)
                sa_session.close()

    def action_parser(self, action):
        """
        parse api action to callable name
        Example: getApiMethod -> get_api_method
        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', action)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def onopen(self):
        pass

    def onclose(self):
        pass

    def onmessage(self, msg):
        if type(msg) != dict:
            raise TypeError("""
                            Request object type is %s not dict!
                            """ % type(msg.data))
        action = self.action_parser(msg['pkg'].get('action', False))
        assert not action.startswith('_'), "security violation"

        if not action:
            raise ValueError("Action not defined, error!")
        handler = getattr(self, action)
        if not handler:
            raise ValueError("Handler not defined, error!")

        assert handler.__name__ == "action_wrapper", \
            "%s is not allowed to be executed externally." % (action)

        response = handler(msg['pkg'].get('data', None))

        if hasattr(getattr(self, 'channel_pusher', None), '__call__'):
            self.channel_pusher(response)
        else:
            self.send(response)

    def onerror(self, e):
        """
        Send here Exception and traceback by Error channel
        """
        f = Formatter()
        traceback = '<pre>%s\n\n%s</pre>' % (
                json.dumps(self.channel_history, indent=2, default=datahandler),
                xml_escape(f.formatException(sys.exc_info())))
        if DEBUG:
            err_message = {'channel': WS_CHANNELS['ERROR_CHID'],
                           'pkg': {'exception': e.__repr__(), 'tb': traceback}}
        else:
            err_message = {'channel': WS_CHANNELS['ERROR_CHID'],
                           'pkg': {'exception': 'error 500',
                                   'tb': 'an error occured'}}
            MailMan.mail_send(MailMan(), e.__repr__(), traceback, with_hostname=True)
        self.transport.send(json.dumps(err_message, separators=(', ', ':')))

    def dispatcher_routine(self):
        """
        This listens dispatcher redis channel and send data through channel
        """
        sub = RedisConn.pubsub()
        log.info('subscribing to %s' % self.subscribe_name)
        sub.subscribe(self.subscribe_name)
        for msg in sub.listen():
            log.info('CHANNEL %s < DISPATCHER MESSAGE %s' % (self, msg))
            self.send(json.loads(msg['data']))

    def bad_request(self, message="Bad request"):
        self.transport.send(json.dumps({
            'pkg': {
                'action': 'open',
                'data': {
                    'result': 400,
                    'message': message,
                },
            },
        }))


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

    class ChannelSender(object):
        """
        Send channel message over websocket
        """
        def __init__(self, channel, _wsh):
            self.channel = channel
            self._wsh = _wsh

        def __call__(self, data):
            if type(data) != dict:
                raise TypeError("data is %s not dict" % type(data))
            package_to_send = {'channel': self.channel,
                               'pkg': data,
                               'session_params': self._wsh.session.params,
                               }
            data = json.dumps(package_to_send, default=datahandler)
            try:
                self._wsh.transport.send(data)
            except:
                log.warning('Can\'t send data to websocket!')
                self._wsh.onclose()

    def __init__(self, **kwargs):
        super(MultiChannelSocket, self).__init__(**kwargs)
        self.channel_handlers = {}
        self.session = WSSession()

    # FIXME: Deprecated method
    def init_channels(self):
        "Override it to add new channel handlers by register_channel method"
        pass
        #raise NotImplementedError('You must specify this function')

    def register_channel(self, channel, channel_handler_class):
        """
        Registers new channel with channel id - channel and channel handler
        class - channel_handler_class"""
        channel_handler = channel_handler_class(request=self.request)
        channel_handler.send = self.ChannelSender(channel, self)
        channel_handler.session = self.session
        channel_handler.permissions = self.permissions
        self.channel_handlers[channel] = channel_handler

    def onopen(self):
        self.init_channels()
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
            action = 'unknown'
            if 'action' in msg.data['pkg']:
                action = msg.data['pkg']['action']
            elif 'Action' in msg.data['pkg']:
                if 'name' in msg.data['pkg']['Action']:
                    action = msg.data['pkg']['Action']['name']
            channel_handler.onmessage(msg.data)
            RIEMANN_QUEUE.put(("ws.%s.%s" % (channel, action),
                               time.time() - start))
        else:
            channel_handler.onmessage(msg.data)

    def channel_404(self, channel):
        data = {
            'channel': channel,
            'action': 'no-such-channel',
            'note': 'Channel with ID=%s not found' % channel,
        }
        return self.transport.send(json.dumps(data))

    def send_error_code(self, code, action, channel):
        data = {
            'pkg': {
                'action': action,
                'data': {
                    'channel': channel,
                    'result': code,
                },
            },
        }
        self.transport.send(json.dumps(data))
        self.transport.close()

    def pre_open(self):
        pass
