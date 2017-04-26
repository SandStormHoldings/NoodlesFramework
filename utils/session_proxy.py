# -*- coding: utf-8 -*-
"""
SA Session Proxy

@author: Yura A
"""
from gevent import getcurrent
from sqlalchemy.orm import scoped_session

from .logger import log


class NotEmptySessionException(Exception):
    pass


class SessionProxy(object):
    """
    Session factory wrapper.
    Instantiates once.
    Contains connections pools to shards
    """
    def __init__(self, createfunc, connections=None):
        self.scoped = scoped_session(createfunc, scopefunc=getcurrent)
        if connections:
            self.scoped.configure(shards=connections)

    def remove(self):
        return self.scoped.remove()

    def __getattr__(self, name):
        if name in ['remove', 'registry', 'query_property', 'rollback',
                    'commit']:
            return getattr(self.scoped, name)
        ses = self.scoped()
        return getattr(ses, name)

    def commit(self, force=False):
        session = self.scoped()
        if not session._is_clean() or force is True:
            session.commit()

    def rollback(self):
        session = self.scoped()
        if not session._is_clean():
            log.warning('ROLLBACK POINT START')
            log.warning('NEW - %s' % len(session.new))
            log.warning('DELETED - %s' % len(session.deleted))
            log.warning('DIRTY - %s' % len(session.dirty))
            log.warning('ROLLBACK POINT END')
            session.rollback()
        else:
            session.close()

    def assert_1_conn(self):
        registry = self.scoped.registry.registry
        ses = registry[getcurrent()].transaction
        cons = lambda ses: set([id(x[0]._Connection__connection.connection)
                            for x in ses._connections.values()]) \
                            if hasattr(ses,'_connections') else set()
        res = cons(ses)
        assert len(res) < 2

    def _remove_registry_session(self, greenlet):
        registry = self.scoped.registry.registry
        if greenlet in registry:
            registry[greenlet].close()
        if greenlet in registry:
            del registry[greenlet]

    def _close_registry_session(self, greenlet):
        registry = self.scoped.registry.registry
        if greenlet in registry:
            registry[greenlet].close()

    def _get_key_connections(self, key):
        registry = self.scoped.registry.registry
        if key in registry and hasattr(registry[key].transaction,
                                       '_connections'):
            return registry[key].transaction._connections
        return {}

    def _invalidate_connections(self, key):
        connections = self._get_key_connections(key)
        uniq = set([x[0] for x in connections.values()])
        for conn in uniq:
            conn.invalidate()

    def _get_open_pairs(self):
        registry = self.scoped.registry.registry
        return [(k, registry[k].transaction) for k in registry.keys()
                if hasattr(registry[k].transaction, '_connections')
                and len(registry[k].transaction._connections) > 0]

    def status(self):
        registry = self.scoped.registry.registry
        cons = lambda ses: set([id(x[0]._Connection__connection.connection)
                            for x in ses._connections.values()]) \
                            if hasattr(ses,'_connections') else 'nothing'
        transaction = lambda greenlet: registry[greenlet].transaction
        result = ['greenlet(%s) transaction(%s): connections: %s' % (
            id(g),
            id(transaction(g)),
            cons(transaction(g))) for g in registry.keys()]
        return '\n'.join(result)
