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
import concurrent.futures
import atexit
"""

search order:
    downwards
    upwards

    home-first
    local-first


vdbinit-search-order
vdbinit-stop-on-find

vdb-search-order
vdb-stop-on-find

theme-search-order
theme-stop-on-find

example tree:

[1]~/.vdb/
[2]~/.vdbinit

[3]~/git/project/.vdb/
[4]~/git/project/.vdbinit


downwards local-first non-stop:

look at (and load)
~/.vdb
~/git/project/.vdb
~/git/.vdb

"""

# First setup the most important settings that configure which parts we want to have active


class cmd_vdb (vdb.command.command):
    """Show vdb status information, start vdb and call subcommands"""

    def __init__ (self):
        super (cmd_vdb, self).__init__ ("vdb", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        if( len(argv) > 0 ):
            if( argv[0] == "start" ):
                start()
                return
            vdb.subcommands.run_subcommand(argv)
            return
        print(f"vdb is loaded with the following modules: {enabled_modules}")
        print("Available subcommands:")
        vdb.subcommands.show([])
        print("Available module commands:")
        maxlen = 0
        for n,c in vdb.command.command_registry.items():
            maxlen = max(maxlen,len(n))

        for n,c in vdb.command.command_registry.items():
            ns = n.ljust(maxlen)
            doc = c.__doc__
            doc = doc.split("\n")[0]
            print(f" {ns} : {doc}")

cmd_vdb()

theme = vdb.config.parameter( "vdb-theme",None)


def is_in_safe_path( pdir ):
    pdir = os.path.normpath(pdir) + "/"
#    print("pdir = '%s'" % pdir )
    sp = gdb.parameter("auto-load safe-path")

    debugdir = gdb.parameter("debug-file-directory")

    datadir = gdb.execute("show data-directory",False,True)
    datadir = datadir.split('"')[1]

    global vdb_dir

    vdir = os.path.normpath(vdb_dir)

    sp=sp.replace("$datadir",datadir)
    sp=sp.replace("$debugdir",debugdir)

    sp = sp.split(":")
    sp.append(vdir)

    for p in sp:
        p = os.path.normpath(p) + "/"
        if( pdir.startswith(p) ):
#            print("pdir = '%s'" % pdir )
#            print("p = '%s'" % p )
            return True
    return False


def load_plugins( plugindir ):
    try:
        oldpath = []
        oldpath += sys.path
        sys.path = [plugindir] + sys.path

        if( not is_in_safe_path(plugindir) ):
            return

        print(f"Loading plugins in {plugindir}…")

        for pt in enabled_modules + [ "plugins" ]:
            pdir = f"{plugindir}/{pt}/"
            if( os.path.isdir(pdir) ):
                for fn in filter( lambda x : x.endswith(".py"), os.listdir(pdir) ):
                    try:
                        print(f"Loading plugin {plugindir}/{pt}/{fn}")
                        importname = f"{pt}.{fn[:-3]}"
                        importlib.import_module(importname)
                    except:
                        print(f"Error while loading plugin {plugindir}/{pt}/{fn}")
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
    if( not is_in_safe_path(tdir) ):
        return
    tfile = f"{tdir}{theme.value}.py"
    if( not os.path.isfile(tfile) ):
        return
#        raise gdb.GdbError(f"Theme file {tfile} not found, can't load")
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

enable_prompt    = vdb.config.parameter( "vdb-enable-prompt",True)
enable_backtrace = vdb.config.parameter( "vdb-enable-backtrace",True)
enable_register  = vdb.config.parameter( "vdb-enable-register",True)
enable_vmmap     = vdb.config.parameter( "vdb-enable-vmmap",True)
enable_hexdump   = vdb.config.parameter( "vdb-enable-hexdump",True)
enable_asm       = vdb.config.parameter( "vdb-enable-asm",True)
enable_grep      = vdb.config.parameter( "vdb-enable-grep",True)
enable_tee       = vdb.config.parameter( "vdb-enable-tee",True)
enable_pahole    = vdb.config.parameter( "vdb-enable-pahole",True)
enable_ftree     = vdb.config.parameter( "vdb-enable-ftree",True)
enable_dashboard = vdb.config.parameter( "vdb-enable-dashboard",True)
enable_hashtable = vdb.config.parameter( "vdb-enable-hashtable",True)
enable_ssh       = vdb.config.parameter( "vdb-enable-ssh",True)
enable_track     = vdb.config.parameter( "vdb-enable-track",True)
enable_graph     = vdb.config.parameter( "vdb-enable-graph",True)
enable_data      = vdb.config.parameter( "vdb-enable-data",True)
enable_syscall   = vdb.config.parameter( "vdb-enable-syscall",True)
enable_types     = vdb.config.parameter( "vdb-enable-types",True)
enable_profile   = vdb.config.parameter( "vdb-enable-profile",True)
enable_unwind    = vdb.config.parameter( "vdb-enable-unwind",True)
enable_hook      = vdb.config.parameter( "vdb-enable-hook",True)

configured_modules = vdb.config.parameter( "vdb-available-modules", "prompt,backtrace,register,vmmap,hexdump,asm,grep,pahole,ftree,dashboard,hashtable,ssh,track,graph,tee,data,syscall,types,profile,unwind,hook" )

home_first  = vdb.config.parameter( "vdb-plugin-home-first",True)
search_down = vdb.config.parameter( "vdb-plugin-search-down",True)
honor_sp    = vdb.config.parameter( "vdb-plugin-honor-safe-path",True)
max_threads = vdb.config.parameter( "vdb-max-threads",4)


enabled_modules = [ ]
vdb_dir = None
texe = None
keep_running = True

def start( vdbd = None ):
    print("Starting vdb modules…")
    
    global texe
    texe = concurrent.futures.ThreadPoolExecutor(max_workers=max_threads.value,thread_name_prefix="vdb")

    global vdb_dir

    if( vdbd is not None ):
        vdb_dir = os.path.expanduser(vdbd)
    else:
        vdb_dir = os.path.expanduser("~") + "/.vdb/"
    vdb_dir = os.path.realpath(vdb_dir)

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

    plug_dirs = []

    rvdb = os.path.realpath(vdb_dir)
    cwd = os.path.realpath(os.getcwd())
#    print("rvdb = '%s'" % rvdb )
    while( cwd != "/" ):
        cvdb = cwd + "/.vdb/"
        if( os.path.normpath(cvdb) == os.path.normpath(rvdb) ):
            break
#        print("cvdb = '%s'" % cvdb )
        plug_dirs.append(cvdb)
#        print("cwd = '%s'" % cwd )
        cwd,down = os.path.split(cwd)
#        print("down = '%s'" % down )

    if( not search_down.value ):
        plug_dirs.reverse()

    if( home_first.value ):
        plug_dirs = [ vdb_dir ] + plug_dirs
    else:
        plug_dirs = plug_dirs + [ vdb_dir ]

    for d in plug_dirs:
        load_plugins(d)

    for d in plug_dirs:
        load_themes(d)

def enabled( mod ):
    if( mod in enabled_modules ):
        return True
    return False

def exit( ):
    print("Exiting vdb...")
    global keep_running
    keep_running = False

atexit.register(exit)
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
