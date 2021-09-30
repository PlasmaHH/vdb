#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command

import gdb

import re
import os
import traceback
import subprocess
import tempfile
import time

ctags_cmd = vdb.config.parameter("vdb-types-ctags-cmd", "ctags" )
ctags_parameters = vdb.config.parameter("vdb-types-ctags-parameters","--extra=+q -f - --sort=no -R")

ctags_dirs = vdb.config.parameter("vdb-types-ctags-files","/usr/include/", on_set  = vdb.config.set_array_elements )
#ctags_dirs = vdb.config.parameter("vdb-types-ctags-files","test.h", on_set  = vdb.config.set_array_elements )
ctags_cache = vdb.config.parameter("vdb-types-cache",True)
ctags_cache_age = vdb.config.parameter("vdb-types-cache-max-age", 86400 )

type_locations = {}
cache_timestamp = 0

rl_thread = None

def load_caches( ):
    if( ctags_cache.value is None ):
        return
    import pickle
    global type_locations
    global cache_timestamp
    fn = vdb.vdb_dir + "/cache/type_locations"
    if( not os.path.exists(fn) ):
        print(f"Skipping to load type_locations cache, {fn} does not exist")
    else:
        tl = pickle.load( open( fn, "rb" ) )
        type_locations,cache_timestamp = tl
    if( time.time() > ( cache_timestamp + ctags_cache_age.value ) ):
        global rl_thread
        rl_thread = vdb.texe.submit(progress_refresh_locations)
        print(f"Cache is {time.time() - cache_timestamp}s old, refreshing")
    else:
        print(f"Cache is {time.time() - cache_timestamp}s old, no need to refresh")


def save_caches( ):
    fn = vdb.vdb_dir + "/cache/type_locations"
    fdir = os.path.dirname(fn)
    os.makedirs(fdir,exist_ok = True)
    global cache_timestamp
    cache_timestamp = time.time()
    import pickle
    pickle.dump( (type_locations,cache_timestamp),open(fn,"wb+"))
    traceback.print_exc()

# only to be set to true on process exit
stop_refreshing = False
ctags = None

@vdb.event.gdb_exiting()
def abort_refresh_locations( ):
    global stop_refreshing
#    print("Setting to true")
    stop_refreshing = True
    if( ctags is not None ):
        ctags.terminate()

"""
search all include dirs (system and extra configured) for types. cache that. maybe later do that in a thread when loading and if the command is used before thats finished wait for it to do?
"""
ctags_progress = None

def get_progress_refresh_locations( ):
    return ctags_progress

def progress_refresh_locations( ):
    vdb.prompt.add_progress( get_progress_refresh_locations )
    global ctags_progress
    global ctags
    try:
        ctags_progress = "[ ctags #/# ]"
        refresh_locations()
    except:
        pass
    finally:
        ctags_progress = None
        ctags = None


def set_progress( c, tc, l ):
    global ctags_progress
    if( l is not None ):
        ctags_progress = f"[ ctags {c}/{tc} {l} ]"
    else:
        ctags_progress = f"[ ctags {c}/{tc} … ]"

def refresh_locations( ):
    print("ctags_dirs.elements = '%s'" % (ctags_dirs.elements,) )
    ccnt = 0
    for d in ctags_dirs.elements:
        set_progress( ccnt, len(ctags_dirs.elements), None )
        ccnt += 1
        cmd = [ ctags_cmd.value ] + ctags_parameters.value.split() + [d]
        print("cmd = '%s'" % (" ".join(cmd),) )

        type_tags = set( [ "t","s","c","u" ] )
#        tags = subprocess.che suoutput( cmd )
        global ctags
        ctags = subprocess.Popen( cmd, stdout=subprocess.PIPE )

        tlo = {}

#        print("Waiting on ctags output...")
        lcnt = 0
#        f4cnt = {}
        for line in ctags.stdout:
            lcnt += 1
            set_progress( ccnt, len(ctags_dirs.elements), lcnt )

