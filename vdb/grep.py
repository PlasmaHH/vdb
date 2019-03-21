#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.pipe

import gdb

import subprocess

class cmd_grep (vdb.command.command):
    """Executes a grep on some command"""

    def __init__ (self):
        super (cmd_grep, self).__init__ ("grep", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:
            call_grep(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_grep()

def grep( data, argv ):
#    pipe = subprocess.Popen([ "grep" ] + argv , stdin = subprocess.PIPE )
    p = subprocess.run([ "grep" ] + argv , input = data, encoding = "utf-8" )
#    print("p = '%s'" % p )
#    print("GREP IN DATA:")
#    print("data = '%s'" % data )
#    print("argv = '%s'" % argv )


vdb.pipe.add("grep",grep)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
