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
import vdb.arch


import gdb

import string
import traceback
import re
import intervaltree


color_head       = vdb.config.parameter("vdb-hexdump-colors-header",                "#ffa",    gdb_type = vdb.config.PARAM_COLOUR)

default_len   = vdb.config.parameter("vdb-hexdump-default-len",8*16)
repeat_header = vdb.config.parameter("vdb-hexdump-repeat-header",42)
default_chaindepth = vdb.config.parameter("vdb-hexdump-default-chaindepth",3)

pc_separator = vdb.config.parameter("vdb-hexdump-pointer-chain-separator","|")
row_format = vdb.config.parameter("vdb-hexdump-row-format", "{p}: {l}{t} {s}{pointer_string}{value_string}")


color_list = vdb.config.parameter("vdb-hexdump-colors-symbols", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,on_set  = vdb.config.split_colors)

def print_header( ):
    plen = vdb.arch.pointer_size // 4
    rowf = row_format.value
    rowf = rowf.replace(":"," ")
    p = f'  {" "*plen}'
    l = "0  1  2  3   4  5  6  7    8  9  A  B   C  D  E  F "
    t = "  01234567 89ABCDEF"
    s = "VARIABLES "
    pointer_string = "POINTERS "
    value_string = "VALUES "
    rowh = rowf.format(**locals())
    print(vdb.color.color(rowh,color_head.value))
#    print(vdb.color.color(f'  {" "*plen}  0  1  2  3   4  5  6  7    8  9  A  B   C  D  E  F   01234567 89ABCDEF',color_head.value))


class sym_location:

    def __init__( self ):
        self.start = 0
        self.end = 0
        self.name = ""

sym_cache = intervaltree.IntervalTree()

symre=re.compile("0x[0-9a-fA-F]* <([^+]*)(\+[0-9]*)*>")
def get_gdb_sym( addr ):
    ret = intervaltree.IntervalTree()
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


pe_cache = {}

def parse_and_eval_cached( ex, override = False ):
    global pe_cache
    if( override ):
        cv = None
    else:
        cv = pe_cache.get( ex,None)
    if( cv is not None ):
        return cv

    res = gdb.parse_and_eval( ex )
    pe_cache[ex] = res
    return res



def get_symbols( addr, xlen ):
    ret = intervaltree.IntervalTree()
    xaddr = addr+xlen

    recnt = 0
    while xaddr > addr:
#        nm = ""
        nm = get_gdb_sym(xaddr)
        astr = f"(void*)({xaddr})"
        xstr = f"0x{int(xaddr):x}"
#        nm = gdb.parse_and_eval(astr)
#        nm = parse_and_eval_cached( astr )

        m = None
        nm = str(nm)
        if( len(nm) != len(xstr) ):
            recnt += 1
#            print("len(nm) = '%s'" % (len(nm),) )
#            print("len(xstr) = '%s'" % (len(xstr),) )
#            print("RE")
            m=symre.match(str(nm))
#        print("xstr = '%s'" % (xstr,) )
#        print("astr = '%s'" % (astr,) )
#        print("nm = '%s'" % (nm,) )
#        print("m = '%s'" % (m,) )
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
#    print(" recnt = '%s'" % ( recnt,) )
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

def hexdump( addr, xlen = -1, pointers = False, chaindepth = -1, values = False, symbols = True ):
    if( chaindepth < 0 ):
        chaindepth = default_chaindepth.value
    if( xlen == -1):
        xlen = default_sizes.get(addr,default_len.value)
    if( symbols ):
        symtree = get_symbols(addr,xlen)
    else:
        symtree = intervaltree.IntervalTree()
    olen = xlen

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
#    p,add,col,mm,_ = vdb.pointer.color(addr,vdb.arch.pointer_size)
#    nm = gdb.parse_and_eval(f"(void*)({addr})")
    current_symbol = None
    next_color = -1
    sym_color = None
    line = 0

    rowf = row_format.value
    while(len(data) > 0 ):
        dc = data[:16]
        data = data[16:]
        p,_,_,_,_ = vdb.pointer.color(xaddr,vdb.arch.pointer_size)
        cnt = 0
        l = ""
        t = ""
        s = ""
        pointer_string=""
        value_string=""
        parr = []
        step = vdb.arch.pointer_size // 8
        if( pointers ):
            for poffset in range(0,16,step):
