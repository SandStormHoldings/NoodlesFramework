# -*- coding: utf-8 -*-
"""
Redis connection wrapper which gives a soft error in case that
noodles is run on a machine without redis
"""
from gevent.coros import RLock
from noodles.utils.helpers import get_config
from noodles.utils.logger import log


class RedisImportError(Exception):
    pass

try:
    import redis
except ImportError:
    redis = None

RedisConn=get_config('REDIS_CONN')

if redis:
    # Use here true Redis connection
    if not RedisConn:
        RDB=get_config('RDB')
        try:
            from config import REDIS_HOST
        except ImportError:
            REDIS_HOST = 'localhost'
        try:
            from config import REDIS_PASSWORD
        except ImportError:
            REDIS_PASSWORD = None

        RedisConn = redis.Redis(host=REDIS_HOST, db=RDB,
                password=REDIS_PASSWORD)

else:
    # Get warning and use dictionary wrapper
    log.warning('\n >>>>>> Redis-py is not intalled. Simple python'
                    'dictionary is used instead <<<<< \n')

    class RedisConnWrapper(object):

        _db = {}
        dumb = True
        db_lock = RLock()

        def lock__db(func):
            def gen(self, *args, **kwargs):
                self.db_lock.acquire()
                func(self, *args, **kwargs)
                self.db_lock.release()
            return gen

        def get(self, key):
            return self._db.get(key)

        @lock__db
        def set(self, key, value):
            self._db[key] = value

        @lock__db
        def incr(self, key):
            if self._db.get(key):
                self._db[key] += 1
            else:
                self._db[key] = 1

        def smembers(self, set_key):
            return self._db.get(set_key)

        @lock__db
        def spop(self, set_key):
            if type(self._db.get(set_key)) != set:
                return None
            self._db[set_key].pop()

        @lock__db
        def srem(self, set_key, value):
            if type(self._db.get(set_key)) != set:
                return False
            else:
                try:
                    self._db[set_key].remove(value)
                    return True
                except KeyError:
                    return False

        @lock__db
        def sadd(self, set_key, value):
            if type(self._db.get(set_key)) != set:
                self._db[set_key] = set()
            self._db[set_key].add(value)

        def __getattr__(self, name):
            raise RedisImportError(
                'You use dumb redis storage that doesn\'t'
                'support this function,\n you should install redis-server'
                'and redis-py')

    RedisConn = RedisConnWrapper()
