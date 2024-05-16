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
import subprocess

# XXX Autodetect which tool is available (by a configurable priority list) and then use that one here
src_command = vdb.config.parameter("vdb-list-source-command","bat -r {start}:{end} -H {line} {file} --style=grid,numbers")
marker_color= vdb.config.parameter("vdb-list-colors-marker",   "#0f0", gdb_type = vdb.config.PARAM_COLOUR)


subs_re = re.compile("`(.*)' -> `(.*)'")
path_re = re.compile("(.*)[\\\\/]")
def add_path_substitution( path ):

    subs = gdb.execute("show substitute-path",False,True)
    subs = subs.split("\n")
#    print(f"{subs=}")
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
def do_list( argv, flags, context, recurse = True ):
    before,after = context
#    print(f"do_list({argv=},{flags=})")
    try:
        frame = gdb.selected_frame()
    except gdb.error:
        # Program is not running yet, try displaying main/default, ignoring everything else for now
        code = gdb.execute(f"list",True,True)
        if( (m := error_re.search(code)) is not None ):
            # Try again
            if( recurse ):
                add_path_substitution( m.group(1) )
                return do_list(argv,flags,context,False)
            else:
                print(f"Unable to find file {m.group(1)} even after possible adding substitutions")
        else:
            print(f"{code}")
        return

    # We have a frame, so we have access to code and all that stuff, lets figure out what the user meant
    line = None
    if( len(argv) == 0 ):
        # No other arguments, chose the current frame position
        pc=frame.pc()
        pc = int(pc)
        # In upper levels the pc points to the instruction after the call, we don't want that, so we let it point into the
        # instruction one above, which should be the call. It doesn't matter that we are not at the beginning
        if( frame.level != 0 ):
            pc -= 1

        funsym = frame.function()
        sal = frame.find_sal()
        fullname = sal.symtab.fullname()
        line = sal.line

        if( before is None ):
            before = 0
        if( after is None ):
            after = 0

        start = line - before
        end   = line + after
    else:
        start = before
        end   = after
        funsym = ""
        filename = argv[0]
        sources = gdb.execute("info sources",True,True)
        for sline in sources.split("\n"):
            for src in sline.split(","):
                src = src.strip()
                if( src.endswith(filename) ):
                    fullname = src
                    break
        line = None

    try:
        print(f"{funsym} in {fullname}:{line}")
        if( src_command.value is not None and len(src_command.value) > 0 ):
            bs = start
            if( bs is None ):
                bs = ""
            ass = end
            if( ass is None ):
                ass = ""
            if( line is None ):
                hline = 0
            else:
                hline = line
            cmd = src_command.value.format( start=bs, end=ass, file=fullname, line = hline )
#            print(f"{cmd=}")
            subprocess.run( cmd.split() , encoding = "utf-8", check=False )
        else:
            with open(fullname) as sf:
                print(f"Opened {fullname} as the source file, printing from {before} to {after}")
                for i,sline in enumerate(sf.readlines(),1):
                    printit = True
                    if( i < start ):
                        printit = False
                    elif( i > end ):
                        printit = False
                    if( printit ):
                        if( line == i ):
                            iss = vdb.color.color(str(i),marker_color.value)
                        else:
                            iss = str(i)
                        print(f"{iss}\t{sline}",end="")
    except FileNotFoundError:
        if( recurse ):
            add_path_substitution(fullname)
            return do_list(argv,flags,context,False)
        else:
            print(f"Cannot find source file {fullname}")
#    code = gdb.execute(f"list *{pc}",True,True)
#    code = gdb.execute(f"list {' '.join(argv)}",False,True)
#    print("exec list")
#    print(f"list *{int(pc)}")
#    print("done list")
#    else:
#        try:
#            code = gdb.execute(f"list {' '.join(argv)}",True,True)
#        except gdb.error:
#            if( recurse ):
#                add_path_substitution(fullname)
#                return do_list(argv,flags,context,False)
#            else:
#                print(f"Unable to execute 'list {argv}'")
#    print(f"{code}")


class cmd_list (vdb.command.command):
    """
list code
"""

    def __init__ (self):
        super ().__init__ ("List", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            context = self.context(flags)
            do_list(argv,flags,context)
#            print (self.__doc__)
        except:
            traceback.print_exc()
            raise
        self.dont_repeat()

cmd_list()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
