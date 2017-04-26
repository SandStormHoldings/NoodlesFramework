import xmlrunner
import sys


def initrunner(suite):
    report = '../reports'
    runner = xmlrunner.XMLTestRunner(output=report,
                                     stream=sys.stderr,
                                     verbosity=2)
    runner.run(suite)
