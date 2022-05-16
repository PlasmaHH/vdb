#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.util
import vdb.arch
import vdb

import gdb
import intervaltree

import traceback
import colors
import re
import bisect
from enum import Enum,auto
import time




vdb.enabled_modules.append("memory")
# Color concept:
# - first more generic colours like for stack/heap/etc.
# - then if there is none, use the more specific ones for sections
# - if there still is none, at least check if they are rw/ro/wo/ex

# generic colors
color_nullpage      = vdb.config.parameter("vdb-memory-colors-nullpage",      "#f33",        gdb_type = vdb.config.PARAM_COLOUR)
color_unknown       = vdb.config.parameter("vdb-memory-colors-unknown",       ",,underline", gdb_type = vdb.config.PARAM_COLOUR,
                    docstring = "Colour to use for memory representations when the access is unkonwn %s")

color_ascii         = vdb.config.parameter("vdb-memory-colors-ascii",         "#aa0",        gdb_type = vdb.config.PARAM_COLOUR)
color_own_stack     = vdb.config.parameter("vdb-memory-colors-stack-own",     "#070",        gdb_type = vdb.config.PARAM_COLOUR)
color_foreign_stack = vdb.config.parameter("vdb-memory-colors-stack-foreign", "#f70",        gdb_type = vdb.config.PARAM_COLOUR)
color_heap          = vdb.config.parameter("vdb-memory-colors-heap",          "#55b",        gdb_type = vdb.config.PARAM_COLOUR)
color_mmap          = vdb.config.parameter("vdb-memory-colors-mmap",          "#11c",        gdb_type = vdb.config.PARAM_COLOUR)
color_shm          = vdb.config.parameter("vdb-memory-colors-shared",          "#15c",        gdb_type = vdb.config.PARAM_COLOUR)
color_code          = vdb.config.parameter("vdb-memory-colors-code",          "#a0a",        gdb_type = vdb.config.PARAM_COLOUR)
color_bss           = vdb.config.parameter("vdb-memory-colors-bss",           "#609",        gdb_type = vdb.config.PARAM_COLOUR)

