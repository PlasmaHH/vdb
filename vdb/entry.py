#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.types

import traceback # pylint: disable=unused-import

def entry(_:list[str]):
    info_file = gdb.execute("info file",False,True)
    ep: str = None
    for line in info_file.splitlines():
        if( line.find("Entry point:") > -1 ):
            epv = line.split(":")
            ep = epv[1]
            ep = vdb.util.rxint(ep)

    if( ep is None ):
        print("Unable to determine entry point")
    else:
        print(f"Setting $pc to {ep:#0x}")
        gdb.execute(f"set $pc={ep:#0x}")

class cmd_entry(vdb.command.command):
    """
    The entry command will try to extract gdbs information about the programs entry point and sets $pc to it
    """

    def __init__ (self):
        super ().__init__ ("entry", gdb.COMMAND_DATA)

    def do_invoke (self, argv:list[str] ):
        self.dont_repeat()

        try:
            entry(argv)
        except Exception: # pylint: disable=try-except-raise
#            traceback.print_exc()
            raise

cmd_entry()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
