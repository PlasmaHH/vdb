#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.pointer
import vdb.event
import vdb.register

from itertools import chain

import gdb

import traceback
import re


subs_re = re.compile("`(.*)' -> `(.*)'")
path_re = re.compile("(.*)[\\\\/]")
def add_path_substitution( path ):

    subs = gdb.execute("show substitute-path",False,True)
    subs = subs.split("\n")
    print(f"{subs=}")
    for sp in subs:
        if( (m := subs_re.search(sp) ) is not None ):
            frm = m.group(1)
            to  = m.group(2)
            if( path.startswith(frm) ):
#                print(f" {frm} =>> {to} matches {path}")
                if( not to.endswith("/") ):
                    to += "/"
                m = path_re.match(path)
                pathpart = m.group(1)
                pathpart = pathpart.replace(frm,to)
                pathpart = pathpart.replace("\\","/")

                nfrom = m.group(1).replace("\\","\\\\")
                print(f"Adding new substitution {nfrom} => {pathpart}")
                gdb.execute(f"set substitute-path '{nfrom}' '{pathpart}'")
#                gdb.execute("show  substitute-path")


error_re = re.compile("[0-9]+\s*(.*): No such file")
def do_list( argv, flags, recurse = True ):
#    print(f"do_list({argv=},{flags=})")
    try:
        frame = gdb.selected_frame()
    except gdb.error:
        # Program is not running yet, try displaying main
        code = gdb.execute(f"list main",False,True)
        if( (m := error_re.search(code)) is not None ):
            # Try again
            if( recurse ):
                add_path_substitution( m.group(1) )
                return do_list(argv,flags,False)
        else:
            print(f"{code}")
        return

    pc=frame.read_register("pc")
    pc = int(pc)
    # In upper levels the pc points to the instruction after the call, we don't want that, so we let it point into the
    # instruction one above, which should be the call. It doesn't matter that we are not at the beginning
    if( frame.level != 0 ):
        pc -= 1

#    code = gdb.execute(f"list {' '.join(argv)}",False,True)
#    print("exec list")
#    print(f"list *{int(pc)}")
#    print("done list")
    code = gdb.execute(f"list *{pc}",False,True)
    print(f"{code}")

class cmd_list (vdb.command.command):
    """
list code
"""

    def __init__ (self):
        super ().__init__ ("List", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            do_list(argv,flags)
#            print (self.__doc__)
        except:
            traceback.print_exc()
            raise
        self.dont_repeat()

cmd_list()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
