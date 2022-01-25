#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

import gdb
import traceback
import sys
import shutil

profile_next = vdb.config.parameter("vdb-command-next-profile",False)

command_registry = {}

class command(gdb.Command):

    terminal_width = 80

    def __init__ (self,n,t,c=None, replace = False, prefix = True):
        if( replace is not True ): # check if the command already exists
            try:
                help = gdb.execute(f"help {n}",False,True)
                if( prefix is not True ):
                    raise Exception("Cannot register command")
                print(f"Command already exists: {n}, replacing it with vdb.{n}")
                n = "vdb." + n
            except gdb.error:
                pass
#                print(f"No such command: {n}")

        if( c is None ):
            super (command, self).__init__ (n,t)
        else:
            super (command, self).__init__ (n,t,c)
        self.name = n
        global command_registry
        command_registry[self.name] = self
        self.last_commands = None
        self.repeat = True

    def dont_repeat( self ):
        self.repeat = False
        super().dont_repeat()

    def pipe( self, arg, argv ):
        import vdb.pipe
        try:
            i = argv.index("|") # throws if not found
            a0 = argv[:i]
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
#            traceback.print_exc()
            pass
        self.do_invoke(argv)

    def invoke_or_pipe( self, arg,argv ):
        if( sys.modules.get("vdb.pipe",None) != None ):
            self.pipe(arg,argv)
        else:
            self.do_invoke(argv)

    def invoke (self, arg, from_tty):
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

            global profile_next
            if( profile_next.value and from_tty ):
                profile_next.value = False
                import cProfile
                cProfile.runctx("self.invoke_or_pipe(arg,argv)",globals(),locals())
            else:
                self.invoke_or_pipe(arg,argv)
        except:
            traceback.print_exc()
            raise
            pass

    def message( self, msg, text ):
        prompt = vdb.prompt.refresh_prompt()
        print("\n")
        print(msg)
        print(prompt,end="")
        print(self.name,end=" ")
        print(text,end="")

    def matches( self, word, completion ):
        if(len(word) == 0 ):
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

    def usage( self ):
        print(self.__doc__)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
