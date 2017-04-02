# -*- coding: utf-8 -*-
"""
SA Session Proxy

@author: Yura A
"""
from gevent import getcurrent
from sqlalchemy.orm import scoped_session

from .logger import log


class SessionProxy(object):
    """
    Session factory wrapper.
    Instantiates once.
    Contains connections pools to shards
    """
    ignore_flag = '_ezs_ignore_watchdog'

    def __init__(self, createfunc, connections=None):
        self.scoped = scoped_session(createfunc, scopefunc=getcurrent)
        if connections:
            self.scoped.configure(shards=connections)

    def __getattr__(self, name):
        if name in {'remove', 'registry', 'query_property', 'rollback',
                    'commit'}:
            return getattr(self.scoped, name)
        ses = self.scoped()
        return getattr(ses, name)

    def rollback(self):
        session = self.scoped()
        session.info.clear()

        if not session._is_clean():
            log.warning('ROLLBACK POINT START')
            log.warning('NEW - %s' % len(session.new))
            log.warning('DELETED - %s' % len(session.deleted))
            log.warning('DIRTY - %s' % len(session.dirty))
            log.warning('ROLLBACK POINT END')
            session.rollback()
        else:
            session.close()

    def assert_conn_count(self, expected=1, msg=None):
        registry = self.scoped.registry.registry
        transaction_holder = registry.get(getcurrent(), None)
        if not transaction_holder:
            return

        transaction = transaction_holder.transaction
        get_connections = lambda trn: set([id(x[0]._Connection__connection.connection)
                            for x in trn._connections.values()]) \
                            if hasattr(trn,'_connections') else set()
        connections = get_connections(transaction)
        result = len(connections) <= expected
        assert result, msg

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

    def _invalidate_connections(self, key=None):
        if key is None:
            key = getcurrent()
        connections = self._get_key_connections(key)
        uniq = set([x[0] for x in connections.values()])
        for conn in uniq:
            conn.invalidate()

    def _get_open_pairs(self):
        registry = self.scoped.registry.registry
        return [(k, registry[k].transaction) for k in registry.keys()
                if hasattr(registry[k].transaction, '_connections')
                and len(registry[k].transaction._connections) > 0]

    def _watchdog_ignored(self, greenlet=None):
        if greenlet is None:
            greenlet = getcurrent()
        registry = self.scoped.registry.registry
        if greenlet in registry:
            return getattr(registry[greenlet], self.ignore_flag, False)
        else:
            return False

    def disable_watchdog(self, greenlet=None):
        setattr(self.scoped(), self.ignore_flag, True)

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
