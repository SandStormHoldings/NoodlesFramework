# -*- coding: utf-8 -*-
import datetime
import decimal


def datahandler(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    return repr(obj)
