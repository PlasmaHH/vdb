#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.shorten
import vdb.color
import vdb.pointer
import vdb.dot
import vdb.command
import vdb.arch
import vdb.register
import vdb.memory

import gdb

import re
import traceback
import sys
import os
import time

asm_colors = [
        ( "j.*", "#f0f" ),
        ( "b.*", "#f0f" ),
        ( "mov.*", "#0ff" ),
        ( "cmp.*|test.*|cmov.*", "#f99" ),
        ( "call.*", "#6666ff" ),
        ( "ret.*", "#8f9" ),
        ( "nop.*" ,"#338" ),
        ( "pxor.*|punpckl.*", "#aa6" ),
        ( "sub.*|add.*|imul.*|mul.*|div.*|dec.*|inc.*|neg.*", "#909" ),
        ( "xor.*|shr.*|and.*|or.*", "#da4" ),
        ( "push.*|pop.*|lea.*", "#080" ),
        ( "hlt.*|syscall.*|int.*", "#a11" ),
        ( "XXXX", "#904449" ),
        ]

asm_colors_dot = [
        ( "j.*", "#f000f0" ),
        ( "b.*", "#f000f0" ),
        ( "mov.*", "#007f7f" ),
        ( "cmp.*|test.*", "#f09090" ),
        ( "call.*", "#6666ff" ),
        ( "ret.*", "#308020" ),
        ( "nop.*" ,"#303080" ),
        ]

pre_colors = [
        ( "lock.*","#f0f" ),
        ( "rep.*","#f29" ),
        ( "bnd.*","#f08" )
        ]

pre_colors_dot = [
        ( "lock.*","#f000f0" ),
        ( "rep.*","#f02090" ),
        ]

def invalidate_cache( c ):
    global parse_cache
    parse_cache = {}

next_marker = vdb.config.parameter("vdb-asm-next-marker", " → " )
next_marker_dot = vdb.config.parameter("vdb-asm-next-marker-dot", " → " )

next_mark_ptr     = vdb.config.parameter("vdb-asm-next-mark-pointer", True )
shorten_header    = vdb.config.parameter("vdb-asm-shorten-header", False )
prefer_linear_dot = vdb.config.parameter("vdb-asm-prefer-linear-dot",False)
debug_registers = vdb.config.parameter("vdb-asm-debug-registers",False, on_set = invalidate_cache )
debug = vdb.config.parameter("vdb-asm-debug-all",False, on_set = invalidate_cache )

offset_fmt = vdb.config.parameter("vdb-asm-offset-format", "<{offset:<+{maxlen}}>:" )
offset_txt_fmt = vdb.config.parameter("vdb-asm-text-offset-format", "<+{offset:<{maxlen}}>:" )
offset_fmt_dot = vdb.config.parameter("vdb-asm-offset-format-dot", " <{offset:<+{maxlen}}>" )
offset_txt_fmt_dot = vdb.config.parameter("vdb-asm-text-offset-format-dot", " <+{offset:<{maxlen}}>" )

