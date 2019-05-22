#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.pointer
import vdb.util
import vdb.shorten
import vdb.command
import vdb.layout


import gdb

import string
import traceback
import re
import intervaltree


color_head       = vdb.config.parameter("vdb-hexdump-colors-header",                "#ffa",    gdb_type = vdb.config.PARAM_COLOUR)

default_len   = vdb.config.parameter("vdb-hexdump-default-len",8*16)
repeat_header = vdb.config.parameter("vdb-hexdump-repeat-header",42)


color_list = vdb.config.parameter("vdb-hexdump-colors-symbols", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,on_set  = vdb.config.split_colors)

def print_header( ):
    plen = 64//4
    print(vdb.color.color(f'  {" "*plen}  0  1  2  3   4  5  6  7    8  9  A  B   C  D  E  F   01234567 89ABCDEF',color_head.value))


class sym_location:

    def __init__( self ):
        self.start = 0
        self.end = 0
        self.name = ""

sym_cache = intervaltree.IntervalTree()

symre=re.compile("0x[0-9a-fA-F]* <([^+]*)(\+[0-9]*)*>")
def get_gdb_sym( addr ):
    addr = int(addr)
    global sym_cache
    xs = sym_cache[addr]
    if( len(xs) > 0 ):
        print("xs = '%s'" % xs )
        for x in xs:
            print("x = '%s'" % x )
    else:
        xaddr = addr
        nm = gdb.parse_and_eval(f"(void*)({xaddr})")
        m=symre.match(str(nm))
        if( m ):
            symsize = 1
            ssz = m.group(2)
            if( ssz is not None ):
                symsize = int(ssz[1:])
            eaddr = xaddr
            xaddr -= symsize + 1
            saddr = eaddr - symsize
#            print("saddr = 0x%x" % saddr )
#            print("eaddr = 0x%x" % eaddr )
#            ret.append( ( saddr, eaddr, m.group(1) ) )
            ret[saddr:eaddr+1] = m.group(1)




def get_symbols( addr, xlen ):
    ret = intervaltree.IntervalTree()
    xaddr = addr+xlen

    while xaddr > addr:
        nm = get_gdb_sym(xaddr)
        nm = gdb.parse_and_eval(f"(void*)({xaddr})")
        m=symre.match(str(nm))
        if( m ):
#            print("m = '%s'" % m )
#            print("m.group(1) = '%s'" % m.group(1) )
#            print("m.group(1) = '%s'" % m.group(2) )
            symsize = 1
            ssz = m.group(2)
            if( ssz is not None ):
                symsize = int(ssz[1:])
            eaddr = xaddr
            xaddr -= symsize + 1
            saddr = eaddr - symsize
#            print("saddr = 0x%x" % saddr )
#            print("eaddr = 0x%x" % eaddr )
#            ret.append( ( saddr, eaddr, m.group(1) ) )
            ret[saddr:eaddr+1] = m.group(1)
        else:
            xaddr -= 1
#    ret.reverse()
#    print("ret = '%s'" % ret )
    return ret

annotation_tree = intervaltree.IntervalTree()
default_sizes = { }

def get_annotation( xaddr, symtree ):
    xs = annotation_tree[xaddr]
    if( len(xs) == 0 ):
        xs = symtree[xaddr]
    return xs

def hexdump( addr, xlen = -1 ):
    if( xlen == -1):
        xlen = default_sizes.get(addr,default_len.value)
    symtree = get_symbols(addr,xlen)
    olen = xlen
    plen = 64//4
    data = vdb.memory.read(addr,xlen)
    if( data is None ):
        data = vdb.memory.read(addr,1)
        if( data is not None ):
            data = None
            while(data is None ):
                xlen -= 1
                data = vdb.memory.read(addr,xlen)
    if( data is None ):
        print(f"Can not access memory at 0x{addr:x}")
        return
    xaddr = addr
    p,add,col,mm = vdb.pointer.color(addr,64)
#    nm = gdb.parse_and_eval(f"(void*)({addr})")
    current_symbol = None
    next_color = -1
    sym_color = None
    line = 0
    while(len(data) > 0 ):
        dc = data[:16]
        data = data[16:]
        p,_,_,_ = vdb.pointer.color(xaddr,64)
        cnt = 0
        l = ""
        t = ""
        s = ""
        for d in dc:
#            xs = symtree[xaddr+cnt]
            xs = get_annotation( xaddr + cnt, symtree )
            nsym = None
            for x in xs:
                nsym = x[2]
                break

#            nm = gdb.parse_and_eval(f"(void*)({xaddr+cnt})")
#            m=symre.match(str(nm))
#            if( m ):
            if( nsym is not None ):
#                print("m.group(0) = '%s'" % m.group(0) )
#                print("m.group(1) = '%s'" % m.group(1) )
#                nsym = m.group(1)
                nsym = vdb.shorten.symbol(nsym)
