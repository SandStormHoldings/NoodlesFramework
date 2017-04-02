import datetime

dthandler = lambda obj: \
    obj.isoformat() if isinstance(obj, datetime.datetime) else obj
