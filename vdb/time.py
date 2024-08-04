#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import time

import gdb
import gdb.types

import traceback # pylint: disable=unused-import

def time_cmd( flags, args ):
    print(f"{args=}")
    t0 = time.time()
    vargs = []
    first = True
    for a in args:
        if( first ):
            vargs.append(f'{a}')
        else:
            vargs.append(f'"{a}"')
        first = False
    cmd = " ".join(vargs)
    print(f"{cmd=}")
    gdb.execute( cmd )
    t1 = time.time()
    tdif = t1-t0
    print(f"Command '{cmd}' took {tdif}s")


class cmd_time(vdb.command.command):
    """
    The time command will 
    """

    def __init__ (self):
        super ().__init__ ("time", gdb.COMMAND_DATA)

    def do_invoke (self, argv:list[str] ):
        self.dont_repeat() # idealls we would want the one from the called command
        argv,flags = self.flags(argv)

        try:
            time_cmd(flags,argv)
        except Exception: # pylint: disable=try-except-raise
#            vdb.print_exc()
            raise

cmd_time()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
