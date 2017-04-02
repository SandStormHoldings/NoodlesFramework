from __future__ import print_function
import os
import sys
import xmlrunner
from datetime import datetime
from unittest import TestResult
from xmlrunner.result import _XMLTestResult, _TestInfo
from functools import wraps

REPORTS_FOLDER='../reports'


class TestResultX(_XMLTestResult):

    def getDescription(self, *args, **kwargs):
        the_time = datetime.now()
        the_time = the_time.replace(microsecond=0)
        desc = super(TestResultX, self).getDescription(*args, **kwargs)
        return '[{}]  {}'.format(str(the_time), desc)


class screenshot(object):
    def __init__(self, fields=['driver']):
        self.fields = fields
    def __call__(self,f , *args, **kwargs):
        # print('screenshot(%s,%s)'%(args,kwargs))
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                rt =  f(*args, **kwargs)
            except Exception, e:
                # print('exception occured. %s'%e)
                screen_fn = os.path.join(REPORTS_FOLDER,
                                  args[0].__class__.__name__+
                                  '.'+
                              f.__name__+
                                  '-%s.png')
                print('saving screenshot(s) %s' % screen_fn)

                for fn in self.fields:
                    cnt=0
                    drobj = getattr(args[0],fn)
                    if type(drobj)==dict:
                        lf = drobj.values()
                    elif type(drobj)==list:
                        lf = drobj
                    else:
                        lf = [drobj]
                    for driver in lf:
                        try:
                            ffn = screen_fn % (fn + '-' + str(cnt))
                            print(ffn)
                            driver.save_screenshot(ffn)
                        except Exception,e2:
                            print('failed to save - %s ; args is %s'%(e2, args))
                        cnt+=1
                raise #return wrapper
        return wrapper


def initrunner(suite):
    report = REPORTS_FOLDER
    runner = xmlrunner.XMLTestRunner(output=report,
                                     stream=sys.stderr,
                                     verbosity=2,
                                     resultclass=TestResultX)

    return runner.run(suite)
