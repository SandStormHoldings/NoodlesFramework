# -*- coding: utf-8 -*-
"""
filedesc: sqlalchemy session support
@author: Yura A
"""
import gevent

from noodles.middleware import BaseMiddleware
from noodles.utils.helpers import get_config
from noodles.utils.detect import is_celery_run
from alchemy_config import known_sessions, session_handler, sa_session as SESSION


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
    g.link_value(session_handler._remove_registry_session)
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
        session_handler.remove()
        return self.link(producer, req)
