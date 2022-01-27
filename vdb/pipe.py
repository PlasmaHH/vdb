#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import functools
import subprocess
import gdb

commands = vdb.config.parameter("vdb-pipe-commands","grep,egrep,tee,head,tail,uniq,sort,less,cat,wc", gdb_type = vdb.config.PARAM_ARRAY )
up_wraps = vdb.config.parameter("vdb-pipe-wrap","show,info,help,x,print,list,set,maint", gdb_type = vdb.config.PARAM_ARRAY )

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

    def do_invoke (self, argv):
        try:
            print("argv = '%s'" % (argv,) )
            # what did I want to do here? hmmm...
#            call_cmd(argv)
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

class cmd_wrap(vdb.command.command):
    """Executes a some command"""

    def __init__ (self,cmdname):
        self.cmdname = cmdname
        self.wrapped_name = cmdname.capitalize()
        super (cmd_wrap, self).__init__ (self.wrapped_name, gdb.COMMAND_DATA)
        self.saved_arg = None
        self.saved_from_tty = None

    def do_invoke (self, argv):
        arg = self.saved_arg
        from_tty = self.saved_from_tty
        try:
            sc = vdb.subcommands.globals.get( [ self.cmdname ] + argv )
#            print("sc = '%s'" % (sc,) )
            if( sc is None ):
                gdb.execute(f"{self.cmdname} {arg}",from_tty)
            else:
                vdb.subcommands.run_subcommand( [ self.cmdname ] + argv )
        except gdb.error as e:
            print(e)
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()


    def invoke (self, arg, from_tty):
        self.saved_arg = arg
        self.saved_from_tty = from_tty
        super().invoke(arg,from_tty)

def do_cmd( cmd, data, argv ):
    p = subprocess.run([ cmd ] + argv , input = data, encoding = "utf-8" )

for cmd in commands.elements:
#    cmd_external(cmd)
    add(cmd,functools.partial(do_cmd,cmd))

def wrap(cmd):
    cmd_wrap(cmd)

for cmd in up_wraps.elements:
    wrap(cmd)
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
