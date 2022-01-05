#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.hexdump

import gdb

import re
import traceback
import time
import datetime

class cmd_profile (vdb.command.command):
    """Run a command under python profiling
"""

    def __init__ (self):
        super (cmd_profile, self).__init__ ("profile", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def invoke (self, arg, from_tty):
        try:
            if( len(arg) == 0 ):
                self.usage()
                return
#            print("arg = '%s'" % (arg,) )
#            gdb.execute( arg, from_tty )
            import cProfile
            cProfile.runctx("gdb.execute(arg,from_tty)",globals(),locals())
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_profile()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
