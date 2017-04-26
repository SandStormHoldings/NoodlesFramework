"""
Simple SQLAlchemy fixtures
"""
import time
import inspect
from noodles.utils.logger import log


class Fixture(object):
    """
    Simple sqlalchemy fixtures
    """
    def __init__(self, destination, session):
        self.destination = destination
        self.session = session()
        self.raw_data = {}
        self.mapped_data = {}

    @classmethod
    def dataset(cls):
        objects = []
        for key, value in cls.__dict__.iteritems():
            if inspect.isclass(value):
                objects.append(value)
        return objects

    def _prepare_raw_data(self):
        """
        Load data from fixtures
        """
        for key, value in self.__class__.__dict__.iteritems():
            if inspect.isclass(value):
                self.raw_data[key] = getattr(self, key)

    def _prepare_mapped_data(self):
        """
        Load data from fixtures class and make model instances without save
        """
        self._prepare_raw_data()
        for key, value in self.raw_data.iteritems():
            obj = self.destination()
            columns = self.destination.__table__.columns.keys()
            for base in obj.__class__.__bases__:
                if hasattr(base, '__table__'):
                    columns.extend(base.__table__.columns.keys())
                    columns = list(set(columns))
            for column in columns:
                if hasattr(value, column):
                    setattr(obj, column, getattr(value, column))
            self.mapped_data[key] = obj

    def load(self):
        log.info('Load fixtures data for %s, %s',
                 self.destination, time.time())
        self._prepare_mapped_data()
        for value in self.mapped_data.values():
            self.session.add(value)
        self.session.commit()  # commit point
        self.session.remove()
