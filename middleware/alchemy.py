# -*- coding: utf-8 -*-
"""
filedesc: sqlalchemy session support
@author: Yura A
"""
import gevent

from noodles.middleware import BaseMiddleware
from noodles.utils.session_proxy import SessionProxy
from alchemy_config import CREATEFUNC, DB_CONNECTIONS


SESSION = SessionProxy(createfunc=CREATEFUNC, connections=DB_CONNECTIONS)


def greenlet_spawn(fn, *args, **kw):
    """
    Spawn greenlet and remove sqlalchemy session on end
    :rtype : greenlet
    :param fn:
    :param args:
    :param kw:
    :return: :rtype:
    """
    g = gevent.spawn(fn, *args, **kw)
    g.link_value(lambda x: SESSION._remove_registry_session(x))
    return g


class AlchemyMiddleware(BaseMiddleware):
    """
    Middleware that handles SqlAlchemy sessions
    """
    def end(self, producer, req):
        """

        :param producer:
        :param req:
        :return: :rtype:
        """
        SESSION.remove()
        return self.link(producer, req)


def watchdog():
    old = set()
    while True:
        gevent.sleep(60)
        pairs = set(SESSION._get_open_pairs())
        selected = old.intersection(pairs)
        for greenlet, transaction in selected:
            SESSION._remove_registry_session(greenlet)
        old = pairs.difference(selected)
        #print SESSION.status()

gevent.spawn(watchdog)
