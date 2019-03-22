#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.config
import vdb.subcommands
import vdb.command

import gdb

import sys
import os
import importlib
import traceback


# First setup the most important settings that configure which parts we want to have active


class cmd_vdb (vdb.command.command):
    """Show vdb status information"""

    def __init__ (self):
        super (cmd_vdb, self).__init__ ("vdb", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        if( len(argv) > 0 ):
            if( argv[0] == "start" ):
                start()
                return
            vdb.subcommands.run_subcommand(argv)
            return
        print("vdb is loaded with the following configuration:")

cmd_vdb()

theme = vdb.config.parameter( "vdb-theme",None)

def load_plugins( plugindir ):
    print("Loading plugins…")
    try:
        oldpath = []
        oldpath += sys.path
        sys.path = [plugindir] + sys.path

        for pt in enabled_modules + [ "plugins" ]:
            pdir = f"{plugindir}{pt}/"
            if( os.path.isdir(pdir) ):
                for fn in filter( lambda x : x.endswith(".py"), os.listdir(pdir) ):
                    try:
                        print(f"Loading plugin {plugindir}{pt}/{fn}")
                        importname = f"{pt}.{fn[:-3]}"
                        importlib.import_module(importname)
                    except:
                        print(f"Error while loading plugin {plugindir}{pt}/{fn}")
                        traceback.print_exc()
                        pass
    except:
        traceback.print_exc()
        pass
    finally:
        sys.path = oldpath

def load_themes( vdbdir ):
    if( len(theme.value) == 0 ):
        print("Not loading any theme")
        return
    tdir = f"{vdbdir}themes/"
    tfile = f"{tdir}{theme.value}.py"
    if( not os.path.isfile(tfile) ):
        raise gdb.GdbError(f"Theme file {tfile} not found, can't load")
    print("Trying to load theme from " + tfile)
    try:
        oldpath = []
        oldpath += sys.path
        sys.path = [tdir] + sys.path
        importlib.import_module(theme.value)
    except:
        traceback.print_exc()
    finally:
        sys.path = oldpath

enable_prompt = vdb.config.parameter( "vdb-enable-prompt",True)
enable_backtrace = vdb.config.parameter( "vdb-enable-backtrace",True)
enable_register = vdb.config.parameter( "vdb-enable-register",True)
enable_vmmap = vdb.config.parameter( "vdb-enable-vmmap",True)
enable_hexdump = vdb.config.parameter( "vdb-enable-hexdump",True)
enable_asm = vdb.config.parameter( "vdb-enable-asm",True)
enable_grep = vdb.config.parameter( "vdb-enable-grep",True)
enable_pahole = vdb.config.parameter( "vdb-enable-pahole",True)

configured_modules = vdb.config.parameter( "vdb-available-modules", "prompt,backtrace,register,vmmap,hexdump,asm,grep,pahole" )


enabled_modules = [ ]
def start():
    print("Starting vdb modules…")
    available_modules = configured_modules.value.split(",")
    for mod in available_modules:
        try:
            bval = gdb.parameter( f"vdb-enable-{mod}")
            if( bval ):
                print(f"Loading module {mod}…")
                importlib.import_module(f"vdb.{mod}")
                enabled_modules.append(mod)
            else:
                print(f"Skipping load of module {mod}…")
        except:
            print(f"Error loading module {mod}:")
            traceback.print_exc()
            pass
    vdb_dir = os.path.expanduser("~") + "/.vdb/"
    load_plugins(vdb_dir)
    load_themes(vdb_dir)

#pre_commands = """
#set confirm off
#set verbose off
#set prompt %s
#set height 0
#set history expansion on
#set history save on
#set follow-fork-mode child
#set backtrace past-main on
#set step-mode on
#set print pretty on
#set width 0
#set print elements 15
#handle SIGALRM nostop print nopass
#handle SIGBUS  stop   print nopass
#handle SIGPIPE nostop print nopass
#handle SIGSEGV stop   print nopass
#""".strip() % prompt
#


try:
#    gdb.execute("set disassembly-flavor intel")
    gdb.execute("set disassembly-flavor att")
except gdb.error:
    pass


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
