#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command

import gdb
import traceback
import sys

profile_next = vdb.config.parameter("vdb-command-next-profile",False)

command_registry = {}

class command(gdb.Command):

    def __init__ (self,n,t,c):
        super (command, self).__init__ (n,t,c)
        self.name = n
        global command_registry
        command_registry[self.name] = self

    def pipe( self, argv ):
        import vdb.pipe
        try:
            i = argv.index("|")
            a0 = argv[:i]
            a1 = argv[i+1:]
            pcmd = a1[0]
            a1 = a1[1:]
            gout = gdb.execute("{} {}".format(self.name," ".join('"{}"'.format(a) for a in a0)),False,True)
#            print("gout = '%s'" % gout )
#            print("argv = '%s'" % argv )
#            print("pcmd = '%s'" % pcmd )
#            print("a0 = '%s'" % a0 )
#            print("a1 = '%s'" % a1 )
            vdb.pipe.call(pcmd,gout,a1)
            return
        except:
            pass
#            traceback.print_exc()
        self.do_invoke(argv)

    def invoke_or_pipe( self, argv ):
        if( sys.modules.get("vdb.pipe",None) != None ):
            self.pipe(argv)
        else:
            self.do_invoke(argv)

    def invoke (self, arg, from_tty):
        try:
            argv = gdb.string_to_argv(arg)

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

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
