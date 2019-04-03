#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.pointer
import vdb.util
import vdb.shorten
import vdb.command


import gdb

import string
import traceback
import re


color_head       = vdb.config.parameter("vdb-hexdump-colors-header",                "#ffa",    gdb_type = vdb.config.PARAM_COLOUR)

default_len = vdb.config.parameter("vdb-hexdump-default-len",8*16)


color_list = vdb.config.parameter("vdb-hexdump-colors-symbols", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,on_set  = vdb.config.split_colors)


symre=re.compile("0x[0-9a-fA-F]* <([^+]*)(\+[0-9]*)*>")
def hexdump( addr, xlen = -1 ):
    if( xlen == -1):
        xlen = default_len.value
    olen = xlen
    plen = 64//4
    print(vdb.color.color(f'  {" "*plen}  0  1  2  3   4  5  6  7    8  9  A  B   C  D  E  F   01234567 89ABCDEF',color_head.value))
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
    nm = gdb.parse_and_eval(f"(void*)({addr})")
    current_symbol = None
    next_color = -1
    sym_color = None
    while(len(data) > 0 ):
        dc = data[:16]
        data = data[16:]
        p,_,_,_ = vdb.pointer.color(xaddr,64)
        cnt = 0
        l = ""
        t = ""
        s = ""
        for d in dc:
            nm = gdb.parse_and_eval(f"(void*)({xaddr+cnt})")
            m=symre.match(str(nm))
            if( m ):
#                print("m.group(0) = '%s'" % m.group(0) )
#                print("m.group(1) = '%s'" % m.group(1) )
                nsym = m.group(1)
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

def call_hexdump( argv ):
#    argv = gdb.string_to_argv(arg)
    colorspec = "sma"
    if( len(argv) == 0 ):
        print("You should at least tell me what to dump")
        return
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
            call_hexdump(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_hexdump()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
