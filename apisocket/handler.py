import re
from socket import SHUT_WR

from gevent.pywsgi import WSGIHandler
from noodles.geventwebsocket.handler import WebSocketHandler


class ApiSocketHandler(WSGIHandler):
    RE_REQUEST_URL = re.compile(ur".*/(?P<namespace>[^/]+)/"
                                "(?P<transport>[^/]+)/?$", re.M | re.S | re.U)

    RE_HANDSHAKE_URL = re.compile(r"^/(?P<namespace>[^/]+)/1/$", re.X)
    ENABLED_TRANSPORTS = [
        'ws',
        'lp',
    ]

    handlers = {
        'ws': WebSocketHandler,
    }

    def __init__(self, *args, **kwargs):
        super(ApiSocketHandler, self).__init__(*args, **kwargs)

    def handle_one_response(self):
        splitted_path = self.path.split("/")

        if self.server.namespace not in splitted_path:
            return super(ApiSocketHandler, self).handle_one_response()

        request_tokens = self.RE_REQUEST_URL.match(self.path)

        if request_tokens:
            request_tokens = request_tokens.groupdict()
            transport_type = request_tokens.get('transport')
            handler = self.handlers.get(transport_type)

        if not handler:
            return self.handle_bad_request()

        self.__class__ = handler
        self.prevent_wsgi_call = True  # thank you
        # TODO: any errors, treat them ??
        self.handle_one_response()

    def handle_bad_request(self):
        self.close_connection = True
        self.start_response("400 Bad Request", [
            ('Content-Type', 'text/plain'),
            ('Connection', 'close'),
            ('Content-Length', 0)
        ])

    def read_requestline(self):
        data = self.rfile.read(7)
        if data[:1] == '<':
            try:
                data += self.rfile.read(15)
                if data.lower() == '<policy-file-request/>':
                    self.socket.sendall(self.server.flash_policy)
                else:
                    self.log_error('Invalid request: %r', data)
            finally:
                self.socket.shutdown(SHUT_WR)
                self.socket.close()
                self.socket = None
        else:
            return data + self.rfile.readline()
