import os
import sys


def activate_this(diradd=None):
    """the equivalent of source bin/activate"""
    if diradd:
        fpath = os.path.join(os.getcwd(), diradd, 'venv/bin',
                             'activate_this.py')
    else:
        fpath = os.path.join(os.getcwd(), 'venv/bin', 'activate_this.py')

    execfile(fpath, dict(__file__=fpath))
    sys.path.append(os.path.join(os.getcwd(), 'src'))
