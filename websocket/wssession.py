# -*- coding: utf-8 -*-
'''
Created on Jul 28, 2011
filedesc: web socket session object definitino
@author: Niko Skrypnik
'''
import gevent
from gevent.coros import Semaphore
from gevent.queue import Queue
from noodles.redisconn import RedisConn
from noodles.utils.logger import log


class WSSession(object):
    """
        Represent all information about web socket session, and provide
        interface to send data through web socket
    """
    _collection = {}

    @classmethod
    def get_session(cls, id):
        """
        Gets alive Web Session object by id or returns None
        if session isn't active
        """
        return cls._collection.get(id)

    def __init__(self):
        # Get id for web-socket session
        self.id = RedisConn.incr("".join([self.__class__.__name__, '_ids']))
        self.output_queue = Queue()
        self.params = {'wssid': self.id}  # Session specific parameters
        # The dictionary that storages all greenlets associated
        # with this session
        self.greenlets = {}
        # except of input/output servelet handlers and main servelet function
        # list of functions for execute while session is terminating
        self.terminators = {}
        self._collection[self.id] = self
        self.semaphore = Semaphore()  # use it concurent data access conditions

    def add_terminator(self, func):
        """Add terminator function to session terminators scope"""
        self.terminators[func.__name__] = func

    def rm_terminator(self, func):
        """Remove function from list of terminator functions"""
        try:
            self.terminators.pop(func.__name__)
        except KeyError:
            # Just in case, but it's not an critical error
            log.warning('Try to delete from WS session empty terminator')

    def tosend(self, chid, data):
        """ Provide ability to send data through websocket by chid """
        self.output_queue.put(
            {'chid': chid, 'pkg': data, 'session_params': self.params})

    def del_greenlet(self, greenlet_name):
        g = self.greenlets[greenlet_name]
        gevent.kill(g)

    def add_greenlet(self, func, terminator=None):
        """ Add some greenlet with function func to session,
            terminator is function that executes after killing of greenlet
        """
        pass  # while pass

    def kill_greenlets(self):
        """ Kill all greenlets associated with this session """
        for green in self.greenlets.values():
            log.debug('Kill greenlet for session')
            gevent.kill(green)

    def terminate(self):
        self.kill_greenlets()
        for t in self.terminators.values():
            t(self)
        self._collection.pop(self.id)

    def __getattr__(self, name):
        " If we try to access to some property isn't existed, returns None"
        return None

    def __setattr__(self, name, value):
        self.__dict__.update({name: value})
