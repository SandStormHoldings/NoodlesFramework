# -*- coding: utf-8 -*-

from noodles.http import XResponse
from noodles.middleware import BaseMiddleware
from noodles.utils.logger import log
from noodles.utils.mailer import report_exception, format_exception


class ExceptionCatchMiddleware(BaseMiddleware):
    def __call__(self):
        try:
            return self.callable()
        except Exception as e:
            log.error(format_exception(e, None))
            report_exception(e)
            data = {'error': 0, 'message': e.message}
            return XResponse(data)
