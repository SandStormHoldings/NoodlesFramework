# -*- coding: utf-8 -*-
"""
filedesc: a kind of redis orm
"""
import copy
import hashlib
import json
import datetime
from noodles.utils.datahandler import datahandler
import os
import re
from config import TIME_TO_OVERWRITE_CLIENT_COOKIE

from noodles.utils.logger import log
from noodles.utils.helpers import get_config


SEPARATOR = ':'


def mkey(*args):
    """
    return a key composed of the arguments passed, delimeted by colon.
    for usage with redis
    """
    return SEPARATOR.join([str(rt) for rt in args])


def pubsub_key(*args):
    """ use to create redis pub/sub channel name """
    return mkey(*args + (get_config('RDB', ''),))

non_record = re.compile(r'__\w+__')
try:
    from config import REDIS_NAMESPACE
except ImportError:
    current_path = os.getcwd()
    current_dir = os.path.split(current_path)[-1]
    REDIS_NAMESPACE = current_dir.lower().replace(' ', '_')


class DoesNotExist(Exception):
    pass


class Value(object):
    """Single value in our data storage
    """

    __isvalue__ = True

    def __init__(self, type_of_value=None):
        if type_of_value:
            self.type = type_of_value
        else:
            self.type = str

    def set_key(self, key):
        self.key = key

    def typing(self, value):
        """ If value is None it returns None, else value value in proper type
        """
        if value is not None:
            return self.type(value)
        else:
            return None

    def get_default(self):
        return None

    def __get__(self, instance, owner):
        valuedict = instance.__instdict__
        if valuedict:
            return self.typing(valuedict[self.key])
        else:
            return self

    def __set__(self, instance, value):
        valuedict = instance.__instdict__
        try:
            valuedict[self.key] = self.type(value)
        except:
            log.info('could not save key %s with value %s as type %s'
                     % (self.key, value, self.type))
            raise


class DateValue(Value):
    """Represents datatime python object
    """
    def it2dt(self, value):
        if len(value.split('.')) > 1:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
        else:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')

    def typing(self, value):
        """ If value is None it returns None, else value value in proper type
        """
        if value is not None and isinstance(value, str):
            return self.it2dt(value)
        elif isinstance(value, datetime.datetime):
            return value
        else:
            return None


