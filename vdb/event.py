#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

def on_event( gdbreg, darg ):
    def decorator( func ):
        def wrapper(*arg):
            func(*darg)

        gdbreg.connect(wrapper)
        return func
    return decorator


def stop( *darg ):
    return on_event( gdb.events.stop, darg )

def before_prompt( *darg ):
    return on_event( gdb.events.before_prompt, darg )

def new_objfile( *darg ):
    return on_event( gdb.events.new_objfile, darg )


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
