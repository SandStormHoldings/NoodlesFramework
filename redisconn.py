# -*- coding: utf-8 -*-
"""
Redis connection wrapper which gives a soft error in case that
noodles is run on a machine without redis
"""
import redis
from redis.client import Lock
from redis.exceptions import LockError
from noodles.utils.helpers import get_config
from functools import wraps


pool = redis.ConnectionPool(**get_config('REDIS_BASE_CONN_DATA'))
RedisConn = redis.Redis(connection_pool=pool)

lock_timeout = get_config('REDIS_LOCK_TIMEOUT', 600)


def single_instance_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = "celery-single-instance-%s" % func.__name__
        suffix = kwargs.get('sit_suffix')
        if suffix:
            key = "%s-%s" % (key, suffix)

        lock = RedisConn.lock(key, timeout=lock_timeout)
        acquire_lock = lambda: lock.acquire(blocking=False)
        force = kwargs.get('force', False)
        if acquire_lock() or force:
            try:
                result = func(*args, **kwargs)
            finally:
                if force:
                    #hack to unlocking
                    lock.acquired_until = Lock.LOCK_FOREVER
                try:
                    lock.release()
                except LockError:
                    pass
            return result
    return wrapper
