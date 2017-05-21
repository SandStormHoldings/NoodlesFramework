# -*- coding: utf-8 -*-
"""
Machinery for launching the wsgi server
"""
from noodles.utils.helpers import get_config
if not get_config('DONT_USE_GEVENT'):
    from gevent import monkey
    monkey.patch_all()


from logging import Formatter
import os
import re
import sys
import threading
import time
import json
from mako.filters import xml_escape
from config import (URL_RESOLVER, CONTROLLERS, MIDDLEWARES, DEBUG, AUTO_STOP,
                    HOST, PORT, SERVER_LOGTYPE, EXCEPTION_FLAVOR)

from noodles.dispatcher import Dispatcher
from noodles.http import Request, Error500
from noodles.middleware.middleware import AppMiddlewares
from noodles.websockserver import server
from noodles.utils.datahandler import datahandler
from noodles.utils.logger import log
from noodles.utils.mailer import report_exception, format_exception


resolver = __import__(URL_RESOLVER, globals(), locals())

# Create an dispatcher instance
dispatcher = Dispatcher(mapper=resolver.get_map(), controllers=CONTROLLERS)

# Load all midllewares for application
middlewares = AppMiddlewares(MIDDLEWARES)


# Our start point WSGI application
def noodlesapp(env, start_response):
    """

    :rtype : noodles.http.Response
    :param env:
    :param start_response:
    :return: :rtype: :raise:
    """
    # Get request object
    if get_config('ENCODE_SEMICOLON_IN_REQUEST') is True:
        env['QUERY_STRING'] = re.sub('[;]', '%3b', env['QUERY_STRING'])
    request = Request(env)

    if "HTTP_X_FORWARDED_FOR" in env:
        x_forwarded_for = env["HTTP_X_FORWARDED_FOR"].split(',')[:1]
        if x_forwarded_for:
            request.remote_addr = x_forwarded_for[0]
    #print("Try to handle url_path '%s'" % request.path)
    # Get callable object with routine method to handle request
    producer = dispatcher.get_callable(request)
    if not producer:
        # May be here an error,raise exception
        raise Exception('Can\'t find callable for this url path')

    # Callable function must return Response object
    try:
        response = middlewares.run_chain(producer, request)
        if not hasattr(response, 'is_noodles_response'):
            response = producer()
    # Capture traceback here and send it if debug mode
    except Exception as e:
        f = Formatter()
        if EXCEPTION_FLAVOR=='html':
            traceback = '<pre>%s\n\n%s</pre>' \
                        % (json.dumps(env, indent=2, default=datahandler),
                           xml_escape(f.formatException(sys.exc_info())))
        else:
            traceback = '%s\n%s' \
                        % (json.dumps(env, indent=2, default=datahandler),
                           f.formatException(sys.exc_info()))
        extra = {'request': request}
        log.error(format_exception(e, None), extra=extra)
        report_exception(e, extra=extra)

        if DEBUG:
            response = Error500(e, traceback)
        else:
            response = Error500()
    finally:
        middlewares.end_chain(lambda x: x, request)

    return response(env, start_response)


def exit_program():
    sys.exit(0)


class Observer(threading.Thread):
    def handler(self, arg1=None, arg2=None):
        print('event handled')  # %s ; %s'%(arg1,arg2))
        if hasattr(self, 'server_instance') and self.server_instance:
            print('stopping server')
            self.server_instance.stop()
            del self.server_instance
            print('done stopping')
        print('exiting program')
        exit_program()

    def scanfiles(self, dr, files, checkchange=False, initial=False):
        goodfiles = ['.py']
        baddirs = ['site-packages', '.git', 'python(2|3)\.(\d+)', 'tmp']
        gfmatch = re.compile('(' + '|'.join(goodfiles) + ')$')
        bdmatch = re.compile('(\/)(' + '|'.join(baddirs) + ')($|\/)')
        walk = os.walk(dr)
        for w in walk:
            if bdmatch.search(w[0]):
                continue
            for fn in w[2]:
                if not gfmatch.search(fn):
                    continue
                ffn = os.path.join(w[0], fn)
                if ffn in files and initial:
                    raise Exception('wtf %s' % ffn)
                if not os.path.exists(ffn):
                    if not fn.startswith('.#'):
                        print('%s does not exist' % ffn)
                    continue
                nmtime = os.stat(ffn).st_mtime
                if checkchange:
                    if (ffn not in files) or (nmtime > files[ffn]):
                        print('change detected in %s' % ffn)
                        return True
                files[ffn] = nmtime
        return False
    do_run=True
    def run(self):
        files = {}
        self.scanfiles(self.mp, files, initial=True)
        print('watching %s files' % len(files))
        while self.do_run:
            rt = self.scanfiles(self.mp, files, checkchange=True)
            if rt:
                self.handler()
            time.sleep(0.5)
    def stop(self):
        self.do_run=False
    def fcntl_run(self):
        import fcntl
        import signal
        import time
        print('starting to watch events on %s' % self.mp)
        signal.signal(signal.SIGIO, self.handler)
        fd = os.open(self.mp,  os.O_RDONLY)
        fcntl.fcntl(fd, fcntl.F_SETSIG, 0)
        fcntl.fcntl(fd, fcntl.F_NOTIFY,
                    fcntl.DN_MODIFY | fcntl.DN_CREATE | fcntl.DN_MULTISHOT)
        while True:
            time.sleep(0.1)
        print('done watching events')


def fs_monitor(server_instance):
    o = Observer()
    o.lck = threading.Lock()
    o.mp = os.getcwd()
    o.server_instance = server_instance
    o.start()
    return o

# Start server function, you may specify port number here
SERVER_INSTANCE = None


def startapp(port=PORT, host=None, start_time=None):
    global SERVER_INSTANCE
    if get_config('DONT_USE_GEVENT'):
        from paste import httpserver
        SERVER_INSTANCE = httpserver.serve(noodlesapp, host=host, port=port)
    else:
        startgeventapp(port, host, start_time)


def startgeventapp(port=PORT, host=None, start_time=None):
    global SERVER_INSTANCE
    if port is None:
        port = PORT
    if host is None:
        host = HOST
    if start_time is None:
        time_passed = ''
    else:
        time_passed = format(time.time() - start_time, '.3')
    print('Binding on %s:%s %s' % (host, port, time_passed))
    log_stream = None
    if SERVER_LOGTYPE == 'supress':
        log_stream = open(os.devnull, "w")
    else:
        log_stream = SERVER_LOGTYPE
    SERVER_INSTANCE = server.ApiSocketServer(
        (host, int(port)),
        noodlesapp,
        log=log_stream)
    if AUTO_STOP:
        observer = fs_monitor(SERVER_INSTANCE)
    else:
        observer = None
    try:
        SERVER_INSTANCE.serve_forever()
    except KeyboardInterrupt:
        if observer:
            print('stopping file change watcher.')
            observer.stop()
    finally:
        if hasattr(log_stream,'close'):
            log_stream.close()


def startbackdoor(host=None, port=8998):
    if get_config('DONT_USE_GEVENT'):
        raise('Backdoor is not available')
    if host is None:
        host=HOST
    from gevent.backdoor import BackdoorServer
    print('Backdoor is on %s:%s' % (host, port))
    bs = BackdoorServer((host, port), locals())
    bs.start()
