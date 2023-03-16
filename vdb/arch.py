#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.event

import gdb

pointer_size = 0
gdb_uintptr_t = None
need_update = True
need_uint_update = True

@vdb.event.new_objfile()
@vdb.event.new_thread()
def reset_info():
    global need_update
    global need_uint_update
    need_update = True
    need_uint_update = True

uint_cache = {}
def uint( sz ):
    global uint_cache
    global need_uint_update
    if( need_uint_update or len(uint_cache) == 0 ):
        for t in [ "uint8_t", "uint16_t", "uint32_t", "uint64_t", "uint128_t", "unsigned char", "unsigned short", "unsigned", "unsigned long", "unsigned long long" ]:
            try:
                ty=gdb.lookup_type(t)
                uint_cache[int(ty.sizeof)*8] = ty
            except gdb.error as e:
                pass
        need_uint_update = False
    return uint_cache.get(sz,None)

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
                break
        except:
            pass
#    print("pointer_size = '%s'" % pointer_size )

@vdb.event.stop()
@vdb.event.before_prompt()
def maybe_gather_info():
    global need_update
    if( need_update ):
        gather_info()
        need_update = False

gather_info()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
