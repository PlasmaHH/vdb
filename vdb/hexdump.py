#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.pointer
import vdb.util
import traceback

import gdb

import string
import re

def hexdump( addr, xlen = 8*16 ):
    olen = xlen
    plen = 64//4
    print(f'  {" "*plen}  0  1  2  3   4  5  6  7    8  9  A  B   C  D  E  F    01234567 89ABCDEF')
    data = vdb.memory.read(addr,xlen)
    if( data is None ):
        data = vdb.memory.read(addr,1)
        if( data is not None ):
            data = None
            while(data is None ):
                xlen -= 1
                data = vdb.memory.read(addr,xlen)
    if( data is None ):
        print(f"Can not access memory at 0x{addr}")
        return
    xaddr = addr
    while(len(data) > 0 ):
        dc = data[:16]
        data = data[16:]
        p,_ = vdb.pointer.color(xaddr,64)
        cnt = 0
        l = ""
        t = ""
        for d in dc:
            d = int.from_bytes(d,"little")
            l += f"{d:02x} "
            c = chr(d)
            if( c in string.printable and not ( c in "\t\n\r\v") ):
                t += c
            else:
                t += "."
            cnt += 1
            if( cnt == 8 ):
                t += " "
                l += "-"
            if( cnt % 4 == 0 ):
                l += " "
#        print("len(t) = '%s'" % len(t) )
        print(f"{p}: {l} {t}")
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

def call_hexdump( arg ):
    argv = gdb.string_to_argv(arg)
    colorspec = "sma"
    if( len(argv) == 0 ):
        print("You should at least tell me what to dump")
        return
    addr = None
    xlen = None
    if( len(argv) == 1 ):
        addr = vdb.util.xint(argv[0])
    elif( len(argv) == 2 ):
        addr = vdb.util.xint(argv[0])
        xlen = vdb.util.xint(argv[1])
    else:
        print("Usage: hexdump <addr> <len>")
        return
    hexdump(addr,xlen)



class cmd_hexdump (gdb.Command):
    """Run the backtrace without filters"""

    def __init__ (self):
        super (cmd_hexdump, self).__init__ ("xdump", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def invoke (self, arg, from_tty):
        try:
            call_hexdump(arg)
        except:
            traceback.print_exc()
            raise
            pass

cmd_hexdump()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
