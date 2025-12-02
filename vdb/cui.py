#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.types

import os
import traceback
import time
import re
import textual.app

def cui_startup( argv, flags ):
    dis=gdb.execute("reg foo",False,True)

class cmd_cui(vdb.command.command):
    """
cui takeover
cui exit
"""

    def __init__ (self):
        super (cmd_cui, self).__init__ ("cui", gdb.COMMAND_DATA)
        self.needs_parameters = True

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)
        self.dont_repeat()
        subcmd = argv[0]
        argv = argv[1:]
        match subcmd:
            case "takeover":
                cui_startup(argv,flags)
            case "exit":
                cui_exit(argv,flags)
            case _:
                raise RuntimeError(f"Unknown subcommand")

cmd_cui()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
