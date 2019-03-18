#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.shorten
import vdb.color

import gdb

import re
import traceback

asm_colors = [
        ( "j.*", "#f0f" ),
        ( "mov.*", "#0ff" ),
        ( "cmp.*|test.*", "#f99" ),
        ( "call.*", "#6666ff" ),
        ( "ret.*", "#8f9" ),
        ]

pre_colors = [
        ( "lock.*","#f0f" ),
        ( "rep.*","#f29" ),
        ]


next_marker = vdb.config.parameter("vdb-asm-next-marker", " → " )
next_mark_ptr = vdb.config.parameter("vdb-asm-next-mark-pointer", True )
shorten_header = vdb.config.parameter("vdb-asm-shorten-header", False )
offset_fmt = vdb.config.parameter("vdb-asm-offset-format", " <+{offset:<{maxlen}}>:" )

color_ns       = vdb.config.parameter("vdb-asm-colors-namespace",   "#ddf", gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-asm-colors-function",    "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_marker   = vdb.config.parameter("vdb-asm-colors-next-marker", "#0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_addr     = vdb.config.parameter("vdb-asm-colors-addr",        None,   gdb_type = vdb.config.PARAM_COLOUR)
color_offset   = vdb.config.parameter("vdb-asm-colors-offset",      "#444", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#059", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix   = vdb.config.parameter("vdb-asm-colors-prefix",      "#f29", gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic = vdb.config.parameter("vdb-asm-colors-mnemonic",    None,   gdb_type = vdb.config.PARAM_COLOUR)
color_args     = vdb.config.parameter("vdb-asm-colors-args",        "#99f", gdb_type = vdb.config.PARAM_COLOUR)
asm_showspec   = vdb.config.parameter("vdb-asm-showspec", "maobnprT" )


class instruction( ):

    def __init__( self ):
        self.mnemonic = None
        self.args = None
        self.reference = None
        self.target_address = None
        self.target_name = None
#        self.target_offset = None
        self.target_of = []
        self.jump_arrows = []
        self.address = None
        self.offset = None
        self.bytes = None
        self.marked = False
        self.prefix = ""
        self.infix = ""

class listing( ):

    def __init__( self ):
        self.function = None
        self.instructions = []
        self.by_addr = {}
        self.maxoffset = 0
        self.maxbytes = 0
        self.maxmnemoic = 0
        self.maxargs = 0
        self.start = 0
        self.end = 0
        self.finished = False

    def color_address( self, addr, marked ):
        mlen = 64//4
        if( next_mark_ptr and marked ):
            return vdb.color.color(f"0x{addr:0{mlen}x}",color_marker.value)
        elif( len(color_addr.value) > 0 ):
            return vdb.color.color(f"0x{addr:0{mlen}x}",color_addr.value)
        else:
            return vdb.pointer.color(addr,64)[0]

    # XXX generic enough for utils?
    def color_relist( self, s, l ):
        for r,c in l:
            if( re.match(r,s) ):
                return vdb.color.color(s,c)
        return s

    def color_mnemonic( self, mnemonic ):
        if( len(color_mnemonic.value) > 0 ):
            return vdb.color.color(mnemonic,color_mnemonic.value)
        else:
            return self.color_relist(mnemonic,asm_colors)

    def color_prefix( self, prefix ):
        if( len(color_prefix.value) > 0 ):
            return vdb.color.color(prefix,color_prefix.value)
        else:
            return self.color_relist(prefix,pre_colors)

    def finish( self ):
        self.finished = True

    def lazy_finish( self ):
        if( self.finished ):
            return
        self.finish()

    def print( self, showspec = "maobnprT" ):
        self.lazy_finish()
        print(f"Instructions in range 0x{self.start:x} - 0x{self.end:x} of {self.function}")
        for i in self.instructions:
            if( "m" in showspec ):
                if( i.marked ):
                    line = vdb.color.color(next_marker.value,color_marker.value)
                else:
                    line = " " * len(next_marker.value)
            if( "a" in showspec ):
                line += self.color_address( i.address, i.marked )
            if( "o" in showspec ):
                line += vdb.color.color(offset_fmt.value.format(offset = i.offset, maxlen = self.maxoffset ),color_offset.value)
            if( "b" in showspec ):
                line += vdb.color.color(f" {' '.join(i.bytes):<{self.maxbytes*3}}",color_bytes.value)
            aslen = 0
            xline = line + "123456789012345678901234567890"
#            print(xline)
            if( "n" in showspec ):
                pre = self.color_prefix(i.prefix)
                mne = self.color_mnemonic(i.mnemonic)
                mxe = pre + i.infix + mne
                mlen = len(i.prefix) + len(i.infix) + len(i.mnemonic)
                aslen += mlen
                if( i.args is not None ):
                    mlen = self.maxmnemoic - mlen
                else:
                    mlen = 0
                aslen += mlen + 1
#                print("mxe = '%s'" % mxe )
                line += f" {mxe}{' '*mlen}"
#            print("aslen = '%s'" % aslen )
#            print(line+"*")
            if( "p" in showspec ):
                if( i.args is not None ):
                    aslen += self.maxargs + 1
                    line += vdb.color.color(f" {i.args:{self.maxargs}}",color_args.value)
            maxlen = self.maxmnemoic+self.maxargs+2
#            print("maxlen = '%s'" % maxlen )
#            print("aslen = '%s'" % aslen )
#            print("self.maxmnemoic = '%s'" % self.maxmnemoic )
#            print("self.maxargs = '%s'" % self.maxargs )
#            print(line+"|")
            if( aslen < maxlen ):
                fillup = maxlen - aslen
#                print("fillup = '%s'" % fillup )
                line += " " * fillup
            line += " "
            if( "r" in showspec ):
                if( i.reference is not None ):
                    line += vdb.shorte.symbol(i.reference)
            if( any((c in showspec) for c in "tT" ) ):
#                if( i.target_address is not None ):
#                    line += i.target_address
                if( "T" in showspec ):
                    if( i.target_name is not None ):
                        line += vdb.shorten.symbol(i.target_name)


            print(line)

    def add( self, ins ):
        self.finished = False
        self.instructions.append(ins)
        self.maxoffset = max(self.maxoffset,len(ins.offset))
        self.maxbytes = max(self.maxbytes,len(ins.bytes))
        if( ins.args is not None ):
            self.maxmnemoic = max(self.maxmnemoic,len(ins.prefix) + 1 + len(ins.mnemonic) )
            self.maxargs = max(self.maxargs,len(ins.args))
        if( len(ins.prefix) > 0 ):
            ins.infix = " "
        self.by_addr[ins.address] = ins


x86_prefixes = set([ "rep" ])

def parse_from_gdb( arg ):
    ret = listing()
    prefixes = x86_prefixes

    dis = gdb.execute(f'disassemble/r {arg}',False,True)
    linere = re.compile("(=>)*\s*(0x[0-9a-f]*)\s*<\+([0-9]*)>:\s*([^<]*)(<[^+]*(.*)>)*")
    funcre = re.compile("for function (.*):")
    bytere = re.compile("^[0-9a-fA-F][0-9a-fA-F]$")
    current_function=""
#    print("dis = '%s'" % dis )
    for line in dis.splitlines():
        ins = instruction()
        fm=re.search(funcre,line)
        if( fm ):
            ret.function = fm.group(1)
            current_function = "<" + fm.group(1)
            continue
        m=re.search(linere,line)
        if( m ):
            tokens = line.split()
            marker = m.group(1)
            if( marker is not None ):
                ins.marked = True
                tokens = tokens[1:]
#            print("tokens = '%s'" % tokens )
            ins.address = vdb.util.xint(tokens[0])
            if( ret.start == 0 ):
                ret.start = ins.address
            ret.end = max(ret.end,ins.address)
            ins.offset = tokens[1][2:-2]
            tpos = 1
            ibytes = []
            while( tpos < len(tokens) ):
                tpos += 1
                tok = tokens[tpos]
                if( bytere.match(tok) ):
                    ibytes.append( tok )
                else:
                    break
            ins.bytes = ibytes
            tokens = tokens[tpos:]
            tpos = 0
            if( tokens[tpos] in prefixes ):
                ins.prefix = tokens[tpos]
                tpos += 1
            ins.mnemonic = tokens[tpos]
            tpos += 1
            if( len(tokens) > tpos ):
                ins.args = tokens[tpos]
                tpos += 1
            print("len(tokens) = '%s'" % len(tokens) )
            print("tpos = '%s'" % tpos )
            if( len(tokens) > tpos ):
                print("tokens[tpos] = '%s'" % tokens[tpos] )
                if( tokens[tpos] == "#" ):
                    ins.reference = " ".join(tokens[tpos+1:])
                    print("ins.reference = '%s'" % ins.reference )
                else:
                    ins.target_address = tokens[tpos-1]
                    ins.target_name = " ".join(tokens[tpos:])
            print("tokens = '%s'" % tokens[tpos:] )
            ret.add(ins)
            continue

            address = m.group(2)
            offset = m.group(3)
            rest = m.group(4)
            function = m.group(5)
            jumpoffset = m.group(6)
            restl = rest.split(" ")
            for ac in asm_colors:
                if( re.match(ac[0],restl[0]) ):
                    restl[0] = vdb.color.color(restl[0],ac[1])
                    break
#					print("m = '%s'" % m )
            if( function is None ):
                function = ""
            else:
                if( function.startswith(current_function) ):
                    function = f"<current function{jumpoffset}>"
                else:
                    function = vdb.shorten.symbol(function)
            rest = " ".join(restl)
            line = ""
            if( marker is not None ):
                line += vdb.color.color(f"{marker:<2} ",color_marker.value)
                line += vdb.color.color(f"{address} ",color_marker.value)
                line += f"<+{offset:<4}>:  {rest}{function}"
            else:
                line += f"   {address} <+{offset:<4}>:  {rest}{function}"
            print(line)
            continue
        if( line in set(["End of assembler dump."]) ):
            continue
        print(f"Don't know what to do with '{line}'")
#			print("m = '%s'" % m )
    return ret

def parse_from( arg ):
    # other disssembler options go here
    return parse_from_gdb(arg)

def disassemble( arg ):
    listing = parse_from(arg)
    listing.print(asm_showspec.value)


class Dis (gdb.Command):
    """Disassemble with bells and whistels"""

    def __init__ (self):
        super (Dis, self).__init__ ("dis", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def invoke (self, arg, from_tty):
        try:
            disassemble( arg )
        except:
            traceback.print_exc()
            raise
            pass

Dis()





# vim: tabstop=4 shiftwidth=4 expandtab ft=python
