from gevent.server import StreamServer


__all__ = ['FlashPolicyServer']


class FlashPolicyServer(StreamServer):
    policy = '<?xml version="1.0"?>'\
             '<!DOCTYPE cross-domain-policy SYSTEM '\
             '"http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">'\
             '<cross-domain-policy><allow-access-from '\
             'domain="*" to-ports="*"/></cross-domain-policy>'

    noisy = False

    def __init__(self, listener=None, backlog=None, noisy=None, policy=None):
        if listener is None:
            listener = ('0.0.0.0', 843)
        if noisy is not None:
            self.noisy = noisy
        if policy is not None:
            self.policy = policy
        StreamServer.__init__(self, listener=listener, backlog=backlog)

    def handle(self, socket, address):
        if self.noisy:
            print 'Accepted connection from %s:%s' % address
        expected = '<policy-file-request/>'
        req = socket.makefile().read(len(expected))
        if req == expected:
            socket.sendall(self.policy)
        elif self.noisy:
            print 'Invalid request: %r' % (req, )