#                print("poffset = '%s'" % poffset )
#                print("step = '%s'" % step )
                pbytes = dc[poffset:poffset+step]
                # XXX get byteorder from global
                pint = int.from_bytes(pbytes,"little")
#                print("pint = '%s'" % pint )
                ps,pu = vdb.pointer.chain( pint, vdb.arch.pointer_size, chaindepth, test_for_ascii = False )
                if( not pu ):
                    pointer_string += ps
                    pointer_string += pc_separator.value

        for d in dc:
#            xs = symtree[xaddr+cnt]
            xs = get_annotation( xaddr + cnt, symtree )
            nsym = None
            for x in xs:
#                print("x[0] = '%s'" % x[0] )
#                print("x[1] = '%s'" % x[1] )
#                print("xaddr = '%s'" % xaddr )
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
                        if( values ):
#                            print("nsym = '%s'" % nsym )
#                            value = gdb.execute(f"p {nsym}",False,True)
                            try:
                                value = gdb.parse_and_eval(f"{nsym}")
                            except:
                                value = ""
                            value = str(value)
#                            print("value = '%s'" % value )
                            if( len(value) > 0 and value[-1] == "\n" ):
                                value = value[:-1]
                            if( len(value) > 0 and value.find("\n") == -1 ):
                                value_string += vdb.color.color(value,sym_color)
                                value_string += " "
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
        print(rowf.format(**locals()))
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

def annotate_var( addr,gval, gtype, name ):
    print("annotate_var( %s, %20s, %s, %s )" % (addr,gval,gtype,name) )
    print("gtype = '%s'" % gtype )
    gtype = gtype.strip_typedefs()
#    gval = gval.cast(gtype)
    print("gtype = '%s'" % gtype )
#        print("gval = '%s'" % gval )
    ol = vdb.layout.object_layout( gtype, gval )
    print("ol.type = '%s'" % (ol.type,) )
    print("ol = '%s'" % ol )
    print("ol.object = '%s'" % ol.object )
        
    for bd in ol.descriptors:
        print("bd.object = '%s'" % bd.object )
        print("bd.object.final = '%s'" % (bd.object.final,) )
        print("bd.object.byte_offset = '%s'" % (bd.object.byte_offset,) )
        print("bd.object.size = '%s'" % (bd.object.size,) )
        print("bd.object.type = '%s'" % (bd.object.type,) )
        print("bd.object.type.code = '%s'" % vdb.util.gdb_type_code(bd.object.type.code) )
        if( bd.object.final and bd.object.byte_offset >= 0 and bd.object.size > 0 ):
            print("bd.prefix = '%s'" % (bd.prefix,) )
            if( bd.prefix is None ):
                continue
            ent = bd.name()
            if( len(ent) > 2 and ent.startswith("::") ):
                ent = ent[2:]
            ent = vdb.shorten.symbol(ent)
            dotpos = ent.find(".")
            if( dotpos != -1 and name is not None ):
                ent = name + ent[dotpos:]

            addr = int(addr)
#            print("bd.object.size = '%s'" % bd.object.size )
#            print("(addr+bd.object.byte_offset) = '%s'" % (addr+bd.object.byte_offset) )
#            print("(addr+bd.object.byte_offset+bd.object.size) = '%s'" % (addr+bd.object.byte_offset+bd.object.size) )
            annotation_tree[addr+bd.object.byte_offset:addr+bd.object.byte_offset+bd.object.size] = ent
