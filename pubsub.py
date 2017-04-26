# -*- coding: utf-8 -*-
"""
Layer for implementation of Publisher/Subscription pattern.
Is done via redis PUBLISH/SUBSCRIBE
"""
import json

import gevent
import redis
from gevent.event import Event
from .utils.logger import log


try:
    from config import REDIS_HOST
except ImportError:
    REDIS_HOST = 'localhost'

try:
    from config import REDIS_PASSWORD
except ImportError:
    REDIS_PASSWORD = None


class PubSubAgent(object):
    """
    Implement default Publisher/Subscriber agent. It has two
    functions - subscriber and publisher which are launched through greenlets
    To use it override publisher function for depth handling connection,
    or just use this and specify pub_handler functions in instance
    """
    def __init__(self, channel, pub_handler=None, default_term=None):
        global REDIS_HOST
        self.channel = channel

        # Deprecated use of pub_handler, now just override pub_handler function
        if pub_handler:
            self.pub_handler = pub_handler
        self.default_term = default_term
        self.terminate_event = Event()
        self.begin_event = Event()

        # also create right here the publish redis connection

    def pub_handler(self, msg):
        " Override this function to handle msg"
        return msg

    def terminate(self):
        "Call this function if agent is terminated"
        # do it once
        if not self.terminate_event.is_set():
            self.before_terminate()
            self.terminate_event.set()

    def before_terminate(self):
        "Override this method to do some routines befor agent is terminated"
        pass

    def publish(self, msg):
        "Publish msg to the agent channel"
        self.pub_conn.publish(self.channel, msg)

    def publisher(self):
        """
        This function listen opened ws socket, get JSON msg and publish
        it to self.chanel
        """
        pub_conn = redis.Redis()
        self.begin_event.wait()
        while 1:
            try:
                msg = self.ws.receive()
            # Some error occures, logg exception and terminate agent
            except Exception as e:
                log.error('Get exception %s' % e.__repr__())
                self.ws.close()
                self.terminate()
                return
            if msg:  # Peer disconected
                msg = json.loads(msg)
                if self.default_term:
                    if msg[self.default_term]:
                        self.ws.close()
                        self.terminate()  # send terminate event to subscriber
                        return
                msg = self.pub_handler(msg)
                log.debug('Sent msg %s' % msg.__repr__())
                if msg:
                    pub_conn.publish(self.channel, msg)
            else:
                self.ws.close()
                self.terminate()
                return
            if self.terminate_event.is_set():
                self.ws.close()
                return

    def subscriber(self):
        global REDIS_HOST
        rc_sub = redis.Redis(REDIS_HOST, password=REDIS_PASSWORD)
        rc_sub.subscribe([self.channel])

        for msg in rc_sub.listen():
            if not self.begin_event.is_set():
                self.begin_event.set()
            if msg['type'] == 'message':
                try:
                    self.ws.send(msg['data'])
                except Exception:  # Seems to be disconnected
                    log.debug('Unsubscribe socket from channel'
                                  ' no.%s ' % self.channel)
                    self.ws.close()
                    self.terminate()
                    return
            if self.terminate_event.is_set():
                self.ws.close()
                return

    def __call__(self, ws):
        self.ws = ws  # web socket instance
        gevent.joinall([gevent.spawn(self.publisher),
                        gevent.spawn(self.subscriber)])
