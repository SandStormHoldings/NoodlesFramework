# -*- coding: utf-8 -*-
from logging import Formatter
import sys
from mako.filters import xml_escape
from config import DEBUG

from noodles.http import XResponse
from noodles.middleware import BaseMiddleware
from noodles.utils.mailer import MailMan
from noodles.utils.logger import log


class ExceptionCatchMiddleware(BaseMiddleware):
    def __call__(self):
        try:
            return self.callable()
        except Exception as e:
            formatter = Formatter()
            traceback = '<pre>' + xml_escape(formatter.formatException(sys.exc_info())) + '</pre>'
            log.error(traceback)

            if not DEBUG:
                MailMan.mail_send(MailMan(), e.__repr__(), traceback, with_hostname=True)

            data = {'error': 0, 'message': e.message}
            return XResponse(data)
