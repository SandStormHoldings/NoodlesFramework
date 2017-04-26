# -*- coding: utf-8 -*-
"""
Create one global redis connection
"""
from config import REDIS_HOST, REDIS_PASSWORD

import redis


REDIS_CONNECTION = redis.connection.Connection(REDIS_HOST, 6379, 0, REDIS_PASSWORD, None)


class RPool(object):
    """
    Manages a list of connections on the local thread
    """
    conncnt = 0

    def __init__(self, connection_class=None):
        pass

    def make_connection_key(self, host, port, db):
        "Create a unique key for the specified host, port and db"
        return '%s:%s:%s' % (host, port, db)

    def get_connection(self):
        """
        Return a specific connection for the specified host, port and db
        """
        global REDIS_CONNECTION
        return REDIS_CONNECTION

    def get_all_connections(self):
        """
        Return a list of all connection objects the manager knows about
        """
        global REDIS_CONNECTION
        return [REDIS_CONNECTION, ]


class RPool2(object):
    """
    Manages a list of connections on the local thread
    """
    connections = {}
    conncnt = 0

    def __init__(self, connection_class=None):
        self.connection_class = connection_class or redis.connection.Connection

    def make_connection_key(self, host, port, db):
        """
        Create a unique key for the specified host, port and db
        """
        return '%s:%s:%s' % (host, port, db)

    def get_connection(self, host, port, db, password, socket_timeout):
        """
        Return a specific connection for the specified host, port and db
        """
        key = self.make_connection_key(host, port, db)
        if key not in self.connections:
            self.conncnt += 1
            print 'instantiating connection %s number %s' % (key, self.conncnt)
            self.connections[key] = self.connection_class(
                host, port, db, password, socket_timeout)
        return self.connections[key]

    def get_all_connections(self):
        """
        Return a list of all connection objects the manager knows about
        """
        return self.connections.values()
