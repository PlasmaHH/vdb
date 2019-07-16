#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.event

import gdb

pointer_size = 0
gdb_uintptr_t = None

@vdb.event.new_objfile()
def gather_info( ):
    global pointer_size
    pointer_size = gdb.lookup_type("void").pointer().sizeof*8

    global gdb_uintptr_t
    # not in all situations we have a proper uint ptr type available, so cycle through all of them until we find an
    # appropriate one
    gdb_uintptr_t = None
    for ct in [ "uintptr_t", "unsigned short", "unsigned", "unsigned long","unsigned long long" ]:
        try:
            xt = gdb.lookup_type(ct)
            if( xt.sizeof*8 == pointer_size ):
                gdb_uintptr_t = xt
#                print(f"Chosing {ct} for uintptr_t")
                break
        except:
            pass
#    print("pointer_size = '%s'" % pointer_size )


gather_info()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
