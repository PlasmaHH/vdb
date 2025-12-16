#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.event

import gdb
import rich
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
need_sint_update = True

@vdb.event.new_objfile()
@vdb.event.new_thread()
def reset_info( _ev = None ):
    global need_update
    global need_uint_update
    global need_sint_update
    need_update = True
    need_uint_update = True
    need_sint_update = True

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

sint_cache: Dict[int,gdb.Type] = {}
def sint( sz: int ) -> gdb.Type:
    global need_sint_update
    if( need_sint_update or len(sint_cache) == 0 ):
        for bits in [ 0,8,16,24,32,64,128 ]:
            try:
                ty=_active_arch.integer_type( bits, True )
                sint_cache[int(ty.sizeof)*8] = ty
            except gdb.error:
                pass
        need_sint_update = False
    return sint_cache.get(sz,None)


_active_arch_name = None
_active_arch = None

def active( ):
    return _active_arch

@vdb.event.new_objfile()
def gather_info( _ev = None ):
    try:
#        print(f"{gdb.selected_frame()=}")
#        print(f"{id(gdb.selected_frame())=}")
#        print(f"{id(gdb.selected_frame())=}")
        now_arch = gdb.selected_frame().architecture()
#        print("NOW ARCH IS FRAME")
    except gdb.error:
        now_arch = gdb.selected_inferior().architecture()
#        print("NOW ARCH IS INFERORI")
    global _active_arch_name
    global _active_arch
    # Nothing to be done here
    shortcut = False
    if( now_arch.name() == _active_arch_name ):
        shortcut = True
#    print(f"GATHERING UPDATED INFO ABOUT NEW ARCH {now_arch.name()}, replacing previous {_active_arch_name}")

    # These must be set to match the object from gdb.selected_frame.architecture()
    _active_arch_name = now_arch.name()
    _active_arch = now_arch

    if( shortcut ):
        return
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
    global pc_name
    pc_name = pc_name_map.get(_active_arch_name,"pc")
#    print(f"Setting {pc_name=}")
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
def maybe_gather_info( _ev = None ):
    global need_update
    if( need_update ):
        gather_info()
        need_update = False

gather_info()

def info( ):
    table = rich.table.Table(
            "Member",
            "Value",
            "Bits",
            "Comment"
            )
    table.add_row( "pointer_size", str(pointer_size), "", "Default register size too" )
    table.add_row( "pc_name", pc_name, "", "Instruction pointer register name" )
    table.add_row( "void_t", void_t.name, "", "gdb.Type" )
    table.add_row( "uintptr_t", str(uintptr_t.strip_typedefs()), str(8*uintptr_t.sizeof), "gdb.Type" )
    table.add_row( "void_ptr_t", str(void_ptr_t), str(8*void_ptr_t.sizeof), "gdb.Type" )
    table.add_row( "void_ptr_ptr_t", str(void_ptr_ptr_t), str(8*void_ptr_ptr_t.sizeof), "gdb.Type" )

    # Cause caches to possibly update
    sint(0)
    uint(0)

    for bits,t in uint_cache.items():
        tc = vdb.util.gdb_type_code(t.code)
        table.add_row( f"uint{bits}_t", str(t.strip_typedefs()), str(8*t.sizeof), f"Accessible via vdb.arch.uint({bits})")
    for bits,t in sint_cache.items():
        tc = vdb.util.gdb_type_code(t.code)
        table.add_row( f"sint{bits}_t", str(t.strip_typedefs()), str(8*t.sizeof), f"Accessible via vdb.arch.sint({bits})")

    table.add_row( "name()", name(), "", "Active arch name" )
    table.add_row( "active()", str(active()), "", "Active arch gdb.Architecture object")

    vdb.util.console.print(table)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
