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
import inspect
import re

from typing import Dict
from types import ModuleType



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
enable_llist     = vdb.config.parameter( "vdb-enable-llist",True)
enable_misc      = vdb.config.parameter( "vdb-enable-misc",True)
enable_svd       = vdb.config.parameter( "vdb-enable-svd",True)
enable_entry     = vdb.config.parameter( "vdb-enable-entry",True)
enable_rtos      = vdb.config.parameter( "vdb-enable-rtos",True)
enable_xi        = vdb.config.parameter( "vdb-enable-xi",True)
enable_list      = vdb.config.parameter( "vdb-enable-list",True)
enable_time      = vdb.config.parameter( "vdb-enable-time",True)
enable_swo       = vdb.config.parameter( "vdb-enable-swo",True)
enable_hardfault = vdb.config.parameter( "vdb-enable-hardfault",True)

configured_modules = vdb.config.parameter( "vdb-available-modules", "prompt,backtrace,register,vmmap,hexdump,asm,xi,pahole,ftree,dashboard,hashtable,ssh,track"
                                                                    ",graph,data,syscall,types,profile,unwind,hook,history,pipe,va,llist,misc,svd,entry,rtos,xi,list"
                                                                    ",time,swo,hardfault" )


home_first      = vdb.config.parameter( "vdb-plugin-home-first",True)
search_down     = vdb.config.parameter( "vdb-plugin-search-down",True)
honor_sp        = vdb.config.parameter( "vdb-plugin-honor-safe-path",True)
max_threads     = vdb.config.parameter( "vdb-max-threads",4)
inithome_first  = vdb.config.parameter( "vdb-init-home-first",True)
initsearch_down = vdb.config.parameter( "vdb-init-search-down",True)
rich_tracebacks = vdb.config.parameter( "vdb-rich-traceback",True)

# enabling as early as possible gives the most value
if( rich_tracebacks.value ):
    import rich.traceback
    rich.traceback.install(show_locals=True)

def print_exc( ):
    if( rich_tracebacks.value ):
        vdb.util.console.print_exception( show_locals = True )
    else:
        vdb.print_exc()

enabled_modules: Dict[str,ModuleType] = {}
vdb_dir = None
vdb_init = None
texe = None
keep_running = True

# XXX check for number/names? of variables
def overrides(method):
    # actually can't do this because a method is really just a function while inside a class def'n
    #assert(inspect.ismethod(method))

    stack = inspect.stack()
    base_classes = re.search(r'class.+\((.+)\)\s*\:', stack[2][4][0]).group(1)

    # handle multiple inheritance
    base_classes = [s.strip() for s in base_classes.split(',')]
    if not base_classes:
        raise ValueError('overrides decorator: unable to determine base class')

    # stack[0]=overrides, stack[1]=inside class def'n, stack[2]=outside class def'n
    derived_class_locals = stack[2][0].f_locals

    # replace each class name in base_classes with the actual class type
    for i, base_class in enumerate(base_classes):

        if '.' not in base_class:
            base_classes[i] = derived_class_locals[base_class]

        else:
            components = base_class.split('.')

            # obj is either a module or a class
            obj = derived_class_locals[components[0]]

            for c in components[1:]:
                assert(inspect.ismodule(obj) or inspect.isclass(obj))
                obj = getattr(obj, c)

            base_classes[i] = obj


    if not ( any( hasattr(cls, method.__name__) for cls in base_classes ) ):
        raise NotImplementedError(f"Method {method.__name__} marked override, but not preset in any base: {base_classes}")
    return method

def xoverrides(interface_class):
    def overrider(method):
        assert(method.__name__ in dir(interface_class))
        return method
    return overrider

