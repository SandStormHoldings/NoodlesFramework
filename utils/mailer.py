"""
Send email
"""
import smtplib
from cStringIO import StringIO

from config import (NOODLES_ERROR_RECIPIENT, MAIL_SERVER, MAIL_PORT,
                    MAIL_LOGIN, MAIL_PASSWORD, NOODLES_ERROR_SENDER)
from email.MIMEMultipart import MIMEMultipart
from email.Utils import COMMASPACE, formatdate
from email.header import Header
from email.mime.text import MIMEText
from email import Charset
from email.generator import Generator
import socket


# Default encoding mode set to Quoted Printable. Acts globally!
Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')


class MailMan(object):
    def __init__(self, server=MAIL_SERVER, port=MAIL_PORT, login=MAIL_LOGIN,
                 password=MAIL_PASSWORD):
        self.server = server
        self.port = port
        self.login = login
        self.password = password

    @staticmethod
    def construct(subject, message, sender, recipient, with_hostname=False):
        # Create message container
        # the correct MIME type is multipart/alternative.
        msg = MIMEMultipart('alternative')
        msg['From'] = "%s" % Header(sender, 'utf-8')
        msg['To'] = Header(COMMASPACE.join(recipient), 'utf-8')
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = "%s" % Header(subject, 'utf-8')
        if with_hostname:
            message += "\n-- \nHost: %s\n" % socket.gethostname()
        # Create the body of the message
        part = MIMEText(message, 'html', 'UTF-8')
        # Attach parts into message container.
        msg.attach(part)
        # And here we have to instantiate a Generator object to convert the multipart
        # object to a string (can't use multipart.as_string, because that escapes
        # "From" lines).
        io = StringIO()
        g = Generator(io, False) # second argument means "should I mangle From?"
        g.flatten(msg)
        return io.getvalue()

    @staticmethod
    def mail_send(
            self, subject, message, sender=NOODLES_ERROR_SENDER,
            recipient=NOODLES_ERROR_RECIPIENT, conn=None, with_hostname=False):
        assert type(recipient) == list
        if len(recipient) == 0:
            return
        if 'example.com' in ''.join(recipient):
            return

        if conn is None:
            conn = self.obtain_conn()
        try:
            body = self.construct(subject, message, sender, recipient, with_hostname=with_hostname)
            conn.sendmail(sender, recipient, body)
        finally:
            conn.quit()

    def obtain_conn(self):
        server = smtplib.SMTP(self.server, self.port)
        server.starttls()
        server.login(self.login, self.password)
        return server