color_ro = vdb.config.parameter("vdb-memory-colors-readonly"    , "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_wo = vdb.config.parameter("vdb-memory-colors-writeonly"   , "#ff5", gdb_type = vdb.config.PARAM_COLOUR)
color_rw = vdb.config.parameter("vdb-memory-colors-readwrite"   , "", gdb_type = vdb.config.PARAM_COLOUR)
color_ex = vdb.config.parameter("vdb-memory-colors-executable"  , "#d4f", gdb_type = vdb.config.PARAM_COLOUR)
color_in = vdb.config.parameter("vdb-memory-colors-inaccessible", "#f33", gdb_type = vdb.config.PARAM_COLOUR)
color_iv = vdb.config.parameter("vdb-memory-colors-invalid"     , "#16f", gdb_type = vdb.config.PARAM_COLOUR)

ignore_empty = vdb.config.parameter("vdb-memory-ignore-empty-sections", False, gdb_type = gdb.PARAM_BOOLEAN )

test_write = vdb.config.parameter("vdb-memory-test-write-access", True )
default_colorspec = vdb.config.parameter("vdb-memory-default-colorspec","sma")


class access_type(Enum):
    ACCESS_RO = auto()
    ACCESS_WO = auto()
    ACCESS_RW = auto()
    ACCESS_EX = auto()
    ACCESS_INV = auto()
    ACCESS_INACCESSIBLE = auto()
    ACCESS_UNKNOWN = auto()

access_colors = {
        access_type.ACCESS_RO : color_ro,
        access_type.ACCESS_WO : color_wo,
        access_type.ACCESS_RW : color_rw,
        access_type.ACCESS_EX : color_ex,
        access_type.ACCESS_INACCESSIBLE : color_in,
        access_type.ACCESS_INV : color_iv,
        access_type.ACCESS_UNKNOWN : color_unknown,
        }



class memory_type(Enum):
    OWN_STACK     = auto()
    FOREIGN_STACK = auto()
    HEAP          = auto()
    MMAP          = auto()
    SHM        = auto()
    CODE          = auto()
    BSS           = auto()
    ASCII         = auto()
    NULL          = auto()
    UNKNOWN       = auto()

colormap = {
    memory_type.OWN_STACK     : color_own_stack,
    memory_type.FOREIGN_STACK : color_foreign_stack,
    memory_type.HEAP          : color_heap,
    memory_type.MMAP          : color_mmap,
    memory_type.SHM        : color_shm,
    memory_type.CODE          : color_code,
    memory_type.BSS           : color_bss,
    memory_type.ASCII         : color_ascii,
    memory_type.NULL          : color_nullpage,
    memory_type.UNKNOWN       : color_unknown,
        }




"""

 0 .interp       0000001c  00000000004002e0  00000000004002e0  000002e0  2**0
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  1 .note.ABI-tag 00000020  00000000004002fc  00000000004002fc  000002fc  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  2 .hash         0000089c  0000000000400320  0000000000400320  00000320  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  3 .gnu.hash     00000060  0000000000400bc0  0000000000400bc0  00000bc0  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  4 .dynsym       00001ad0  0000000000400c20  0000000000400c20  00000c20  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  5 .dynstr       00000b82  00000000004026f0  00000000004026f0  000026f0  2**0
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  6 .gnu.version  0000023c  0000000000403272  0000000000403272  00003272  2**1
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  7 .gnu.version_r 00000130  00000000004034b0  00000000004034b0  000034b0  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  8 .rela.dyn     00000120  00000000004035e0  00000000004035e0  000035e0  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  9 .rela.plt     00001998  0000000000403700  0000000000403700  00003700  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 10 .init         00000017  0000000000406000  0000000000406000  00006000  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
 11 .plt          00001120  0000000000406020  0000000000406020  00006020  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
 12 .text         0052835c  0000000000407140  0000000000407140  00007140  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
 13 .fini         00000009  000000000092f49c  000000000092f49c  0052f49c  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
 14 .rodata       001b5e10  0000000000930000  0000000000930000  00530000  2**5
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 15 .stapsdt.base 00000001  0000000000ae5e10  0000000000ae5e10  006e5e10  2**0
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 16 .eh_frame_hdr 0001f7dc  0000000000ae5e14  0000000000ae5e14  006e5e14  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 17 .eh_frame     000a8820  0000000000b055f0  0000000000b055f0  007055f0  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 18 .gcc_except_table 00071a2c  0000000000bade10  0000000000bade10  007ade10  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 19 .tdata        00000005  0000000000c21530  0000000000c21530  00820530  2**4
                  CONTENTS, ALLOC, LOAD, DATA, THREAD_LOCAL
 20 .tbss         000063c8  0000000000c21540  0000000000c21540  00820535  2**4
                  ALLOC, THREAD_LOCAL
 21 .init_array   00000278  0000000000c21540  0000000000c21540  00820540  2**3
                  CONTENTS, ALLOC, LOAD, DATA
 22 .fini_array   00000008  0000000000c217b8  0000000000c217b8  008207b8  2**3
                  CONTENTS, ALLOC, LOAD, DATA
 23 .data.rel.ro  00008008  0000000000c217c0  0000000000c217c0  008207c0  2**5
                  CONTENTS, ALLOC, LOAD, DATA
 24 .dynamic      00000230  0000000000c297c8  0000000000c297c8  008287c8  2**3
                  CONTENTS, ALLOC, LOAD, DATA
 25 .got          000005f0  0000000000c299f8  0000000000c299f8  008289f8  2**3
                  CONTENTS, ALLOC, LOAD, DATA
 26 .got.plt      000008a0  0000000000c2a000  0000000000c2a000  00829000  2**3
                  CONTENTS, ALLOC, LOAD, DATA
 27 .data         0002b068  0000000000c2a8a0  0000000000c2a8a0  008298a0  2**5
                  CONTENTS, ALLOC, LOAD, DATA
 28 .bss          000a0920  0000000000c55920  0000000000c55920  00854908  2**5
                  ALLOC
 29 .comment      00000091  0000000000000000  0000000000000000  00854908  2**0
                  CONTENTS, READONLY
 30 .GCC.command.line 000057fd  0000000000000000  0000000000000000  00854999  2**0
                  CONTENTS, READONLY
 31 .note.stapsdt 00000048  0000000000000000  0000000000000000  0085a198  2**2
                  CONTENTS, READONLY
 32 .debug_aranges 00046d10  0000000000000000  0000000000000000  0085a1e0  2**4
                  CONTENTS, READONLY, DEBUGGING
 33 .debug_info   038872df  0000000000000000  0000000000000000  008a0ef0  2**0
                  CONTENTS, READONLY, DEBUGGING
 34 .debug_abbrev 00130f58  0000000000000000  0000000000000000  041281cf  2**0
                  CONTENTS, READONLY, DEBUGGING
 35 .debug_line   0059bb2d  0000000000000000  0000000000000000  04259127  2**0
                  CONTENTS, READONLY, DEBUGGING
 36 .debug_str    02ae4878  0000000000000000  0000000000000000  047f4c54  2**0
                  CONTENTS, READONLY, DEBUGGING
 37 .debug_loc    026201be  0000000000000000  0000000000000000  072d94cc  2**0
                  CONTENTS, READONLY, DEBUGGING
 38 .debug_ranges 005fbf30  0000000000000000  0000000000000000  098f9690  2**4
                  CONTENTS, READONLY, DEBUGGING
 39 .debug_macro  0018c0ed  0000000000000000  0000000000000000  09ef55c0  2**0
                  CONTENTS, READONLY, DEBUGGING

"""

# some more specific sections that we support
color_sections = {

        ".interp":           None,
        ".note.ABI-tag":     None,
        ".hash":             None,
        ".gnu.hash":         None,
        ".dynsym":           None,
        ".dynstr":           None,
        ".gnu.version":      None,
        ".gnu.version_r":    None,
        ".rela.dyn":         None,
        ".rela.plt":         None,
        ".init":             None,
        ".plt":              None,
        ".text":             None,
        ".fini":             None,
        ".rodata":           None,
        ".stapsdt.base":     None,
        ".eh_frame_hdr":     None,
        ".eh_frame":         None,
        ".gcc_except_table": None,
        ".tdata":            None,
        ".tbss":             None,
        ".init_array":       None,
        ".fini_array":       None,
        ".data.rel.ro":      None,
        ".dynamic":          None,
        ".got":              None,
        ".got.plt":          None,
        ".data":             None,
        ".bss":              None,
        ".comment":          None,
        ".GCC.command.line": None,
        ".note.stapsdt":     None,
        ".debug_aranges":    None,
        ".debug_info":       None,
        ".debug_abbrev":     None,
        ".debug_line":       None,
        ".debug_str":        None,
        ".debug_loc":        None,
        ".debug_ranges":     None,
        ".debug_macro":      None,
        }

color_configs = {}
for sec,col in color_sections.items():
    esec = sec.replace(".","_")
    color_configs[sec] = vdb.config.parameter(f"vdb-memory-colors-section-{esec}", col, gdb_type = vdb.config.PARAM_COLOUR )

def section_color( sec ):
    if( sec is None ):
        return sec
    co=color_configs.get(sec,None)
    return co

valid_colorspec="Aams"

def check_colorspec( colorspec ):
    if( colorspec is not None ):
        for c in colorspec:
            if( c not in valid_colorspec ):
                raise Exception("'%s' is not allowed in colorspecs" % c )


def print_legend( colorspec = "Aasm" ):
    if( colorspec is None ):
        colorspec = default_colorspec.value
    legends = []
    if( "A" in colorspec ):
        legends.append(vdb.color.color("[ASCII]",        vdb.memory.color_ascii.value))
    if( "m" in colorspec ):
        legends.append(vdb.color.color("[STACK(OWN)]",   colormap[memory_type.OWN_STACK ].value ))
        legends.append(vdb.color.color("[STACK(OTHER)]", colormap[memory_type.FOREIGN_STACK ].value ))
        legends.append(vdb.color.color("[HEAP]",         colormap[memory_type.HEAP ].value ))
        legends.append(vdb.color.color("[MMAP]",         colormap[memory_type.MMAP ].value ))
        legends.append(vdb.color.color("[SHM]",          colormap[memory_type.SHM ].value ))
        legends.append(vdb.color.color("[CODE]",         colormap[memory_type.CODE ].value ))
        legends.append(vdb.color.color("[BSS]",          colormap[memory_type.BSS ].value ))
        legends.append(vdb.color.color("[NULL]",         colormap[memory_type.NULL ].value ))
#        legends.append(vdb.color.color("[UNK]",          colormap[memory_type.UNKNOWN ].value ))
    if( "a" in colorspec ):
        legends.append(vdb.color.color("[RO]",   access_colors[access_type.ACCESS_RO].value ))
        legends.append(vdb.color.color("[WO]",   access_colors[access_type.ACCESS_WO].value ))
        legends.append(vdb.color.color("[RW]",   access_colors[access_type.ACCESS_RW].value ))
        legends.append(vdb.color.color("[EX]",   access_colors[access_type.ACCESS_EX].value ))
        legends.append(vdb.color.color("[INV]",  access_colors[access_type.ACCESS_INV].value ))
        legends.append(vdb.color.color("[INAC]", access_colors[access_type.ACCESS_INACCESSIBLE].value ))
        legends.append(vdb.color.color("[UNK]",  access_colors[access_type.ACCESS_UNKNOWN].value ))
    if( "s" in colorspec ):
        for cs,_ in color_sections.items():
#            print("cs = '%s'" % cs )
            co = section_color(cs).value
            legends.append( vdb.color.color(f"[{cs}]",co) )

    s=""
    for l in legends:
        if( colors.ansilen(s) > 120 ):
            print(s)
            s=""
        s += " "
        s += l
    print(s)

default_region_prefixes = [
        ( ".bss" , memory_type.BSS ),
        ( ".tbss" , memory_type.BSS ),
#        ( ".data", memory_type.DATA ),
        ( ".text", memory_type.CODE ),
        ( ".init", memory_type.CODE ),
        ( ".plt", memory_type.CODE ),
        ( ".fini", memory_type.CODE ),
]

@vdb.util.memoize
def read( ptr, count = 1 ):
#    vdb.util.bark(-2) # print("BARK")
#    vdb.util.bark(-1) # print("BARK")
#    print("type(ptr) = '%s'" % (type(ptr),) )
#    print("type(count) = '%s'" % (type(count),) )
#    print(f"read( 0x{int(ptr):x},{count} )")
    result = None
    if( isinstance(ptr,str) ):
        addr=vdb.util.gint(ptr)
    else:
        addr=ptr
    try:
#        print("addr = '%s'" % (addr,) )
        while( addr < 0 ):
            addr += 2** vdb.arch.pointer_size
        if( addr.bit_length() > vdb.arch.pointer_size ):
            addr &= ( 2 ** vdb.arch.pointer_size - 1 )
            
#        print("addr = '%s'" % (addr,) )
#        print("count = '%s'" % (count,) )
#        print("addr.bit_length() = '%s'" % (addr.bit_length(),) )
        result = gdb.selected_inferior().read_memory(addr, count)
    except gdb.error:
        pass
    return result

def write( ptr, buf ):
    if( isinstance(ptr,str) ):
        addr=vdb.util.gint(ptr)
    else:
        addr=ptr
    try:
        gdb.selected_inferior().write_memory( addr, buf )
    except gdb.error:
        pass




class memory_region:


    def __init__(self,start,end,section,file):
        self.start = start
        self.end = end
        self.section = section
        self.file = file
        self.atype = access_type.ACCESS_UNKNOWN
        self.mtype = None
        self.can_read = False
        self.can_write = False
        self.thread = None
        self.size = end-start
        self.procline = None
        self.maintline = None
        self.fileline = None
        if( self.size > 0 ):
            self._test_access()
            if( self.can_write and self.can_read ):
                self.atype = access_type.ACCESS_RW
            elif( self.can_read ):
                self.atype = access_type.ACCESS_RO
            elif( self.can_write ):
                self.atype = access_type.ACCESS_WO
            else:
                self.atype = access_type.ACCESS_INACCESSIBLE
        self._test_prefixes()
        # TODO figure out how to find out executable, and also if executalbe is always RO

    def is_unknown( self ):
        return self.start == 0 and self.end == 0 and self.section is None and self.file is None

    def rwxp( self ):
        ret = ""
        if( self.can_read ):
            ret += "r"
        else:
            ret += "-"

        if( self.can_write ):
            ret += "w"
        else:
            ret += "-"

        if( self.atype == access_type.ACCESS_EX ):
            ret += "x"
        else:
            ret +="-"

        ret += "?" # shared/private, hmmm...
        return ret

    def __str__( self ):
        s = ""
        plen = vdb.arch.pointer_size // 4
        sz,suf = vdb.util.num_suffix( self.size )
        s += f"memory_region from {self.start:#0{plen}x} to {self.end:#0{plen}x} ({sz:.3f}{suf}Bytes):\n"
        s += vdb.util.ifset("Section '{}'\n",self.section)
        s += vdb.util.ifset("File '{}'\n", self.file)
        s += vdb.util.ifset("Memory Access : {}\n", self.atype )
        s += vdb.util.ifset("Memory Type : {}\n", self.mtype )
        s += vdb.util.ifset("Associated Thread : {}\n", thread_print(self.thread) )
        s += vdb.util.ifset("/proc/<pid>/maps {}\n", self.procline )
        s += vdb.util.ifset("info files {}\n", self.fileline )
        s += vdb.util.ifset("maint info sections {}\n", self.maintline )
        return s

    def __repr__( self ):
        return str(self)

    def _test_prefixes( self ):
        if( self.section is not None ):
            for p,m in default_region_prefixes:
                if( self.section.startswith(p) ):
#                    print("m = '%s'" % m )
                    self.mtype = m
                    if( self.mtype == memory_type.CODE ):
                        self.atype = access_type.ACCESS_EX
                    break

    def _test_access( self ):
        try:
            mem = gdb.selected_inferior().read_memory(self.start,1)
            self.can_read = True
            if( test_write.value ):
                gdb.selected_inferior().write_memory(self.start,mem,1)
                self.can_write = True
        except:
            pass
        return ( self.can_read, self.can_write )


    def __lt__(self, other):
        if( isinstance(other,int) ):
            return self.start < other
        else:
            if( self.start == other.start ):
                return self.end < other.end
            return self.start < other.start

class memory_key:
    def __init__(self, value ):
        self.value = value

    def __lt__(self, other):
        return self.value < other.start

def thread_print( thr ):
    if( thr is None ):
        return thr
    return f"{thr.num} LWP {thr.ptid} '{thr.name}'"

class memory_map:

    def __init__( self ):
        self.regions = intervaltree.IntervalTree()
        self.parsed_version = 0
        self.needed_version = 1
        self.unknown = memory_region(0,0,None,None)

    def lazy_parse( self ):
        if( self.needed_version > self.parsed_version ):
            self.parsed_version = self.needed_version
            self.parse()

    def section( self, start, end ):
        self.lazy_parse()
#        mskey = memory_region(start,end,None,None)
        mms = self.regions[start:end]
#        mm = bisect.bisect_left( self.regions,mskey )
#        if( mm < 0 or mm >= len(self.regions) ):
#            return None
#        mm = self.regions[mm]
        for mm in mms :
            mm = mm[2]
            if( mm.start == start and mm.end == end ):
                return mm
        return None


    def find( self, addr, mm = None ):
#        print(f"find(0x{addr:x})")
        if( mm is not None ):
            return mm
        self.lazy_parse()
#        print("len(self.regions) = '%s'" % len(self.regions) )
#        print("addr = '%s'" % addr )
#        mmi = bisect.bisect_left( self.regions, addr )
#        mmi = bisect.bisect_right( self.regions, memory_key(addr) )

        mms = self.regions[addr]
        
        candidates = []
        for mm in mms:
            mm = mm[2]
#            mm = self.regions[mmi]
#            print("mm = '%s'" % mm )
#            print("type(mm.start) = '%s'" % type(mm.start) )
#            print("type(addr) = '%s'" % type(addr) )
#            print(f"0x{mm.start:x} <= 0x{addr:x} = {mm.start<=addr}")
#            print(f"0x{addr:x} <= 0x{mm.start:x} = {addr<=mm.start}")
            if( mm.start <= addr <= mm.end ):
                candidates.append(mm)
            if( mm.start > addr ):
                break

#        print("candidates = '%s'" % candidates )
        if( len(candidates) == 0 ):
            return None

        mr = candidates[0]
        for c in candidates:
            if( mr.size > c.size ):
                mr = c
        return mr


    def get_asciicolor( self, addr ):
        """
        Colour according to the a(scii)type, as well as a possible ascii formatted string (or None)
        """

        aptr = addr
        ascii=True
        plen = vdb.arch.pointer_size // 4
        ba = bytearray()
        for i in range(0,plen//2):
            bi = aptr & 0xFF
            b = chr(bi)
            if( bi == 0 ):
                if( i != (plen//2)-1 ):
                    ascii = False
                    break
            else:
                ba.append(bi)
            aptr = aptr >> 8
        if( ascii ):
            bs = vdb.util.maybe_utf8(ba)
            if( bs is not None ):
                return ( memory_type.ASCII, ( bs, f"[{len(bs)}]'{bs}'") )
        return ( None, None )

    def get_atype( self, addr, mm = None ):
        mm = self.find(addr,mm)
        if( mm is not None ):
            return mm.atype
        return None

    def get_mtype( self, addr, mm = None ):
        mm = self.find(addr,mm)
        if( mm is not None ):
            return mm.mtype
        return None

    def accessible( self, addr, mm = None ):
        at = self.get_atype( addr, mm )
#        print("addr = '%s'" % (addr,) )
#        print("at = '%s'" % (at,) )
        if( at is None ):
            return False
        if( at in [ access_type.ACCESS_INV, access_type.ACCESS_INACCESSIBLE, access_type.ACCESS_UNKNOWN ] ):
            return False
        return True

    def get_mcolor( self, addr, mm = None ):
        """
        Colour according to the m(emory)type
        """
        mm = self.find(addr,mm)
        ret = None
        if( mm is not None ):
            mtype = mm.mtype
            if( mtype == memory_type.FOREIGN_STACK ):
                if( gdb.selected_thread() == mm.thread ):
                    mtype = memory_type.OWN_STACK
            ret = colormap.get(mtype,None)
            if( ret is not None ):
                ret = ret.value
                if( len(ret) == 0 ):
                    ret = None
#        print("ret = '%s'" % ret )
#        print("mm.mtype = '%s'" % mm.mtype )
        return ( ret, mm )

    def get_acolor( self, addr, mm = None ):
        """
        Colour according to the a(ccess) type
        """
        mm = self.find(addr,mm)
        ret = None
        if( mm is not None ):
            ret = access_colors.get(mm.atype,None)
            if( ret is not None ):
                ret = ret.value
                if( len(ret) == 0 ):
                    ret = None
        return ( ret, mm )


    def get_scolor( self, addr, mm = None ):
        """
        Colour according to the s(ection)
        """
        mm = self.find(addr,mm)
        ret = None
        if( mm is not None ):
#            ret = color_configs.get(mm.section,None)
            ret = section_color(mm.section)
            if( ret is not None ):
                ret = ret.value
                if( len(ret) == 0 ):
                    ret = None
#        print("ret = '%s'" % ret )
#        print("mm.section = '%s'" % mm.section )
        return ( ret, mm )

    def color( self, addr, s = None, colorspec = None, mm = None ):
        """
        returns a tuple of the coloured string as well as the region that matched it, or None
        """
        if( colorspec is None ):
            colorspec = default_colorspec.value
        self.lazy_parse()
        if( s is None ):
#            s = str(addr)
            plen = vdb.arch.pointer_size // 4
            s = f"{addr:#0{plen}x}"
        if( mm is None ):
            mm = self.find(addr)
        if( mm is None ):
            mm = self.unknown
        ascii = None
        col = None
        for cs in colorspec:
            if( cs == "s" ):
                # section colors (.bss, .data etc.)
                col,_ = self.get_scolor(addr,mm)
            elif( cs == "m" ):
                # memory_type colors (stack, heap etc.)
                col,_ = self.get_mcolor(addr,mm)
            elif( cs == "a" ):
                # access type colors (read,write etc.)
                col,_ = self.get_acolor(addr,mm)
            elif( cs == "A" ):
                # is the pointer value an ascii string?
                mt,ascii = self.get_asciicolor(addr)
                if( mt is not None ):
                    col = color_ascii.value
            if( col is not None ):
                break

        if( col is not None ):
            s = vdb.color.color(s,col)

        return ( s, mm, col, ascii )

    def add_region( self, mm ):
        self.regions[mm.start:mm.end+1] = mm

    def parse( self ):
        self.regions.clear()

        selected_thread = gdb.selected_thread()
        if( selected_thread is None ):
            return
        info_files = gdb.execute("info files",False,True)
        fre = re.compile("(0x[0-9a-fA-F]*) - (0x[0-9a-fA-F]*) is (.*?)(?: in (.*))?$")
        for info in info_files.splitlines():
            info=info.strip()
            m = fre.match(info)
            if( m ):
                start=int(m.group(1),16)
                end=int(m.group(2),16)
                section=m.group(3)
                file=m.group(4)
                size=end-start
                if( ignore_empty.value and size == 0 ):
                    continue
                mr = memory_region( start, end, section, file )
                mr.fileline = info
                self.add_region( mr )
        nullr = memory_region( 0, 0x1000, None, None )
        nullr.atype = access_type.ACCESS_INV
        nullr.mtype = memory_type.NULL
        self.add_region(nullr)
#        self.regions.sort()
        info_proc_mapping = gdb.execute("info proc mapping",False,True)
        mre = re.compile("(0x[0-9a-fA-F]*)\s*(0x[0-9a-fA-F]*)\s*(0x[0-9a-fA-F]*)\s*(0x[0-9a-fA-F]*)\s*(.*)")

        
        for mapping in info_proc_mapping.splitlines():
            mapping=mapping.strip()
            m = mre.match(mapping)
#            print("mapping = '%s'" % mapping )
#            print("m = '%s'" % m )
            if( m ):
                start=int(m.group(1),16)
                end=int(m.group(2),16)
                file=m.group(5)
                mm = self.section(start,end)
                size = end-start
                if( ignore_empty.value and size == 0 ):
                    continue
                if( mm is None ):
                    mm = memory_region( start, end, None, file )
                    self.add_region(mm)
                mm.procline = mapping
                if( len(file) > 0 and mm.file is None ):
                    mm.file = file
                if( file.startswith("/SYSV00000000 (deleted)") ):
                    mm.mtype = memory_type.SHM
                elif( file.endswith( "[stack]") ):
                    mm.mtype = memory_type.FOREIGN_STACK
                elif( file.endswith( "[heap]") ):
                    mm.mtype = memory_type.HEAP
                elif( file.endswith( "[vsyscall]") ):
                    mm.mtype = memory_type.CODE
                elif( file.endswith( "[vdso]") ):
                    mm.mtype = memory_type.CODE

#        self.regions += map_regions
#        self.regions.sort()
        maint_sections = gdb.execute("maint info sections ALLOBJ",False,True)
        sre = re.compile(".*(0x[0-9a-fA-F]*)->(0x[0-9a-fA-F]*)\s*at\s*(0x[0-9a-fA-F]*):\s*(.*?)\s\s*(.*)")
#        sec_regions = []
        for sec in maint_sections.splitlines():
            sec = sec.strip()
            m = sre.match(sec)
            if( m ):
                start = int(m.group(1),16)
                # Those are registers and all kinds of other stuff
                if( start == 0 ):
                    continue
                end = int(m.group(2),16)
                section = m.group(4)
                rest = m.group(5)
                rest = set( rest.split() )
                size = end-start
                if( ignore_empty.value and size == 0 ):
                    continue
#                print(f"{start} {end} {section} {rest} {size}")
                mm = self.section(start,end)
                if( mm is None ):
                    mm = memory_region( start, end, section, None )
                    self.add_region(mm)
                else:
                    if( mm.section is not None and mm.section != section ):
                        mm.section += f"[{section}]"
                        print(f"Section mismatch, previous {mm.section}, new {section}")
                mm.maintline = sec
#                print("mm = '%s'" % mm )
#                if( "LOAD" not in rest ):
#                    print("LOAD mm.mtype = '%s'" % mm.mtype )
                if( "CODE" in rest ):
#                    print("CODE mm.mtype = '%s'" % mm.mtype )
                    if( mm.atype == None and "READONLY" in rest ):
                        mm.atype = access_type.ACCESS_EX
                if( ( mm.atype == None or mm.atype == access_type.ACCESS_RW ) and "READONLY" in rest ):
                    mm.atype = access_type.ACCESS_RO
#                    mm.mtype = memory_type.HEAP
#        print("sec_regions = '%s'" % sec_regions )
#        self.regions += sec_regions
#        self.regions.sort()
        try:
            # check if any is a stack
            selected_frame = gdb.selected_frame()
            for thread in gdb.selected_inferior().threads():
                thread.switch()
                f = gdb.selected_frame()
                sp = f.read_register("sp")
#                mm = self.find(int(sp))
                mms = self.regions[int(sp)]
                for mm in mms:
                    mm = mm[2]
                    if( mm ):
                        mm.mtype = memory_type.FOREIGN_STACK
                        mm.thread = thread
        except:
            traceback.print_exc()
            pass
        finally:
            try:
                # may not run anymore
                selected_thread.switch()
            except:
                pass
            selected_frame.select()


# XXX This is basically the vmmap implementation, maybe we move parts of it there?
    def print( self, colorspec, short = False ):
        self.lazy_parse()
        otbl = []
#        cnt = 0
#        plen = vdb.arch.pointer_size // 4

        for r in sorted(self.regions):
            r = r[2]
#            cnt += 1
#            if( cnt > 10 ):
#                break
            _,mm,col,ascii = self.color(r.start, colorspec = colorspec, mm = r )
            rwxp = r.rwxp()

            xplen = 2 * ( ( r.end.bit_length() + 7 ) // 8 )

            ms = vdb.color.colorl(f"{r.start:#0{xplen}x}", col)
            me = vdb.color.colorl(f"{r.end:#0{xplen}x}", col)

            size= r.end - r.start
            f = vdb.util.nstr(r.file)
            s = vdb.util.nstr(r.section)
            if( short and r.section is not None ):
                continue

            sz,suf=vdb.util.num_suffix(r.size,factor = 1)
            by = f"{sz:.1f}{suf}B"
#            print("0x{:x} - 0x{:x} {} {}".format(r.start,r.end,r.section,r.file))
#            print("{} - {} {:>10} {:<20} {}".format(ms,me,by,s,f))
            otbl.append([ms,"-",me,rwxp,by,s,f])
        print( vdb.util.format_table(otbl))
#            print("size = '%s'" % size )
#            print("r.mtype = '%s'" % r.mtype )

mmap = memory_map()

last_refresh_at = 0
last_run_start = 0

@vdb.event.start()
@vdb.event.run()
def run_start():
    global last_run_start
    last_run_start += 1

# might be a bottleneck for some situations
@vdb.event.stop()
def maybe_refresh( x ):
    global mmap
    global last_refresh_at
    if( last_refresh_at == last_run_start ):
        return
    t0 = time.time()
    mmap.parse()
    t1 = time.time()
    print("Automatically refreshed memory map in %.4fs" % (t1-t0) )
    last_refresh_at = last_run_start


sym_cache = intervaltree.IntervalTree()

symre=re.compile("0x[0-9a-fA-F]* <([^+]*)(\+[0-9]*)*>")

# addr in, ( start, size, string ) out...

def is_sym_at( addr, symbol ):
    nm = gdb.parse_and_eval(f"(void*)({addr})")
#    print("nm = '%s'" % (nm,) )
    m=symre.match(str(nm))
    if( m ):
        if( m.group(1) == symbol ):
            return True
    return False

def get_gdb_sym( addr ):
#    vdb.util.bark() # print("BARK")
#    print("addr = '%s'" % (addr,) )

    addr = int(addr)
    global sym_cache
    xs = sym_cache[addr]
    if( len(xs) > 0 ):
#        print("xs = '%s'" % xs )
        for x in xs:
#            print("x = '%s'" % (x,) )
            return x[2]
    else:
        xaddr = addr
        nm = gdb.parse_and_eval(f"(void*)({xaddr})")
#        print("nm = '%s'" % (nm,) )
        m=symre.match(str(nm))
#        print("m = '%s'" % (m,) )
        if( m ):
#            print("m.group(0) = '%s'" % (m.group(0),) )
#            print("m.group(1) = '%s'" % (m.group(1),) )
#            print("m.group(2) = '%s'" % (m.group(2),) )
            symbol = m.group(1)
            symsize = 1
            ssz = m.group(2)
            if( ssz is not None ):
                symsize = int(ssz[1:]) + 1
            start_addr = xaddr - ( symsize - 1 )
#            print("xaddr = '0x%x'" % (xaddr,) )
#            print("start_addr = '0x%x'" % (start_addr,) )
#            print("symsize = '%s'" % (symsize,) )

            # Now we are at the beginning of the symbol and know to the passed address where it is, but we don't really
            # know where the end is
            last_addr = start_addr + symsize - 1 # last known address that belongs to the symbol
            # This is a bit slow but we cache things, maybe thats ok then
            offset = 8
            # Start with bigger steps for functions
            if( symbol.find("(") != -1 ):
                offset += 64

            while( offset > 0 ):
                while( is_sym_at( last_addr + offset, symbol ) ):
                    last_addr += offset
                offset //= 2
            symsize = (last_addr - start_addr) + 1

#            print("start_addr = '0x%x'" % (start_addr,) )
#            print("last_addr = '0x%x'" % (last_addr,) )
#            print("symsize = '%s'" % (symsize,) )
#            print("symbol = '%s'" % (symbol,) )
#            print("is_sym_at(start_addr,symbol) = '%s'" % (is_sym_at(start_addr,symbol),) )
            tpl = ( start_addr, symsize, symbol )
            sym_cache[start_addr:start_addr+symsize] = tpl
#            print("sym_cache = '%s'" % (sym_cache,) )
            return tpl
    return (None,None,None)

def get_symbols( addr, xlen ):
    ret = intervaltree.IntervalTree()
    xaddr = addr+xlen

    recnt = 0
    while xaddr > addr:
        start,size,name = get_gdb_sym(xaddr)
#        print("start = '%s'" % (start,) )
#        print("size = '%s'" % (size,) )
#        print("name = '%s'" % (name,) )
        if( start is None ):
            xaddr -= 1
        else:
            ret[start:start+size] = name
            xaddr = start - 1
#        print("xaddr = '%s'" % (xaddr,) )
#    print("ret = '%s'" % (ret,) )
    return ret




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
