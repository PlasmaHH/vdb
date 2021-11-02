#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import functools
import subprocess

commands = vdb.config.parameter("vdb-pipe-commands","grep,egrep,tee,head,tail",on_set = vdb.config.set_array_elements )

pipe_commands = { }

def add( cmd, call ):
    global pipe_commands
    pipe_commands[cmd] = call

def call( cmd, data, argv ):
    call = pipe_commands.get(cmd,None)
    if( call is not None ):
        call(data, argv)
    else:
        raise Exception("Unknonwn pipe command %s" % cmd )


class cmd_external(vdb.command.command):
    """Executes a some command"""

    def __init__ (self,cmdname):
        super (cmd_external, self).__init__ (cmdname, gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:
            # what did I want to do here? hmmm...
            call_cmd(argv)
        except:
            traceback.print_exc()
            raise
            pass

def do_cmd( cmd, data, argv ):
    p = subprocess.run([ cmd ] + argv , input = data, encoding = "utf-8" )

for cmd in commands.elements:
#    cmd_external(cmd)
    add(cmd,functools.partial(do_cmd,cmd))

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
