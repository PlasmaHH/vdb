#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb
import vdb.config
import vdb.color
import vdb.vmmap
import vdb.util
import vdb.asm

import gdb

import string
import re
import math
import struct
from enum import Enum,auto

vdb.enabled_modules.append("pointer")

arrow_right = vdb.config.parameter("vdb-pointer-arrow-right", " → " )
arrow_left = vdb.config.parameter("vdb-pointer-arrow-left", " ←  " )
arrow_infinity = vdb.config.parameter("vdb-pointer-arrow-infinity", " ↔ " )

ellipsis = vdb.config.parameter("vdb-pointer-ellipsis", "…" )

min_ascii = vdb.config.parameter("vdb-pointer-min-ascii", 3 )
max_exponents = vdb.config.parameter("vdb-pointer-max-exponents", "-6,15", gdb_type = vdb.config.PARAM_ARRAY )


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

def as_c_str( ptr, maxlen = 64 ):
    c_str = bytearray()
#    rptr = ptr

    data = vdb.memory.read(int(ptr),maxlen)
    if( data is None ):
        return None

#    print("data = '%s'" % (data,) )
#    for i in range(0,maxlen):
    for b in data:
#        print("b = '%s'" % (b,) )
#        print("type(b) = '%s'" % (type(b),) )
#        b = read(rptr)
        if( b is None ):
            break
#        b = b[0]
#        print("type(b) = '%s'" % type(b) )
#        rptr += 1
        if( b == b'\x00' ):
            break
        ib = int.from_bytes(b,byteorder="little")
        if( ib == (0x7f & ib) ):
            if( b.decode("ascii") not in string.printable ):
                break
        c_str += b
    if( len(c_str) > 0 ):
        c_str = vdb.util.maybe_utf8(c_str)
        return c_str
    else:
        return None

def annotate( ptr ):
    try:
        mv=gdb.parse_and_eval("(void*)(%s)" % int(ptr) )
        mv = str(mv)
        pbs = mv.find("<")
        if( pbs != -1 ):
            mv = mv[pbs:]
            return mv
    except:
        pass
    return None

def dereference( ptr ):
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
    return (nptr,gvalue)


def escape_spaces( s ):
    s = s.replace("\\","\\\\")
    s = s.replace("\t","\\t")
    s = s.replace("\n","\\n")
    s = s.replace("\r","\\r")
    s = s.replace("\v","\\v")
    s = s.replace("\f","\\f")
    return s

# XXX move to util? pre-compile regex?
def printable_str( s ):
    l = len(s)
    ret = re.sub(f'[^{re.escape(string.printable)}]', '.', s)
#    ret = re.sub(f'[\t\n\r\v\f]', '.', ret)
    ret = escape_spaces(ret)
    return (ret,l)

def as_tailspec( ptr, minasc, spec ):
#    vdb.util.bark() # print("BARK")
#    print("ptr = '%x'" % (ptr,) )

    for sp in spec:
        if( sp == "a" ): # points to an ascii string
            s = as_c_str(ptr)
            if( s is not None ):
                if( len(s) >= minasc ):
                    s,l = printable_str(s)
                    return f"[{l}]'{s}'"
        elif( sp == "x" ): # points to executable memory
            at = vdb.memory.mmap.get_atype( ptr )
            if( at  == vdb.memory.access_type.ACCESS_EX ):
                return vdb.asm.get_single(ptr)
        elif( sp == "n" ): # points to a named object
            a = annotate(ptr)
            if( a is not None ):
                # The caller will already have properly formatted the pointer with colors and name, so we point to
                # really nothing, but since "None" means to chain more, lets try empty string here
                return ""
        elif( sp == "d"): # points to a double
#            print("ptr = '%s'" % (ptr,) )
            try: # might not point to anything valid
                gptr = gdb.Value(ptr)
#                print("gptr = '%s'" % (gptr,) )
                dptr = gptr.cast(gdb.lookup_type("double").pointer())
#                print("dptr = '%s'" % (dptr,) )
                dvalue = dptr.dereference()
                if( math.isnan(dvalue) ):
                    continue
                if( dvalue == 0 ): # all 0 bytes result in this, most likely a false positive
                    continue
#                print("dvalue = '%s'" % (dvalue,) )
                m,e = math.frexp( dvalue )
#                print("m = '%s'" % (m,) )
#                print("e = '%s'" % (e,) )
                if( e >= max_exponents.elements[0] and e <= max_exponents.elements[1] ):
                    return f"(double){dvalue}"
            except:
                pass
        elif( sp == "D"): # Is itself possible a double value
            try:
                ba = struct.pack("q",int(ptr))
                dv = struct.unpack("d",ba)
                m,e = math.frexp( dv )
                if( e >= max_exponents.elements[0] and e <= max_exponents.elements[1] ):
                    return f"(double){dv}"
            except:
                pass
        else:
            # for convenienve just ignore them for now
            pass
    print(f"No idea what {int(ptr):#0x} points to really...")
    return None


def as_tail( ptr, minasc ):
    return as_tailspec( ptr, minasc, "ax" )

def color( ptr, archsize ):
    """Colorize the pointer according to the currently known memory situation"""

    ptr=vdb.util.xint(ptr)
    plen = archsize // 4
#    t,additional = get_type(ptr,archsize)

    s,mm,col,additional = vdb.memory.mmap.color(ptr,colorspec="Asma")
#    scolor = colormap.get(t,color_unknown)

    if( mm.mtype == vdb.memory.memory_type.NULL ):
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
        ret,rl = vdb.color.colorl("0x" + ps0,col)
        ret += ps1
        rl += len(ps1)
    else:
#        print("ptr = '%s'" % ptr )
#        print("plen = '%s'" % plen )
#        print("type(ptr) = '%s'" % type(ptr) )
        ret,rl = vdb.color.colorl(f"0x{ptr:0{plen}x}",col)
#    return ( ret, additional )
    return ( ret, additional, col, mm, rl )

def chain( ptr, archsize, maxlen = 8, test_for_ascii = True, minascii = None, last = True, tailspec = None ):
    if( gdb_void == None ):
        update_types()
    if( maxlen == 0 ):
        return (ellipsis.value,True)

#    print("chain(0x%x,…)" % ptr )
#    print("type(ptr) = '%s'" % type(ptr) )
    ret,add,_,_,_ = color(ptr,archsize)
    pure = True

    an = annotate( ptr )
    plen = archsize // 4
    plen += 4
    if( an ):
        ret += f" {an:<{plen}}"
        pure = False
    if( minascii is None ):
        minascii = min_ascii.value
    if( tailspec is not None ):
        s = as_tailspec( ptr, minascii, tailspec )
    else:
        s = as_tail(ptr, minascii)
    if( s is not None ):
        if( len(s) > 0 ):
            ret += f"{arrow_right.value}{s}"
        pure = False
        return (ret,pure)
    if( add is not None and test_for_ascii ):
        ascstring = add[1]
        ascstring = escape_spaces(ascstring)
        pure = False
        ret += f"   {ascstring}"
    try:
        nptr,gvalue = dereference( ptr )
        if( nptr == gvalue ):
            ret += arrow_infinity.value + color(gvalue,archsize)[0]
        else:
#        print("gvalue = '%s'" % gvalue )
            if( not last and maxlen == 1):
                pass
            else:
                ret += arrow_right.value + chain(gvalue,archsize,maxlen-1,tailspec=tailspec)[0]
        pure = False
    except gdb.MemoryError as e:
#        print("e = '%s'" % e )
        pass
    except:
        raise
    return (ret,pure)




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
