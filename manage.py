#!/usr/bin/env python
'''
filedesc: noodles helper script. right now only inits new projects
from boilerplate template
'''
import commands
import os
import sys
sys.path.append(os.getcwd())
from noodles.utils.logger import log


current_dir = os.path.dirname(sys.argv[0])
template_dir = os.path.join(current_dir, 'project_template')
if len(sys.argv) >= 2:
    op = sys.argv[1]

    if op == 'init':
        cmd = 'cp -r -i %s/* .' % (template_dir)
        st, op = commands.getstatusoutput(cmd)
        assert st == 0, "%s returned %s" % (cmd, st)
        log.info('just initialized a project into ./')
