#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.event

import gdb

import re
import traceback

hooks = []
def any_after( regex, callback ):
    cre = re.compile(regex)
    global hooks
    hooks.append( (cre, callback) )

@vdb.event.before_prompt()
def before_prompt():
#    print("hooks = '%s'" % (hooks,) )
    if( len(hooks) == 0 ):
        return
    last_cmds = gdb.execute("show commands",False,True)
    last_cmds = last_cmds.splitlines()
    last_cmd = last_cmds[-1]
    last_cmd = last_cmd[7:]
#    print("last_cmd = '%s'" % (last_cmd,) )
    for re,cb in hooks:
        m = re.search(last_cmd)
        if m is not None:
#            print("re = '%s'" % (re,) )
#            print("m = '%s'" % (m,) )
            cb(last_cmd)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
