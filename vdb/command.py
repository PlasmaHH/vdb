#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command

import gdb
import traceback
import sys

profile_next = vdb.config.parameter("vdb-command-next-profile",False)

command_registry = {}

class command(gdb.Command):

    def __init__ (self,n,t,c=None):
        if( c is None ):
            super (command, self).__init__ (n,t)
        else:
            super (command, self).__init__ (n,t,c)
        self.name = n
        global command_registry
        command_registry[self.name] = self

    def pipe( self, argv ):
        import vdb.pipe
        try:
            i = argv.index("|") # throws if not found
            a0 = argv[:i]
            a1 = argv[i+1:]
            pcmd = a1[0]
            a1 = a1[1:]

#            print("argv = '%s'" % argv )
#            print("i = '%s'" % (i,) )
#            print("a0 = '%s'" % (a0,) )
#            print("a1 = '%s'" % (a1,) )
#            print("pcmd = '%s'" % (pcmd,) )
            gout = gdb.execute("{} {}".format(self.name," ".join('"{}"'.format(a) for a in a0)),False,True)
#            print("gout = '%s'" % gout )

            vdb.pipe.call(pcmd,gout,a1)
            return
        except:
#            traceback.print_exc()
            pass
        self.do_invoke(argv)

    def invoke_or_pipe( self, argv ):
        if( sys.modules.get("vdb.pipe",None) != None ):
            self.pipe(argv)
        else:
            self.do_invoke(argv)

    def invoke (self, arg, from_tty):
        try:
#            print("arg = '%s'" % (arg,) )
            argv = gdb.string_to_argv(arg)

            if( len(argv) == 1 and argv[0] == "/?" ):
                self.usage()
                return

            global profile_next
            if( profile_next.value ):
                profile_next.value = False
                import cProfile
                cProfile.runctx("self.invoke_or_pipe(argv)",globals(),locals())
            else:
                self.invoke_or_pipe(argv)
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
