#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.config
import vdb.color

import gdb

import string
from enum import Enum,auto


color_nullpage      = vdb.config.parameter("vdb-pointer-colors-nullpage",      "#f33",        gdb_type = vdb.config.PARAM_COLOUR)
color_unknown       = vdb.config.parameter("vdb-pointer-colors-unknown",       ",,underline", gdb_type = vdb.config.PARAM_COLOUR)
color_ascii         = vdb.config.parameter("vdb-pointer-colors-ascii",         "#aa0",        gdb_type = vdb.config.PARAM_COLOUR)

color_own_stack     = vdb.config.parameter("vdb-pointer-colors-stack-own",     "#050",        gdb_type = vdb.config.PARAM_COLOUR)
color_foreign_stack = vdb.config.parameter("vdb-pointer-colors-stack-foreign", "#a50",        gdb_type = vdb.config.PARAM_COLOUR)
color_heap          = vdb.config.parameter("vdb-pointer-colors-heap",          "#55b",        gdb_type = vdb.config.PARAM_COLOUR)
color_mmap          = vdb.config.parameter("vdb-pointer-colors-mmap",          "#11c",        gdb_type = vdb.config.PARAM_COLOUR)
color_code          = vdb.config.parameter("vdb-pointer-colors-code",          "#909",        gdb_type = vdb.config.PARAM_COLOUR)
color_bss           = vdb.config.parameter("vdb-pointer-colors-bss",           "#508",        gdb_type = vdb.config.PARAM_COLOUR)

arrow_right = vdb.config.parameter("vdb-pointer-arrow-right", " → " )
arrow_left = vdb.config.parameter("vdb-pointer-arrow-left", " ←  " )

class memory_type(Enum):
    OWN_STACK     = auto()
    FOREIGN_STACK = auto()
    HEAP          = auto()
    MMAP          = auto()
    CODE          = auto()
    BSS           = auto()
    ASCII         = auto()
    NULL          = auto()
    UNKNOWN       = auto()


def get_type( ptr, archsize ):
    if( ptr < 0x1000 ):
        return memory_type.NULL
    else:
#        print("ptr = '%s'" % ptr )
#        print("ptr = '%x'" % ptr )
        aptr = ptr
        ascii=True
        plen = archsize // 4
        for i in range(0,plen//2):
            b = aptr & 0xFF
#            print("b = 0x%02x" % b )
            b = chr(b)
            if( b == 0 and i == (plen//2)-1 ):
                break
            if( b not in string.printable ):
#                print("NOT PRINTABLE")
                ascii = False
                break
#            else:
#                print("PRINTABLE")
            aptr = aptr >> 8
#        print("ascii = '%s'" % ascii )
        if( ascii ):
            return memory_type.ASCII
    return memory_type.UNKNOWN

colormap = {
    memory_type.OWN_STACK     : color_own_stack,
    memory_type.FOREIGN_STACK : color_foreign_stack,
    memory_type.HEAP          : color_heap,
    memory_type.MMAP          : color_mmap,
    memory_type.CODE          : color_code,
    memory_type.BSS           : color_bss,
    memory_type.ASCII         : color_ascii,
    memory_type.NULL          : color_nullpage,
    memory_type.UNKNOWN       : color_unknown,
        }

gdb_void     = None
gdb_void_ptr = None
gdb_void_ptr_ptr = None

def update_types( ):
    global gdb_void
    global gdb_void_ptr
    global gdb_void_ptr_ptr
    gdb_void     = gdb.lookup_type("void")
    gdb_void_ptr = gdb_void.pointer()
    gdb_void_ptr_ptr = gdb_void_ptr.pointer()


def color( ptr, archsize ):
    """Colorize the pointer according to the currently known memory situation"""
    ptr=int(ptr)
    plen = archsize // 4
    t = get_type(ptr,archsize)
    scolor = colormap.get(t,color_unknown)

    if( t == memory_type.NULL ):
        ps = f"{ptr:0{plen}x}"
        ps0 = ""
        ps1 = ""
        rest=False
        for p in ps:
            if( rest or p != "0" ):
                ps1 += p
                rest = True
            else:
                ps0 += p
        ret = vdb.color.color("0x" + ps0,scolor.value) + ps1
    else:
        print("ptr %x of type %s" % (ptr,t))
        ret = vdb.color.color(f"0x{ptr:0{plen}x}",scolor.value)
    return ret

def chain( ptr, archsize ):
    if( gdb_void == None ):
        update_types()

#    print("chain(0x%x,…)" % ptr )
#    print("type(ptr) = '%s'" % type(ptr) )
    ret = color(ptr,archsize)
    try:
        gptr = gdb.Value(ptr)
#        print("gptr = '%s'" % gptr )
#        print("gptr.type = '%s'" % gptr.type )
#        xptr = gptr.cast(gdb_void_ptr)
        xptr = gptr.cast(gdb.lookup_type("void").pointer())
#        print("xptr = '%s'" % xptr )
#        print("xptr.type = '%s'" % xptr.type )
        xptr = gptr.cast(gdb_void_ptr)
#        print("xptr = '%s'" % xptr )
#        print("xptr.type = '%s'" % xptr.type )
        nptr = gptr.cast(gdb_void_ptr_ptr)
#        print("nptr = '%s'" % nptr )
        gvalue = nptr.dereference()
#        print("gvalue = '%s'" % gvalue )
        ret += arrow_right.value + chain(gvalue,archsize)
    except gdb.MemoryError as e:
#        print("e = '%s'" % e )
        pass
    except:
        raise
    return ret




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