color_ns       = vdb.config.parameter("vdb-asm-colors-namespace",   "#ddf", gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-asm-colors-function",    "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_marker   = vdb.config.parameter("vdb-asm-colors-next-marker", "#0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_xmarker  = vdb.config.parameter("vdb-asm-colors-marker",      "#049", gdb_type = vdb.config.PARAM_COLOUR)
color_addr     = vdb.config.parameter("vdb-asm-colors-addr",        None,   gdb_type = vdb.config.PARAM_COLOUR)
color_offset   = vdb.config.parameter("vdb-asm-colors-offset",      "#444", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#059", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix   = vdb.config.parameter("vdb-asm-colors-prefix",      None,   gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic = vdb.config.parameter("vdb-asm-colors-mnemonic",    None,   gdb_type = vdb.config.PARAM_COLOUR)
color_args     = vdb.config.parameter("vdb-asm-colors-args",        "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_var      = vdb.config.parameter("vdb-asm-colors-variable",    "#fc8", gdb_type = vdb.config.PARAM_COLOUR)
color_location = vdb.config.parameter("vdb-asm-colors-location",    "#08a", gdb_type = vdb.config.PARAM_COLOUR)



color_ns_dot       = vdb.config.parameter("vdb-asm-colors-namespace-dot",       "#d0d0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_function_dot = vdb.config.parameter("vdb-asm-colors-function-dot",        "#9090f0", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes_dot    = vdb.config.parameter("vdb-asm-colors-bytes-dot",           "#9090f0", gdb_type = vdb.config.PARAM_COLOUR)
color_marker_dot   = vdb.config.parameter("vdb-asm-colors-next-marker-dot",     "#008000", gdb_type = vdb.config.PARAM_COLOUR)
color_addr_dot     = vdb.config.parameter("vdb-asm-colors-addr-dot",            "#0000c0", gdb_type = vdb.config.PARAM_COLOUR)
color_offset_dot   = vdb.config.parameter("vdb-asm-colors-offset-dot",          "#909090", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes_dot    = vdb.config.parameter("vdb-asm-colors-bytes-dot",           "#005090", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix_dot   = vdb.config.parameter("vdb-asm-colors-prefix-dot",               None, gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic_dot = vdb.config.parameter("vdb-asm-colors-mnemonic-dot",             None, gdb_type = vdb.config.PARAM_COLOUR)
color_args_dot     = vdb.config.parameter("vdb-asm-colors-args-dot",            "#3030a0", gdb_type = vdb.config.PARAM_COLOUR)

color_jump_false_dot = vdb.config.parameter("vdb-asm-colors-jump-false-dot", "#ff0000", gdb_type = vdb.config.PARAM_COLOUR)
color_jump_true_dot  = vdb.config.parameter("vdb-asm-colors-jump-true-dot",  "#00ff00", gdb_type = vdb.config.PARAM_COLOUR)
color_jump_dot       = vdb.config.parameter("vdb-asm-colors-jump-dot",       "#000088", gdb_type = vdb.config.PARAM_COLOUR)
color_call_dot       = vdb.config.parameter("vdb-asm-colors-call-dot",       "#6600ff", gdb_type = vdb.config.PARAM_COLOUR)



nonfunc_bytes      = vdb.config.parameter("vdb-asm-nonfunction-bytes",16)
history_limit      = vdb.config.parameter("vdb-asm-history-limit",4)
tree_prefer_right  = vdb.config.parameter("vdb-asm-tree-prefer-right",False)
asm_showspec       = vdb.config.parameter("vdb-asm-showspec", "maodbnpTrjhc" )
asm_showspec_dot   = vdb.config.parameter("vdb-asm-showspec-dot", "maobnpTr" )
asm_tailspec       = vdb.config.parameter("vdb-asm-tailspec", "axndD" )
asm_sort           = vdb.config.parameter("vdb-asm-sort", True )
dot_fonts          = vdb.config.parameter("vdb-asm-font-dot", "Inconsolata,Source Code Pro,DejaVu Sans Mono,Lucida Console,Roboto Mono,Droid Sans Mono,OCR-A,Courier" )

callgrind_events   = vdb.config.parameter("vdb-asm-callgrind-events", "Ir,CEst", gdb_type = vdb.config.PARAM_ARRAY )
callgrind_jumps    = vdb.config.parameter("vdb-asm-callgrind-show-jumps", True )
header_repeat      = vdb.config.parameter("vdb-asm-header-repeat", 50 )
direct_output      = vdb.config.parameter("vdb-asm-direct-output", True )
gv_limit           = vdb.config.parameter("vdb-asm-variable-expansion-limit", 3 )

callgrind_eventmap = {} # name to index
callgrind_data = {}
from_tty = None


color_list = vdb.config.parameter("vdb-asm-colors-jumps", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,gdb_type = vdb.config.PARAM_COLOUR_LIST )

def wrap_shorten( fname ):
    return fname
    # we can get multiple things that are not function names, try to shorten only really for things that look like
    # templates
    try:
        if( fname.startswith("<") and fname.endswith(">") ):
            xfname = fname[1:-1]
            if( xfname.find("<") != -1 ):
                fname = "<" + vdb.shorten.symbol(xfname) + ">"
    except:
        pass
    return fname

def get_syscall( nr ):
    if( vdb.enabled("syscall") ):
        return vdb.syscall.get(nr)
    else:
        return None


reg_altlists = {}

# might be useful to put elsewhere for other archs and features
def gen_altlist( ):
    import vdb.register
    global reg_altlists
    for pr in vdb.register.possible_registers:
        if( type(pr) is tuple ):
            for rn in pr:
                nl = list(pr)
                nl.remove(rn)
                nl = [rn] + nl
                reg_altlists[rn] = nl
#    print("reg_altlists = '%s'" % (reg_altlists,) )

def reg_alts( reg ):
    if( len(reg_altlists) == 0 ):
        gen_altlist()
    return reg_altlists.get(reg,[reg])

def reg_reg( possible_registers, regfrom, regto ):
    try:
        if( regfrom.startswith("fs:0") ):
            add = regfrom[3:]
            oldmem = vdb.memory.read(f"$fs_base + {add}",vdb.arch.pointer_size//8)
            oldmem = oldmem.cast("P")
            oldval = oldmem[0]
        else:
            oldval,_ = possible_registers.get(regfrom,None)
            if( oldval is None ):
                oldval,_ = possible_registers.get(vdb.register.altname(regfrom),None)

        if( oldval is not None ):
            possible_registers.set( regto, oldval )
    except:
#        traceback.print_exc()
        pass

ix = -1
def next_index( ):
    global ix
    ix += 1
    return ix

# similar to register_set a wrapper around a dict that stores possible flag values
class flag_set:

    def __init__( self ):
        self.flags = {}

    def set( self, name, value ):
        self.flags[name] = value

    def get( self, name ):
        return self.flags.get(name,None)

    def clone( self ):
        ret = flag_set()
        ret.flags = self.flags.copy()
        return ret

    def __str__( self ):
        ret = "{"
        for f,v in self.flags.items():
            ret += f"{f}={v},"
        ret += "}"
        return ret

    def __repr__( self ):
        return str(self)

# a wrapper around a register dict that can deal with alternative register names
class register_set:

    def __init__( self ):
        self.values = {}

    def clone( self ):
        ret = register_set()
        ret.values = self.values.copy()
        return ret

    # Sets the value of a register, possible removing all alternative names that may be present
    def set( self, name, value, remove_alts = True ):
        if( remove_alts ):
            for rname in reg_alts(name):
                self.values.pop(rname,None)

        if( value is None ):
            self.values.pop(name,None)
            return

        try:
            value.fetch_lazy()
        except AttributeError: # not a gdb.Value
            pass
        except gdb.MemoryError: 
            # a lazy values memory access failed, don't save anything, in fact since we don't konw what it could have
            # been, its better to pretend its unknown
            self.values.pop(name,None)
            return

        self.values[name] = int(value)

    def get( self, name, altval = None ):
        for rname in reg_alts(name):
            rv = self.values.get(rname,None)
            if( rv is not None ):
                return ( rv, rname )
        return ( altval, name )

    def merge( self, other ):
        for n,v in other.values.items():
            self.set( n, v )

    def copy( self, other, rlist ):
        for rn in rlist:
            rv,rn = other.get( rn )
            if( rv is not None ):
                self.set( rn,rv )

    def remove( self, rname ):
        for rname in reg_alts(rname):
            self.values.pop(rname,None)

    def __str__( self ):
        ret = "{"
        for r,v in self.values.items():
            ret += f"{r}={v:#0x},"
        ret += "}"
        return ret

    def __repr__( self ):
        return str(self)



class asm_arg( ):

    def __init__( self, target, arg ):
        self.register = None
        self.immediate = None
        self.immediate_hex = False
        self.dereference = None
        self.prefix = None
        self.offset = None
        self.target = target
        self.jmp_target = None
        self.multiplier = None
        self.add_register = None
        self.asterisk = False
        try:
            self.parse(arg)
        except:
            traceback.print_exc()
            print("Failed to parse " + arg)
            raise

    def parse( self, arg ):
#        print("arg = '%s'" % (arg,) )
        oarg = arg
        if( arg[0] == "*" ):
            self.asterisk = True
            arg = arg[1:]

        if( arg[-1] == ")" ):
            self.dereference = True
            if( arg[0] == "(" ):
                arg = arg[1:-1]
            else:
                argv = arg.split("(")
#                print("argv = '%s'" % (argv,) )
                po = argv[0]
#                print("po = '%s'" % (po,) )
                if( po[0] == "%" ):
                    if( po[-1] == ":" ):
                        self.prefix = po[1:-1]
                else:
                    self.offset = vdb.util.rxint(po)
#                    print("self.offset = '%s'" % (self.offset,) )
                arg = argv[1][:-1]
#                print("arg = '%s'" % (arg,) )
                marg = arg.split(",")
#                print("marg = '%s'" % (marg,) )
                if( len(marg) == 2 ):
                    self._check(oarg)
                    pass
                elif( len(marg) == 3):
                    if( len(marg[0]) > 0 ):
                        self.add_register = marg[0][1:]
#                        print("self.add_register = '%s'" % (self.add_register,) )
                    self.register = marg[1][1:]
                    self.multiplier = vdb.util.rxint(marg[2])
                    self._check(oarg)
                    return

        if( arg[0] == "%" ):
            self.register = arg[1:]

        if( arg[0] == "$" ):
            if( arg.startswith("$0x") ):
                self.immediate_hex = True
            self.immediate = vdb.util.rxint( arg[1:] )

        if( arg.startswith("0x") ):
            self.jmp_target = vdb.util.rxint( arg )
        self._check(oarg)

    def _check(self,oarg):
        if( str(self) != oarg ):
            print("oarg = '%s'" % (oarg,) )
            print("str(self) = '%s'" % (str(self),) )
            self._dump()
            raise RuntimeError("Parser self check failed")

    # registers is a register_set object to possible get the value from
    # XXX At the moment we do not support prefixes
    def value( self, registers, target = None ):
        if( self.register is not None ):
            val,_ = registers.get( self.register )
#            print("self.register = '%s'" % (self.register,) )
#            print("val = '%s'" % (val,) )
#            print("self.offset = '%s'" % (self.offset,) )
            if( val is not None  ):
                if( self.offset is not None ):
                    val += self.offset
                if( self.dereference ):
                    castto = "P"
                    if( target is None ):
#                        print("val = '%s'" % (val,) )
                        dval = vdb.memory.read(val,vdb.arch.pointer_size//8)
                    else:
                        if( target.register[0] == "r" ):
                            dval = vdb.memory.read(val,8)
                        else:
                            dval = vdb.memory.read(val,4)
                            castto = "I"
                    if( dval is not None ):
                        dval = dval.cast(castto)[0]
                    return ( dval, val )
            return ( val, None )

        if( self.immediate is not None ):
            return ( self.immediate, None )

        return ( None, None )

    def __str__( self ):
        ret = ""
        if( self.asterisk ):
            ret +=  "*"
        if( self.prefix is not None ):
            ret += f"%{self.prefix}:"
        if( self.offset is not None ):
            ret += f"{self.offset:#0x}"
        if( self.dereference ):
            ret += "("
            if( self.multiplier is not None ):
                if( self.add_register is not None ):
                    ret += "%" + self.add_register
                ret += ","
            ret += "%" + self.register
            if( self.multiplier is not None ):
                ret += f",{self.multiplier}"
            ret += ")"
        elif( self.register is not None ):
            ret += "%" + self.register
        if( self.immediate is not None ):
            if( self.immediate_hex ):
                ret += f"${self.immediate:#0x}"
            else:
                ret += f"${self.immediate}"
        if( self.jmp_target is not None ):
            ret += f"{self.jmp_target:#0x}"
        return ret

    def __repr__( self ):
        return str(self)


    def _dump( self ):
        if( self.offset is None ):
            offset = "None"
        else:
            offset = f"{self.offset:#0x}"
        print(f"arg %{self.register}, ${self.immediate}, ({self.dereference}), {self.offset},,, T{self.target} :{self.prefix}:: {self.multiplier}*REG + {self.add_register} => {self}")

class instruction( ):

    def __init__( self ):
        self.mnemonic = None
        self.args = None
        self.arguments = []
        self.args_string = None
        self.reference = []
        self.targets = set()
        self.conditional_jump = False
        self.call = False
        self.return_ = False
        self.target_name = None
#        self.target_offset = None
        self.target_of = set()
        self.address = None
        self.offset = None
        self.bytes = None
        self.marked = False
        self.xmarked = False
        self.prefix = ""
        self.infix = ""
        self.jumparrows = ""
        self.arrowwidth = 0
        self.bt = None
        self.history = None
        self.bt_idx = None
        self.extra = []
        self.file_line = None
        self.possible_in_register_sets = []
        self.possible_out_register_sets = []

        self.possible_in_flag_sets = []
        self.possible_out_flag_sets = []
        self.next = None
        self.previous = None
        self.passes = 0
        self.file = None
        self.line = None

    def _gen_extra_regs( self, name, rs ):
        for prs in rs:
            self.add_extra(f"{name} {prs}")
            args = ""
            for a in self.arguments:
                av,aa = a.value(prs)
                if( av is not None ):
                    av = f"{av:#0x}"
                if( aa is not None ):
                    aa = f"{aa:#0x}"
                args += f",({av},@{aa})"
                if( a.target ):
                    args += "T"
            self.add_extra(f"ARG {args}")


    def _gen_extra( self ):
        self._gen_extra_regs( "INREG", self.possible_in_register_sets )
        self._gen_extra_regs( "OUTREG", self.possible_out_register_sets )
        for pfs in self.possible_in_flag_sets:
            self.add_extra(f"INFLG {pfs}")
        for pfs in self.possible_out_flag_sets:
            self.add_extra(f"OUTFLG {pfs}")

    def _gen_debug( self ):
        self.add_extra( f"self.args      : '{self.args}'")
        self.add_extra( f"self.targets   : '{self.targets}'")
        self.add_extra( f"self.target_of : '{self.target_of}'")

    def add_extra( self, s ):
        self.extra.append( (s,1,1) )

    def __str__( self ):
        ta = "None"
        if( len(self.targets) ):
            ta = ""
            for t in self.targets:
                ta += f"{t:#0x}"
        to = "("
        for target in self.target_of:
            to += f"{target:#0x}"
        to += ")"
        a = self.address
        if( a is None ):
            a = 0
        ret = f"INS @{a:x} => {ta} <={to}"
        return ret

class listing( ):

    def __init__( self ):
        self.function = None
        self.instructions = []
        # map from address to sources
        self.ins_map = {}
        self.by_addr = {}
        self.maxoffset = 0
        self.maxbytes = 0
        self.maxmnemoic = 0
        self.maxargs = 0
        self.start = 0
        self.end = 0
        self.finished = False
        self.current_branch = "a"
        self.bt_q = []
        self.var_addresses = None
        self.var_expressions = None
        self.function_header = None
        self.initial_registers = register_set()

    def sort( self ):
        self.instructions.sort( key = lambda x:( x.address, x ) )

    def color_address( self, addr, marked, xmarked ):
        mlen = 2 + vdb.arch.pointer_size // 4
        if( next_mark_ptr ):
            if( marked ):
                return vdb.color.colorl(f"{addr:#0{mlen}x}",color_marker.value)
            if( xmarked ):
                return vdb.color.colorl(f"{addr:#0{mlen}x}",color_xmarker.value)
        if( len(color_addr.value) > 0 ):
            return vdb.color.colorl(f"{addr:#0{mlen}x}",color_addr.value)
        else:
            pv,_,_,_,pl = vdb.pointer.color(addr,vdb.arch.pointer_size)
            return ( pv, pl )

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
    """
ascii mockup:
    For styles we should have special chars for every possible utf8 char and then replace them? or single variables that are filled by the style?

+---<   jmp A1
|
| +-<   jmp A2
| |
+--->   A1:
  |
+-+=>   A2: jmp A3
|
+--->   A3:


.
─
│
├
┤
┬
┴
┼
╭
╮
╯
╰
►
◄
◆

    UTF8 version mockup:
╭───◄   jmp A1
│
│ ╭─◄   jmp A2
│ │
╰───►   A1:
╰───→
  |
  ↑
╭─┴─◆   A2: jmp A3
  ▲
╭─┷─◆   A2: jmp A3
│
╰───►   A3:
"""
    def add_target( self,ins ):
#        print("add_target")
#        print("ins = '%s'" % ins )
        if( len(ins.targets) > 0  ):
            for tga in ins.targets:
#                print("tga = '%s'" % (tga,) )
                tgt = self.by_addr.get(tga,None)
#                print("tgt = '%s'" % (tgt,) )
                if( tgt is not None ):
                    tgt.target_of.add(ins.address)
#                print("tgt = '%s'" % (tgt,) )

    def finish( self ):
        global ix
        ix = -1

        def acolor ( s, idx ):
            if( idx >= 0 ):
                return vdb.color.mcolor(s,color_list.elements[idx % len(color_list.elements) ] )
            else:
                return s

        class arrow:
            def __init__( self, fr, to ):
                self.fr = fr
                self.to = to
                self.coloridx = next_index()
                self.lines = 0
                self.rows = 0
                self.done = False
                self.merger = None

            def __str__( self ):
                return f"{self.fr:#0x} -> {self.to:#0x}, c={self.coloridx},l={self.lines},r={self.rows},d={self.done}"

        def find_next( cl, ar ):
            clen = len(cl)
            if( tree_prefer_right.value ):
                r = range(clen-1,-1,-1)
            else:
                r = range(0,clen)

            for i in r:
                if( cl[i] is None ):
                    cl[i] = ar
                    return i
                if( cl[i].done ):
                    old = cl[i]
                    ar.merger = old
                    cl[i] = ar
                    return i

            cl += [ None ]
            cl[clen] = ar
            return clen

        def to_arrows( ins, cl, ignore_target = False  ):
#            print("###################")
            ret = []
            alen = 0
#            print("ins.address = '%x'" % ins.address )

#            print("current_lines = '%s'" % current_lines )
            ridx = 0
            doneleft = False
            leftarrow = None
            remove_indices = set()
            for cidx in range(0,len(cl)):
                ar = cl[cidx]
#                print("ar = '%s'" % ar )
                if( ar is None ):
                    # No vertical line expected here, lets see if we need some horizontal
                    if( leftarrow is not None ):
                        ret.append( ("-",leftarrow.coloridx) )
                    else:
                        ret.append( (" ",-1) )
                else: # c is not None here
                    if( ar.done ):
                        remove_indices.add(cidx)
                    if( ar.rows == 0 ):
                        # arrow starts here, so goes down
                        # but what if there already was another?
                        if( leftarrow is not None ):
                            if( ar.merger ):
                                ret.append( ("+",leftarrow.coloridx) )
                            else:
                                ret.append( ("T",leftarrow.coloridx) )
                        else:
                            if( ar.merger ):
                                if( ar.to == ar.fr ):
                                    ret.append( ("^",ar.coloridx) )
                                else:
                                    ret.append( ("#",ar.coloridx) )
                            elif( ins.address in ins.targets ):
                                ret.append( (" ",-1) )
                            else:
                                ret.append( ("v",ar.coloridx) )
                            leftarrow = ar
                    else:
                        if( ar.done ):
                            if( leftarrow is not None ):
                                ret.append( ("u",leftarrow.coloridx) )
                            else:
                                ret.append( ("^",ar.coloridx) )
                                leftarrow = ar
                        else:
                            # arrow already had a start
                            if( ar.lines == 0 ):
                                ret.append( ("|",ar.coloridx) )
                            else:
                                ret.append( ("|",ar.coloridx) )
                        ar.lines += 1
                    ar.rows += 1
                alen += 1
                # back to the current_line loop from here
            if( leftarrow is not None ):
                if( ins.address in ins.targets ):
                    ret.append( ("Q",leftarrow.coloridx) )
                elif( leftarrow.to == ins.address ):
                    ret.append( (">",leftarrow.coloridx) )
                else:
                    ret.append( ("<",leftarrow.coloridx) )
                alen += 1
            for i in remove_indices:
                cl[i] = None
            return ( ret, alen )

        self.do_backtrack()

        self.finished = True
        current_lines = []
        adict = {}

        # Seperate loop for the later needs all informaation always
        for ins in self.instructions:
            self.add_target(ins)

        for ins in self.instructions:
#            print("INS_----------------------------------")
#            print("ins = '%s'" % ins )
            self.add_target(ins)

            # Remove those arrows that end here, whiche are always from above. Those that start here are not yet in the
            # list
            for cl in current_lines:
                if( cl is not None ):
                    # One of the arrow ends targets this instruction
                    if( cl.to == ins.address or cl.fr == ins.address ):
                        cl.done = True
#                        print("DONE_01 cl = '%s'" % cl )


            # Now add the new ones
            for tgt in ins.targets:
                if( self.start <= tgt <= self.end ):
                    if( tgt == ins.address ):
                        ar = arrow(ins.address,tgt)
                        find_next( current_lines, ar )
                        ar.done = True
#                        print("ADD2 %s" % ar)
                    # Target is further down, add an arrow
                    elif( tgt > ins.address ):
                        ar = arrow(ins.address,tgt)
                        find_next( current_lines, ar )
#                        print("ADD1 %s" % ar)
            if( len(ins.target_of) > 0 ):
                # We are a target of something, lets have a look if those are further down
                for target in ins.target_of :
                    if( target > ins.address ):
                        # yep, further down, we need a new arrow
                        ar = arrow(target,ins.address)
                        find_next( current_lines, ar )
            (ins.jumparrows,ins.arrowwidth) = to_arrows(ins,current_lines)

        while( self.optimize_arrows() ):
            pass

        for ins in self.instructions:
            nj = ""
            for ja,jl in ins.jumparrows:
                nj += acolor(ja,jl)
            ins.jumparrows = nj

        self.maxarrows = len(current_lines)+1

        if( debug.value ):
            for ins in self.instructions:
                ins._gen_debug()

    def optimize_arrows( self ):
        start = -1
        col = 0
        ecol = 5000
        ret = False
        for ii in range(0,len(self.instructions) ):
            ins = self.instructions[ii]
#            print("ins.address = '0x%x'" % (ins.address,) )
#            print("ii = '%s'" % (ii,) )
#            print("len(ins.jumparrows) = '%s'" % (len(ins.jumparrows),) )
            for ji in range(col,len(ins.jumparrows)-1):
#                print("ji = '%s'" % (ji,) )
                ja,jl=ins.jumparrows[ji]
                jan,jln=ins.jumparrows[ji+1]
                if( jan != "-" and jan != " " ):
#                    print("jan = '%s'" % (jan,) )
                    start = -1
                    col = 0
                    continue

                if( ja == "v" ):
                    start = ii
                    col = ji
#                    print("=====================")
#                    print("start = %s, ja = '%s'" % (start,ja,) )
                    ecol = len(ins.jumparrows)+10
                    break
                elif( ja == "|" or ja == "#" ):
#                    print("ja = '%s'" % (ja,) )
#                    print("start = '%s'" % (start,) )
                    break
                elif( ja == "^" and start > 0 ):
#                    print("col = '%s'" % (col,) )
#                    print("ecol = '%s'" % (ecol,) )
#                    print("start = '%s'" % (start,) )
#                    print("ii = '%s'" % (ii,) )
                    for ni in range(start,ii+1):
                        mi = self.instructions[ni]
                        ma,ml = mi.jumparrows[col]
#                        print("ma = '%s'" % (ma,) )
                        if( col == 0 ):
                            for rc in range(col,ecol):
                                ret = True
                                mi.jumparrows[rc] = ( " ", -1 )
                            mi.jumparrows[ecol] = (ma,ml)
                        else:
                            for rc in range(col,ecol):
                                ret = True
                                pja = mi.jumparrows[rc-1]
                                pjn = mi.jumparrows[rc+1]
                                if( pja[0] == "|" or pja[0] == " "):
                                    mi.jumparrows[rc] = ( " ", -1 )
                                else:
                                    mi.jumparrows[rc] = pjn
                            mi.jumparrows[ecol] = (ma,ml)
                    break
                else:
#                    print("else ja = '%s'" % (ja,) )
                    start = -1
                    col = 0
#            print("start = '%s'" % (start,) )
            if( start >= 0 ):
                xnc = 0
                for nc in range(col+1,len(ins.jumparrows)):
#                    print("nc = '%s'" % (nc,) )
#                    print("ins.jumparrows[nc] = '%s'" % (ins.jumparrows[nc],) )
                    if( ins.jumparrows[nc][0] == "-" or ins.jumparrows[nc][0] == " " ):
                        xnc = max(nc,xnc)
                    else:
#                        ins.jumparrows[nc] = ("X",0)
                        break
                ecol = min(ecol,xnc)
#                print("xnc = '%s'" % (xnc,) )
#                print("ecol = '%s'" % (ecol,) )

        return ret

    def lazy_finish( self ):
        if( self.finished ):
            return
        self.finish()

    def next_backtrack( self ):
        ret = self.current_branch
        self.current_branch = chr(ord(ret)+1)
        return ret

    def q_backtrack_next( self, idx, bt, limit ):
        self.bt_q.append( (idx,bt,limit) )

    def backtrack_next( self, idx, bt, limit ):
        ins=self.instructions[idx]
        if( ins.bt is not None ):
            return
        ins.bt = "%s%s" % (bt[0],bt[1])
        if( limit == 0 ):
            return
        if( idx == 0 ):
            return
        for src in self.ins_map.get(ins.address,()):
            src=self.by_addr[src]
            nb = self.next_backtrack()
            ins.bt += nb
            self.q_backtrack_next( src.bt_idx , ( bt[0]+1, nb ), limit - 1 )

        self.q_backtrack_next( idx-1, (bt[0]+1,bt[1]), limit - 1 )


    def do_backtrack( self ):
        self.ins_map = {}
        idx = 0
        midx = None
        self.current_branch = "a"
#        if( any((c in showspec) for c in "hH" ) ):
        rec = gdb.current_recording()
#        else:
#            rec = None
        inh = {}
#        print("rec = '%s'" % (rec,) )
        if( rec is not None ):
            try:
                rins = rec.instruction_history
            except NotImplementedError:
#                print("not implemented")
                rins = None
#            print("rins = '%s'" % rins )
            if( rins is not None ):
                for h in rins:
#                    print("h = '%s'" % h )
#                    print("h.pc = '%s'" % h.pc )
#                    print("h.decoded = '%s'" % h.decoded )
#                    print("h.data = '%s'" % h.data.tolist() )
                    hn = h.number
                    if( h.is_speculative ):
                        hn = -hn
                    inh.setdefault(h.pc,[]).append(str(hn))
        for i in self.instructions:
            if( rec is not None ):
                h = inh.get(i.address,None)
                if( h is not None ):
                    i.history = h[-history_limit.value:]
#                    print("h = '%s'" % h )
            i.bt_idx = idx
            i.bt = None
            for sr in i.target_of:
                self.ins_map.setdefault(i.address,set()).add(sr)
            for tgt in i.targets:
                self.ins_map.setdefault(tgt,set()).add(i.address)
            if( i.marked ):
                midx = idx
            idx += 1

#        print("midx = '%s'" % midx )
        # Just don't do anything if we have no marker
        if( midx is None ):
            return

        self.q_backtrack_next( midx, (0,""), 10 )

        while( len(self.bt_q) > 0 ):
            x_q = self.bt_q
            self.bt_q = []
            for x in x_q:
                self.backtrack_next( x[0], x[1], x[2] )

    def compute_context( self, context, marked_line ):
        context_start = None
        context_end = None
        if( context is not None ):
            if( context[0] is not None and context[1] is not None ):
                # old behaviour
                context_start = marked_line - context[0]
                context_end = marked_line + context[1] + 1
            elif( context[0] is not None ):
                context_start = marked_line - context[0]
                context_end = marked_line + 1
            elif( context[1] is not None ):
                context_start = marked_line 
                context_end = marked_line + context[1] + 1
        return ( context_start, context_end )

    m_trans = str.maketrans("v^-|<>u#Q~T+","╭╰─│◄►┴├⥀◆┬┼" )
    p_trans = str.maketrans("v^-|<>u#Q~T+","|  |   |  ||" )

    def to_str( self, showspec = "maodbnprT", context = None, marked = None, source = False, suppress_header = False ):
        self.lazy_finish()
        hf = self.function
        if( shorten_header.value ):
            hf = wrap_shorten(hf)

        marked_line = None
        cnt = 0
        context_start = None
        context_end = None

        otbl = []

        otmap = {0:0}

        extra_marker = None
        file_line = ""

        cg_events = []
        cg_header = []
        for evn in callgrind_events.elements:
            ix = callgrind_eventmap.get(evn,None)
            if( ix is not None ):
                cg_events.append(ix)
                cg_header.append( (evn,",,bold",0) )
            else:
                vdb.util.log(f"Specified callgrind event {evn} not present in any loaded file", level = 4)

        headfields = [    ("m" ,[ ("Marker",",,bold",0,0) ])
                        , ("a" ,[("Address",",,bold")])
                        , ("j" ,[ ("History",",,bold",0,0)])
                        , ("hH",[ ("History",",,bold",0,0) ])
                        , ("o" ,[ ("Offset",",,bold",0,0)])
                        , ("c" ,cg_header)
                        , ("d" ,[ ("Jumps",",,bold",0,0) ])
                        , ("b" ,[("Bytes",",,bold",0,0)])
                        , ("n" ,[("Mnemonic",",,bold",0,0)])
                        , ("p" ,[("Args",",,bold",0,0)])
                        , ("r" ,[("Reference",",,bold",0,0) ])
                        , ("tT",[("Target",",,bold",0,0) ])
                        ]
        header = []
        for sp,hf in headfields:
            if( any((s in showspec) for s in sp ) ):
                header += hf

        cg_columns = 0
        if( "c" in showspec ):
            cg_columns = len(cg_header)
                        
        for i in self.instructions:
            cg_extra = []
            if( header_repeat.value is not None and suppress_header != True ):
                if( header_repeat.value > 0 ):
                    if( cnt % header_repeat.value == 0 ):
                        otbl.append( header )
                elif( cnt == 0 ):
                    otbl.append( header )

            if( source ):
                if( i.file is None ):
                    i.file,i.line = info_line( i.address )
                fl = f"{i.file}:{i.line}"
                if( fl != file_line ):
                    file_line = fl
                    i.file_line = file_line
            else:
                i.file_line = None

            if( marked is not None):
                if( i.address == marked ):
                    i.xmarked = True
                    extra_marker = cnt
                elif( marked > i.address ):
                    if( (marked - i.address) < len(i.bytes) ):
                        extra_marker = cnt
            line = []
            otbl.append(line)
            prejump = 0
            postjump = 0
            if( "m" in showspec ):
                prejump += 1
                if( i.marked ):
                    line.append( ( vdb.color.color(next_marker.value,color_marker.value), len(next_marker.value) ) )
                    marked_line = cnt
                    context_start, context_end = self.compute_context(context,marked_line)
                elif( i.xmarked ):
                    line.append( ( vdb.color.color(next_marker.value,color_xmarker.value), len(next_marker.value) ) )
                else:
                    line.append( "" )

            if( "a" in showspec ):
                prejump += 1
                line.append( self.color_address( i.address, i.marked, i.xmarked ))


            if( "j" in showspec ):
                prejump += 1
                line.append( i.bt )


            if( any((c in showspec) for c in "hH" ) ):
                prejump += 1
#                line.append("H")
                if( i.history is not None ):
                    if( "h" in showspec ):
                        line.append( i.history[0] )
                    else:
                        line.append( ",".join(i.history) )
                else:
                    line.append(None)

            if( "o" in showspec ):
                prejump += 1
                try:
#                    io = vdb.util.xint(i.offset)
                    io = int(i.offset)
                    line.append( vdb.color.colorl(offset_fmt.value.format(offset = io, maxlen = self.maxoffset ),color_offset.value))
                except:
                    line.append( vdb.color.colorl(offset_txt_fmt.value.format(offset = i.offset, maxlen = self.maxoffset ),color_offset.value))

            if( "c" in showspec ):

                ci = callgrind_data.get( i.address, None )
                if( ci is not None ):
                    for _,jump in ci.jumps.items():
                        cg_extra.append( (str(jump),1,1) )
                    for cge in cg_events:
                        cv = ci.event(cge)
                        if( cv == 0 ):
                            line.append( None )
                        else:
                            line.append( cv )
                else:
                    line += [None] * len(cg_events)

            jumparrows = None
            postarrows = None
            if( "d" in showspec ):
#                mt=str.maketrans("v^-|<>+#Q~I","╭╰─│◄►┴├⥀◆↑" )
                                    
                if( len(i.jumparrows) ):
                    ja=i.jumparrows.translate(self.m_trans)
                    pa=i.jumparrows.translate(self.p_trans).translate(self.m_trans)
                    fillup = " " * (self.maxarrows - i.arrowwidth)
                    jumparrows = (f"{ja}{fillup}", self.maxarrows)
                    postarrows = (f"{pa}{fillup}", self.maxarrows)
                    line.append( jumparrows )
                else:
                    line.append( "" )
                    postarrows = ""

            if( "b" in showspec ):
                postjump += 1
                line.append( vdb.color.colorl(f"{' '.join(i.bytes)}",color_bytes.value) )
            aslen = 0
#            xline = line + "123456789012345678901234567890"
#            print(xline)
            if( "n" in showspec ):
                postjump += 1
                pre = self.color_prefix(i.prefix)
                mne = self.color_mnemonic(i.mnemonic)
                mxe = pre + i.infix + mne
                mlen = len(i.prefix) + len(i.infix) + len(i.mnemonic)
#                aslen += mlen
#                if( i.args is not None ):
#                    mlen = self.maxmnemoic - mlen
#                else:
#                    mlen = 0
#                aslen += mlen + 1
#                print("mxe = '%s'" % mxe )
#                line.append( f" {mxe}{' '*mlen}")
                line.append( ( mxe, mlen ) )
#            line.append("%s = %s %s %s" % (mlen,len(i.prefix),len(i.infix),len(i.mnemonic)))
#            print("aslen = '%s'" % aslen )
#            print(line+"*")
            if( "p" in showspec ):
                if( i.args is not None ):
                    aslen += self.maxargs + 1
#                    args = ",".join(i.args)
                    args = i.args_string
#                    line.append( vdb.color.color(f" {i.args:{self.maxargs}}",color_args.value))
                    line.append( (vdb.color.color(f"{args}",color_args.value),len(args)) )
                else:
                    line.append(None)
#            maxlen = self.maxmnemoic+self.maxargs+2
#            print("maxlen = '%s'" % maxlen )
#            print("aslen = '%s'" % aslen )
#            print("self.maxmnemoic = '%s'" % self.maxmnemoic )
#            print("self.maxargs = '%s'" % self.maxargs )
#            print(line+"|")
#            if( aslen < maxlen ):
#                fillup = maxlen - aslen
#                print("fillup = '%s'" % fillup )
#                line.append( " " * fillup)

            if( "r" in showspec ):
                f = ""
                for r in i.reference:
                    f += wrap_shorten(r) + " "
                if( len(f) > 0 ):
                    f = f[:-1]
                    line.append(f)

            if( any((c in showspec) for c in "tT" ) ):
#                if( i.targets is not None ):
#                    line.append( i.targets)
                if( "T" in showspec ):
                    if( i.target_name is not None ):
                        line.append( wrap_shorten(i.target_name))


#            ret.append(line)
            cnt += 1
#            print("cnt = '%s'" % (cnt,) )
#            print("len(otbl) = '%s'" % (len(otbl),) )

#            print("i.file_line = '%s'" % (i.file_line,) )
            if( len(i.extra) > 0 or i.file_line is not None or len(cg_extra) > 0 ):
                fll = []
                if( i.file_line is not None ):
                    fll.append( (i.file_line,1,1) )
#                print("prejump = '%s'" % (prejump,) )
#                print("postjump = '%s'" % (postjump,) )
                for ex in i.extra + fll + cg_extra:
#                    print("ex = '%s'" % (ex,) )
                    pre = ( prejump + cg_columns) * [None]
                    post = (postjump-1) * [None]
                    if( postarrows is None ):
                        el = pre + post
                    else:
                        el = pre + [postarrows] + post
#                    el = ["m","a","h","H","o","d","BYTES" + str(len(line)-1)]
                    el.append(ex)
                    otbl.append(el)

            otmap[cnt] = len(otbl)
            if( context is not None and context_end is not None and context_end <= cnt ):
                break

        if( context_start is None and extra_marker is not None ):
            context_start, context_end = self.compute_context(context,extra_marker)

        if( context_start is not None ):
            if( context_start < 0 ):
                context_start = 0
            if( context_end > cnt ):
                context_end = cnt
            context_start = otmap[context_start]
            context_end = otmap[context_end]

        ret = otbl
        if( context_start is not None and context_end is not None ):
            ret = ret[context_start:context_end]


#        print("ret = '%s'" % ret )
        ret = vdb.util.format_table(ret,padbefore=" ",padafter="")
        if( self.function_header is not None ):
            hf = wrap_shorten(self.function_header)

        return f"Instructions in range {self.start:#0x} - {self.end:#0x} of {hf}\n{ret}"
#        return "\n".join(ret)

    def print( self, showspec = "maodbnprT", context = None, marked = None, source = False ):
        if( direct_output.value and from_tty ):
            os.write(1,self.to_str(showspec, context, marked,source).encode("utf-8"))
        else:
            print(self.to_str(showspec, context, marked,source))

    def color_dot_relist( self, s, l ):
        for r,c in l:
            if( re.match(r,s) ):
                return vdb.dot.color(s,c)
        return vdb.dot.dot_escape(s)


    def ins_to_dot( self, i, node, showspec ):
#        if( "m" in showspec ):
#            if( i.marked ):
#                line = vdb.color.color(next_marker.value,color_marker.value)
#            else:
#                line = " " * len(next_marker.value)
        tr = vdb.dot.tr()
        tr["align"] = "left"
        node.table.add(tr)

        plen = vdb.arch.pointer_size // 4

        if( "m" in showspec ):
            if( i.marked ):
                tr.td_raw(vdb.dot.color(next_marker_dot.value,color_marker_dot.value))
            else:
                tr.td_raw("&nbsp;")

        if( "a" in showspec ):
            tr.td_raw(vdb.dot.color(f"{i.address:#0{plen}x}",color_addr_dot.value))["port"] = str(i.address)

        if( "o" in showspec ):
            try:
                io = int(i.offset)
                tr.td_raw(vdb.dot.color(offset_fmt_dot.value.format(offset = io, maxlen = self.maxoffset),color_offset_dot.value))
            except:
                tr.td_raw(vdb.dot.color(offset_txt_fmt_dot.value.format(offset = i.offset, maxlen = self.maxoffset),color_offset_dot.value))

        if( "b" in showspec ):
            tr.td_raw(vdb.dot.color(' '.join(i.bytes),color_bytes_dot.value))

        if( "n" in showspec ):
            tr.td_raw("&nbsp;")
            txt = ""
            if( len(i.prefix) > 0 ):
                if( len(color_prefix_dot.value) > 0 ):
                    pcol = vdb.dot.color(i.prefix,color_prefix_dot.value)
                else:
                    pcol = self.color_dot_relist(i.prefix,pre_colors_dot)
                txt += pcol
                txt += "&nbsp;"

            if( len(color_mnemonic_dot.value) > 0 ):
                mcol = vdb.dot.color(i.mnemonic,color_mnemonic_dot.value)
            else:
                mcol = self.color_dot_relist(i.mnemonic,asm_colors_dot)
            txt += mcol
            tr.td_raw(txt)

        if( "p" in showspec ):
            if( i.args is not None ):
                tr.td_raw(vdb.dot.color(i.args,color_args_dot.value))
            else:
                tr.td_raw("&nbsp;")

        if( "r" in showspec ):
            f = ""
            for r in i.reference:
                f += wrap_shorten(r) + " "
            if( len(f) > 0 ):
                tr.td_raw(vdb.dot.color(f,color_function_dot.value))

        if( any((c in showspec) for c in "tT" ) ):
            if( "T" in showspec ):
                if( i.target_name is not None ):
                    tr.td_raw(vdb.dot.color(wrap_shorten(i.target_name),color_function_dot.value))

        for td in tr.tds:
            td["align"]="left"


    def to_dot( self,showspec ):
        self.lazy_finish()
        g = vdb.dot.graph("disassemble")
        g.node_attributes["fontname"] = dot_fonts.value

        node = None
        previous_node = None
        previous_instruction = None
        for ins in self.instructions:
            if( node is None or len(ins.target_of) > 0 ):
                node = g.node(ins.address)
                if( previous_node is not None ):
                    if( previous_instruction is not None and ( not previous_instruction.return_ ) ):
                        if( len(previous_instruction.targets) > 0  and not ( previous_instruction.conditional_jump or previous_instruction.call ) ):
                            pass
                        else:
                            e=previous_node.edge( ins.address )
                            if( previous_instruction and previous_instruction.conditional_jump ):
                                e["color"] = color_jump_false_dot.value
                            elif( previous_instruction and previous_instruction.call ):
                                e["color"] = color_call_dot.value
                    previous_node = None
                    previous_instruction = None
            if( node.table is None ):
                node.table = vdb.dot.table()
                node.table.attributes["border"] = "1"
                node.table.attributes["cellspacing"] = "0"
                node.table.attributes["cellborder"] = "0"
            self.ins_to_dot(ins,node,showspec)
            previous_node = node
            previous_instruction = ins
            if( len(ins.targets) > 0 and not ins.call ):
                for tgt in ins.targets:
                    port = None
                    if( tgt < ins.address ):
                        port = tgt
                    e=node.edge(tgt,port)
                    if( ins.conditional_jump ):
                        e["color"] = color_jump_true_dot.value
                    else:
                        e["color"] = color_jump_dot.value
                    if( prefer_linear_dot.value ):
                        e["constraint"] = "false"
                node = None
            if( ins.return_ ):
                node = None
        return g



    def add( self, ins ):
        self.finished = False
        self.instructions.append(ins)
        self.maxoffset = max(self.maxoffset,len(ins.offset))
        self.maxbytes = max(self.maxbytes,len(ins.bytes))
        if( ins.args is not None ):
            self.maxmnemoic = max(self.maxmnemoic,len(ins.prefix) + 1 + len(ins.mnemonic) )
            self.maxargs = max(self.maxargs,len(ins.args_string))
        if( len(ins.prefix) > 0 ):
            ins.infix = " "
        self.by_addr[ins.address] = ins
        # "up" jumping part of the target_of, the "down" jumping part is done in finish()
        self.add_target(ins)

x86_conditional_jump_mnemonics = set([ "jo", "jno", "js", "jns", "je", "jz", "jne", "jnz", "jb", "jnae", "jc", "jnb","jae","jnc","jbe","jna","ja","jnbe","jl","jng","jge","jnl","jle","jng","jg","jnle","jp","jnle","jp","jpe","jnp","jpo","jcxz","jecxz" ])
x86_unconditional_jump_mnemonics = set([ "jmp", "jmpq" ] )
x86_return_mnemonics = set (["ret","retq","iret"])
x86_call_mnemonics = set(["call","callq","int"])
x86_prefixes = set([ "rep","repe","repz","repne","repnz", "lock", "bnd" ])

call_preserved_registers = [ "rbx", "rsp", "rbp", "r12", "r13", "r14", "r15" ]

arm_conditional_suffixes = [ "eq","ne","cs","hs","cc","lo","mi","pl","vs","vc","hi","ls","ge","lt","gt","le" ]
arm_unconditional_jump_mnemonics = set([ "b", "bl", "blx" ] )
arm_conditional_jump_mnemonics = set()
for uj in arm_unconditional_jump_mnemonics:
    for csuf in arm_conditional_suffixes:
        arm_conditional_jump_mnemonics.add(uj+csuf)

#print("arm_conditional_jump_mnemonics = '%s'" % (arm_conditional_jump_mnemonics,) )

arm_return_mnemonics = set ([])
arm_call_mnemonics = set([])
arm_prefixes = set([ ])

mnemonics = {
        "i386:x86-64" : ( x86_prefixes , x86_conditional_jump_mnemonics, x86_unconditional_jump_mnemonics , x86_return_mnemonics , x86_call_mnemonics ),
        "arm" : ( arm_prefixes , arm_conditional_jump_mnemonics, arm_unconditional_jump_mnemonics , arm_return_mnemonics , arm_call_mnemonics ),

        }

pc_list = [ "rip", "eip", "ip", "pc" ]
last_working_pc = ""

class fake_frame:

    class fake_function:
        def __init__( self ):
            self.name = "__fake_function__"
        
    def __init__( self ):
        pass

    def read_register(self,reg):
        return None

    def function( self ):
        return self.fake_function()

    def block( self ):
        return []

def fix_marker( ls, alt = None ):
#    mark = vdb.util.gint("$rip")
    try:
        mark = vdb.util.gint(f"${last_working_pc}")
    except:
        try:
            mark = vdb.util.gint(alt)
        except:
            mark = None

    for i in ls.instructions:
#            print("%s == %s ? %s " % (i.address,mark,(i.address == mark)))
        if( i.address == mark ):
            i.marked = True
        else:
            i.marked = False
    ls.do_backtrack()
    return ls

parse_cache = {}

def split_args( in_args ):
#    vdb.util.bark() # print("BARK")
#    print("in_args = '%s'" % (in_args,) )
    args = in_args.split(",")
#    print("args = '%s'" % (args,) )
    ret = []
    in_brackets = False
    for arg in args:
        if( in_brackets ):
            ret[-1] += "," + arg
        else:
            ret.append(arg)
        # lets hope there is no nesting in any syntax, if yes we need full parsing
        if( arg.find("(") != -1 or arg.find("[") != -1 or arg.find("{") != -1 ):
            in_brackets = True
        if( arg.find(")") != -1 or arg.find("]") != -1 or arg.find("}") != -1 ):
            in_brackets = False

#    print("ret = '%s'" % (ret,) )
    if( ",".join(ret) != in_args ):
        print("in_args = '%s'" % (in_args,) )
        print("ret = '%s'" % (ret,) )
    return ret

class fake_symbol( gdb.Value ):

    def __init__( self, val, name ):
        super().__init__( val )
        self.name = name
        self.is_base_class = False

    def value( self, frame ):
        return frame.read_var( self.name )

def gather_vars( frame, lng, symlist, pval = None, prefix = "", reglist = None, level = 0 ):
    if( level >= gv_limit.value ):
        return ""
    level += 1
    ret = ""
    regindex = -1
    if( reglist is None ):
        regindex = 0
        # we have these list all over the place, save them in an architecture dependent object instead
        reglist = [ "rdi", "rsi", "rdx", "rcx", "r8", "r9" ]
    # TODO support float/double registers and vectors

    rbp = "rbp" # adapt for other archs
    
    rbpval = frame.read_register(rbp)
    if( rbpval is not None ):
        rbpval = int(rbpval)
#    print("rbpval = '%s'" % (rbpval,) )

    lng.initial_registers.merge( function_registers.get(frame.function().name,register_set() ) )
#    print("lng.initial_registers = '%s'" % (lng.initial_registers,) )

    if( debug.value ):
        print("symlist = '%s'" % (symlist,) )
    for b in symlist:
        if( debug.value ):
            print("b = '%s'" % (b,) )
            print("b.type = '%s'" % (b.type,) )
            print("b.name = '%s'" % (b.name,) )
            try:
                print("b.type.fields() = '%s'" % (b.type.fields(),) )
            except:
                print("fields() failed")
        bval = None
        baddr = None
        try:
            if( pval is None ):
                bval = b.value(frame)
                baddr= bval.address
#                print("bval = '%s'" % (bval,) )
            else:
                if( b.name is None ): # ignore anonymous structs/unions etc. for now
                    continue
                if( b.is_base_class ):
                    continue
                bval = pval[b.name]
                baddr= bval.address
        except:
            traceback.print_exc()
            pass

        try:
            bval = bval.dereference()
#            print("bval.type.fields() = '%s'" % (bval.type.fields(),) )
            ret += gather_vars( frame, lng, bval.type.fields() , bval, prefix + b.name + "->", [], level )
        except:
#            traceback.print_exc()
            pass
        try:
#            for f in b.type.fields():
#                print("f.name = '%s'" % (f.name,) )
#                print("bval[f.name] = '%s'" % (bval[f.name],) )
            ret += gather_vars( frame, lng, b.type.fields(), bval, prefix + b.name + ".", [], level )
        except:
#            traceback.print_exc()
            pass

        if( debug.value ):
            print("prefix = '%s'" % (prefix,) )
            print("b.name = '%s'" % (b.name,) )
            print("baddr = '%s'" % (baddr,) )
        if( baddr is not None ):
            lng.var_addresses[int(baddr)] = prefix + b.name

            boffset = int(baddr) - rbpval
            expr = f"{boffset:#0x}(%{rbp})"
            lng.var_expressions[expr] = prefix + b.name

        try:
            if( b.is_argument ):
                if( debug.value ):
                    print("b = '%s'" % (b,) )
                if( regindex >= 0 ):
                    if( debug.value ):
                        print("regindex = '%s'" % (regindex,) )
                        print("reglist[regindex] = '%s'" % (reglist[regindex],) )
                        print("bval = '%s'" % (bval,) )
                        print("bval.address = '%s'" % (bval.address,) )
                        print("type(lng.initial_registers) = '%s'" % (type(lng.initial_registers),) )
#                    lng.initial_registers[reglist[regindex]] = int(bval.address)
                    lng.initial_registers.set( reglist[regindex] , int(bval))
                    if( debug.value ):
                        print("lng.initial_registers = '%s'" % (lng.initial_registers,) )
                    regindex += 1
                ret += f" {b.name}"

                try:
                    ret += f"@{bval.address}"
                    boffset = int(baddr) - rbpval
                    ret += f"[{boffset:#0x}(%{rbp})]"
                except:
                    pass

                if( bval is not None ):
                    if( bval.type.tag is None ):
                        ret += f" = {bval}"
                    else:
                        ret += " = <...>"
                ret += ","
        except:
#            traceback.print_exc()
            pass
    if( debug.value ):
        print("ret = '%s'" % (ret,) )
        print("lng.var_addresses = '%s'" % (lng.var_addresses,) )
    return ret


ilinere = re.compile('Line ([0-9]*) of "(.*)"')

@vdb.util.memoize
def info_line( addr ):
    il = gdb.execute(f"info line *{addr:#0x}",False,True)
    m = ilinere.match(il)
    if( m is not None ):
        return ( m.group(2), m.group(1) )
#    print("il = '%s'" % (il,) )
    return (None,None)

def parse_from_gdb( arg, fakedata = None, arch = None, fakeframe = None, cached = True ):

#    print(f"parse_from_gdb(arg={arg},fakedata={len(fakedata)}, arch={arch}, fakeframe={fakeframe}, cached={cached}")
    global parse_cache

    key = arg

    if( len(arg) == 0 ):
        if( gdb.selected_thread() == None ):
            return listing()

#        gdb.execute(f"p $rip")
        global last_working_pc
        for pc in [ last_working_pc ] + pc_list:
            try:
#                key = gdb.execute(f"info symbol $rip",False,True)
                key = gdb.execute(f"info symbol ${pc}",False,True)
                last_working_pc = pc
                if( key.startswith("No symbol matches") ):
                    continue
#                print("pc = '%s'" % pc )
                break
            except:
                pass
#        print("key = '%s'" % key )
        key = re.sub(r" \+ [0-9]+","",key)

#    print("arg = '%s'" % arg )
#    print("key = '%s'" % key )

    ret = None
    if( not debug_registers.value and cached ):
        ret = parse_cache.get(key,None)
    ret = parse_cache.get(key,None)
#    print("ret = '%s'" % ret )
    if( ret is not None and fakedata is None ):
        return fix_marker(ret,arg)
    ret = listing()
#    vdb.util.bark() # print("BARK")
#    print("key = '%s'" % (key,) )
#    print("parse_cache = '%s'" % (parse_cache,) )


    prefixes = x86_prefixes
    conditional_jump_mnemonics = x86_conditional_jump_mnemonics
    unconditional_jump_mnemonics = x86_unconditional_jump_mnemonics
    return_mnemonics = x86_return_mnemonics
    call_mnemonics = x86_call_mnemonics

    archname="x86"
    try:
        if( arch is not None ):
            archname = arch
        else:
            archname = gdb.selected_frame().architecture().name()
            prefixes, conditional_jump_mnemonics, unconditional_jump_mnemonics, return_mnemonics, call_mnemonics = mnemonics[archname]
    except:
        print("Not configured for architecture %s, falling back to x86" % archname )
        pass

#    print("arg = '%s'" % (arg,) )
    if( fakedata is None ):
        t0 = time.time()
        dis = gdb.execute(f'disassemble/r {arg}',False,True)
        t1 = time.time()
#        print("t1-t0 = '%s'" % (t1-t0,) )
    else:
        dis = fakedata
#    print("dis = '%s'" % dis )
#    linere = re.compile("^(=>)*\s*(0x[0-9a-f]*)\s*<\+([0-9]*)>:\s*([^<]*)(<[^+]*(.*)>)*")
    linere = re.compile("^(=>)*\s*(0x[0-9a-f]*)(\s*<\+([0-9]*)>:)*\s*([^<]*)(<[^+]*(.*)>)*")
    funcre = re.compile("for function (.*):")
    rangere = re.compile("Dump of assembler code from (0x[0-9a-f]*) to (0x[0-9a-f]*):")
    bytere = re.compile("^[0-9a-fA-F][0-9a-fA-F]$")
    jmpre  = re.compile("^\*(0x[0-9a-fA-F]*)\(.*")
    cmpre  = re.compile("^\$(0x[0-9a-fA-F]*),.*")
    current_function=""
    last_cmp_immediate = 1

    markers = 0
    oldins = None

    for line in dis.splitlines():
        ins = instruction()
        ins.line = line
        fm=re.search(funcre,line)
        if( fm ):
            ret.function = fm.group(1)
            try:
                # try to demangle
                fsym = gdb.lookup_symbol(ret.function)
                ret.function = fsym[0].name
            except:
                pass
            current_function = "<" + fm.group(1)
            continue
        rr = re.search(rangere,line)
        if( rr ):
            continue
        if( line.startswith("Address range") ):
            continue
        m=re.search(linere,line)
        if( m ):
            tokens = line.split()
            marker = m.group(1)
            if( marker is not None ):
                ins.marked = True
                markers += 1
                tokens = tokens[1:]
#            print("tokens = '%s'" % tokens )
            # the dissamble version without <line+>
            if( tokens[0][-1] == ":" ):
                tokens[0] = tokens[0][:-1]
            elif( tokens[1][-1] != ":" ):
                while( tokens[1][-1] != ":" ):
#                    print("tokens[1][-1] = '%s'" % tokens[1][-1] )
                    tokens[1] += tokens[2]
#                    print("tokens[1] = '%s'" % tokens[1] )
                    del tokens[2]

            xtokens = []
#            print("tokens = '%s'" % tokens )
            while len(tokens) > 0:
                tok = tokens[0]
                if( len(xtokens) > 0 and xtokens[-1].endswith(",") ):
                    xtokens[-1] += tok
                else:
                    xtokens.append(tok)
                tokens = tokens[1:]
#            print("xtokens = '%s'" % xtokens )
            tokens = xtokens

            ins.address = vdb.util.xint(tokens[0])
            if( ret.start == 0 ):
                ret.start = ins.address
            else:
                ret.start = min(ret.start,ins.address)
            ret.end = max(ret.end,ins.address)
#            print("tokens[1] = '%s'" % tokens[1] )
            if( len(tokens[1]) < 2 or tokens[1][1] == "+" ):
                ins.offset = tokens[1][2:-2]
            else:
                ins.offset = tokens[1][1:-2]
#            print("ins.offset = '%s'" % ins.offset )
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
            if( ins.mnemonic in return_mnemonics ):
                ins.return_ = True
            if( len(tokens) > tpos ):
                ins.args = split_args(tokens[tpos])
                ins.args_string = tokens[tpos]
                tpos += 1

            if( ins.mnemonic in conditional_jump_mnemonics ):
                ins.conditional_jump = True
            if( ins.mnemonic.startswith("cmp") ):
                m = re.search(cmpre,ins.args_string)
#                print("m = '%s'" % m )
                if( m is not None ):
                    cmparg = m.group(1)
                    last_cmp_immediate = vdb.util.xint(cmparg)

            if( len(tokens) > tpos ):
#                print("tokens = '%s'" % (tokens,) )
#                print("tokens[tpos] = '%s'" % tokens[tpos] )
                if( tokens[tpos] == "#" ):
                    ins.reference.append( " ".join(tokens[tpos+1:]) )
#                    print("ins.reference = '%s'" % ins.reference )
                else:
                    if( ins.mnemonic not in unconditional_jump_mnemonics ):
                        ins.conditional_jump = True
#                    print("TARGET ADD '%s'" % tokens[tpos-1])
                    try:
                        ins.targets.add(vdb.util.xint(tokens[tpos-1]))
                    except:
                        pass
                    ins.target_name = " ".join(tokens[tpos:])
#            elif( ins.mnemonic in conditional_jump_mnemonics ):
            elif( ins.conditional_jump ):
#                print("CONDITIONAL JUMP? %s %s" % (ins.mnemonic, tokens ) )
                try:
                    ins.targets.add(vdb.util.xint(tokens[tpos-1]))
                except:
                    pass
            elif( ins.mnemonic in unconditional_jump_mnemonics ):
#                print("UNCONDITIONAL JUMP? %s %s" % (ins.mnemonic, tokens ) )
                m = re.search(jmpre,ins.args_string)
                if( m is not None ):
                    table = m.group(1)
                    cnt = 0
                    while True:
                        try:
                            jmpval = gdb.parse_and_eval(f"*((void**){table}+{cnt})")
#                        print("jmpval = '%s'" % jmpval )
                            if( jmpval == 0 ):
                                break
                        except gdb.MemoryError:
                            break
                        if( cnt > last_cmp_immediate ):
                            break
#                        print("last_cmp_immediate = '%s'" % last_cmp_immediate )
                        ins.targets.add(int(jmpval))
                        cnt += 1
                    ins.reference.append( f"{len(ins.targets)} computed jump targets " ) # + str(ins.targets)
#                    print("jmpval = '%s'" % jmpval )
#                    print("m = '%s'" % m )
#                    print("m.group(1) = '%s'" % m.group(1) )
#                    print("ins = '%s'" % ins )
                else:
                    try:
                        ins.targets.add(vdb.util.xint(tokens[tpos-1]))
                    except:
                        pass

            if( ins.mnemonic in call_mnemonics ):
                ins.call = True
                ins.conditional_jump = False
#            print("tokens = '%s'" % tokens[tpos:] )
            ret.add(ins)

            if( oldins is not None and oldins.mnemonic != "ret" ):
                oldins.next = ins
                ins.previous = oldins
            oldins = ins
            continue
        if( line in set(["End of assembler dump."]) ):
            continue
        if( len(line) == 0 ):
            continue
        print(f"Don't know what to do with '{line}'")
#			print("m = '%s'" % m )
    if( fakedata is None ):
        parse_cache[key] = ret
    if( markers == 0 ):
        ret = fix_marker(ret,arg)

    if( fakeframe is not None ):
        frame = fakeframe
    else:
        try:
            frame = gdb.selected_frame()
        except:
            frame = fake_frame()

    fun = frame.function()
#    print("fun.name = '%s'" % (fun.name,) )
#    print("ret.function = '%s'" % (ret.function,) )
#    print("ret.function = '%s'" % (ret.function,) )
#    print("fun.symtab = '%s'" % (fun.symtab,) )
    # only extract names from the block when we disassemble the current frame
    if( fun is not None and fun.name == ret.function ):
        block = frame.block()
    else:
        block = []
#    print("block = '%s'" % (block,) )
#    for b in block:
#        print("b = '%s'" % (b,) )
#        print("b.is_argument = '%s'" % (b.is_argument,) )
#        if( b.value(frame).type.tag is None ):
#            print("b.value(frame) = '%s'" % (b.value(frame),) )
#        print("b.value(frame).address = '%s'" % (b.value(frame).address,) )
    
    va = function_vars.get( ret.function, {} ).copy()
    ret.var_addresses = va.copy()
#    print("ret.var_addresses = '%s'" % (ret.var_addresses,) )
    ret.var_expressions = {}

    if( fun is None ):
        funhead = "????"
    else:
        funhead = ret.function

#    print("va = '%s'" % (va,) )
    for a,n in va.items():
#        print("a = '%s'" % (a,) )
        try:
            vv = frame.read_var(n)
#            print("vv = '%s'" % (vv,) )
#            print("vv.type = '%s'" % (vv.type,) )
            # XXX do we want to output this anywhere? 
#            gather_vars( frame, ret, vv.type.fields(), vv, n + "." )
            gather_vars( frame, ret, [ fake_symbol(vv,n) ], None, n + "." )

        except TypeError:
            pass
        except ValueError:
#            print(f"{n} not found in frame")
            # variable not recognized
            pass

    gv = gather_vars( frame, ret, block )

    if( len(gv) > 0 ):
        funhead += "(" + gv + ")"

    ret.function_header = funhead
#    print("var_addresses = '%s'" % (ret.var_addresses,) )
#    print("var_expressions = '%s'" % (ret.var_expressions,) )

    register_flow(ret,frame)
    return ret


flow_vtable = {}

movre = re.compile("([-]0x[0-9a-f]*)\((%[a-z]*)\),(%[a-z]*)")

def vt_flow_push( ins, frame, possible_registers, possible_flags ):
    vl,rname = possible_registers.get("sp")
    if( vl is not None ):
        vl = int(vl) - ( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl)

    return ( possible_registers, possible_flags )


def vt_flow_mov( ins, frame, possible_registers, possible_flags ):
    if( debug.value ):
        print()
        vdb.util.bark() # print("BARK")


    if( debug.value ):
        print("ins = '%s'" % (ins,) )
        print("ins.mnemonic = '%s'" % (ins.mnemonic,) )
        print("ins.args_string = '%s'" % (ins.args_string,) )
        print("ins.args = '%s'" % (ins.args,) )
        print("ins.arguments = '%s'" % (ins.arguments,) )

        print("possible_registers = '%s'" % (possible_registers,) )
        print("ins.possible_in_register_sets = '%s'" % (ins.possible_in_register_sets,) )
        print("ins.possible_out_register_sets = '%s'" % (ins.possible_out_register_sets,) )

    frm = ins.arguments[0]
    to  = ins.arguments[1]

    # the new register value will be...
    if( not to.dereference ):
        # We ignore any (initial frame setup) move of rsp to rbp to keep the value intact
        # XXX if we do it that way we can also from here on (backwards?) assume rsp=rbp. (likely just after it we
        # sub something from rsp, we should support basic calculations too)
        if( frm.register != "rsp" and to.register != "rbp" ):
            frmval,_ = frm.value( possible_registers )
            possible_registers.set( to.register, frmval )
        if( frm.register == "rsp" and to.register == "rbp" ):
            toval,_ = to.value( possible_registers )
            if( toval is not None ):
                possible_registers.set( "rsp", toval )

    if( debug.value ):
        print("possible_registers = '%s'" % (possible_registers,) )
        print("ins.possible_in_register_sets = '%s'" % (ins.possible_in_register_sets,) )
        print("ins.possible_out_register_sets = '%s'" % (ins.possible_out_register_sets,) )

    return ( possible_registers, possible_flags )

def vt_flow_sub( ins, frame, possible_registers, possible_flags ):
#    vdb.util.bark() # print("BARK")
#    print("ins.previous = '%s'" % (ins.previous,) )
#    print("ins = '%s'" % (ins,) )
#    print("ins.next = '%s'" % (ins.next,) )
#    print("frame = '%s'" % (frame,) )
#    print("possible_registers = '%s'" % (possible_registers,) )
#    print("ins.arguments[0] = '%s'" % (ins.arguments[0],) )
    sub,_ = ins.arguments[0].value( possible_registers )
#    print("sub = '%s'" % (sub,) )
#    print("ins.arguments[1] = '%s'" % (ins.arguments[1],) )
    tgtv,_ = ins.arguments[1].value( possible_registers )
#    print("tgtv = '0x%x'" % (tgtv,) )
    if( tgtv is not None and sub is not None):
        nv = tgtv - sub
        possible_registers.set( ins.arguments[1].register, nv )

    return ( possible_registers, possible_flags )

def vt_flow_test( ins, frame, possible_registers, possible_flags ):
#    print("ins = '%s'" % (ins,) )
    a0,_ = ins.arguments[0].value( possible_registers )
    a1,_ = ins.arguments[1].value( possible_registers )
#    print("a0 = '%s'" % (a0,) )
#    print("a1 = '%s'" % (a1,) )
    if( a0 is not None and a1 is not None ):
        t = a0 & a1
        possible_flags.set("ZF",t == 0 )
        # XXX add SF and PF support as soon as some other place needs it
        ins.possible_flag_sets.append( possible_flags )
    # No changes in registers, so just
    return ( possible_registers, possible_flags )

def vt_flow_xor( ins, frame, possible_registers, possible_flags ):
    args = ins.args
    if( len(args) == 2 ):
        # xor zeroeing out a register
        if( args[0] == args[1] and args[0][0] == "%" ):
            regname = args[0][1:]
            possible_registers.set(regname,0)

    return ( possible_registers, possible_flags )

leare = re.compile("([-]0x[0-9a-f]*)\((%[a-z]*)\),(%[a-z]*)")
def vt_flow_lea( ins, frame, possible_registers, possible_flags ):
#    print("ins.line = '%s'" % (ins.line,) )
#    print("ins = '%s'" % (ins,) )
#    print("ins.args_string = '%s'" % (ins.args_string,) )
    m = leare.match(ins.args_string)
    if( m is not None ):
#                print("m = '%s'" % (m,) )
#                print("m.group(0) = '%s'" % (m.group(0),) )
#                print("m.group(1) = '%s'" % (m.group(1),) )
#                print("m.group(2) = '%s'" % (m.group(2),) )
#                print("m.group(3) = '%s'" % (m.group(3),) )
        offset = m.group(1)
        sreg = m.group(2)[1:]
        treg = m.group(3)[1:]
        sregv,_ = possible_registers.get(sreg,None)
#                print("sregv = '%s'" % (sregv,) )
        if( sregv is None and ( sreg == "rbp" or sreg == "ebp" ) ):
            sregv = frame.read_register(sreg)
            if( sregv is not None ):
                sregv = int(sregv)
#                print("sregv = '%s'" % (sregv,) )
        if( sregv is not None ):
            expr = f"({offset} + {sregv})"
#                    print("expr = '%s'" % (expr,) )
            tval = gdb.parse_and_eval(expr)
            possible_registers.set( treg, tval )

    return ( possible_registers, possible_flags )

def vt_flow_syscall( ins, frame, possible_registers, possible_flags ):
#            print("possible_registers = '%s'" % (possible_registers,) )
#            ins._gen_extra()
    rax,_ = possible_registers.get("rax",None)
    if( rax is not None ):
        sc = get_syscall( rax )
#                    print("rax = '%s'" % (rax,) )
#                    print("sc = '%s'" % (sc,) )
        if( sc is not None ):
            qm = "?"
            if( ins.marked or (ins.next and ins.next.marked) ):
                qm="!"
            ins.add_extra( sc.to_str(possible_registers,qm,frame) )
            possible_registers = sc.clobber(possible_registers)
        else:
            ins.add_extra(f"syscall[{rax}]()")
#                    ins.add_extra(f"{possible_registers}")
    return ( possible_registers, possible_flags )

def vt_flow_leave( ins, frame, possible_registers, possible_flags ):
    rbp,_ = possible_registers.get("rbp",None)
    if( rbp is not None ):
        possible_registers.set("rsp",rbp)
    # XXX do the "pop rbp" too
    return ( possible_registers, possible_flags )

def vt_flow_call( ins, frame, possible_registers, possible_flags ):
    npr = register_set()
    npr.copy( possible_registers, call_preserved_registers )
    possible_registers = npr
    return ( possible_registers, possible_flags )

def vt_flow_ret( ins, frame, possible_registers, possible_flags ):
    npr = register_set()
    possible_registers = npr
    return ( possible_registers, possible_flags )

def gen_vtable( ):
    vdb.util.bark() # print("BARK")
    global flow_vtable
    thismodule = sys.modules[__name__]
    for funname in dir(thismodule):
        if( funname.startswith("vt_flow_") ):
            fun = getattr( thismodule, funname )
            funname = funname[8:]
            flow_vtable[funname] = fun
#    print("flow_vtable = '%s'" % (flow_vtable,) )

gen_vtable()

def register_flow( lng, frame ):
    global flow_vtable
    if( len(flow_vtable) == 0 ):
        gen_vtable()

    for i in lng.instructions:
        i.passes = 0
        i.possible_in_register_sets = []
        i.possible_out_register_sets = []
        i.possible_in_flag_sets = []
        i.possible_out_flag_sets = []
        i.extra = []

    ins = lng.instructions[0]
#    print("lng.var_addresses = '%s'" % (lng.var_addresses,) )
    # Try to follow execution path to figure out possible register values (and maybe later flags)
#    possible_registers = {}
    possible_registers = lng.initial_registers.clone()
    possible_flags = flag_set()
    
    rbp = frame.read_register("rbp")
    if( rbp  is not None ):
        possible_registers.set( "rbp", rbp )

#    for ins in ret.instructions:
    flowstack = [ (None,None) ]

    hexre = re.compile("0x[0-9a-f]*$")

    passlimit = 2
    next = None
    previous = None

    # XXX make it perhaps possible to pre-populate it by an option so we can disable handling this way?
    unhandled_mnemonics = set()

    while ins is not None:
        # Simple protection against any kinds of endless loops
        # XXX Better would be to check (additionally?) if the register and flag sets are the same as in previous runs
        ins.passes += 1
        if( ins.passes >= passlimit ):
            next = None
        else:
            next = ins.next

        # Assumes the last one is the target, might be different for different archs
        if( ins.args is not None ):
            target = False
            for a in ins.args:
                ins.arguments.append( asm_arg(target,a) )
                target = True

        # As per convention, rip on x86 as an argument is the next instruction
        if( ins.next is not None ):
            possible_registers.set( "pc", ins.next.address )
        elif( len(ins.bytes) > 0 ):
            possible_registers.set( "pc", ins.address + len(ins.bytes) )

        # Check if we have a special function handling more than the basics
        fun = flow_vtable.get(ins.mnemonic,None)
        if( fun is not None ):
            ins.possible_in_register_sets.append( possible_registers.clone() )
            ins.possible_in_flag_sets.append( possible_flags.clone() )
            # clone of registers and flags from the last instruction output register set, returns a clone of the ins
            # output sets
            (possible_registers, possible_flags) = fun( ins, frame, possible_registers, possible_flags )
            ins.possible_out_register_sets.append( possible_registers.clone() )
            ins.possible_out_flag_sets.append( possible_flags.clone() )
        # There is none, check if there is any that can be synthesized from the table
        else:
            if( ins.mnemonic not in unhandled_mnemonics ):
                for mn,fun in flow_vtable.items():
                    if( ins.mnemonic.startswith(mn) ):
                        print(f"{mn} => {ins.mnemonic}")
                        flow_vtable[ins.mnemonic] = fun
                        ins.possible_in_register_sets.append( possible_registers.clone() )
                        ins.possible_in_flag_sets.append( possible_flags.clone() )
                        (possible_registers, possible_flags) = fun( ins, frame, possible_registers, possible_flags )
                        ins.possible_out_register_sets.append( possible_registers.clone() )
                        ins.possible_out_flag_sets.append( possible_flags.clone() )
                        break
                else:
                    # Store for later to be quicker
                    unhandled_mnemonics.add( ins.mnemonic )

        if( len(ins.targets) > 0 ):
#            print("ins.targets = '%s'" % (ins.targets,) )
#            print("ins.conditional_jump = '%s'" % (ins.conditional_jump,) )
#            print("ins.call = '%s'" % (ins.call,) )
#            ins.add_extra(f"targets {ins.targets}")
            if( not ins.conditional_jump and not ins.call ):
                next = None
            for tga in ins.targets:
                tgt = lng.by_addr.get(tga,None)
                if( tgt is not None and tgt.passes < passlimit ):
                    flowstack.append( (tgt,ins) )

#        if( len(ins.constants) > 0 ):
#            for c in ins.constants:
#                xc = vdb.util.xint(c)
#                    print("vdb.memory.mmap.accessible(xc) = '%s'" % (vdb.memory.mmap.accessible(xc),) )
#                if( vdb.memory.mmap.accessible(xc) ):
#                    ch = vdb.pointer.chain( xc, vdb.arch.pointer_size, 1, True, 1, False, asm_tailspec.value )
#                    ins.reference.append(ch[0])
        for ri in range(0,len(ins.reference)):
            m = hexre.match( ins.reference[ri] )
            if( m is not None ):
                xr = vdb.util.xint(ins.reference[ri])
                if( vdb.memory.mmap.accessible(xr) ):
                    ch = vdb.pointer.chain( xr, vdb.arch.pointer_size, 1, True, 1, False, asm_tailspec.value )
                    ins.reference[ri] = ch[0]

#        vdb.util.bark() # print("BARK")
        printed_addrs = set()
        # Check if we can output a bit more info about the register values used in this 
        if( len(ins.arguments) > 1 ):
            cnt = 0
            target = ins.arguments[1]
            for aidx in range(0,len(ins.args)):
                a = ins.args[aidx]
                arg = ins.arguments[aidx]

                pre=""
                av = lng.var_expressions.get(a,None)
                if( av is not None ):
                    if( cnt > 0 ):
                        pre = ","
                    ins.reference.append( pre + vdb.color.color(av,color_var.value) + "@" + vdb.color.color(a,color_location.value) )
                    cnt += 1
#                ins.add_extra(f"ARG {a}")
                try:
                    # If its a target we want to use the value after the instruction executed
                    regset = ins.possible_in_register_sets
                    if( arg.target ):
                        regset = ins.possible_out_register_sets
                    # Check via the possible register sets the value of the register
                    for prs in regset:
                        argval,argaddr= arg.value(prs,target)
#                        if( argval is not None ):
#                            print(f"argval = {int(argval):#0x}")
#                        if( argaddr is not None ):
#                            print(f"argaddr = {int(argaddr):#0x}")
                        if( argval is not None or argaddr is not None ):
                            break
                    addr = argaddr
                    if( addr is not None and addr not in printed_addrs ):
                        printed_addrs.add(addr)

                        av = lng.var_addresses.get(addr,None)

#                        print("arg = '%s'" % (arg,) )
                        if( addr is not None ):
                            addr = f"{addr:#0x}"
                            if( cnt > 0 ):
                                pre=","
                            if( av is None ):
                                pre = ""
                                av = ""
                            ins.reference.append( pre + vdb.color.color(av,color_var.value) + "@" + vdb.color.color(addr,color_location.value) )
                            cnt += 1
                            if( argval is not None and not arg.target):
#                        if( argval is not None ):
#                            print("argval = '%s'" % (argval,) )
                                val = f"{argval:#0x}"
                                if( cnt > 0 and len(av) > 0 ):
                                    pre=","
                                ins.reference.append( pre + vdb.color.color(av,color_var.value) + "=" + vdb.color.color(val,color_location.value) )
                                cnt += 1
#                    vdb.util.bark() # print("BARK")
                    if( addr is None and argval not in printed_addrs ):
                        printed_addrs.add(argval)
                        _,_,symbol = vdb.memory.get_gdb_sym( argval )
                        if( symbol is not None ):
                            symbol = symbol.split("@")
                            symbol = vdb.color.color(symbol[0],color_var.value) + "@" + "@".join(symbol[1:])
                            fav = f"{argval:#0x}"
                            ins.reference.append(symbol + "@" + vdb.color.color( fav, color_location.value ) )
                        else:
#                            vdb.util.bark() # print("BARK")
#                            print("arg = '%s'" % (arg,) )
#                            print(f"argval = {int(argval):#0x}")
#                            print("vdb.memory.mmap.accessible(argval) = '%s'" % (vdb.memory.mmap.accessible(argval),) )
                            if( vdb.memory.mmap.accessible(argval) ):
#                                vdb.util.bark() # print("BARK")
                                ch = vdb.pointer.chain( argval, vdb.arch.pointer_size, 1, True, 1, False, asm_tailspec.value )
#                                print("ch = '%s'" % (ch,) )
                                ins.reference.append(ch[0])
                except:

                    if( debug.value ):
                        traceback.print_exc()
                    pass

        

        if( debug_registers.value ):
            ins._gen_extra()

#        print(f"{ins} ===> {next}    ({ins.next})")
        previous = ins
        ins = next

        if( ins is None ):
            ins,previous = flowstack.pop()

    # while(ins) done
    print("unhandled_mnemonics = '%s'" % (unhandled_mnemonics,) )

def parse_from( arg, fakedata = None, context = None ):
    rng = arg.split(",")
#    print("rng = '%s'" % (rng,) )
    if( len(rng) == 2 ):
        try:
            fr=vdb.util.gint(rng[0])
            to=vdb.util.gint(rng[1])
#            print("fr = '%x'" % fr )
#            print("to = '%x'" % to )
            if( to < fr ):
                to = fr + to + 1
            arg = f"{fr:#0x},{to:#0x}"

        except:
#            print("rng = '%s'" % rng )
            pass
    # other disssembler options go here
    try:
#        print("arg = '%s'" % arg )
#        print("fakedata = '%s'" % fakedata )
        if( arg.startswith("000000") ): # really do some regex for a hex value and check that it starts with a digit
            ret = parse_from_gdb("0x" + arg,fakedata)
        else:
            ret = parse_from_gdb(arg,fakedata)
    except gdb.error as e:
        nfbytes = str(nonfunc_bytes.value)
        if( context is not None and context[1] is not None ):
            nfbytes = str(context[1])
#        print("context = '%s'" % (context,) )
        if( str(e) == "No function contains specified address." ):
            return parse_from(arg+","+nfbytes)
        elif( str(e) == "No function contains program counter for selected frame." ):
            return parse_from("$pc,"+nfbytes)
        else:
            print("e = '%s'" % e )
            traceback.print_exc()
            raise e

    return ret



class callgrind_instruction:

    def __init__( self, line, previous ):
        self.values = None
        self.address = None
        self.parse( line.split(), previous )
        self.jumps = {}
#        self._dump()

    def _dump( self ):
        print(f"@{self.address:#08x} : {self.values}")

    def event( self, evidx ):
        val = self.values.get(evidx,0)
        return val

    def value( self, evname ):
        evidx = callgrind_eventmap.get(evname,None)
        if( evidx is not None ):
            return self.event(evidx)
        else:
            return 0

    def add_synth( self, name, elist ):
        global callgrind_eventmap
        nni = callgrind_eventmap.get(name,None)
        if( nni is None ):
#            print("callgrind_eventmap = '%s'" % (callgrind_eventmap,) )
            nni = len(callgrind_eventmap) + 2
            callgrind_eventmap[name] = nni
#            print("callgrind_eventmap = '%s'" % (callgrind_eventmap,) )

        val = 0
        for e in elist:
            eidx = callgrind_eventmap.get(e,None)
            if( eidx is None ):
                vdb.util.log(f"Could not synthesize event {name}, at least event {e} is unavailable",level=4)
                return None
            v = self.event(eidx)
#            print("e = '%s'" % (e,) )
#            print("v = '%s'" % (v,) )
            val += v
#        print("val = '%s'" % (val,) )
        if( val ):
            self.values[nni] = val
        return val

    def synthesize( self ):
        self.add_synth( "L1m", [ "I1mr", "D1mr", "D1mw" ] )
        self.add_synth( "L2m", [ "I2mr", "D2mr", "D2mw" ] )
        self.add_synth( "LLm", [ "ILmr", "DLmr", "DLmw" ] )
        self.add_synth( "Bm",  [ "Bim", "Bcm" ] )

        global callgrind_eventmap
        cidx = callgrind_eventmap.get("CEst",None)
        if( cidx is None ):
            cidx = len(callgrind_eventmap) + 2
            callgrind_eventmap["CEst"] = cidx

        cest = 0
        cest += self.value( "Ir" )
        cest += self.value( "Bm" )  * 10
        cest += self.value( "L1m" ) * 10
        cest += self.value( "Ge" )  * 20
        cest += self.value( "L2m" ) * 100
        cest += self.value( "LLm" ) * 100
        if( cest ):
            self.values[cidx] = cest

    class jump_info:

        def __init__( self ):
            self.target = None
            self.executed = 0
            self.jumped = None

        def merge( self, other ):
            if( self.target != other.target ):
                raise RuntimeError(f"Can not merge jump info of different targets {self.target} and {other.target}")
            self.executed += other.executed
            if( self.jumped is not None ):
                self.jumped += other.jumped

        def __str__( self ):
            if( self.jumped is None ):
                return f"Jumped {self.executed} times to {self.target:#08x}"
            else:
                return f"Jumped {self.jumped} of {self.executed} times to {self.target:#08x}"

    def add_jump( self, j, ex, target, raw = None ):
#        outof = outof.split("/")
#        print("outof = '%s'" % (outof,) )
#        print("target = '%s'" % (target,) )
#        print("self.address = '%s'" % (self.address,) )
        ji = self.jump_info()
        if( target[0] == "+" ):
            offset = int(target[1:])
            ji.target = self.address + offset
        elif( target[0] == "-" ):
            offset = int(target[1:])
            ji.target = self.address - offset
        elif( target == "*" ):
            ji.target = self.address
        else:
            ji.target = int(target,16)
        ji.executed = int(ex)
        if( j is not None ):
            ji.jumped  = int(j)
        ji.raw = raw
        si = self.jumps.get(ji.target,None)
        if( si is not None ):
            si.merge(ji)
        else:
            self.jumps[ji.target] = ji


    # This is the "previous" we ask for the next addr
    def parse_address( self, addrstr ):
        if( addrstr.startswith( "0x" ) ):
            return int(addrstr,16)
        elif( addrstr.startswith( "+" ) ):
            return self.address + int(addrstr[1:])
        elif( addrstr.startswith( "-" ) ):
            return self.address - int(addrstr[1:])
        else:
            raise RuntimeError("Invalid address string " + addrstr)

    def parse( self, vec, previous ):
        if( previous is not None ):
            self.address = previous.parse_address( vec[0] )
        else:
            self.address = self.parse_address( vec[0] )
        self.values = {}
        for i in range(1,len(vec)):
            val = vec[i]
            if( val == "*" ):
                val = previous.values[i]
            elif( val.startswith("+") ):
                add = int(val[1:])
                val = previous.values[i] + add
            else:
                val = int(val)
            self.values[i] = val
        self.synthesize()

    def get_next( self, cline ):
        vec = cline.split()
        next_addr = self.parse_address( vec[0] )
        return get_instruction( next_addr )

    def merge( self, other ):
        if( other.address != self.address ):
            raise RuntimeError(f"Can not merge different addresses {self.address} and {other.address}")
        for _,oj in other.jumps.items():
            si = self.jumps.get(oj.target,None)
            if( si is not None ):
                si.merge(oj)
            else:
                self.jumps[oj.target] = oj

        for oi,ov in other.values.items():
            ov += self.values.get(oi,0)
            self.values[oi] = ov

        self.synthesize()

def get_instruction( addr ):
    global callgrind_data
    ci = callgrind_data.get(addr,None)
    return ci

def get_next( cline, ci ):
    if( ci is not None ):
        pci = ci.get_next(cline)
        if( pci is None ):
            return callgrind_instruction( cline, ci )

    ci = callgrind_instruction( cline, ci )
    pci = get_instruction( ci.address )
    if( pci is not None ):
        pci.merge(ci)
        return pci
    return ci

def load_callgrind( argv ):
#    print("argv = '%s'" % (argv,) )
    global callgrind_data
    global callgrind_eventmap
    if( argv[0] == "clear" ):
        callgrind_data = {}
        print("Cleared callgrind database")
        return None
    current_instruction = None
    with open( argv[0], "r" ) as cf:
        for cfline in cf:
            cfline = cfline.rstrip()
            if( len(cfline) == 0 ):
                continue

            if( cfline.startswith("0x") ):
                current_instruction = get_next( cfline, current_instruction )
                callgrind_data[current_instruction.address] = current_instruction
            elif( cfline[0] == "+" or cfline[0] == "-" ):
                current_instruction = get_next( cfline, current_instruction )
                callgrind_data[current_instruction.address] = current_instruction
            elif( cfline.startswith("events:") ):
                cfv = cfline.split()
                for i in range( 1,len(cfv) ):
                    callgrind_eventmap[cfv[i]] = i+1
#                    print("cfv[i] = '%s'" % (cfv[i],) )
            elif( cfline.startswith( "jcnd=" ) ):
                cfline = cfline[5:]
                vec = cfline.split()
                oo = vec[0]
                oo = oo.split("/")
                current_instruction.add_jump( oo[0], oo[1], vec[1], cfline )
            elif( cfline.startswith( "jump=" ) ):
                cfline = cfline[5:]
                vec = cfline.split()
                current_instruction.add_jump( None, vec[0], vec[1] )
            else:
#                print("cfline = '%s'" % (cfline,) )
                pass


#        while( cfline := cf.readline().rstrip() ):
#            print("cfline = '%s'" % (cfline,) )

    print(f"Read information for {len(callgrind_data)} instructions from {argv[0]}")

function_vars = {}
function_registers = {}

# XXX determine the type (or pass it along) and descend into subfields
def add_variable( argv ):
    if( len(argv) != 3 ):
        print("Format is: dis/v <vname> <register> <vaddr>")
    fun = gdb.selected_frame().function().name
    vname = argv[0]
    vreg  = argv[1]
    vaddr = argv[2]

    vaddr = vdb.util.rxint(vaddr)

    global function_vars
    global function_registers
    
    fv = function_vars.get(fun,None)
    if( fv is None ):
        fv = {}
        function_vars[fun] = fv
#    fv.set(vname,vaddr)
    fv[vaddr] = vname

    fr = function_registers.get(fun,None)
    if( fr is None ):
        fr = register_set()
        function_registers[fun] = fr
    fr.set(vreg, vaddr)

    print("function_vars = '%s'" % (function_vars,) )
    print("function_registers = '%s'" % (function_registers,) )

    invalidate_cache(None)


def disassemble( argv ):
    dotty = False
    context = None
    fakedata = None
    source = False

    if( len(argv) > 0 ):
        if( argv[0][0] == "/" ):
            argv0 = argv[0][1:]
            argv=argv[1:]

            while( len(argv0) > 0 ):
                vdb.util.log("argv0={argv0}",argv0 = argv0, level = 4)
                if( argv0[0] == "d" ):
                    dotty = True
                    argv0 = argv0[1:]
                elif( argv0[0] == "c" ):
                    load_callgrind( argv )
                    return None
                elif( argv0[0] == "f" ):
                    with open (argv[0], 'r') as fakefile:
                        fakedata = fakefile.read()
                    argv=["fake"]
                    break
                elif( argv0[0] == "r" ):
                    gdb.execute("disassemble " + " ".join(argv))
                    return
                elif( argv0[0] == "s" ):
                    source = True
                    argv0 = argv0[1:]
                elif( argv0[0] == "+" and argv0[1:].isdigit() ):
                    context = ( None, int(argv0[1:]) )
                    break
                elif( argv0[0] == "-" and argv0[1:].isdigit() ):
                    context = ( int(argv0[1:]), None )
                    break
                elif( argv0[0:].isdigit() ):
                    context = int(argv0[0:])
                    context = ( context, context )
                    break
                elif( argv0.find(",") != -1 ):
                    context = argv0[0:].split(",")
                    context = ( int(context[0]), int(context[1]) )
                    break
                elif( argv0[0] == "v" ):
                    add_variable( argv )
                    return
                else:
                    break

#    print("context = '%s'" % (context,) )
#    print("argv = '%s'" % (argv,) )

    listing = parse_from(" ".join(argv),fakedata,context)
    if( asm_sort.value ):
        listing.sort()
    marked = None
    if( context is not None ):
        try:
            marked = int(gdb.parse_and_eval(" ".join(argv)))
        except:
            pass
        try:
            if( marked is None and len(argv) == 0 ):
                marked = int(gdb.parse_and_eval("$pc"))
        except:
            pass

    try:
        listing.print(asm_showspec.value, context,marked, source)
        if( dotty ):
            g = listing.to_dot(asm_showspec_dot.value)
            g.write("dis.dot")
            os.system("nohup dot -Txlib dis.dot &")
    except:
        traceback.print_exc()
        pass


def get_single( bpos ):
    ret="<??>"
    try:
        da=gdb.selected_frame().architecture().disassemble(int(bpos),count=1)
        da=da[0]
        fake = f"{da['addr']:#0x} <+0>: {da['asm']}"
        li = parse_from_gdb("",fake)
        ret = li.to_str(asm_showspec.value.replace("a","").replace("o",""),suppress_header = True)
        ret = ret.splitlines()
        ret = ret[1]
    except:
        pass
    return ret

class Dis (vdb.command.command):
    """Disassemble with bells and whistels

Parses the gdb disassembler output and reformats it to look nicer and be coloured. Adds arrows for jumps, can show
record history and sometimes display some extra information (e.g. for syscalls)

Displayed columns can be set using a showspec (see documentation)

dis/r       - runs the plain gdb disassemble command (accepts all parameters so you can run dis/r /r to show bytes)
dis/d       - instead of showing text output, this will generate a dotty graph, trying to recover basic blocks
dis/<N>     - Have N instructions of context before and after the current marker (useful for dashboards)
dis/+<N>    - Have N Instructions of context after the marker
dis/-<N>    - Have N Instructions of context before the marker
dis/<N>,<M> - Have N Instructions of context before and M after the Marker

All further parameters are handled like for the built in disasemble command with the exception of addresses that are not
part of a function, unlike the disassemble command those are right away disassembled vdb-asm-nonfunction-bytes (default
16) bytes long
"""

    def __init__ (self):
        super (Dis, self).__init__ ("dis", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION, replace = True)

    def do_invoke (self, argv ):

        try:
            global from_tty
            from_tty = self.from_tty
            disassemble( argv )
        except gdb.error as e:
            print("asm: %s" % e)
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

Dis()

# We only support it, silently try to force it
try:
    gdb.execute("set disassembly-flavor att")
except gdb.error:
    pass

if __name__ == "__main__":
    try:
        disassemble( sys.argv[1:] )
    except:
        traceback.print_exc()
        pass



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
