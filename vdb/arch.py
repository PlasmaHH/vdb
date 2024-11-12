#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.event

import gdb
from typing import Dict

pointer_size = 0
pc_name = None

# A few shortcuts for types we commonly need
uintptr_t = None
void_t     = None
void_ptr_t = None
void_ptr_ptr_t = None



need_update = True
need_uint_update = True

@vdb.event.new_objfile()
@vdb.event.new_thread()
def reset_info():
    global need_update
    global need_uint_update
    need_update = True
    need_uint_update = True

uint_cache: Dict[int,gdb.Type] = {}
def uint( sz: int ) -> gdb.Type:
    global need_uint_update
    if( need_uint_update or len(uint_cache) == 0 ):
        for bits in [ 0,8,16,24,32,64,128 ]:
            try:
                ty=_active_arch.integer_type( bits, False )
                uint_cache[int(ty.sizeof)*8] = ty
            except gdb.error:
                pass
        need_uint_update = False
    return uint_cache.get(sz,None)

_active_arch_name = None
_active_arch = None

def active( ):
    return _active_arch

#@vdb.event.new_objfile()
def gather_info( ):
    now_arch = gdb.selected_inferior().architecture()
    global _active_arch_name
    global _active_arch
    # Nothing to be done here
    if( now_arch.name() == _active_arch_name ):
        return
    print(f"GATHERING UPDATED INFO ABOUT NEW ARCH {now_arch.name()}, replacing previous {_active_arch_name}")
    _active_arch_name = now_arch.name()
    _active_arch = now_arch

    global pointer_size
    pointer_size = gdb.lookup_type("void").pointer().sizeof*8

    global uintptr_t
    # not in all situations we have a proper uint ptr type available, so cycle through all of them until we find an
    # appropriate one
    uintptr_t = None
    try:
        xt = gdb.lookup_type("uintptr_t")
        if( xt.sizeof*8 == pointer_size ):
            uintptr_t = xt
    except gdb.error:
        pass
    # Not under this name, take an appropriately sized unsigned integer
    if( uintptr_t is None ):
        uintptr_t = uint(pointer_size)

    global void_t
    global void_ptr_t
    global void_ptr_ptr_t
    void_t     = gdb.lookup_type("void")
    void_ptr_t = void_t.pointer()
    void_ptr_ptr_t = void_ptr_t.pointer()

    # All we don't now about are "pc"
    pc_name = pc_name_map.get(_active_arch_name,"pc")
#    print("pointer_size = '%s'" % pointer_size )

pc_name_map = {
        "i386:x86-64" : "rip"
        }

def name( ):
    return _active_arch_name

def get_pc_name( ):
    return pc_name

@vdb.event.stop()
@vdb.event.before_prompt()
def maybe_gather_info():
    global need_update
    if( need_update ):
        gather_info()
        need_update = False

gather_info()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
