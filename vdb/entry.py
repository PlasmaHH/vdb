#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.types

import os
import traceback
import time
import re

def entry(argv):
    info_file = gdb.execute("info file",False,True)
    ep = None
    for line in info_file.splitlines():
        if( line.find("Entry point:") > -1 ):
#            print("line = '%s'" % (line,) )
            ep = line.split(":")
#            print("ep = '%s'" % (ep,) )
            ep = ep[1]
#            print("ep = '%s'" % (ep,) )
            ep = vdb.util.rxint(ep)
#            print("ep = '%s'" % (ep,) )
    if( ep is None ):
        print("Unable to determine entry point")
    else:
        print(f"Setting $pc to {ep:#0x}")
        gdb.execute(f"set $pc={ep:#0x}")

class cmd_entry(vdb.command.command):
    """

"""

    def __init__ (self):
        super (cmd_entry, self).__init__ ("entry", gdb.COMMAND_DATA)

    def do_invoke (self, argv ):
        self.dont_repeat()

        try:
            entry(argv)
        except Exception as e:
            traceback.print_exc()

cmd_entry()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
