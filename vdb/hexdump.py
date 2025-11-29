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
default_align = vdb.config.parameter("vdb-hexdump-default-align",False)

pc_separator = vdb.config.parameter("vdb-hexdump-pointer-chain-separator","|")
row_format = vdb.config.parameter("vdb-hexdump-row-format", "{p}: {l}{t} {s}{pointer_string}{value_string}")


color_list = vdb.config.parameter("vdb-hexdump-colors-symbols", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" , gdb_type = vdb.config.PARAM_COLOUR_LIST )
unknown_color = vdb.config.parameter("vdb-hexdump-colors-unknown-bytes", "#666666", gdb_type =vdb.config.PARAM_COLOUR )

def print_header( ):
    #pylint: disable=possibly-unused-variable
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

annotation_tree = intervaltree.IntervalTree()
default_sizes = { }

def _dump_tree( ):
    tbl = [ [ "From", "To", "Size", "Name" ] ]
    tbl.append(None)
    for x in annotation_tree:
        tbl.append( [ x[0], x[1], int(x[1]) - int(x[0]), vdb.shorten.symbol(x[2]) ] )
    vdb.util.print_table(tbl)

def get_annotation( xaddr, symtree ):
#    vdb.util.bark() # print("BARK")
#    print(f"{symtree=}")
#    print(f"{xaddr=}")
    xs = annotation_tree[xaddr]
    if( len(xs) == 0 ):
        xs = symtree[xaddr]
    return xs

def spacer_format( cnt, t, l ):
    t += (cnt-1)*" "
    l += (cnt)*"   "
    l += ((cnt-1)//4)*" "
    l += ((cnt+7)//8)*" "
    t += ((cnt+7)//8)*" "
    return (t,l)

def tile_format( cnt, t, l ):
    if( cnt == 8 ):
        t += " "
        l += "-"
    if( cnt % 4 == 0 ):
        l += " "
    return (t,l)

def hexdump( addr, xlen = -1, pointers = False, chaindepth = -1, values = False, symbols = True, align = None, uncached = False ):

    if( align is None ):
        align = default_align.value



    if( chaindepth < 0 ):
        chaindepth = default_chaindepth.value
    if( xlen == -1):
        xlen = default_sizes.get(addr,default_len.value)
    if( symbols ):
        symtree = vdb.memory.get_symbols(addr,xlen)
    else:
        symtree = intervaltree.IntervalTree()

    suppress = 0 # amount of bytes at the beginning to leave out
    if( align ): # needs to align to 16 bytes
        naddr = addr & ~0xf
        suppress = addr - naddr
        addr = naddr
        xlen += suppress

    olen = xlen

#    print(f"hexdump reads {addr:#0x}")
    data = vdb.memory.read_u(uncached,addr,xlen,partial=True)
#    print(f"{type(data)=}")
#    if( data is not None ):
#        print(f"{data.tobytes()=}")

    # Could not read data for whatever reason...
    if( data is None ):
#        print(f"vdb.memory.read({addr:#0x},xlen,True) => None")
        data = vdb.memory.read_u(uncached,addr+suppress,1)
        if( data is not None ):
            data = None
            while(data is None ):
                xlen -= 1
                data = vdb.memory.read_u(uncached,addr,xlen)
    if( data is None ):
        print(f"Can not access memory at {addr:#0x}")
        return
#    print(f"{type(data)=}")
#    print(f"{type(data[0])=}")

    xaddr = addr
#    p,add,col,mm,_ = vdb.pointer.color(addr,vdb.arch.pointer_size)
#    nm = gdb.parse_and_eval(f"(void*)({addr})")
    current_symbol = None
    next_color = -1
    sym_color = None
    line = 0

    rowf = row_format.value

    if( len(data) > 0 ):
        vdb.memory.print_legend( )
    #pylint: disable=possibly-unused-variable
    while(len(data) > 0 ):
#        print(f"{data=}")
        dc = data[:16]
#        print(f"{dc=}")
        data = data[16:]
#        print(f"{dc.tobytes()=}")
#        print(f"{data.tobytes()=}")
        p,_,_,_,_ = vdb.pointer.color(xaddr,vdb.arch.pointer_size)
        cnt = 0
        l = ""
        t = ""
        s = ""
        pointer_string=""
        value_string=""
        parr = []
        step = vdb.arch.pointer_size // 8
        # XXX Suppress the output of the pointers also when at least one of their bytes is suppressed
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

#        print(f"{type(dc)=}")
#        print(f"{type(dc[0])=}")
        for d in dc:
#            vdb.util.inspect(dc)
#            vdb.util.inspect(d)
#            if( isinstance(d,int) ):
#                d=d.to_bytes()
#            print(f"{type(d)=}")
#            print(f"1{d=}")
#            d = bytes(d)
#            print(f"2{d=}")
            if( suppress ):
                suppress -= 1
                l += "   "
                t += " "
                cnt += 1
                t,l = tile_format(cnt,t,l)
                continue
#            xs = symtree[xaddr+cnt]
#            print("")
#            print(f"xaddr = {int(xaddr):#0x}" if xaddr is not None else "xaddr = None")
#            print(f"{cnt=}")
            xs = get_annotation( xaddr + cnt, symtree )
#            print(f"{xs=}")
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

            if( d == ... ):
                if( sym_color is None ):
                    sym_color = unknown_color.value
                l += vdb.color.color("?? ",sym_color)
                t += vdb.color.color("?",sym_color)
            else:
                d = int.from_bytes(d,"little")
                l += vdb.color.color(f"{d:02x} ",sym_color)
                c = chr(d)
                if( c in string.printable and not ( c in "\t\n\r\v\f") ):
                    t += vdb.color.color(c,sym_color)
                else:
                    t += vdb.color.color(".",sym_color)
            cnt += 1
            t,l = tile_format(cnt,t,l)
        cnt = (16-cnt)
        t,l = spacer_format(cnt,t,l)
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

def annotate_range( addr, length, name ):
    annotation_tree[addr:addr+length] = name

def annotate_var( addr,gval, gtype, name ):

    gtype = gtype.strip_typedefs()

    ol = vdb.layout.object_layout( gtype, gval )

    addr = int(addr)
    abc = ol.flatten()
    print(f"{len(abc)=}")
    for _,oname,obj in ol.flatten()[0]:
#        print(f"{obj=}")
#        print(f"{type(addr)=}")
#        print(f"{type(obj.byte_offset)=}")
#        print(f"{type(obj.size)=}")
        annotation_tree[addr+obj.byte_offset:addr+obj.byte_offset+obj.size] = oname

def annotate_block( block ):
    if( block.is_static or block.is_global ):
        return
#    print("block.is_static = '%s'" % (block.is_static,) )
#    print("block.is_global = '%s'" % (block.is_global,) )
#    if( block.function is None ):
#        return
#    print("block.function = '%s'" % (block.function,) )
#    print("block.superblock = '%s'" % (block.superblock,) )
    for i in block:
        try:
#            print("i.is_argument = '%s'" % (i.is_argument,) )
#            print("i.name = '%s'" % (i.name,) )
            v = gdb.selected_frame().read_var(i.name)
            if( v.address is not None ):
                annotate_var( v.address,v, v.type, i.name )
        except:
            vdb.print_exc()
#            pass
    if( block.superblock ):
        annotate_block( block.superblock )

def annotate( argv ):
#    global annotation_tree
    if( len(argv) == 2 ):
        addr = vdb.util.gint( argv[0] )
        ttype = argv[1]
        gtype = gdb.lookup_type( ttype )
#        global default_sizes
        default_sizes[addr] = gtype.sizeof
        gval = gdb.parse_and_eval(f"*({ttype}*)({addr})")
        annotate_var( addr,gval,gtype,"")
    elif( len(argv) == 3):
        addr = vdb.util.gint( argv[0] )
        tlen = vdb.util.xint( argv[1] )
        txt = argv[2]
        annotate_range(addr,tlen,txt)
    elif( len(argv) == 1 and argv[0] == "frame" ):
        fr = gdb.selected_frame()
        annotate_block( fr.block() )
#        print("annotation_tree = '%s'" % annotation_tree )
    elif( len(argv) == 1 ):
        print(f"Automatically annotating variable {argv[0]}")
        varname = argv[0]
        var = gdb.parse_and_eval(varname)
        print(f"var = '{var}'")
        annotate_var( var.address,var, var.type, varname )
    else:
        print("Usage: hexdump annotate <addr> <len> <text> or <addr> <typename>")
    print(f"Annotated {argv}")


def call_hexdump( argv, flags ):
#    argv = gdb.string_to_argv(arg)
    if( len(argv) == 0 ):
        print(cmd_hexdump.__doc__)
        return
    pointers = False
    values = False
    align = None
    uncached = False
    chainlen = -1

    m = re.search("p[0-9]*",flags)
    if( m is not None ):
        pointers = True
        try:
            chainlen = int(flags[1:])
        except:
            pass
        flags = flags.replace(m.group(0),"")

    # Maybe we want a "flags consume" object thing?

    if( flags.find("u") != -1 ):
        uncached = True
        flags = flags.replace("u","")

    if( flags.find("v") != -1 ):
        values = True
        flags = flags.replace("v","")

    if( flags.find("a") != -1 ):
        align = True
        flags = flags.replace("a","")

    if( len(flags) > 0 ):
        print(f"Unknown flags {flags}")
        return

    if( len(argv) > 0 and argv[0] == "annotate" ):
        annotate( argv[1:] )
    else:
        addr = None
        xlen = None
        if( len(argv) == 1 ):

            oaddr = None
            olen = -1
            # Try to detect if its a variable or a pointer
            obj = gdb.parse_and_eval(argv[0])
#            print(f"{obj=}")
            otype = obj.type
#            print(f"{otype=}")
            ptype = otype.strip_typedefs()
#            print(f"{ptype=}")
            dtype = ptype
            if( ptype.code == gdb.TYPE_CODE_PTR ):
#                print("PTR")
                oaddr = vdb.util.gint("(void*)" + argv[0])
                dtype = ptype.target()
            elif( ptype.code == gdb.TYPE_CODE_REF ):
#                print("REF")
                oaddr = int(obj.address)
                dtype = ptype.target()
            elif( ptype.code == gdb.TYPE_CODE_INT ):
                oaddr = vdb.util.gint("(void*)" + argv[0])
            else: # just some object/variable
#                print("ELSE")
                oaddr = int(obj.address)
#            print(f"{oaddr=:#0x}")
#            print(f"{dtype=}")
#            print(f"{olen=}")
            # in case its a (ptr/ref) struct we hexdump that one only
            if( dtype.code == gdb.TYPE_CODE_STRUCT ):
                olen = dtype.sizeof
#            print(f"{olen=}")

            hexdump(oaddr,olen,pointers=pointers,chaindepth=chainlen,values=values,align=align,uncached=uncached)
        elif( len(argv) == 2 ):
            addr = vdb.util.gint("(void*)" + argv[0])
            xlen = vdb.util.gint(argv[1])
            hexdump(addr,xlen,pointers=pointers,chaindepth=chainlen,values=values,align=align,uncached=uncached)
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
hexdump/a                                   - Output addresses 16 byte aligned

hexdump annotate <varname>                  - annotates the variable <varname> according to the type information known to gdb
hexdump annotate <addres> <type>            - annotates the given address like a variable of type <type>
hexdump annotate <addres> <length> <text>   - arbitrary annotation of a length of bytes with a given text (to mark intresting memory locations)
hexdump annotate frame                      - Checks the current frame for known addresses of local variables and annotates those.

We recommend having an alias hd = hexdump in your .gdbinit
"""

    def __init__ (self):
        super ().__init__ ("hexdump", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = True

    def do_invoke (self, argv):
        argv,flags = self.flags(argv)
        call_hexdump(argv,flags)
        self.dont_repeat()

cmd_hexdump()

# TODO/BUG/XXX/ETC
# When first byte of a hd is a variable that is 1 byte in size, it will not be coloured
# BUG: When memory is not accessible within the last few (one?) bytes of a hexdump, all will be displayed as 0

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
