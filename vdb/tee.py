#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.pipe

import gdb

import subprocess

class cmd_tee (vdb.command.command):
    """Executes a tee on some command"""

    def __init__ (self):
        super (cmd_tee, self).__init__ ("tee", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:
            call_tee(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_tee()

def tee( data, argv ):
#    pipe = subprocess.Popen([ "tee" ] + argv , stdin = subprocess.PIPE )
    p = subprocess.run([ "tee" ] + argv , input = data, encoding = "utf-8" )
#    print("p = '%s'" % p )
#    print("tee IN DATA:")
#    print("data = '%s'" % data )
#    print("argv = '%s'" % argv )


vdb.pipe.add("tee",tee)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
