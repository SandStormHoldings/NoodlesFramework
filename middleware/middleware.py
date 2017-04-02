# -*- coding: utf-8 -*-
"""
filedesc: framework middleware base class
@author: Yura A
"""
import sys
from importlib import import_module as im
from functools import reduce


class MiddlewareLoadError(Exception):
    pass


class BaseMiddleware(object):
    def __init__(self, link):
        self.link = link

    def run(self, producer, req):
        """

        :rtype : producer
        :param producer:
        :param req:
        :return: :rtype:
        """
        return self.link(producer, req)

    def end(self, producer, req):
        """

        :param producer:
        :param req:
        :return: :rtype:
        """
        return self.link(producer, req)


class AppMiddlewares(object):
    """
    Class represents application middlewares
    """
    def __init__(self, names):
        """
        Takes a raw list of middlewares and stores the call chains
        """
        names.reverse()
        mws = []
        splitted = [n.rpartition('.') for n in names]
        for mod_name, _, cls_name in splitted:
            try:
                mw_mod = sys.modules.get(mod_name, im(mod_name))
                mws.append(getattr(mw_mod, cls_name))
            except ImportError:
                raise MiddlewareLoadError('can not get module %s' % mod_name)
            except AttributeError:
                raise MiddlewareLoadError(
                    'No such class %s in %s module' % (cls_name, mod_name))
        chain = lambda xs, mth: reduce(
            lambda ca, x: mth(x(ca)), xs, lambda cb, _: cb)
        self.run_chain = chain(mws, lambda x: x.run)
        self.end_chain = chain(mws, lambda x: x.end)
