# -*- coding: utf-8 -*-
"""
Send email
"""
import smtplib
import socket
from logging import Formatter
import sys
import json
import inspect
import time
import os.path
from datetime import datetime
from collections import namedtuple

from mako import exceptions
from mako.filters import xml_escape
from mako.template import Template
from io import BytesIO as cStringIO
from email import charset, encoders
from email.generator import Generator
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import COMMASPACE, formatdate
from noodles import NOODLES_PATH
from noodles.utils.logger import log
from noodles.utils.helpers import get_config
from noodles.utils.datahandler import datahandler


# Default encoding mode set to Quoted Printable. Acts globally!
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class MailMan(object):
    server = None
    def __init__(self,
                 server=get_config('MAIL_SERVER'),
                 port=get_config('MAIL_PORT'),
                 login=get_config('MAIL_LOGIN'),
                 password=get_config('MAIL_PASSWORD'),
                 recipient=None):
        fnd=False
        if recipient:
            for rcp in recipient:
                for sndk,snd in get_config('SECONDARY_EMAIL_SERVERS').items():
                    if rcp.endswith(sndk):
                        assert fnd!=True and \
                            hasattr(self,'server') and \
                            getattr(self,'server')!=snd['server'],\
                            "allow only one override (%s != %s)"%(getattr(self,'server'),snd['server'])
                        self.server = snd['server']
                        self.port = snd['port']
                        self.login = snd['login']
                        self.password = snd['password']

                        fnd = True
        if not fnd:
            self.server = server
            self.port = port
            self.login = login
            self.password = password

        self.recipient = recipient #this is used to choose a connection

    def construct(self, subject, message, sender, recipient, with_hostname=False, attachments=None,is_html=True):
        # Create message container
        # the correct MIME type is multipart/alternative.
        # Attachments must be dict {'filename': 'content'}
        msg = MIMEMultipart('alternative')
        msg['From'] = "%s" % Header(sender, 'utf-8')
        msg['To'] = Header(COMMASPACE.join(recipient), 'utf-8')
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = "%s" % Header(subject, 'utf-8')
        if with_hostname:
            message += "\n-- \nHost: %s\n" % socket.gethostname()
        # Create the body of the message
        message = '\n' + message
        part = MIMEText(message,_subtype = (is_html and 'html' or 'plain'), _charset='UTF-8')
        # Attach parts into message container.
        msg.attach(part)
        if attachments:
            assert type(attachments) == dict
            for filename, body in attachments.items():
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(body)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename=%s' % filename)
                msg.attach(part)
        # And here we have to instantiate a Generator object to convert the
        # multipart object to a string (can't use multipart.as_string,
        # because that escapes "From" lines).
        io = StringIO()
        g = Generator(io, False)  # second argument means "should I mangle From?"
        g.flatten(msg)
        return io.getvalue()

    def mail_send(
            self, 
            subject, 
            message, 
            sender=get_config('NOODLES_ERROR_SENDER'),
            recipient=get_config('NOODLES_ERROR_RECIPIENT'), 
            conn=None,
            with_hostname=False, 
            attachments=None, 
            is_html=True):
        if with_hostname:
            sender = socket.gethostname() + '_' + sender
        assert type(recipient) == list
        if len(recipient) == 0:
            return
        if 'example.com' in ''.join(recipient):
            return
        if conn is None:
            conn = self.obtain_conn()


        try:
            body = self.construct(
                subject, message, sender, recipient,
                with_hostname=with_hostname, attachments=attachments, is_html=is_html)

            conn.sendmail(sender, recipient, body)
        finally:
            conn.quit()
            
    def obtain_conn(self):
        server = smtplib.SMTP(self.server, self.port)
        server.starttls()
        if self.login:
            server.login(self.login, self.password)
        return server


def send_email(subject, message, sender=get_config('NOODLES_ERROR_SENDER'),
               recipient=get_config('NOODLES_ERROR_RECIPIENT'), conn=None,
               with_hostname=False, attachments=None, is_html=True):
    mailman = MailMan(recipient=recipient)
    mailman.mail_send(subject, message, sender, recipient, conn, with_hostname,
                      attachments, is_html)


class HTMLFormatter:
    template = Template(filename=os.path.join(NOODLES_PATH,
                                              'templates/error_email.html'))

    def format(self, report, maxdepth=5):
        return self.template.render(maxdepth=maxdepth, report=report,
                                    datetime=datetime)


Report = namedtuple('Report', ['timestamp', 'exception', 'traceback'])
Frame = namedtuple('Frame', ['file', 'line', 'locals'])


def __collect_frame(frame):
    return Frame(
        file=inspect.getfile(frame),
        line=frame.f_lineno,
        locals=frame.f_locals,
    )


def _collect(exception):
    traceback = []
    exc_info = sys.exc_info()
    tb = exc_info[2]

    while tb:
        frame = tb.tb_frame
        traceback.append(__collect_frame(frame))
        tb = tb.tb_next

    return Report(
        timestamp=time.time(),
        exception=exception,
        traceback=traceback,
    )


def format_exception(exc, env, extra=None, msg=''):
    """
    варианты поведения:
    1) exc -> tuple from sys.exc_info
    2) exc -> Exception, sys.exc_info has something
    3) exc -> Exception, sys.exc_info is empty
    """
    if extra is None:
        extra = {}

    if isinstance(exc, tuple):
        e = Formatter().formatException(exc)
        msg = msg or exc[1].message
        tb = [msg]
        if env:
            tb.append(json.dumps(env, indent=2, default=datahandler) or '')
        tb.append(e or '')
    else:
        tb = [str(exc)]
        if env:
            tb.append(json.dumps(env, indent=2, default=datahandler) or '')
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            e = Formatter().formatException(exc_info)
            tb.append(e or '')
    for key, value in extra.items():
        tb.append('%s <%s>' % (key, value))
    tb = map(str, tb)
    return '\n'.join(tb)


def report_exception(exc, env=None, extra=None):
    if extra is None:
        extra = {}
    formatted = format_exception(exc, env, extra)

    if isinstance(exc, tuple):
        'pick an exception from the tuple (type, value, traceback)'
        exc = exc[1]
    if not get_config('NOODLES_SEND_FULL_MAIL'):
        send_email(repr(exc), formatted, with_hostname=True, is_html=False)
        return
    subject = repr(exc)
    report = ''
    try:
        subject = repr(exc)
        report = _collect(exc)
        report = HTMLFormatter().format(report, maxdepth=4)
    except exceptions.MakoException:
        error = exceptions.text_error_template().render()
        formatted += '\nTemplate rendering error ' + error
        log.error(error)
    attachments = None
    if report:
        attachments = {
            'report.html': report,
        }
    send_email(subject, formatted, with_hostname=True, attachments=attachments,
               is_html=False)


def basic_report_exception(exc, env=None, msg=''):
    formatted = format_exception(exc, env, msg)
    log.error(formatted)
    send_email(repr(exc), formatted, with_hostname=True, is_html=False)
