#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import functools
import subprocess
import gdb
import traceback

commands  = vdb.config.parameter("vdb-pipe-commands","grep,egrep,tee,head,tail,uniq,sort,less,cat,wc", gdb_type = vdb.config.PARAM_ARRAY )
up_wraps  = vdb.config.parameter("vdb-pipe-wrap","show,info,help,x,print,list,set,maint", gdb_type = vdb.config.PARAM_ARRAY )
externals = vdb.config.parameter("vdb-pipe-externals","binwalk,objdump,tmux:,addr2line:-e {file} -a", gdb_type = vdb.config.PARAM_ARRAY )

pipe_commands = { }

def add( cmd, ncall ):
#    global pipe_commands
    pipe_commands[cmd] = ncall

def call( cmd, data, argv ):
    ncall = pipe_commands.get(cmd,None)
    if( ncall is not None ):
        ncall(data, argv)
    else:
        raise Exception(f"Unknonwn pipe command {cmd}")


class cmd_external(vdb.command.command):
    """Executes a some command"""

    def __init__ (self,cmdname):
#        print("cmdname = '%s'" % (cmdname,) )
        if( isinstance(cmdname,str) ):
            cmds = cmdname.split(":")
        else:
            cmds = cmdname
#        print("cmds = '%s'" % (cmds,) )
        if( len(cmds) == 1 ):
            self.cmdname = cmdname
            self.arglist = None
        else:
            self.cmdname= cmds[0]
            self.arglist = cmds[1].split()
#        print("self.cmdname = '%s'" % (self.cmdname,) )
#        print("self.arglist = '%s'" % (self.arglist,) )
        super ().__init__ (self.cmdname, gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

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
            if( self.arglist is not None and len(self.arglist) == 0 ):
                use_arglist = False

            if( use_arglist is True and self.arglist is not None ):
                for arg in self.arglist:
                    if( file is not None ):
                        narg = arg.format(file=file)
                    if( narg != arg ):
                        file_used = True
                    cmd.append(narg)

            for i,a in enumerate(argv):
                if( file is not None ):
                    na = a.format(file=file)
                if( na != a ):
                    file_used = True
                    argv[i] = na


            cmd += argv
            # When file is there use it, unless it is already used or /r
            if( not file_used and file is not None and use_arglist is True ):
                cmd.append(file)
#            print("self.cmdname = '%s'" % (self.cmdname,) )
#            print("self.arglist = '%s'" % (self.arglist,) )
#            print("cmd = '%s'" % (cmd,) )
#            print("file = '%s'" % (file,) )
#            print("argv = '%s'" % (argv,) )
            subprocess.run( cmd , encoding = "utf-8", check=False )
        except:
            traceback.print_exc()
            raise
#            pass
        self.dont_repeat()

class cmd_wrap(vdb.command.command):
    """Executes a some command"""

    def __init__ (self,cmdname):
        self.cmdname = cmdname
        self.wrapped_name = cmdname.capitalize()
        super ().__init__ (self.wrapped_name, gdb.COMMAND_DATA)
        self.saved_arg = None
        self.saved_from_tty = None

    def do_invoke (self, argv):
        arg = self.saved_arg
        from_tty = self.saved_from_tty
        try:
            slpos = argv[0].find("/")
            if( slpos != -1 ):
                cmd = argv[0][:slpos]
                par = argv[0][slpos:]
                argv = [ cmd, par ] + argv[1:]
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
#            pass
        self.dont_repeat()


    def invoke (self, arg, from_tty):
        self.saved_arg = arg
        self.saved_from_tty = from_tty
        super().invoke(arg,from_tty)

def do_cmd( cmd, data, argv ):
    subprocess.run([ cmd ] + argv , input = data, encoding = "utf-8", check = False )

for icmd in commands.elements:
#    cmd_external(cmd)
    add(icmd,functools.partial(do_cmd,icmd))

def wrap(cmd):
    cmd_wrap(cmd)

for icmd in up_wraps.elements:
    wrap(icmd)

def external(cmd):
#    print("cmd = '%s'" % (cmd,) )
    cmd_external(cmd)

for icmd in externals.elements:
    external(icmd)
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
