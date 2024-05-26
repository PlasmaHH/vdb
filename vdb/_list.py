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
import os

# XXX Autodetect which tool is available (by a configurable priority list) and then use that one here
src_command     = vdb.config.parameter("vdb-list-source-command","bat -r {start}:{end} -H {line} {file} --style=numbers --paging=never -f")
marker_color    = vdb.config.parameter("vdb-list-colors-marker",   "#0f0", gdb_type = vdb.config.PARAM_COLOUR)
default_context = vdb.config.parameter("vdb-list-default-context", 10 )


path_substitutions = {}


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
            path_substitutions[frm] = to
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
                path_substitutions[nfrom.replace("\\\\","\\")] = pathpart
                break
#                gdb.execute("show  substitute-path")
#    print(f"{path_substitutions=}")

@vdb.util.memoize(gdb.events.new_objfile)
def get_sources( ):
    print("Gathering source file information (may take a while for bigger binaries)")
    return gdb.execute("info sources",True,True)

error_re = re.compile("[0-9]+\s*(.*): No such file")
def do_list( argv, flags, context, recurse = True ):
    before,after = context
    line = None
#    print(f"do_list({argv=},{flags=},{context=})")

    if( before is None and after is None ):
        after = before = default_context.value
       # Program is not running yet, try displaying main/default, ignoring everything else for now
#        code = gdb.execute(f"list",True,True)
#        if( (m := error_re.search(code)) is not None ):
#             Try again
#            if( recurse ):
#                add_path_substitution( m.group(1) )
#                return do_list(argv,flags,context,False)
#            else:
#                print(f"Unable to find file {m.group(1)} even after possible adding substitutions")
#        else:
#            print(f"{code}")
#        return

    if( len(argv) == 0 ):
        try:
            frame = gdb.selected_frame()
        except gdb.error:
            frame = None
    
        if( frame is not None ):
            # We have a frame, so we have access to code and all that stuff, lets figure out what the user meant
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
        else: # no frame, lets see if gdb can be of any help here
            # "help info main" gets entry point?
            
            current_file = None
            smallest_name = None
            smallest_file = None
            line = None
            for sline in gdb.execute("info functions main",True,True).split("\n"):
                sline = sline.strip()
                if( len(sline) == 0 ):
                    continue
                if( sline.startswith("File") ):
                    current_file = sline[5:-1]
#                    print(f"{sline} -> {current_file=}")
                    continue
                if( not sline.endswith(";") ):
                    continue
                # rest should be function position information
                vl = sline.split(":")
                sline = ":".join(vl[1:]).strip()

#                print(f"{sline=}")
                if( smallest_name is None or len(sline) < len(smallest_name) ):
                    smallest_name = sline
                    smallest_file = current_file
                    line = int(vl[0])

            fullname = smallest_file
            funsym = smallest_name

        if( before is None ):
            before = 0
        if( after is None ):
            after = 0

        start = max(1,line - before)
        end   = line + after
    else: # passed a filename XXX do we want to support symbols too? Can get a bit more complicated
        start = before
        end   = after
        funsym = ""
        filename = argv[0]
        sources = get_sources()
        for sline in sources.split("\n"):
            for src in sline.split(","):
                src = src.strip()
                if( src.endswith(filename) ):
                    fullname = src
                    break
        line = 0


    # Check if its accessible, if not we may need to adapt the path and try again
    if( not os.path.isfile(fullname) or not os.access(fullname,os.R_OK) ):
        if( recurse ):
            add_path_substitution( fullname )
            return do_list(argv,flags,context,False)


    # This should cause a fresh parse into our dict
    if( len(path_substitutions) == 0 ):
        add_path_substitution("")

    for f,t in path_substitutions.items():
        if( fullname.startswith(f) ):
            nfl = fullname.replace(f,t)
            nfl=nfl.replace("\\","/")
            if( os.path.isfile(nfl) and os.access(nfl,os.R_OK) ):
                fullname = nfl
                break


    # XXX We can get the return type via "whatis" for nicer display. Maybe we want to go through everything and gather
    # generic type handling tools? 
    try:
        print(f"{funsym} in {fullname}:{line}")
        if( src_command.value is not None and len(src_command.value) > 0 ):
            bs = start
            ass = end
            if( bs is None ):
                bs = ""
                if( ass is None ):
                    ass = "1000000"

            if( ass is None ):
                ass = ""
            if( line is None ):
                hline = 0
            else:
                hline = line
            cmd = src_command.value.format_map( vdb.util.kw_dict(start=bs, end=ass, line = hline) )
            cmd = cmd.split()

            for i,c in enumerate(cmd):
                cmd[i] = c.format(file=fullname)
#            print(f"{cmd=}")
            result = subprocess.run( cmd , encoding = "utf-8", check=False , stdin = subprocess.DEVNULL, capture_output = True )
            print(result.stdout,end="")
            print(result.stderr,end="")
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
