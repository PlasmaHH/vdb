#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.hexdump

import gdb

import traceback # pylint: disable=unused-import
import os
import pstats

class cmd_profile (vdb.command.command):
    """Run a command under python profiling
"""

    def __init__ (self):
        super ().__init__ ("profile", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    @vdb.overrides
    def do_invoke( self, argv: list[str] ):
        pass

    def invoke (self, arg: str, from_tty: bool):
        try:
            if( len(arg) == 0 ):
                self.usage()
                return
            argv = gdb.string_to_argv(arg)
            filename = None
            if( argv[0][0] == "/" ):
                if( argv[0][1] == "d" ):
                    filename="__vdb_profile.tmp"
                    arg = arg[3:]
                else:
                    self.usage()
                    return

            import cProfile # pylint: disable=import-outside-toplevel
            cProfile.runctx("gdb.execute(arg,from_tty)",globals(),locals(),filename=filename,sort="tottime")
            if( filename is not None ):
                os.system(f"gprof2dot -f pstats {filename} -o __vdb_profile.dot")
                os.system("nohup dot -Txlib __vdb_profile.dot &")
                p = pstats.Stats(filename)
                p.sort_stats("tottime").print_stats()

        except: # pylint: disable=try-except-raise
#            traceback.print_exc()
            raise

        self.dont_repeat()

cmd_profile()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
