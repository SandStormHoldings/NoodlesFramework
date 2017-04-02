"""
It should be some detect-role routines here
@author: Yura A
"""
import sys

is_celery_run = lambda: sys.argv[0].endswith('celery')
