#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import functools
import subprocess
import gdb

commands  = vdb.config.parameter("vdb-pipe-commands","grep,egrep,tee,head,tail,uniq,sort,less,cat,wc", gdb_type = vdb.config.PARAM_ARRAY )
up_wraps  = vdb.config.parameter("vdb-pipe-wrap","show,info,help,x,print,list,set,maint", gdb_type = vdb.config.PARAM_ARRAY )
externals = vdb.config.parameter("vdb-pipe-externals","binwalk,objdump", gdb_type = vdb.config.PARAM_ARRAY )

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
        cmds = cmdname.split(":")
        if( len(cmds) == 1 ):
            self.cmdname = cmdname
            self.arglist = [ ]
        else:
            self.cmdname= cmds[0]
            self.arglist = cmds[1].split()
        super (cmd_external, self).__init__ (self.cmdname, gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv):
        try:
            infofile = gdb.execute("info file",False,True)
            parse_next = False
            file = None
            use_arglist = True
            if( len(argv) > 0 and argv[0] == "/r" ):
                use_arglist = False
                argv = argv[1:]

            for l in infofile.split("\n"):
                if( parse_next is True ):
                    fs = l.split("'")
                    file = fs[0].strip()[1:]
                    break
                if( l.startswith("Local exec file") ):
                    parse_next = True
            cmd = [ self.cmdname ]
            file_used = False
            if( use_arglist is True ):
                for arg in self.arglist:
                    narg = arg.format(file=file)
                    if( narg != arg ):
                        file_used = True
                    cmd.append(narg)
            cmd += argv
            if( not file_used ):
                cmd.append(file)
#            print("self.cmdname = '%s'" % (self.cmdname,) )
#            print("self.arglist = '%s'" % (self.arglist,) )
            print("cmd = '%s'" % (cmd,) )
#            print("file = '%s'" % (file,) )
#            print("argv = '%s'" % (argv,) )
            p = subprocess.run( cmd , encoding = "utf-8" )
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

def external(cmd):
    cmd_external(cmd)

for cmd in externals.elements:
    external(cmd)
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