#            print("line = '%s'" % (line,) )
            if( stop_refreshing ):
                print("Aborting background type location refresh")
                return None
#            else:
#                print(".",end="",flush=True)
            line = line.decode("utf-8")
            line = line[:-1]
            comp = line.split(';"')
#            print("comp = '%s'" % (comp,) )
            fields = []
            fields += comp[0].split("\t",1) + comp[1].split("\t") + [None]*3
            if( len(fields[3]) != 1 ):
                print("line = '%s'" % (line,) )
                print("fields = '%s'" % (fields,) )
                continue
#            f4cnt[fields[3]] = f4cnt.get( fields[3],0) + 1
            if fields[3] not in type_tags:
                continue

            ns = fields[4]
            tr = None
            if fields[3] == "t" :
                tr = ns
                ns = None
#                print("fields = '%s'" % (fields,) )
                if fields[5] is not None:
                    if( fields[0].find(":") == -1 ):
                        continue
            else:
                if( fields[4] is not None ):
                    if( fields[0].find(":") == -1 ):
                        continue
            file=fields[1].split()[0]

            tlo[ fields[0] ] = file

#            print(f"identifier={fields[0]} file={file} namespace={ns} typeref={tr}")
#        for k,v in f4cnt.items():
#            print(f"{k} : {v}")
    global type_locations
    type_locations = tlo
    print("Background type location refresh finished")
    save_caches()

def compile( code ):
    cxx = tempfile.NamedTemporaryFile( suffix = ".cpp" )
    cxx.write(code.encode("utf-8"))
    cxx.flush()
#    print("cxx.name = '%s'" % (cxx.name,) )
    subprocess.check_output( f"cat {cxx.name}",shell = True)
    subprocess.check_output( f"g++ -I. -w -std=gnu++2b -g -ggdb3 -c {cxx.name} -o {cxx.name}.o", shell = True )
#    subprocess.check_output( f"gcc -w -std=gnu++2b -g -ggdb3 -c {cxx.name} -o {cxx.name}.o", shell = True )
    gdb.execute( f"add-symbol-file {cxx.name}.o 0", from_tty = False, to_string = True )

def do_load( argv ):
    global type_locations
    if( len(argv) < 1 ):
        print("load needs at least a type argument to load")
        return
    tname = argv[0]
    if( len(argv) > 1 ):
        fn = argv[1]
    else:
        fn = type_locations.get(tname,None)
        if( fn is None ):
            print(f"Sorry, unable to find {argv[0]} in the type cache")
            return
#    print("fn = '%s'" % (fn,) )
    
    compile(f"""
    #include "{fn}"
    extern {tname} varx;
    {tname} var;
    void __vdb_injector( {tname}* var ) {{ }}
    """)
    print(f"Loaded type info for symbol {tname}")

def do_create( argv ):
    tname = argv[0]
    code = " ".join(argv[1:])
    compile(f"""
    {code}

    extern {tname} varx;
    {tname} var;
    void __vdb_injector( {tname}* var ) {{ }}
    """)
    print(f"Loaded type info for symbol {tname}")
    
class cmd_types (vdb.command.command):
    """Introduce new types into the currently debugged process
  types <subcommand> <parameter>
  
  Available subcommands are:

  create    - create a new type from scratch. Basically compiles the given code for the type name to be loaded.
  load      - load an existing type from a header. Header can be optionally specified.
    """

    def __init__ (self):
        super (cmd_types, self).__init__ ("types", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            if( len(argv) > 0 ):
                if( argv[0] == "create" ):
                    do_create(argv[1:])
                if( argv[0] == "load" ):
                    do_load(argv[1:])

            else:
                raise Exception("types got %s arguments, expecting 1 or more" % len(argv) )



        except:
            traceback.print_exc()
            raise
            pass

cmd_types()
load_caches()



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
