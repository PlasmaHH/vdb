#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.config
import vdb.subcommands

import gdb

import sys
import os
import shlex
import importlib
import traceback


# First setup the most important settings that configure which parts we want to have active


class cmd_vdb (gdb.Command):
    """Show vdb status information"""

    def __init__ (self):
        super (cmd_vdb, self).__init__ ("vdb", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def invoke (self, arg, from_tty):
        argv=shlex.split(arg)
        if( len(argv) > 0 ):
            if( argv[0] == "start" ):
                start()
                return
            vdb.subcommands.run_subcommand(argv)
            return
        print("vdb is loaded with the following configuration:")

cmd_vdb()

enable_prompt = vdb.config.parameter( "vdb-enable-prompt",True)
enable_backtrace = vdb.config.parameter( "vdb-enable-backtrace",True)
enable_register = vdb.config.parameter( "vdb-enable-register",True)
enable_vmmap = vdb.config.parameter( "vdb-enable-vmmap",True)

def start():
    print("Starting vdb modules…")
    if( enable_prompt ):
        print("Enabling submodule prompt…")
        import vdb.prompt
    if( enable_backtrace ):
        print("Enabling submodule backtrace…")
        import vdb.backtrace
    if( enable_register ):
        print("Enabling submodule register…")
        import vdb.register
    if( enable_vmmap ):
        print("Enabling submodule vmmap…")
        import vdb.vmmap




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

# This may throw an exception, see pwndbg/pwndbg#27
try:
#    gdb.execute("set disassembly-flavor intel")
    gdb.execute("set disassembly-flavor att")
except gdb.error:
    pass




print("Loading plugins")

plugin_types = [ "plugins" ]

def load_plugins( plugindir ):
    try:
        oldpath = []
        oldpath += sys.path
        sys.path.append(plugindir)

        for pt in plugin_types:
            pdir = f"{plugindir}{pt}/"
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


load_plugins("/home/plasmahh/.vdb/")


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
