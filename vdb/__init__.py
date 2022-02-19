#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.subcommands
import vdb.command
import vdb.util

import gdb

import sys
import os
import importlib
import traceback
import concurrent.futures
import atexit



# First setup the most important settings that configure which parts we want to have active

enable = vdb.config.parameter( "vdb-enable", True )
theme  = vdb.config.parameter( "vdb-theme",None)

enable_prompt    = vdb.config.parameter( "vdb-enable-prompt",True)
enable_backtrace = vdb.config.parameter( "vdb-enable-backtrace",True)
enable_register  = vdb.config.parameter( "vdb-enable-register",True)
enable_vmmap     = vdb.config.parameter( "vdb-enable-vmmap",True)
enable_hexdump   = vdb.config.parameter( "vdb-enable-hexdump",True)
enable_asm       = vdb.config.parameter( "vdb-enable-asm",True)
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
enable_history   = vdb.config.parameter( "vdb-enable-history",True)
enable_pipe      = vdb.config.parameter( "vdb-enable-pipe",True)
enable_va        = vdb.config.parameter( "vdb-enable-va",True)

configured_modules = vdb.config.parameter( "vdb-available-modules", "prompt,backtrace,register,vmmap,hexdump,asm,pahole,ftree,dashboard,hashtable,ssh,track,graph,data,syscall,types,profile,unwind,hook,history,pipe,va" )

home_first      = vdb.config.parameter( "vdb-plugin-home-first",True)
search_down     = vdb.config.parameter( "vdb-plugin-search-down",True)
honor_sp        = vdb.config.parameter( "vdb-plugin-honor-safe-path",True)
max_threads     = vdb.config.parameter( "vdb-max-threads",4)
inithome_first  = vdb.config.parameter( "vdb-init-home-first",True)
initsearch_down = vdb.config.parameter( "vdb-init-search-down",True)


enabled_modules = [ ]
vdb_dir = None
vdb_init = None
texe = None
keep_running = True



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


def is_in_safe_path( pdir ):
    if( not honor_sp.value ):
        return True

    pdir = os.path.normpath(pdir) + "/"
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
            return True
    return False

def load_init( vdb_init ):
    try:
        with open(vdb_init,"r") as f:
            vdb.config.execute(f.read(),vdb_init)
    except FileNotFoundError:
        pass

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
    tdir = f"{vdbdir}/themes/"
    tfile = f"{tdir}{theme.value}.py"
    if( not is_in_safe_path(tdir) ):
        if( os.path.isfile(tfile) ):
            print(f"{tdir} is not in safe path, not loading {tfile} from there")
        return
    if( not os.path.isfile(tfile) ):
        print(f"Theme file {tfile} not found, not loading any theme")
        return

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

def start( vdbd = None, vdbinit = None ):
    if( enable.value is False ):
        print("Not starting vdb, disabled by vdb-enable")
        return None
    print("Starting vdb modules…")
    
    global texe
    texe = concurrent.futures.ThreadPoolExecutor(max_workers=max_threads.value,thread_name_prefix="vdb")

    global vdb_dir
    global vdb_init

    if( vdbd is not None ):
        vdb_dir = os.path.expanduser(vdbd)
    else:
        vdb_dir = os.path.expanduser("~") + "/.vdb/"
    vdb_dir = os.path.realpath(vdb_dir)

    if( vdbinit is not None ):
        vdb_init = os.path.expanduser(vdbinit)
    else:
        vdb_init = os.path.expanduser("~") + "/.vdbinit"
    vdb_init = os.path.realpath(vdb_init)


    available_modules = configured_modules.value.split(",")
    for mod in available_modules:
        try:
            bval = gdb.parameter( f"vdb-enable-{mod}")
            if( bval ):
                vdb.util.log(f"Loading module {mod}…")
                importlib.import_module(f"vdb.{mod}")
                enabled_modules.append(mod)
            else:
                vdb.util.log(f"Skipping load of module {mod}…")
        except:
            print(f"Error loading module {mod}:")
            traceback.print_exc()
            pass

    plug_dirs = []
    init_files = []

    rvdb = os.path.realpath(vdb_dir)
    cwd = os.path.realpath(os.getcwd())

    while( cwd != "/" ):
        cvdb = cwd + "/.vdb/"
        if( os.path.normpath(cvdb) == os.path.normpath(rvdb) ):
            break

        plug_dirs.append(cvdb)
        init_files.append(cwd + "/.vdbinit")
        cwd,down = os.path.split(cwd)


    if( not search_down.value ):
        plug_dirs.reverse()

    if( not initsearch_down.value ):
        init_files.reverse()

    if( home_first.value ):
        plug_dirs = [ vdb_dir ] + plug_dirs
    else:
        plug_dirs = plug_dirs + [ vdb_dir ]

    if( inithome_first.value ):
        init_files = [ vdb_init ] + init_files
    else:
        init_files = init_files + [ vdb_init ]

    for i in init_files:
        load_init(i)

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

log = vdb.util.log

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
