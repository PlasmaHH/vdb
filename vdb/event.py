#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

from enum import Enum,auto

class events(Enum):
    start = auto()
    run   = auto()

def on_event( gdbreg, darg ):
    def decorator( func ):
        def wrapper(*arg):
#            print("type(arg) = '%s'" % type(arg) )
#            print("type(darg) = '%s'" % type(darg) )
#            print("arg = '%s'" % (arg,) )
#            print("darg = '%s'" % (darg,) )
            try:
                func(*(arg+darg) )
            except Exception as a:
#                print("a = '%s'" % a )
                func(*darg)

        gdbreg.connect(wrapper)
        return func
    return decorator

hooks = {}

def register_hook( ev, f ):
    global hooks
    hl = hooks.setdefault(ev,[])
    hl.append(f)

def on_hook( ev, darg ):
    def decorator( func ):
        def wrapper(*arg):
#            print("type(arg) = '%s'" % type(arg) )
#            print("type(darg) = '%s'" % type(darg) )
#            print("arg = '%s'" % (arg,) )
#            print("darg = '%s'" % (darg,) )
            try:
                func(*(arg+darg) )
            except Exception as a:
#                print("a = '%s'" % a )
                func(*darg)

        register_hook(ev,wrapper)
        return func
    return decorator

def exec_hook( ev ):
    hl = hooks.get(ev,[])
    for h in hl:
        h(ev)

def stop( *darg ):
    return on_event( gdb.events.stop, darg )

def before_prompt( *darg ):
    return on_event( gdb.events.before_prompt, darg )

def new_objfile( *darg ):
    return on_event( gdb.events.new_objfile, darg )

def new_inferior( *darg ):
    return on_event( gdb.events.new_inferior, darg )

def new_thread( *darg ):
    return on_event( gdb.events.new_thread, darg )

def exited( *darg ):
    return on_event( gdb.events.exited, darg )

def run( *darg ):
    return on_hook( events.run, darg )

def start( *darg ):
    return on_hook( events.start, darg )

def run_hook():
    exec_hook(events.run)

def start_hook():
    exec_hook(events.start)

gdb.execute("""
define hook-run
    python vdb.event.run_hook()
end
define hook-start
    python vdb.event.start_hook()
end
""")

#@new_objfile()
#@new_inferior()
#@new_thread()
#def debug_event( *arg ):
#    print("DEBUG EVENT")
#    print("arg = '%s'" % (arg,) )
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