#                print("nsym = '%s'" % nsym )
                if( current_symbol != nsym ):
                    if( nsym ):
                        next_color += 1
                        next_color %= len(color_list.elements)
                        sym_color = color_list.elements[next_color]
                        s += vdb.color.color(nsym,sym_color)
                        s += " "
                    else:
                        sym_color = None
                    current_symbol = nsym
            else:
                sym_color = None
                current_symbol = None

            d = int.from_bytes(d,"little")
            l += vdb.color.color(f"{d:02x} ",sym_color)
            c = chr(d)
            if( c in string.printable and not ( c in "\t\n\r\v\f") ):
                t += vdb.color.color(c,sym_color)
            else:
                t += vdb.color.color(".",sym_color)
            cnt += 1
            if( cnt == 8 ):
                t += " "
                l += "-"
            if( cnt % 4 == 0 ):
                l += " "
        cnt = (16-cnt)
        t += (cnt-1)*" "
        l += (cnt)*"   "
        l += ((cnt-1)//4)*" "
        l += ((cnt+7)//8)*" "
        t += ((cnt+7)//8)*" "
        if( line % repeat_header.value == 0 ):
            print_header()
        line += 1
#        print("len(t) = '%s'" % len(t) )
        print(f"{p}: {l}{t} {s}")
#        print("dc = '%s'" % dc )
#        print("len(dc) = '%s'" % len(dc) )
#        print("data = '%s'" % data )
#        print("len(data) = '%s'" % len(data) )
        xaddr += 16
#    print("data = '%s'" % data )
    
#    print("HEXDUMP")
#    print("addr = '%s'" % addr )
#    print("xlen = '%s'" % xlen )
    if( olen != xlen ):
        print(f"Could only access {xlen} of {olen} requested bytes")

def annotate_var( addr,gval, gtype ):
#        print("gtype = '%s'" % gtype )
#        print("gval = '%s'" % gval )
    ol = vdb.layout.object_layout( gtype, gval )
    print("ol = '%s'" % ol )
    print("ol.object = '%s'" % ol.object )
        
    for bd in ol.descriptors:
        print("bd.object = '%s'" % bd.object )
        if( bd.object.final and bd.object.byte_offset >= 0 and bd.object.size > 0 ):
            if( bd.prefix is None ):
                continue
            ent = bd.name()
            if( len(ent) > 2 and ent.startswith("::") ):
                ent = ent[2:]
            ent = vdb.shorten.symbol(ent)
            annotation_tree[addr+bd.object.byte_offset:addr+bd.object.byte_offset+bd.object.size] = ent
#        print("annotation_tree = '%s'" % annotation_tree )

def annotate( argv ):
    global annotation_tree
    if( len(argv) == 2 ):
        addr = vdb.util.gint( argv[0] )
        ttype = argv[1]
        gtype = gdb.lookup_type( ttype )
        global default_sizes
        default_sizes[addr] = gtype.sizeof
        gval = gdb.parse_and_eval(f"*({ttype}*)({addr})")
        annotate_var( addr,gval,gtype)

    elif( len(argv) == 3):
        addr = vdb.util.gint( argv[0] )
        tlen = vdb.util.xint( argv[1] )
        txt = argv[2]
        annotation_tree[addr:addr+tlen] = txt
    elif( len(argv) == 1 and argv[0] == "frame" ):
        fr = gdb.selected_frame()
        for i in fr.block():
            print("i.name = '%s'" % i.name )
            v = gdb.selected_frame().read_var(i.name)
            print("v = '%s'" % v )
            print("v.address = '%s'" % v.address )
            print("v.type = '%s'" % v.type )
            annotate_var( v.address,v, v.type )
#            break
        print("annotation_tree = '%s'" % annotation_tree )

    else:
        print("Usage: hexdump annotate <addr> <len> <text> or <addr> <typename>")
    print("Annotated {}".format(argv))

def call_hexdump( argv ):
#    argv = gdb.string_to_argv(arg)
    colorspec = "sma"
    if( len(argv) == 0 ):
        print("You should at least tell me what to dump")
        return
    if( argv[0] == "annotate" ):
        annotate( argv[1:] )
    else:
        addr = None
        xlen = None
        if( len(argv) == 1 ):
            addr = vdb.util.gint(argv[0])
            hexdump(addr)
        elif( len(argv) == 2 ):
            addr = vdb.util.gint(argv[0])
            xlen = vdb.util.gint(argv[1])
            hexdump(addr,xlen)
        else:
            print("Usage: hexdump <addr> <len>")
    return



class cmd_hexdump (vdb.command.command):
    """Shows a hexdump of a specified memory range"""

    def __init__ (self):
        super (cmd_hexdump, self).__init__ ("hexdump", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:

#            import cProfile
#            cProfile.runctx("call_hexdump(argv)",globals(),locals())
            call_hexdump(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_hexdump()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
