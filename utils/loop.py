# -*- coding: utf-8 -*-
"""
filedesc: common loops
@author: Yura A
"""
import gevent
from noodles.middleware.alchemy import SESSION, greenlet_spawn
from noodles.redisconn import RedisConn


def spawn_listener(channel_name,
                   action,
                   on_spawn=None,
                   termination=None):
    " Listen channel and do the given action"
    def _listener():
        pb = RedisConn.pubsub()
        _pubsub = pb.subscribe(channel_name)
        if on_spawn:
            on_spawn(_pubsub)
        for msg in pb.listen():
            try:
                if termination and termination(channel_name):
                    # it could be unsubscribe here
                    return
                if msg['type'] == 'message':
                    SESSION.begin()
                    action(msg, channel_name)
            finally:
                gevent.sleep(0)
                SESSION.close()
    return greenlet_spawn(_listener)

