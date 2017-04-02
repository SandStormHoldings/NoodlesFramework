#!/usr/bin/env python
'''
filedesc: noodles helper script. right now only inits new projects
from boilerplate template
'''
import subprocess
import os
import sys
import glob

sys.path.append(os.getcwd())


current_dir = os.path.dirname(sys.argv[0])
template_dir = os.path.join(current_dir, 'project_templates')
if len(sys.argv) >= 3:
    op = sys.argv[1]
    dr = sys.argv[2]
    cwd = os.path.join(os.path.dirname(__file__),'..')
    if op == 'init':
        glb = '%s/%s/*'%(template_dir,dr)
        tocopy = glob.glob(glb)
        cmd = ['/bin/cp','-r','-i']+tocopy+['.']
        print(' '.join(cmd))
        rt = subprocess.run(cmd,cwd=cwd)
        code = rt.check_returncode()
    elif op == 'copy':
        tdir = os.path.join(current_dir,'project_templates',dr)
        cmds = (['/bin/mkdir','-p',tdir],
                ['cp','-r']+glob.glob('*')+[tdir],)
        for cmd in cmds:
            print(' '.join(cmd))
            subprocess.run(cmd)
else:
    print("please provide the following args: 1. operation (init,copy) 2. name")