class Model(object):
    """General class for objects description in data storage
    """
    # static model parameters
    __structure__ = {}
    __collection__ = {}
    __salt__ = None
    id = Value(str)

    def __init__(self, valuedict=None, embedded=False, expire=None, **kwargs):

        # we might use salt to make our sequence key for this object
        # more interesting
        if 'salt' in kwargs:
            self.__salt__ = kwargs['salt']
        self.expire = expire
        self.__init_structure__(self.__class__.__name__, valuedict, **kwargs)
        self.collection_name = self.__collection__[self.__class__.__name__]
        self.embedded = embedded
        self._generate_id_if_empty()

    def _generate_id_if_empty(self):
        if not self.id:
            if hasattr(self, '__gen_id__'):
                new_id = self.__gen_id__()
            else:
                new_id = self.RedisConn.incr(
                    mkey(REDIS_NAMESPACE,
                         self.__class__.__name__.lower() + '_key'))
            if hasattr(self, '__encrypt__'):
                self.id = self.__encrypt__(new_id)
            elif self.__salt__:
                self.id = hashlib.md5(str(new_id) + self.__salt__).hexdigest()
            else:
                self.id = new_id

    def __init_structure__(self, classname, valuedict=None, **kwargs):
        # create dictionary for model instance
        self.__instdict__ = {}
        # Check static model structure
        if not self.__structure__.get(classname):
        # if not - create it
            self.__structure__[classname] = {}
            # Specify the collection name
            self.__collection__[classname] = classname.lower() + 's'
            log.debug('Creating structure for model %s' % classname)
            # Browse model for properties
            for key in dir(self):
                if not non_record.match(key):
                    value = getattr(self, key)
                    if hasattr(value, '__isvalue__'):
                        value.set_key(key)
                        self.__structure__[classname][key] \
                            = value.get_default()
        if valuedict:
            self.__instdict__ = valuedict
        else:
            self.__instdict__ = copy.deepcopy(self.__structure__[classname])

        for k in kwargs:
            if k == 'salt':
                continue
            elif k in self.__instdict__:
                if hasattr(kwargs[k], 'get_values'):
                    self.__instdict__[k] = kwargs[k].get_values()
                else:
                    self.__instdict__[k] = kwargs[k]
            else:
                raise Exception('There is no such value \'%s\' in %s model.'
                                % (k, classname))

    def save(self, storage=None):
        """Save object to redis storage
        """
        if self.embedded:
            log.warning('You should save embedded objects '
                        'with high level object')
            return
        self._generate_id_if_empty()
        id_ = self.id
        if hasattr(self, '__encrypt__'):
            id_ = self.__decrypt__(id_)
        key = self.storage_key(id_)
        data = json.dumps(self.__instdict__, default=datahandler)

        if self.expire is None:
            ttl = self.RedisConn.ttl(key)
            if ttl is not None and ttl >= 0:
                self.expire = ttl

        self.RedisConn.set(key, data)
        if self.expire is not None:
            self.RedisConn.expire(key, self.expire)

        if hasattr(self, 'after_save'):
            self.after_save()

    @classmethod
    def get_structure(cls):
        structure = cls.__structure__.get(cls.__name__)
        if not structure:
            # Structure of the class is not created yet
            return cls.__structure__.get(cls.__name__)
        return structure

    @classmethod
    def get_collection_name(cls):
        collection_name = cls.__collection__.get(cls.__name__)
        if not collection_name:
            cls.__collection__[cls.__name__] = cls.__name__.lower() + 's'
            return cls.__collection__[cls.__name__]
        return collection_name

    def get_values(self):
        return copy.deepcopy(self.__instdict__)

    @classmethod
    def get(cls, idx, storage=None, salt=None):
        """Get object from Redis storage by ID
        """
        if hasattr(cls, '__encrypt__'):
            try:
                id_to_get = cls.__decrypt__(idx)
            except:
                return None

        elif salt:
            id_to_get = hashlib.md5(idx + salt).hexdigest()
        else:
            id_to_get = idx
        # First try to find object by Id
        inst_key = cls.storage_key(id_to_get)
        inst_data = cls.RedisConn.get(inst_key)
        if not inst_data:  # No objects with such ID
            raise DoesNotExist('RedisModel - missing id: {}'.format(inst_key))
        else:
            # Copy structure of Class to new dictionary
            print('inst_data=',inst_data)
            instance_dict = json.loads(inst_data.decode('utf-8')) #.__str__())
            return cls(valuedict=instance_dict)

    @classmethod
    def delete(cls, id, storage=None):  # storage=None for backword capability
        """Delete key specified by ``id``
        """
        key = cls.storage_key(id)
        result = cls.RedisConn.delete(key)
        return result

    #return flag to update client cookie
    def update(self, storage=None, **kwargs):
        """
        update time expire
        """
        id = mkey(REDIS_NAMESPACE, self.collection_name, self.id)

        if 'expire' in kwargs:
            if TIME_TO_OVERWRITE_CLIENT_COOKIE > self.RedisConn.ttl(id):
                result = self.RedisConn.expire(id, kwargs['expire'])
                return result
            else:
                log.debug('non_update_SESSION')
        else:
            raise Exception('unknown action!!!')

    @classmethod
    def exists(cls, id, storage=None):  # storage=None for backword capability
        return cls.RedisConn.exists(cls.storage_key(id))

    @classmethod
    def ttl(cls, id, storage=None):
        return cls.RedisConn.ttl(cls.storage_key(id))

    @classmethod
    def expire(cls, _id, seconds):
        return cls.RedisConn.expire(cls.storage_key(_id), seconds)

    @classmethod
    def expire_if_needed(cls, _id, seconds):
        key = cls.storage_key(_id)
        ttl = cls.RedisConn.ttl(key)
        if ttl < seconds:
            return cls.RedisConn.expire(key, seconds)

        return ttl

    @classmethod
    def storage_key(cls, id_=None):
        """
        Если передается id_, то делаем ключ и возвращаем его.

        Если не передается id_, то возвращаем функцию, которая принимает id
        и возвращает ключ.
        """
        result = lambda x: mkey(REDIS_NAMESPACE, cls.get_collection_name(), x)
        if id_:
            return result(id_)
        return result


class Node(Value):
    """Use it for embeded objects to model
    """

    def __init__(self, model_class):
        self.model = model_class

    def __get__(self, instance, owner):
        valuedict = instance.__instdict__
        if valuedict:
            # TODO: Optimize this!
            model_inst = self.model(valuedict=valuedict[self.key])
            return model_inst
        else:
            return self

    def __set__(self, instance, value):
        pass

    def get_default(self):
        model_inst = self.model()
        return model_inst.get_structure()
