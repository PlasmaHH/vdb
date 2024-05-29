#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

from enum import Enum,auto
from typing import Dict,List,Callable

class events(Enum):
    start = auto()
    run   = auto()
    first_prompt = auto()
    step = auto()

def on_event( gdbreg, darg ):
    def decorator( func ):
        def wrapper(*arg):
#            print("type(arg) = '%s'" % type(arg) )
#            print("type(darg) = '%s'" % type(darg) )
#            print("arg = '%s'" % (arg,) )
#            print("darg = '%s'" % (darg,) )
            try:
                func(*(arg+darg) )
            except TypeError:
#                print("a = '%s'" % a )
                func(*darg)

        gdbreg.connect(wrapper)
        return func
    return decorator

def on_noop( _darg ):
    def decorator( func ):
        def wrapper(*_arg):
            pass
        return func
    return decorator

hooks : Dict[ events, List ] = {}

def register_hook( ev: events, f: Callable ):
#    print(f"register_hook({ev=},{f=})")
    hl = hooks.setdefault(ev,[])
    hl.append(f)

def on_hook( ev, darg ):
#    print(f"on_hook({ev},{darg})")
    def decorator( func ):
        def wrapper(*arg):
#            print("type(arg) = '%s'" % type(arg) )
#            print("type(darg) = '%s'" % type(darg) )
#            print("arg = '%s'" % (arg,) )
#            print("darg = '%s'" % (darg,) )
            try:
                func(*(arg+darg) )
            except TypeError:
#                print("a = '%s'" % a )
                func(*darg)

        register_hook(ev,wrapper)
        return func
    return decorator

def exec_hook( ev ):
    if( isinstance(ev,str) ):
        ev = events[ev]
    hl = hooks.get(ev,[])
#    print(f"exec_hook({ev}) : {len(hl)}")
#    print(f"{hooks=}")
    for h in hl:
        h(ev)


# Decorators to call the decorated function

# First gdb standard events in the order they appear in the documentation
def cont( *darg ):
    return on_event( gdb.events.cont, darg )

def exited( *darg ):
    return on_event( gdb.events.exited, darg )

def stop( *darg ):
    return on_event( gdb.events.stop, darg )

def new_objfile( *darg ):
    return on_event( gdb.events.new_objfile, darg )

def free_objfile( *darg ):
    return on_event( gdb.events.free_objfile, darg )

def clear_objfiles( *darg ):
    return on_event( gdb.events.clear_objfiles, darg )

def inferior_call( *darg ):
    return on_event( gdb.events.inferior_call, darg )

def memory_changed( *darg ):
    return on_event( gdb.events.memory_changed, darg )

def register_changed( *darg ):
    return on_event( gdb.events.register_changed, darg )

def breakpoint_created( *darg ):
    return on_event( gdb.events.breakpoint_created, darg )

def breakpoint_modified( *darg ):
    return on_event( gdb.events.breakpoint_modified, darg )

def breakpoint_deleted( *darg ):
    return on_event( gdb.events.breakpoint_deleted, darg )

def before_prompt( *darg ):
    return on_event( gdb.events.before_prompt, darg )

def new_inferior( *darg ):
    return on_event( gdb.events.new_inferior, darg )

def inferior_deleted( *darg ):
    return on_event( gdb.events.inferior_deleted, darg )

def new_thread( *darg ):
    return on_event( gdb.events.new_thread, darg )

def thread_exited( *darg ):
    return on_event( gdb.events.thread_exited, darg )

def gdb_exiting( *darg ):
    try:
        return on_event( gdb.events.gdb_exiting, darg )
    # Only supported since gdb 12, silently ignore otherwise
    except:
        return on_noop( darg )

def connection_removed( *darg ):
    return on_event( gdb.events.connection_removed, darg )

def executable_changed( *darg ):
    return on_event( gdb.events.executable_changed, darg )

def new_progspace( *darg ):
    return on_event( gdb.events.new_progspace, darg )

def free_progspace( *darg ):
    return on_event( gdb.events.free_progspace, darg )



# Events not natively available in python, emulated through gdbscript hooks

def run( *darg ):
    return on_hook( events.run, darg )

def start( *darg ):
    return on_hook( events.start, darg )

# Our own event

def before_first_prompt( *darg ):
    return on_hook( events.first_prompt, darg )


# Functions to be called from generated gdbscript to get events into python

def run_hook():
    exec_hook(events.run)

def start_hook():
    exec_hook(events.start)


eventlist = ["cont", "exited", "stop", "new_objfile", "free_objfile", "clear_objfiles", "inferior_call", "memory_changed", "register_changed", "breakpoint_created", "breakpoint_modified", "breakpoint_deleted", "before_prompt", "new_inferior", "inferior_deleted", "new_thread", "thread_exited", "gdb_exiting", "connection_removed", "executable_changed", "new_progspace", "free_progspace", "run", "start", "before_first_prompt", "step" ]

# generic event mechanism (not a decorator)
# @param eventname a string with the name
# @param callback a callable that gets the eventname, gdb event issued arguments and darg
def on( eventname, callback, *darg ):
#    print(f"on({eventname=},{callback=},{darg=})")
    def wrapper(*arg):
        try:
            callback(*(arg+darg) )
        except TypeError:
            callback(*darg)


    if( eventname in [ "run", "start", "before_first_prompt", "step" ] ):
        register_hook( events[eventname], wrapper )
    elif( eventname in eventlist and hasattr(gdb.events,eventname) ):
        ge=getattr(gdb.events,eventname)
        ge.connect(wrapper)
    else:
        raise RuntimeError(f"Unknown event name {eventname}")


# Install gdbscript hooks for run and start. Those are not available natively in python

gdb.execute("""
define hook-run
    python vdb.event.run_hook()
end
define hook-start
    python vdb.event.start_hook()
end
""")

# The function responsible to emit the first prompt event
def first_prompt_handler( ):
#    print("first_prompt_handler")
    exec_hook(events.first_prompt)
    gdb.events.before_prompt.disconnect(first_prompt_handler)
gdb.events.before_prompt.connect(first_prompt_handler)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