#        print("annotation_tree = '%s'" % annotation_tree )

def annotate_block( block ):
    if( block.is_static or block.is_global ):
        return
#    print("block.is_static = '%s'" % (block.is_static,) )
#    print("block.is_global = '%s'" % (block.is_global,) )
#    if( block.function is None ):
#        return
    print("block.function = '%s'" % (block.function,) )
    print("block.superblock = '%s'" % (block.superblock,) )
    for i in block:
        try:
            v = gdb.selected_frame().read_var(i.name)
            if( v.address is not None ):
                annotate_var( v.address,v, v.type, i.name )
        except:
            traceback.print_exc()
            pass
    if( block.superblock ):
        annotate_block( block.superblock )

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
        annotate_block( fr.block() )
        print("annotation_tree = '%s'" % annotation_tree )
    elif( len(argv) == 1 ):
        print("Automatically annotating variable %s" % argv[0] )
        varname = argv[0]
        var = gdb.parse_and_eval(varname)
        print("var = '%s'" % var )
        annotate_var( var.address,var, var.type, varname )
    else:
        print("Usage: hexdump annotate <addr> <len> <text> or <addr> <typename>")
    print("Annotated {}".format(argv))


def call_hexdump( argv ):
#    argv = gdb.string_to_argv(arg)
    colorspec = "sma"
    if( len(argv) == 0 ):
        print(cmd_hexdump.__doc__)
        return
    pointers = False
    values = False
    chainlen = -1
    if( argv[0].startswith("/") ):
        argv[0] = argv[0][1:]
        m = re.search("p[0-9]*",argv[0])
        if( m is not None ):
            pointers = True
            try:
                chainlen = int(argv[0][1:])
            except:
                pass
            argv[0] = argv[0].replace(m.group(0),"")

        if( argv[0].find("v") != -1 ):
            values = True
            argv[0] = argv[0].replace("v","")

        if( len(argv[0]) > 0 ):
            print("Unknown argument %s" % argv[0])
            return
        argv = argv[1:]
    if( len(argv) > 0 and argv[0] == "annotate" ):
        annotate( argv[1:] )
    else:
        addr = None
        xlen = None
        if( len(argv) == 1 ):
            addr = vdb.util.gint("(void*)" + argv[0])
            hexdump(addr,pointers=pointers,chaindepth=chainlen,values=values)
        elif( len(argv) == 2 ):
            addr = vdb.util.gint("(void*)" + argv[0])
            xlen = vdb.util.gint(argv[1])
            hexdump(addr,xlen,pointers=pointers,chaindepth=chainlen,values=values)
        else:
            print(cmd_hexdump.__doc__)
    return



class cmd_hexdump (vdb.command.command):
    """Shows a hexdump of a specified memory range

The hexdump will output coloured pointer offsets according to the vmmap information as well as coloured bytes for when
it has some known annotations (like static variables or previously registered annotations). You are encouraged for raw
memory that you parse to write code to be able to annotate bytes yourself.

hexdump[/p#|v] <addr> [<len>]               - shows a hexdump of <len> or vdb-hexdump-default-len bytes

hexdump/p#                                  - In the annotation text, show pointer chains of (aligned) pointers with max length of #
hexdump/v                                   - In case of annotated known variables, print their pretty printed values too

hexdump annotate <varname>                  - annotates the variable <varname> according to the type information known to gdb
hexdump annotate <addres> <type>            - annotates the given address like a variable of type <type>
hexdump annotate <addres> <length> <text>   - arbitrary annotation of a length of bytes with a given text (to mark intresting memory locations)
hexdump annotate frame                      - Checks the current frame for known addresses of local variables and annotates those.

We recommend having an alias hd = hexdump in your .gdbinit
"""

    def __init__ (self):
        super (cmd_hexdump, self).__init__ ("hexdump", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:
            call_hexdump(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_hexdump()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
