import sys


class ErrorTee(object):
    def __init__(self):
        self.stream = sys.stderr
        self.log = open("errors.log", "a", 1)

    def write(self, message):
        self.stream.write(message)
        self.log.write(message)


def enable_log_errors():
    if not isinstance(sys.stderr, ErrorTee):
        sys.stderr = ErrorTee()
        from noodles.utils.logger import log
        log.warn('errors log enabled errors.log')
