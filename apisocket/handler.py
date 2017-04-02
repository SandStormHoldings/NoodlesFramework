# -*- coding: utf-8 -*-
from socket import SHUT_WR

import re
from gevent.pywsgi import WSGIHandler
from geventwebsocket.handler import WebSocketHandler


RE_REQUEST_URL = re.compile(r".*/(?P<namespace>[^/]+)/(?P<transport>[^/]+)/?$", re.M | re.S | re.U)

RE_HANDSHAKE_URL = re.compile(r"^/(?P<namespace>[^/]+)/1/$", re.X)
ENABLED_TRANSPORTS = ('ws',)


class ApiSocketHandler(WSGIHandler):

    handlers = {
        'ws': WebSocketHandler,
    }

    def __init__(self, *args, **kwargs):
        super(ApiSocketHandler, self).__init__(*args, **kwargs)
        self.close_connection = False
        self.headers_sent = False

    def handle_one_response(self):
        handler = None
        splitted_path = self.path.split("/")

        if self.server.namespace not in splitted_path:
            return super(ApiSocketHandler, self).handle_one_response()
        request_tokens = RE_REQUEST_URL.match(self.path)

        if request_tokens:
            request_tokens = request_tokens.groupdict()
            transport_type = request_tokens.get('transport')
            handler = self.handlers.get(transport_type)

        if handler is None:
            return self.handle_bad_request()

        self.__class__ = handler
        self.response_use_chunked = False
        # TODO: any errors, treat them ??
        self.run_application()

    def handle_bad_request(self):
        self.close_connection = True
        self.start_response("400 Bad Request", [
            ('Content-Type', 'text/plain'),
            ('Connection', 'close'),
            ('Content-Length', 0)
        ])

    def read_requestline(self):
        try:
            return self.rfile.readline()
        except Exception as e:
            self.socket.shutdown(SHUT_WR)
            self.socket.close()
            self.socket = None
            self.log_error(e)
