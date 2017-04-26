# -*- coding: utf-8 -*-
"""
Machinery for launching the wsgi server
"""
from noodles.utils.helpers import get_config
if not get_config('DONT_USE_GEVENT'):
    from gevent import monkey
    monkey.patch_all()


from logging import Formatter
from noodles.utils.logger import log
import os
import re
import sys
import threading
import time
import json
from mako.filters import xml_escape
from config import (URL_RESOLVER, CONTROLLERS, MIDDLEWARES, DEBUG, AUTO_RELOAD,
                    HOST, PORT, SERVER_LOGTYPE)

from noodles.dispatcher import Dispatcher
from noodles.http import Request, Error500
from noodles.middleware import AppMiddlewares
from noodles.utils.mailer import MailMan
from noodles.websockserver import server
from noodles.utils.datahandler import datahandler


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
    request = Request(env)

    if env.get("HTTP_X_FORWARDED_FOR"):
        request.remote_addr = env.get("HTTP_X_FORWARDED_FOR")
    #print "Try to handle url_path '%s'" % request.path
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
        return response(env, start_response)
    # Capture traceback here and send it if debug mode
    except Exception as e:
        f = Formatter()
        traceback = '<pre>%s\n\n%s</pre>' % (
                json.dumps(env, indent=2, default=datahandler),
                f.formatException(sys.exc_info()))
        log.exception(traceback)
        if DEBUG:
            response = Error500(e, traceback)
        else:
            response = Error500()
            MailMan.mail_send(
                MailMan(), e.__repr__(), traceback, with_hostname=True)
        return response(env, start_response)
    finally:
        middlewares.end_chain(lambda x: x, request)


def restart_program(mp, lck):
    print 'acquiring lock'
    from config import NO_GEVENT_MONKEYPATCH
    if NO_GEVENT_MONKEYPATCH:
            acquired = lck.acquire()
    else:
        acquired = lck.acquire(blocking=False)
    if not acquired:
        print 'failed to acquire'
        return None
    """Restarts the current program.
    Note: this function does not return. Any cleanup action (like
    saving data) must be done before calling this function."""
    import commands
    print 'deleting pyc'
    rmcmd = 'find %s -iname "*.pyc" -exec rm -rf {} \;' % mp
    st, op = commands.getstatusoutput(rmcmd)
    assert st == 0, "%s -> %s (%s)" % (rmcmd, op, st)
    python = sys.executable
    print 'executing %s %s' % (python, sys.argv)
    #os.execl(python, python, * sys.argv)
    os.spawnl(os.P_WAIT, python, python, *sys.argv)
    #os.execvp(python,**sys.argv)
    #os.kill(os.getpid(),signal.SIGINT)
    print 'executed'

    lck.release()
    print 'released lock'


class Observer(threading.Thread):
    def handler(self, arg1=None, arg2=None):
        print('event handled')  # %s ; %s'%(arg1,arg2))
        if hasattr(self, 'server_instance') and self.server_instance:
            print 'stopping server'
            self.server_instance.stop()
            del self.server_instance
            print 'done stopping'
        print 'restarting program'
        restart_program(self.mp, self.lck)
        print 'done restarting'

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
                #print fn
                if ffn in files and initial:
                    raise Exception('wtf %s' % ffn)
                if not os.path.exists(ffn):
                    if not fn.startswith('.#'):
                        print ('%s does not exist' % ffn)
                    continue
                nmtime = os.stat(ffn).st_mtime
                if checkchange:
                    if (ffn not in files) or (nmtime > files[ffn]):
                        print 'change detected in %s' % ffn
                        return True
                files[ffn] = nmtime
        return False

    def run(self):
        files = {}
        self.scanfiles(self.mp, files, initial=True)
        print 'watching %s files' % len(files)
        while True:
            rt = self.scanfiles(self.mp, files, checkchange=True)
            if rt:
                self.handler()
            time.sleep(0.5)

    def fcntl_run(self):
        import fcntl
        import signal
        import time
        print 'starting to watch events on %s' % self.mp
        signal.signal(signal.SIGIO, self.handler)
        fd = os.open(self.mp,  os.O_RDONLY)
        fcntl.fcntl(fd, fcntl.F_SETSIG, 0)
        fcntl.fcntl(fd, fcntl.F_NOTIFY,
                    fcntl.DN_MODIFY | fcntl.DN_CREATE | fcntl.DN_MULTISHOT)
        while True:
            time.sleep(0.1)
        print 'done watching events'


def fs_monitor(server_instance):
    raise NotImplementedError('autoreload broken at the moment.')
    o = Observer()
    o.lck = threading.Lock()
    o.mp = os.getcwd()
    o.server_instance = server_instance
    o.start()

# Start server function, you may specify port number here
SERVER_INSTANCE = None


def startapp(port=PORT, host=None):
    if get_config('DONT_USE_GEVENT'):
        from paste import httpserver
        if AUTO_RELOAD:
            from paste import httpserver,reloader
            reloader.install()
        SERVER_INSTANCE = httpserver.serve(noodlesapp,host=host,port=int(port))

    else:
        startgeventapp(port, host)

def startgeventapp(port=PORT, host=None):
    global SERVER_INSTANCE
    if port is None:
        port = PORT
    if host is None:
        host=HOST
    print 'Binding on %s:%s' % (host, port)
    if SERVER_LOGTYPE == 'supress':
        import StringIO
        s = StringIO.StringIO()
    else:
        s = SERVER_LOGTYPE
    if get_config('NO_GEVENT_MONKEYPATCH'):
        if AUTO_RELOAD:
            from paste import httpserver,reloader
            reloader.install()
        SERVER_INSTANCE = httpserver.serve(noodlesapp,host=host,port=int(port))
    else:
        SERVER_INSTANCE = server.ApiSocketServer((host, int(port)),
                                                 noodlesapp, log=s)
        if AUTO_RELOAD:
            raise Exception('why am i here')
            fs_monitor(SERVER_INSTANCE)

    SERVER_INSTANCE.serve_forever()


def startbackdoor(host=None, port=8998):
    if get_config('DONT_USE_GEVENT'):
        raise('Backdoor is not available')
    if host is None:
        host=HOST
    from gevent.backdoor import BackdoorServer
    print 'Backdoor is on %s:%s' % (host, port)
    bs = BackdoorServer((host, port), locals())
    bs.start()
