import sys
import logging
from logging.handlers import SysLogHandler
from noodles.utils.helpers import get_config


formatter = logging.Formatter('%(asctime)s.%(msecs)d::'
                              '%(levelname)s::'
                              '%(filename)s L[%(lineno)d] '
                              '%(module)s::'
                              '%(message)s', '%Y-%m-%d %H:%M:%S')
is_error = lambda level: level >= logging.ERROR

log = logging.getLogger('GameServer')
log.setLevel(get_config('LOG_LEVEL'))


class FilterOut(logging.Filter):
    def filter(self, rec):
        return not is_error(rec.levelno)


handler_out = logging.StreamHandler(sys.stdout)
handler_out.setFormatter(formatter)
handler_out.setLevel(get_config('LOG_LEVEL'))
handler_out.addFilter(FilterOut())
log.addHandler(handler_out)


class FilterErr(logging.Filter):
    def filter(self, rec):
        return is_error(rec.levelno)


handler_err = logging.StreamHandler(sys.stderr)
handler_err.setFormatter(formatter)
handler_err.setLevel(get_config('LOG_LEVEL'))
handler_err.addFilter(FilterErr())
log.addHandler(handler_err)
# syslog_handler_err = SysLogHandler('/dev/log')
# syslog_handler_err.setFormatter(formatter)
# syslog_handler_err.setLevel(get_config('LOG_LEVEL'))
# syslog_handler_err.addFilter(FilterErr())
# log.addHandler(syslog_handler_err)
