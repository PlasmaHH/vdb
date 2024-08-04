#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

import gdb
import traceback
import sys
import shutil

import abc

profile_next = vdb.config.parameter("vdb-command-next-profile",False)

command_registry = {}

class command(gdb.Command,abc.ABC):

    terminal_width = 80

    def __init__ (self,n,t,c=None, replace = False, prefix = True):
        if( replace is not True ): # check if the command already exists
            try:
                _ = gdb.execute(f"help {n}",False,True)
                if( prefix is not True ):
                    raise RuntimeError("Cannot register command")
                print(f"Command already exists: {n}, replacing it with vdb.{n}")
                n = "vdb." + n
            except gdb.error:
                pass
#                print(f"No such command: {n}")

        if( c is None ):
            super ().__init__ (n,t)
        else:
            super ().__init__ (n,t,c)
        self.name = n
        command_registry[self.name] = self
        self.last_commands = None
        self.repeat = True
        self.from_tty = None

    def usage( self ):
        print(self.__doc__)

    def dont_repeat( self ):
        self.repeat = False
        super().dont_repeat()

    def pipe( self, arg, argv ):
        import vdb.pipe # pylint: disable=redefined-outer-name,import-outside-toplevel
        try:
            i = argv.index("|") # throws if not found
#            a0 = argv[:i]
            a1 = argv[i+1:]
            pcmd = a1[0]
            a1 = a1[1:]

            i = arg.rfind("|",0,len(arg))
            if( i < 0 ):
                self.do_invoke(argv)
            ocmd = arg[0:i].strip()
#            print("i = '%s'" % (i,) )
            pcmd = arg[i+1:].strip()
#            print("ocmd = '%s'" % (ocmd,) )
#            print("pcmd = '%s'" % (pcmd,) )

            gout=gdb.execute(self.name + " " + ocmd,False,True)
            pa = gdb.string_to_argv(pcmd)
#            gout = gdb.execute("{} {}".format(self.name," ".join('"{}"'.format(a) for a in a0)),False,True)

            vdb.pipe.call(pa[0],gout,pa[1:])
            return
        except:
#            vdb.print_exc()
            pass
        self.do_invoke(argv)

    @abc.abstractmethod
    def do_invoke( self, argv ):
        pass

    def flags( self, argv ):
        flags = ""
        if( len(argv) > 0 and len(argv[0]) > 0 and argv[0][0] == "/" ):
            flags = argv[0][1:]
            argv = argv[1:]
        return ( argv, flags )

    def context( self, flags ):
        context = (None,None)
        if( len(flags) != 0 ):
            if( flags == "*" ):
                context = ( sys.maxsize, sys.maxsize )
            elif( flags[0] == "+" and flags[1:].isdigit() ):
                context = ( None, int(flags[1:]) )
            elif( flags[0] == "-" and flags[1:].isdigit() ):
                context = ( int(flags[1:]), None )
            elif( flags[0:].isdigit() ):
                context = int(flags[0:])
                context = ( context, context )
            elif( flags.find(",") != -1 ):
                context = flags[0:].split(",")
                context = ( int(context[0]), int(context[1]) )
        return context

    def invoke_or_pipe( self, arg,argv ):
        if( sys.modules.get("vdb.pipe",None) is not None ):
            self.pipe(arg,argv)
        else:
            self.do_invoke(argv)

    def invoke (self, arg, from_tty):
        self.from_tty = from_tty
#        print("arg = '%s'" % (arg,) )
#        print("from_tty = '%s'" % (from_tty,) )

        tw = shutil.get_terminal_size().columns
        if( tw is not None ):
            command.terminal_width = tw

        if( self.repeat is not True and from_tty is True ):
            super().dont_repeat()

        try:
#            print("arg = '%s'" % (arg,) )
            argv = gdb.string_to_argv(arg)

            if( len(argv) == 1 and argv[0] == "/?" ):
                self.usage()
                return

            if( profile_next.value and from_tty ):
                profile_next.value = False
                import cProfile # pylint: disable=import-outside-toplevel
                cProfile.runctx("self.invoke_or_pipe(arg,argv)",globals(),locals(),sort="tottime")
            else:
                self.invoke_or_pipe(arg,argv)
        except:
            vdb.print_exc()
            raise

    def message( self, msg, text ):
        prompt = vdb.prompt.refresh_prompt()
        print("\n")
        print(msg)
        print(prompt,end="")
        print(self.name,end=" ")
        print(text,end="")

    def matches( self, word, completion ):
        if(word is None or len(word) == 0 ):
            return completion
        nc = []
        for c in completion:
            if( c.startswith(word) ):
                nc.append(c)
        return nc

    def current_word( self, word, argv ):
        if( len(word) == 0 ):
            return len(argv)+1
        return len(argv)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