class cmd_vdb (vdb.command.command):
    """Show vdb status information, start vdb and call subcommands"""

    def __init__ (self):
        super ().__init__ ("vdb", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    @overrides
    def do_invoke (self, argv ):
        if( len(argv) > 0 ):
            if( argv[0] == "start" ):
                start()
                return
            vdb.subcommands.run_subcommand(argv)
            return
        print(f"vdb is loaded with the following modules: {enabled_modules.keys()}")
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
    sp: str = str(gdb.parameter("auto-load safe-path"))

    debugdir = str(gdb.parameter("debug-file-directory"))

    datadir = str(gdb.execute("show data-directory",False,True))
    datadir = datadir.split('"')[1]

    vdir = os.path.normpath(vdb_dir)

    sp=sp.replace("$datadir",datadir)
    sp=sp.replace("$debugdir",debugdir)

    vsp = sp.split(":")
    vsp.append(vdir)

    for p in vsp:
        p = os.path.normpath(p) + "/"
        if( pdir.startswith(p) ):
            return True
    return False

def load_init( vdb_init_file ):
    try:
        with open(vdb_init_file,"r") as f:
            vdb.config.execute(f.read(),vdb_init_file)
    except FileNotFoundError:
        pass

def load_plugins( plugindir ):
    try:
        oldpath = []
        oldpath += sys.path
        sys.path = [plugindir] + sys.path

        if( not is_in_safe_path(plugindir) ):
            return
        if( not os.path.isdir(plugindir) ):
            return

        vdb.util.log(f"Loading plugins in {plugindir}…", level=vdb.util.Loglevel.info)

        for pt in list(enabled_modules.keys()) + [ "plugins" ]:
            pdir = f"{plugindir}/{pt}/"
            if( os.path.isdir(pdir) ):
                for fn in filter( lambda x : x.endswith(".py"), os.listdir(pdir) ):
                    try:
                        vdb.util.log(f"Loading plugin {plugindir}/{pt}/{fn}", level=vdb.util.Loglevel.info)
                        importname = f"{pt}.{fn[:-3]}"
                        importlib.import_module(importname)
                    except ModuleNotFoundError as e:
                        vdb.util.log(f"Could not load plugin {plugindir}/{pt}/{fn}. {e}", level=vdb.util.Loglevel.warn)
                    except:
                        vdb.util.log(f"Error while loading plugin {plugindir}/{pt}/{fn}", level=vdb.util.Loglevel.error)
                        vdb.print_exc()
    except:
        vdb.print_exc()
    finally:
        sys.path = oldpath

def load_themes( vdbdir ):
    vdb.util.log(f"load_themes({vdbdir})", level=vdb.util.Loglevel.trace)
    if( len(theme.get()) == 0 ):
        vdb.util.log(f"Not loading any theme", level=vdb.util.Loglevel.info)
        return
    tdir = f"{vdbdir}/themes/"
    tfile = f"{tdir}{theme.value}.py"
    if( not os.path.isdir(tdir) ):
        return
    if( not is_in_safe_path(tdir) ):
        if( os.path.isfile(tfile) ):
            vdb.util.log(f"{tdir} is not in safe path, not loading {tfile} from there", level=vdb.util.Loglevel.warn)
        return
    if( not os.path.isfile(tfile) ):
        vdb.util.log(f"Theme file {tfile} not found, not loading any theme", level=vdb.util.Loglevel.warn)
        return

    vdb.util.log(f"Trying to load theme from {tfile}", level=vdb.util.Loglevel.info)
    try:
        oldpath = []
        oldpath += sys.path
        sys.path = [tdir] + sys.path
        importlib.import_module(theme.get())
    except ModuleNotFoundError as e:
        vdb.util.log(f"Could not load theme {theme.value}: {e}", level=vdb.util.Loglevel.error)
    except:
        vdb.print_exc()
    finally:
        sys.path = oldpath

def start( vdbd = None, vdbinit = None ):
    if( enable.value is False ):
        print("Not starting vdb, disabled by vdb-enable")
        return
    print("Starting vdb modules…")

    global texe
    texe = concurrent.futures.ThreadPoolExecutor(max_workers=max_threads.get(),thread_name_prefix="vdb")

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


    available_modules = configured_modules.get().split(",")
    special = { "list" }
    for mod in available_modules:
        try:
            bval = gdb.parameter( f"vdb-enable-{mod}")
            if( bval ):
                vdb.util.log(f"Loading module {mod}…",level=vdb.util.Loglevel.info)
                modname = mod
                if( mod in special ):
                    modname = f"_{mod}"
                lmod=importlib.import_module(f"vdb.{modname}")
                enabled_modules[mod] = lmod
            else:
                vdb.util.log(f"Skipping load of module {mod}…",level=vdb.util.Loglevel.warn)
        except ModuleNotFoundError as e:
            vdb.util.log(f"Could not load module {mod}. {e}", level=vdb.util.Loglevel.warn)
        except:
            ex = traceback.format_exc()
            vdb.util.log(f"Error loading module {str(mod)}:\n{ex}", level=vdb.util.Loglevel.error)

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
        cwd,_= os.path.split(cwd)


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


    for name,mod in enabled_modules.items():
        if( hasattr(mod,"start") ):
            print(f"Calling second stage start of {name}")
            mod.start()

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

def rich_theme( ts ):
    theme = {}
    for l in vdb.util.stripped_lines(ts):
        name,style = l.split(maxsplit=2)
        theme[name] = style
    if( len(theme) > 0 ):
        import rich.theme
        vdb.util.console = rich.console.Console( force_terminal = True, color_system = "truecolor", theme = rich.theme.Theme(theme) )


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
