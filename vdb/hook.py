#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.event

from collections.abc import Callable

import gdb
import re

hooks = []
def any_after( regex: str, callback: Callable[[str],None] ) -> None:
    cre = re.compile(regex)
    hooks.append( (cre, callback) )

@vdb.event.before_prompt()
def before_prompt():

    if( len(hooks) == 0 ):
        return
    last_cmds = gdb.execute("show commands",False,True)
    last_cmdsv = last_cmds.splitlines()
    last_cmd = last_cmdsv[-1]
    last_cmd = last_cmd[7:]

    for cre,cb in hooks:
        m = cre.search(last_cmd)
        if m is not None:
            cb(last_cmd)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
