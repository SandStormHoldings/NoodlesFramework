# -*- coding: utf-8 -*-
import sys
import os
import logging
from logging.handlers import WatchedFileHandler
from pythonjsonlogger import jsonlogger
from noodles.utils.helpers import get_config
LOG_DIR = get_config('LOG_DIR',ignore_import_errors=True)
LOG_LEVEL = get_config('LOG_LEVEL',ignore_import_errors=True)

formatter = logging.Formatter('%(asctime)s.%(msecs)d::'
                              '%(levelname)s::'
                              '%(filename)s L[%(lineno)d] '
                              '%(module)s::'
                              '%(message)s', '%Y-%m-%d %H:%M:%S')

json_formatter = jsonlogger.JsonFormatter('%(asctime)s '
                                          '%(created)f '
                                          '%(filename)s '
                                          '%(funcName)s '
                                          '%(levelname)s '
                                          '%(lineno)d '
                                          '%(module)s '
                                          '%(message)s '
                                          '%(name)s '
                                          '%(pathname)s ')
is_error = lambda level: level >= logging.ERROR

log = logging.getLogger('GameServer')
if LOG_LEVEL:
    log.setLevel(LOG_LEVEL)


class FilterOut(logging.Filter):
    def filter(self, rec):
        return not is_error(rec.levelno)


handler_out = logging.StreamHandler(sys.stdout)
handler_out.setFormatter(formatter)
if LOG_LEVEL:
    handler_out.setLevel(LOG_LEVEL)
handler_out.addFilter(FilterOut())
log.addHandler(handler_out)


class FilterErr(logging.Filter):
    def filter(self, rec):
        return is_error(rec.levelno)

handler_err = logging.StreamHandler(sys.stderr)
handler_err.setFormatter(formatter)
if LOG_LEVEL:
    handler_err.setLevel(LOG_LEVEL)
handler_err.addFilter(FilterErr())
log.addHandler(handler_err)

if LOG_LEVEL and LOG_DIR:
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        if not os.path.isdir(LOG_DIR):
            raise
    filename = os.path.basename(sys.argv[0])
    if filename.endswith('.py'):
        filename = filename[:-3]
    filename += '.log'
    logfile = os.path.join(LOG_DIR, filename)
    file_handler_err = WatchedFileHandler(logfile)
    file_handler_err.setFormatter(json_formatter)
    file_handler_err.setLevel(LOG_LEVEL)
    file_handler_err.addFilter(FilterErr())
    log.addHandler(file_handler_err)
