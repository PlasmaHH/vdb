#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations # for postponed annotation evaluation

import vdb.shorten
import vdb.color
import vdb.pointer
import vdb.dot
import vdb.command
import vdb.arch
import vdb.register
import vdb.memory

import gdb
import colors
import importlib

import re
import traceback
import sys
import os
import time
import abc

asm_class_colors = {
            "jump" : "#f0f",
            "mem"  : "#0ff",
            "nop"  : "#338",
            "bit"  : "#da4",
            "math" : "#909",
            "sys"  : "#a11",
            "ret"  : "#8f9",
            "call" : "#66f",
            "stack": "#080",
            "cond" : "#f99",
            "vector" : "#aa6",
            "default" : "#f00"
        }

asm_colors_dot = [
        ( "j.*", "#f000f0" ),
        ( "b.*", "#f000f0" ),
        ( "cb.*", "#f000f0" ),
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

@vdb.event.start()
def invalidate_cache( c ):
    global parse_cache
    if( len(parse_cache) ):
        vdb.log("Invalidating disassembler parse cache",level=4)
    parse_cache = {}

bp_marker = vdb.config.parameter("vdb-asm-breakpoint-marker", "⬤" )
bp_marker_disabled = vdb.config.parameter("vdb-asm-breakpoint-disabled-marker", "◯" )
bp_number = vdb.config.parameter("vdb-asm-breakpoint-use-numbers", True )

bp_numbers = vdb.config.parameter("vdb-asm-breakpoint-numbers", "❶❷❸❹❺❻❼❽❾❿" )
bp_numbers_disabled = vdb.config.parameter("vdb-asm-breakpoint-numbers-disabled", "➀➁➂➃➄➅➆➇➈➉" )

next_marker = vdb.config.parameter("vdb-asm-next-marker", "→" )
next_marker_dot = vdb.config.parameter("vdb-asm-next-marker-dot", " → " )

next_mark_ptr     = vdb.config.parameter("vdb-asm-next-mark-pointer", True )
shorten_header    = vdb.config.parameter("vdb-asm-shorten-header", False )
prefer_linear_dot = vdb.config.parameter("vdb-asm-prefer-linear-dot",False)
debug_registers = vdb.config.parameter("vdb-asm-debug-registers",False, on_set = invalidate_cache )
debug = vdb.config.parameter("vdb-asm-debug-all",False, on_set = invalidate_cache )
debug_addr = vdb.config.parameter("vdb-asm-debug-address",0, on_set = invalidate_cache )

offset_fmt = vdb.config.parameter("vdb-asm-offset-format", "<{offset:<+{maxlen}}>:" )
offset_txt_fmt = vdb.config.parameter("vdb-asm-text-offset-format", "<+{offset:<{maxlen}}>:" )
offset_fmt_dot = vdb.config.parameter("vdb-asm-offset-format-dot", " <{offset:<+{maxlen}}>" )
offset_txt_fmt_dot = vdb.config.parameter("vdb-asm-text-offset-format-dot", " <+{offset:<{maxlen}}>" )

color_ns       = vdb.config.parameter("vdb-asm-colors-namespace",   "#ddf", gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-asm-colors-function",    "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_marker   = vdb.config.parameter("vdb-asm-colors-next-marker", "#0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_rmarker  = vdb.config.parameter("vdb-asm-colors-next2-marker", "#080", gdb_type = vdb.config.PARAM_COLOUR)
color_xmarker  = vdb.config.parameter("vdb-asm-colors-marker",      "#049", gdb_type = vdb.config.PARAM_COLOUR)
color_bpmarker = vdb.config.parameter("vdb-asm-colors-breakpoint-marker", "#e45", gdb_type = vdb.config.PARAM_COLOUR)
color_bpmarker_disabled = vdb.config.parameter("vdb-asm-colors-breakpoint-disabled-marker", "#e45", gdb_type = vdb.config.PARAM_COLOUR)
color_addr     = vdb.config.parameter("vdb-asm-colors-addr",        None,   gdb_type = vdb.config.PARAM_COLOUR)
color_offset   = vdb.config.parameter("vdb-asm-colors-offset",      "#444", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#059", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix   = vdb.config.parameter("vdb-asm-colors-prefix",      None,   gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic = vdb.config.parameter("vdb-asm-colors-mnemonic",    None,   gdb_type = vdb.config.PARAM_COLOUR)
color_args     = vdb.config.parameter("vdb-asm-colors-args",        "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_var      = vdb.config.parameter("vdb-asm-colors-variable",    "#fc8", gdb_type = vdb.config.PARAM_COLOUR)
color_location = vdb.config.parameter("vdb-asm-colors-location",    "#08a", gdb_type = vdb.config.PARAM_COLOUR)
color_explanation = vdb.config.parameter("vdb-asm-colors-explanation",    "#6666ff", gdb_type = vdb.config.PARAM_COLOUR)



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
asm_showspec       = vdb.config.parameter("vdb-asm-showspec", "maodbnptrjhcx" )
asm_showspec_dot   = vdb.config.parameter("vdb-asm-showspec-dot", "maobnptr" )
asm_tailspec       = vdb.config.parameter("vdb-asm-tailspec", "andD" )
asm_sort           = vdb.config.parameter("vdb-asm-sort", True )
dot_fonts          = vdb.config.parameter("vdb-asm-font-dot", "Inconsolata,Source Code Pro,DejaVu Sans Mono,Lucida Console,Roboto Mono,Droid Sans Mono,OCR-A,Courier" )

callgrind_events   = vdb.config.parameter("vdb-asm-callgrind-events", "Ir,CEst", gdb_type = vdb.config.PARAM_ARRAY )
callgrind_jumps    = vdb.config.parameter("vdb-asm-callgrind-show-jumps", True )
header_repeat      = vdb.config.parameter("vdb-asm-header-repeat", 50 )
direct_output      = vdb.config.parameter("vdb-asm-direct-output", True )
gv_limit           = vdb.config.parameter("vdb-asm-variable-expansion-limit", 3 )
default_argspec    = vdb.config.parameter("vdb-asm-default-argspec", "i@%=,o@%" )
annotate_jumps     = vdb.config.parameter("vdb-asm-annotate-jumps", True )
annotate_cmove     = vdb.config.parameter("vdb-asm-annotate-cmove", True )
asm_explain        = vdb.config.parameter("vdb-asm-explain", False, on_set = invalidate_cache  )
ref_width          = vdb.config.parameter("vdb-asm-reference-width", 120 )

callgrind_eventmap = {} # name to index
callgrind_data = {}
from_tty = None

xi_history = {}


color_list = vdb.config.parameter("vdb-asm-colors-jumps", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,gdb_type = vdb.config.PARAM_COLOUR_LIST )

valid_archs = [ "x86", "arm" ]
arch_aliases = {
                "i386" : "x86",
                "i386:x86-64" : "x86",
                "aarch64" : "arm",
                "armv7" : "arm",
                "armv7-m" : "arm",
                "armv7-m.main" : "arm",
                "armv8-m" : "arm",
                "armv8-m.main" : "arm",
                }


def debug_all( ins = None ):
    if( debug_addr.value is not None and ins is not None ):
        return ( int(ins.address) == int(debug_addr.value) )
    return debug.value

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
        elif( pr[0] == "r" ):
            reg_altlists[pr] = [ pr, pr + "d" ]
            reg_altlists[pr + "d"] = [ pr + "d", pr ]

def reg_alts( reg ):
    if( len(reg_altlists) == 0 ):
        gen_altlist()
    return reg_altlists.get(reg,[reg])

ix = -1
def next_index( ):
    global ix
    ix += 1
    return ix

# to be able to put it into lists and modify later for output reasons
class string_ref:

    def __init__( self, value = "" ):
        self.value = value

    def __str__( self ):
        return self.value

    def __repr__( self ):
        return f"string_ref({self.value})"

    def __len__( self ):
        return len(self.value)

# similar to register_set a wrapper around a dict that stores possible flag values
class flag_set:

    def __init__( self ):
        self.flags = {}

    def set( self, name, value ):
#        vdb.util.bark() # print("BARK")
#        vdb.util.bark(-1) # print("BARK")
#        print("name = '%s'" % (name,) )
        self.flags[name] = value
        self._maybe_set_sf_of(name)
#        print("self = '%s'" % (self,) )

    def unset( self, name ):
#        vdb.util.bark() # print("BARK")
#        vdb.util.bark(-1) # print("BARK")
#        print("name = '%s'" % (name,) )
        if( not isinstance(name,str) ):
            for n in name:
                self.unset(n)
        else:
            self.flags.pop(name,None)
            self._maybe_set_sf_of(name)
#        print("self = '%s'" % (self,) )

    # XXX Can possibly be removed
    def _maybe_set_sf_of( self, name  ):
#        print("name = '%s'" % (name,) )
        if( name in set(["SF","OF"]) ):
            self._set_sf_of()

    # XXX Can possibly be removed
    def _set_sf_of( self ):
        sfv = self.get("SF")
        ofv = self.get("OF")
        if( sfv is not None and ofv is not None ):
            self.set("SF_OF", int(sfv == ofv) )
        else:
            self.unset("SF_OF")

    def get( self, name ):
        return self.flags.get(name,None)

    def clear( self ):
        self.flags = {}

    def clone( self ):
        ret = flag_set()
        ret.flags = self.flags.copy()
        return ret

    def merge( self, other ):
        for k,v in other.flags.items():
            self.set(k,v)

    def subset( self, filterset ):
        ret = flag_set()
        for fk,fv in self.flags.items():
            if( fk in filterset ):
                ret.flags[fk] = fv
        return ret

    def __str__( self ):
        ret = "{"
        for f,v in self.flags.items():
            ret += f"{f}={v},"
        ret += "}"
        return ret

    def __repr__( self ):
        return str(self)

def current_flags( frame, flagregister ):
    eflags = frame.read_register(flagregister)
#    print(f"EFLAGS    ------------------ {eflags=}")
    if( eflags is None ):
        return None
#    print("eflags = '%s'" % (eflags,) )
#    print("type(eflags) = '%s'" % (type(eflags),) )
#    print("eflags.type = '%s'" % (eflags.type,) )
#    print("eflags.type.code = '%s'" % (vdb.util.gdb_type_code(eflags.type.code),) )
    e_val = int(eflags)
#    print("eflags.type.fields() = '%s'" % (eflags.type.fields(),) )
    fs = vdb.asm.flag_set()
    _,_,fdesc,_ = vdb.register.flag_info.get( flagregister )
    for bit,fd in fdesc.items():
        mask = 1 << bit
#        print(f"mask = {int(mask):#0x}")
#        print("fd[1] = '%s'" % (fd[1],) )
        fval = e_val & mask
#        print("fval = '%s'" % (fval,) )
        if( fval > 0 ):
            fs.set(fd[1],1)
        else:
            fs.set(fd[1],0)
#    print("fs = '%s'" % (fs,) )
    return fs



# returns ( True/False/None, "description string" )
# None means "not handled"
def flag_check( suffix, flagset, condset ):
#    print(f"flag_check( {suffix=}, {flagset=}, {len(condset)=} )")

    use_or,exflags = condset.get(suffix,(None, None))
    if( exflags is None ):
        return (None,f"Unhandled conditional suffix {suffix}")
    else:
        extrastring = ""
        taken = None

        for exflag in exflags:
            flag0,flag1,cresult = exflag
            flag0text,flag1text,_ = exflag

            if( isinstance(flag0,str) ):
                flag0 = flagset.get(flag0)
                flag0text = f"{exflag[0]}[{flag0}]"
            if( isinstance(flag1,str) ):
                flag1 = flagset.get(flag1)
                flag1text = f"{exflag[1]}[{flag1}]"

            if( flag0 is None or flag1 is None ):
                # We cant say anything,
                extrastring += f"Flag value(s) {exflag[0]},{exflag[1]} unknown"
                taken = None
                break
            else:
                if( cresult ):
                    cmp = "=="
                    ncmp = "=="
                else:
                    ncmp = "!="
                # We should compare the values
                matches = ( flag0 == flag1 ) == cresult
                if( matches ):
                    extrastring += f", {flag0text} {cmp} {flag1text}"
                else:
                    extrastring += f", {flag0text} {ncmp} {flag1text}"

                if( use_or ):
                    if( matches ):
                        taken = True
                        break
                else: #  use and
                    if( not matches ):
                        taken = False
                        break
#                    vdb.util.bark() # print("BARK")
        else:
            # We only ever end here when all AND cases got true, None and or cases break early
            taken = True

    return (taken,extrastring)


# a wrapper around a register dict that can deal with alternative register names
class register_set:

    def __init__( self ):
        self.values = {}

    def clone( self ):
        ret = register_set()
        ret.values = self.values.copy()
        return ret

    # Sets the value of a register, possible removing all alternative names that may be present
    # XXX We need to be able to handle in an easy way specifcations like %al and %ah, best would be through some extra
    # layer that can easily expanded for other archs
    def set( self, name, value, remove_alts = True, origin = None ):
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

        try:
            self.values[name] = ( int(value), origin )
        except gdb.error:
            pass


    def empty( self ):
        return len(self.values) == 0

    def get( self, name, altval = None ):
        for rname in reg_alts(name):
            rv,origin = self.values.get(rname,(None,None) )
            if( rv is not None ):
                rs = vdb.register.register_size(name)
                if( rs is not None ):
                    mask = ( 1 << rs ) - 1
                    rv &= mask
                return ( rv, rname, origin )
        return ( altval, name, None )

    def merge( self, other, origin = None ):
        for n,(v,o) in other.values.items():
            if( origin is not None ):
                o = origin
            self.set( n, v, origin=o )

    def copy( self, other, rlist ):
        for rn in rlist:
            rv,rn,origin = other.get( rn )
            if( rv is not None ):
                self.set( rn,rv,origin )

    def remove( self, rname ):
        for rname in reg_alts(rname):
            self.values.pop(rname,None)

    def __str__( self ):
        ret = "{"
        for r,(v,o) in self.values.items():
            ret += f"{r}={v:#0x}@{o},"
        ret += "}"
        return ret

    def __repr__( self ):
        return str(self)



class asm_arg_base( ):

    def __init__( self, target, arg ):
        self.register = None
        self.immediate = None
        self.immediate_hex = False
        self.dereference = None
        self.prefix = None
        self.offset = None
        self.offset_shift = None
        self.target = target
        self.jmp_target = None
        self.multiplier = None
        self.add_register = None
        self.asterisk = False
        self.reset_argspec()
        self.list_start = False
        self.list_end = False
        try:
            self.parse(arg)
        except:
            vdb.print_exc()
            print("Failed to parse " + arg)
            raise
        self.arg_string = arg
        self._bitsize = vdb.register.register_size( self.register )

    def reset_argspec( self ):
        asp = default_argspec.value.split(",")
        if( self.target ):
            self.argspec = asp[1]
        else:
            self.argspec = asp[0]


    @property
    def bitsize( self ):
        # XXX add heuristics for when its None
        return self._bitsize

    def specfilter( self, sp ):
        if( sp is None ):
            self.argspec = ""
        else:
            self.argspec = self.argspec.replace(sp,"")

    @abc.abstractmethod
    def parse( self, arg ):
        pass

    def _check(self,oarg,fail = True):
        if( str(self) != oarg ):
            print("_check() failed:")
            print("oarg = '%s'" % (oarg,) )
            print("str(self) = '%s'" % (str(self),) )
            self._dump()
            if( fail ):
                raise RuntimeError(f"Parser self check failed ({str(self)} != {oarg})")

    def _fixup_value( self, val ):
        if( val is None ):
            return val
        if( isinstance(val,memoryview) ):
            val = int.from_bytes(val.tobytes(),"little") # any more efficient way?
        while( val < 0 ):
            val += 2** vdb.arch.pointer_size
        if( val.bit_length() > vdb.arch.pointer_size ):
            val &= ( 2 ** vdb.arch.pointer_size - 1 )
        return val

    def _fixup_values( self, dval, val ):
        dval = self._fixup_value(dval)
        val = self._fixup_value(val)
        return (dval,val)

    # registers is a register_set object to possible get the value from
    # XXX At the moment we do not support prefixes
    # In case we read the value from memory, the second tuple element contains its address
    def value( self, registers, target = None ):
        prefixval = 0
        if( self.prefix is not None ):
            preg = self.prefix + "_base"
            pv = vdb.register.read(preg)
            if( pv is not None ):
                prefixval = int(pv)
#        print("prefixval = '%s'" % (prefixval,) )
#        print("self.register = '%s'" % (self.register,) )
#        print("self.immediate = '%s'" % (self.immediate,) )
#        print("self.jmp_target = '%s'" % (self.jmp_target,) )

        if( self.register is not None ):
#            vdb.util.bark() # print("BARK")
#            vdb.util.bark(-1) # print("BARK")
#            print(f"{registers=}")
#            print(f"{type(registers)=}")
#            print(f"{self.register=}")
            val,_,_ = registers.get( self.register )
#            print(f"{val=}")
#            print("self.prefix = '%s'" % (self.prefix,) )
#            print("self.register = '%s'" % (self.register,) )
#            print("val = '%s'" % (val,) )
#            print("self.offset = '%s'" % (self.offset,) )
            if( val is not None  ):
#                print(f"{val=:#0x}")
#                print(f"{prefixval=}")
                val += prefixval
#                print(f"{self.offset=}")
                if( self.offset is not None ):
                    if( isinstance(self.offset,str) ):
                        ofreg,_,_ = registers.get( self.offset )
                        if( ofreg is None ):
                            return (None,None)
                        val += ofreg
                    else:
                        val += self.offset
                if( self.dereference ):
                    castto = "P"
                    if( target is None ):
                        dval = vdb.memory.read(val,vdb.arch.pointer_size//8)
                        if( vdb.arch.pointer_size == 32 ):
                            castto = "I"
                    else:
                        if( target.bitsize == 64 ):
                            dval = vdb.memory.read(val,8)
                        else:
                            dval = vdb.memory.read(val,4)
                            castto = "I"
                    if( dval is not None ):
#                        print("dval = '%s'" % (dval,) )
#                        print("dval.hex() = '%s'" % (dval.hex(),) )
#                        print("dval.nbytes = '%s'" % (dval.nbytes,) )
#                        print("dval.itemsize = '%s'" % (dval.itemsize,) )
#                        print("type(dval) = '%s'" % (type(dval),) )
#                        print("castto = '%s'" % (castto,) )
#                        dval = dval.cast(castto)[0]
                        dval = dval.cast(castto)
                    return self._fixup_values( dval, val )
            return self._fixup_values( val, None )

        if( self.immediate is not None ):
            return self._fixup_values( self.immediate + prefixval, None )

        if( self.jmp_target is not None ):
            return self._fixup_values( self.jmp_target + prefixval, None )

        return self._fixup_values( None, None )


    def __repr__( self ):
        return str(self)


    def _dump( self ):
        if( self.offset is None ):
            offset = "None"
        else:
            offset = f"{self.offset:#0x}"
        print(f"arg %{self.register}, ${self.immediate}, ({self.dereference}), {self.offset},,, T{self.target} :{self.prefix}:: {self.multiplier}*REG + {self.add_register} => {self}")







class instruction_base( abc.ABC ):

    """
    abstract base class for instructions
    """

    bytere  = re.compile("^[0-9a-fA-F][0-9a-fA-F]$")
    bytere2 = re.compile("^[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$")
    cmpre  = re.compile("^\$(0x[0-9a-fA-F]*),.*")

#    class_cache = {}
#    class_res = []

    @staticmethod
    def compile_class_res( relist ):
        ret = []
        for r,n in relist:
            ret.append( ( re.compile(r), n ) )
        return ret

    @classmethod
    def mnemonic_class( cls, mnemonic ):
        # XXX can be a base class functionality
        ret = cls.class_cache.get( mnemonic )
        if( ret is None ):
            for r,n in cls.class_res:
                if( r.match(mnemonic) ):
                    ret = n
                    cls.class_cache[mnemonic] = n
                    break
            else:
                ret = "default"
                cls.class_cache[mnemonic] = "default"
        return ret

    def __init__( self ):
        self.mnemonic = None            # Instructions "name" like mov or sub or push or call
        self.args = []                  # tokenized list of argument strings
        self.arguments = []             # objects for each arguments
        self.args_string = ""           # Original full string for the arguments

        self.conditional_jump = False   # Whether this is a conditional jump type of instruction
        self.unconditional_jump = False # Whether this is a unconditional jump type of instruction
        self.call = False               # Whether this is a call type of instruction
        self.jump = False               # Any kind of jump/call etc. that could change the execution flow and has a target
        self.return_ = False            # Whether this is a return kind of instruction (next will not be executed)

        self.raw_target = None          # For jumps etc. the raw string that gdb displays

        self.target_name = None
        self.parsed_target_name = None

        self.raw_reference = None       # For all kinds of operations gdb displays an address or more 
        self.reference = []
        self.parsed_reference = None

        self.targets = set()            # jmp/call target address(es) of this instruction
        self.target_of = set()          # instructions at these addresses may jump to us
        self.address = None             # Address this instruction is stored at
        self.offset = None              # Offset relative to function start
        self.bytes = None               # Byte sequence that encodes this instruction
        self.marked = False             # Is marked by gdbs "next to be executed" marker
        self.xmarked = False            # marked by a user defined marker
        self.rmarked = False            # marked by the "possibly current position" heuristic
        self.prefix = ""
        self.infix = ""
        self.jumparrows = ""
        self.arrowwidth = 0
        self.bt = None
        self.history = None
        self.bt_idx = None
        self.extra = []
        self.static_extra = []
        self.file_line = None
        self.override_register_set = None
        self.possible_in_register_sets = []
        self.possible_out_register_sets = []
        self.iclass = None

        self.possible_in_flag_sets = []
        self.possible_out_flag_sets = []
        self.next = None
        self.previous = None
        self.passes = 0
        self.file = None
        self.line = None
        self.unhandled = False
        self.explanation = []
        self.last_seen_registers = None # last time this was marked with real registers

    # parse common parts of all asm dialects like
    # - current position marker
    # - address
    # - offset marker ( <+55> )
    def parse_common( self, line, m, oldins ):
        self.line = line

        tokens = line.split()
        marker = m.group(1)
        if( marker is not None ):
            self.marked = True
            tokens = tokens[1:]

        addr = tokens[0].strip()
        # A : there tells us there is no <+###> offset following (common when the symbol is not known)
        if( addr[-1] == ":" ):
            addr = addr[:-1]
            self.offset = ""
            del tokens[0] # address
        else:
            self.offset = tokens[1].strip()[1:-2]
            if( self.offset[0] == "+" ):
                self.offset = self.offset[1:]
            del tokens[0] # address
            del tokens[0] # offset

        self.address = vdb.util.xint(addr)

        return tokens

    def color_mnemonic( self ):
        if( len(color_mnemonic.value) > 0 ):
            return vdb.color.color(mnemonic,color_mnemonic.value)
        else:
            return self.color_mnemonic_class()

    def color_mnemonic_class( self ):
        col = asm_class_colors.get(self.iclass)
        return vdb.color.color(self.mnemonic,col)

    def add_explanation( self, ex ):
        if( len(self.explanation) > 0 ):
            if( ex == self.explanation[0] ):
                return
        self.explanation.append(ex)

    def reset_argspecs( self ):
        for arg in self.arguments:
            arg.reset_argspec()

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
                args += f",[{a.argspec}]({av},@{aa} [{a}])"
                if( a.target ):
                    args += "T"
            self.add_extra(f"ARG {args}")


    def _gen_extra( self ):
        self._gen_extra_regs( "INREG", self.possible_in_register_sets )
        self._gen_extra_regs( "OUTREG", self.possible_out_register_sets )
        if( self.last_seen_registers is not None ):
            self._gen_extra_regs( "LASTREG", [ self.last_seen_registers ] )

        for pfs in self.possible_in_flag_sets:
            self.add_extra(f"INFLG {pfs}")
        for pfs in self.possible_out_flag_sets:
            self.add_extra(f"OUTFLG {pfs}")
        if( self.unhandled ):
            self.add_extra("UNHANDLED")
        self.add_extra(f"REFERENCES = {self.reference}")
        self.add_extra(f"PASS = {self.passes}")
#        self.add_extra(f"NEXT = {self.next}")

    def _gen_debug( self ):
        self.add_extra( f"self.line      : '{self.line}'")
        self.add_extra( f"self.mnemonic  : '{self.mnemonic}'")
        self.add_extra( f"self.next      : '{self.next}'")
        self.add_extra( f"self.args      : '{self.args}'")
        self.add_extra( f"self.targets   : '{self.targets}'")
        self.add_extra( f"self.target_of : '{self.target_of}'")
        self.add_extra( f"self.reference          : '{self.reference}'")
        self.add_extra( f"self.parsed_reference   : '{self.parsed_reference}'")
        self.add_extra( f"self.raw_target         : '{self.raw_target}'")
        self.add_extra( f"self.raw_reference      : '{self.raw_reference}'")
        self.add_extra( f"self.target_name        : '{self.target_name}'")
        self.add_extra( f"self.parsed_target_name : '{self.parsed_target_name}'")


    """
    Add some extra message to be displayed along with the instructions
    lvl 
    * 0 Aligned with mnemonic
    * 1 Aligned with arguments
    * 2 Aligned with the column after the instruction
    s
    * a string (can not be coloured)
    * a tuple[str,int] for table cells. Third value will be extended to be 0 to not garble the table
    * a list. Will vdb.color.concat() them to a tuple for a cell
    """
    def add_extra( self, s, lvl = 0, static = False ):
#        print(f"add_extra({type(s)}:{s})")
        if( isinstance(s,string_ref) ):
#            s = str(s)
            pass
        if( isinstance(s,str) ):
            # Check, remove after it never triggers
            unc = vdb.color.colors.strip_color(s)
#            print(f"uncoloured: {unc}")
            if( unc != s ):
                raise RuntimeError(f"add_extra({s}) with colours only not allowed")
            s = (s,0,0)
        elif( isinstance(s,tuple) ):
            if( len(s) == 2 ):
                s0,s1 = s
                s = (s0,s1,0)
            elif( len(s) != 3 ):
                raise RuntimeError(f"add_extra({s}) with tuple only of len 2 or 3 allowed")
        elif( isinstance(s,list) ):
            ns = ("",0)
            for rs in s:
                if( isinstance(rs,str) ):
                    unc = vdb.color.colors.strip_color(rs)
                    if( unc != rs ):
                        raise RuntimeError("add_extra([{s}]) with colours only not allowed")
                ns=vdb.color.concat(ns,rs)
            s0,s1 = ns
            s = (s0,s1,0)

#        print("s[0] = '%s'" % (s[0],) )
#        print("s[1] = '%s'" % (s[1],) )

        if( static ):
            self.static_extra.append( (s,lvl) )
        else:
            self.extra.append( (s,lvl) )

    def __str__( self ):
        ta = "None"
        if( len(self.targets) != 0 ):
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
        nx=""
        if( self.next is not None ):
            nx=f"…{int(self.next.address):#0x}"
        ret = f"INS @{a:x} => {ta} <={to}{nx}"
        return ret

    @abc.abstractmethod
    def parse( self, line, m, oldins ):
        pass
# Reset should we ever be able to change classes dynamically


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
        self.current_branch = 0
        self.bt_q = []
        self.var_addresses = None
        self.var_expressions = None
        self.function_header = None
        self.initial_registers = register_set()
        self.marker = None
        self.frame = None

    def get_frame_register( self, reg ):
        ret = None
        if( self.frame is not None ):
            ret=self.frame.read_register(reg)
        return ret

    def sort( self ):
        self.instructions.sort( key = lambda x:( x.address, x ) )

    def color_address( self, addr, marked, xmarked, rmarked ):
        mlen = 2 + vdb.arch.pointer_size // 4
        if( next_mark_ptr ):
            if( marked ):
                return vdb.color.colorl(f"{addr:#0{mlen}x}",color_marker.value)
            if( xmarked ):
                return vdb.color.colorl(f"{addr:#0{mlen}x}",color_xmarker.value)
            if( rmarked ):
                return vdb.color.colorl(f"{addr:#0{mlen}x}",color_rmarker.value)
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
            if( ins.marked ):
                self.marker = int(ins.address)
#                print(f"{self.marker=:#0x}")

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

        if( debug_all() ):
            for ins in self.instructions:
                if( debug_all(ins) ):
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
        btsym = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if( self.current_branch >= len(btsym) ):
            ret = f"({self.current_branch})"
        else:
            ret = btsym[self.current_branch]
        self.current_branch += 1
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
#        vdb.util.bark() # print("BARK")
        self.ins_map = {}
        idx = 0
        midx = None
        self.current_branch = 0
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
#        print(f"compute_context({context=},{marked_line=})")
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
        if( len(callgrind_eventmap) > 0 ):
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
                        , ("x" ,[ ("xi History",",,bold",0,0)])
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
        num_headfields = len(header)

        cg_columns = 0
        if( "c" in showspec ):
            cg_columns = len(cg_header)
        from vdb.track import parse_breakpoints
        raw_breakpoints = parse_breakpoints()

        breakpoints = {}
        for _,bp in raw_breakpoints.items():
            breakpoints[bp.address] = bp

        current_pc = self.get_frame_register(last_working_pc)
        if( current_pc is None ):
            current_pc = 0
        else:
            current_pc = int( current_pc )
#        print(f"{current_pc=:#0x}")
#        vdb.util.bark() # print("BARK")
        for idx,i in enumerate(self.instructions):
            if( idx > 0 ):
                previous = self.instructions[idx-1]
                if( previous.address <= current_pc < i.address ):
#                    print(f"{i.address=}")
                    previous.rmarked = True
#            print(f"{len(otbl)=}\r",end="",flush=True,file=sys.stderr)
            line_extra = []
            if( header_repeat.value is not None and not suppress_header ):
                if( header_repeat.value > 0 ):
                    if( cnt % header_repeat.value == 0 ):
                        otbl.append( header )
                elif( cnt == 0 ):
                    otbl.append( header )

            if( source ):
                if( i.file is None ):
                    i.file,i.line = info_line( i.address )
                fl = f"{i.file}:{i.line}"
                fl = [ (fl,0,0) ]
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
                marker_str=" "

                bp = breakpoints.get(i.address, None )

                if( bp is not None ):
                    if( bp.enabled ):
                        bpmark=bp_marker.value
                        bpnum=bp_numbers.value
                        mcol = color_bpmarker.value
                    else:
                        bpmark=bp_marker_disabled.value
                        bpnum=bp_numbers_disabled.value
                        mcol = color_bpmarker_disabled.value

                    if( bp_number.value ):
#                        for ii in range(0,len(bpnum)):
#                            print(f"{ii:2} : {bpnum[ii-1]}")
                        num=None
                        try:
                            num=int(bp.number)
                        except ValueError:
                            try:
                                num=int(bp.key[0])
                            except ValueError:
                                num=None
                        if( num is not None ):
                            if( num > len(bpnum) ):
#                                mval=bpmark
                                mval=str(num)
                            else:
                                mval=bpnum[num-1]
                        else:
                            mval=bpmark
                    else:
                        mval=bpmark
                    marker_str += vdb.color.color_str( mval, mcol )

                
                marked_line = cnt
                color = None
                if( i.marked ):
                    color = color_marker.value
                elif( i.xmarked ):
                    color = color_xmarker.value
                elif( i.rmarked ):
                    color = color_rmarker.value
                else:
                    marked_line = None

                if( color is not None ):
                    marker_str+=vdb.color.color_str(next_marker.value,color)

                if( marked_line is not None ):
                    context_start, context_end = self.compute_context(context,marked_line)
                marker_str+=" "
                line.append( marker_str )

            if( "a" in showspec ):
                prejump += 1
                line.append( self.color_address( i.address, i.marked, i.xmarked, i.rmarked ))


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

            if( "x" in showspec ):
                prejump += 1
                if( ( xilist := xi_history.get(i.address,None) ) is not None ):
                    entry = ""
                    for xi in xilist:
                        entry = f"{entry},{xi}"
                    entry = entry[1:]
                    line += [ entry ]
                else:
                    line += [None]

            if( "c" in showspec ):

                ci = callgrind_data.get( i.address, None )
                if( ci is not None ):
                    for _,jump in ci.jumps.items():
                        line_extra.append( (str(jump),0,0) )
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
#                mne = self.color_mnemonic(i.mnemonic)
                mne = i.color_mnemonic()
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

            reference_lines = []
            if( "r" in showspec ):
                rtpl=("",0)
                if( i.unhandled ):
                    rtpl=vdb.color.colorl("!","#900")

                if(len(i.reference) == 0 ):
                    line.append(rtpl)
                else:
                    # Refrence line data plus its display length
#                    print("i.reference = '%s'" % (i.reference,) )
                    for rf in i.reference:
#                        print("rf = '%s'" % (rf,) )
#                        print("type(rf) = '%s'" % (type(rf),) )
#                        print("rtpl = '%s'" % (rtpl,) )
                        if( isinstance(rf,str) ):
                            rf = (rf,len(rf))
                        if( rtpl[1] > 0 and ( rtpl[1] + rf[1] + 1) > ref_width.value ): # would be too big, start a new one
                            reference_lines.append(rtpl)
                            rtpl=("",0)
                        if( rtpl[1] > 0 ):
                            rtpl=vdb.color.concat( [rtpl,",",rf] )
                        else:
                            rtpl=rf
#                    print("rtpl = '%s'" % (rtpl,) )
                    if( rtpl[1] > 0 ):
                        reference_lines.append(rtpl)
                    # only append one, the others will be put onto seperate "empty" lines later
                    if( len(reference_lines) > 0 ):
                        line.append(reference_lines[0])
                        reference_lines = reference_lines[1:]

            # t : show our target, and only the raw_target if our target is unavailable
            # T : Always show our target and the raw target, even when both exist
            if( any((c in showspec) for c in "tT" ) ):
                if( len(i.reference) == 0 ):
                    if( i.targets is not None ):
                        for tgt in i.targets:
                            symtree = vdb.memory.get_symbols(tgt,1)
                            for sym in symtree:
                                offset = tgt - sym.begin
                                name = sym.data
                                if( offset == 0 ):
                                    sstr = f"{tgt:#0x} <{name}>"
                                else:
                                    sstr = f"{tgt:#0x} <{name}+{offset}>"
                                #line.append( sstr )
                                ltpl = line[-1]
                                ltpl=vdb.color.concat( [ltpl,",",sstr] )
                                line[-1] = ltpl
                if( "T" in showspec ):
                    if( i.target_name is not None ):
                        line.append( "TGT:"+wrap_shorten(i.target_name))


#            ret.append(line)
            cnt += 1
#            print("cnt = '%s'" % (cnt,) )
#            print("len(otbl) = '%s'" % (len(otbl),) )
            if( asm_explain.value ):
                for e in i.explanation:
                    line_extra.append( vdb.color.colorl(e,color_explanation.value) )

            def output_extra( lst, otbl, lvl = None ):
                if( lst is None ):
                    return
                if( len(lst) == 0 ):
                    return
                if( lvl is not None ):
                    lst = list( (x,lvl) for x in lst )
#                print("lst = '%s'" % (lst,) )

                for ex,nlvl in lst:
                    if( isinstance(ex,str) ):
                        unc = vdb.color.colors.strip_color(ex)
                        if( unc != ex ):
                            raise RuntimeError(f"List contains coloured only entry: {ex}")
#                    print("ex = '%s'" % (ex,) )
#                    print("len(ex) = '%s'" % (len(ex),) )
#                    print("type(ex) = '%s'" % (type(ex),) )
                    if( isinstance(ex,tuple) ):
                        if( len(ex) == 2 ):
                            a,b = ex
                            ex = (a,b,1)
                    elif( isinstance(ex,string_ref) ):
                        ex = (str(ex),len(ex),1)
                    else:
                        ex = (ex,len(ex),1)
#                    print("ex = '%s'" % (ex,) )
                    pre = ( prejump + cg_columns) * [None]
                    post = (postjump-1) * [None]
                    if( postarrows is None ):
                        el = pre + post
                    else:
                        el = pre + [postarrows] + post
                    el += nlvl*[None]
#                    el = ["m","a","h","H","o","d","BYTES" + str(len(line)-1)]
                    el.append(ex)
#                    print("el = '%s'" % (el,) )
                    otbl.append(el)

#            output_extra(["END"],0,otbl)
            output_extra( reference_lines,otbl,2)
            output_extra(i.static_extra,otbl)
            output_extra(i.extra,otbl)
            output_extra(i.file_line,otbl,0)
            output_extra(line_extra,otbl,1)


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
                tr.td_raw(vdb.dot.color(i.args_string,color_args_dot.value))
            else:
                tr.td_raw("&nbsp;")

        if( "r" in showspec ):
            f = ""
            for r in i.reference:
                if( isinstance(r,str) ):
                    r = colors.strip_color(r)
                elif( isinstance(r,tuple) ):
                    r = colors.strip_color(r[0])

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




#print("arm_conditional_jump_mnemonics = '%s'" % (arm_conditional_jump_mnemonics,) )


pc_list = [ "pc", "rip", "eip", "ip" ]
last_working_pc = ""

current_arch = None


def configure_arch( arch = None ):
#    print(f"configure_arch( {arch=} )")
    archname = "x86"
    origarch = archname
#    print(f"forced arch: {arch}")
    try:
        if( arch is not None ):
            archname = arch
        else:
            # might throw "no frame currently selected" when not running
            archname = gdb.selected_inferior().architecture().name()
#            print(f"gdb frame arch {archname}")

        origarch = archname
    except gdb.error:
#        vdb.print_exc()
        try:
            archname = gdb.execute("show architecture",False,True)
#            print(f"show architecutre: {archname}")
            archname = archname.split('"')
            archname = archname[3]
#            print(f"parsed {archname=}")
        except:
            vdb.log(f"Not configured for architecture {archname}, falling back to x86", level=2 )

    
#    print(f"Trying aliases of {archname}")
    archname = arch_aliases.get(archname,archname)
#    print(f"dealiased {archname=}")
    if( archname.startswith("armv") ):
        vdb.log(f"Architecture {archname} prefix mapped to arm, you might want to add it to aliases",level=3)
        arch_aliases[archname] = "arm"
        archname = "arm"
#    traceback.print_stack()

    global current_arch
    if( current_arch is not None and archname == current_arch.name ): # already setup
        return
    vdb.log(f"Configuring asm architecture {archname}",level=3)

    imod = importlib.import_module(f"vdb.asm.{archname}")
    current_arch = imod

    try:
        module = sys.modules[__name__]
        # First set them to the default architecture
#        for gv in dir(module):
#            if( gv.startswith("x86_") ):
#                varn = gv[4:]
#                def_val = getattr(module,gv,None)
#                if( def_val is not None ):
#                    setattr( module, varn, def_val )
#                    print(f"{varn} => {def_val}")

        # Now overwrite with the architecture name ( note that the vt_flow stuff does it in its own way so we don't
        # interfere here with setting those
#        arch_prefix = archname + "_"
#        print("arch_prefix = '%s'" % (arch_prefix,) )
#        for gv in dir(module):
#            if( gv.startswith(arch_prefix) ):
#                varn = gv[len(arch_prefix):]
#                xval = getattr(module,gv)
#                setattr( module, varn, xval )
#                print(f"{varn} => {xval}")
    except:
        pass

#    current_arch = archname
    gen_vtable()
    return archname


class fake_frame:

    class fake_function:
        def __init__( self ):
            self.name = "__fake_function__"
            self.linkage_name = self.name

    class fake_architecture:
        def registers( self ):
            return []

    def __init__( self ):
        pass

    def read_register(self,reg):
        return None

    def function( self ):
        return self.fake_function()

    def block( self ):
        return []

    def architecture( self ):
        return self.fake_architecture()

def fix_marker( ls, alt = None, frame = None, do_flow = True ):
#    print(f"fix_marker({ls},{alt},frame,{do_flow})")

    try:
#        print(f"{last_working_pc=}")
#        vdb.util.bark() # print("BARK")
        mark = vdb.util.gint(f"${last_working_pc}")
#        vdb.util.bark() # print("BARK")
#        print(f"{last_working_pc=} = {mark=:#0x}")
    except gdb.error:
#        vdb.util.bark() # print("BARK")
#        vdb.print_exc()
        try:
#            print(f"{alt=}")
#            vdb.util.bark() # print("BARK")
#            mark = vdb.util.gint(alt)
            mark = gdb.parse_and_eval(alt)
            if( mark.type.code not in { gdb.TYPE_CODE_INT, gdb.TYPE_CODE_PTR } ):
                mark = mark.address

#            print(f"{mark=}")
#            print(f"{mark.type=}")
#            print(f"{vdb.util.gdb_type_code(mark.type.code)=}")
        except gdb.error:
#            vdb.util.bark() # print("BARK")
#            vdb.print_exc()
            mark = None
#    vdb.util.bark() # print("BARK")
#    if( mark is not None ):
#        print(f"{mark=}")
#    if( ls.marker is not None ):
#            print(f"{ls.marker=:#0x}")

    # marker hasn't changed, no need to update anything
    if( ls.marker == mark ):
        return ls

    current_pc = ls.get_frame_register(last_working_pc)
    if( current_pc is None ):
        current_pc = 0
    else:
        current_pc = int( current_pc )
    if( mark is not None ):
#        print(f"{mark=:#0x} => {ls.marker=:#0x}")
        ls.marker = int(mark)

    for idx,i in enumerate(ls.instructions):
        previous = None
        if( idx > 0 ):
            previous = ls.instructions[idx-1]
        i.xmarked = False
        if( i.address == mark ):
            i.marked = True
        else:
            i.marked = False
        if( previous is not None ):
            if( previous.address <= current_pc < i.address ):
                previous.rmarked = True
            else:
                previous.rmarked = False

    update_vars(ls,frame)
    ls.do_backtrack()
    if( do_flow ):
        register_flow(ls,frame)
    return ls


parse_cache = {}

def split_args( in_args : str ) -> list[str]:
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
        print("BUG? ##############################################")
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

#TODO This whole thing is a total mess, we need at least a bit documentation and possibly refactor some stuff to tell what it is that this funciton is really doing

# frame is the frame to extract the information from
# lng is the ListiNG to attacht the gathered information to
# symlist can either be:
# - a gdb fields() iterator
# - a gdb block
# - an empty list
# - a list with one fake symbol
# pval is when recursing into a struct the variable object
# prefix is the variable expression so far, empty string when starting at the outer frame
# reglist not sure what this is really, we sometimes pass an empty list. This is somehow used for functions when
# parameters are passed in registers
def gather_vars( frame, lng, symlist, pval = None, prefix = "", reglist = None, level = 0 ):
    """
    @returns a string suitable for display as function parameter list ( together with values )
    """
#    print(".",end="",flush=True)
#    if( pval is not None ):
#        try:
#            print(f"{int(pval.address)=:#0x}")
#            print(f"gather_vars({frame=},{lng=},symlist,{str(pval)=},{prefix=},{reglist=},{level=}")
#        except:
#            vdb.print_exc()

    # We don't want to descend too deep into structures, it could get messy and more unlikely to be accssed.
    if( level >= gv_limit.value ):
        return ""
    level += 1 # to keep track how deep we decended
    ret = "" # Add to this for later return

    # XXX Figure out exactly how we use this
    regindex = -1
    if( reglist is None ):
        regindex = 0
        reglist = current_arch.argument_registers
    # TODO support float/double registers and vectors

    # Base of the stackframe, almost all local variable accesses will use expressions relative to this so these
    # expressions we synthesize to later be able to match
    rbp = current_arch.base_pointer

    rbpval = frame.read_register(rbp)
    if( rbpval is not None ):
        rbpval = int(rbpval)

    rsp = current_arch.stack_pointer

    rspval = frame.read_register(rsp)
    if( rspval is not None ):
        rspval = int(rspval)


    if( frame.function() is not None ):
        fname = frame.function().name
    else:
        fname = "__anonymous__"

    # funcion_registers contains user set registers for named functions. This is our first input to the initial
    # registers, the user can help us here when we cannot automatically determine values at the function start (e.g.
    # when the $pc is in the middle of it already)
    lng.initial_registers.merge( function_registers.get(fname,register_set() ) )

    if( debug_all() ):
        print("symlist = '%s'" % (symlist,) )

#    print(f"{type(symlist)=}")
    # type(symlist)=<class 'list'>
    # type(symlist)=<class 'gdb.Block'>
    # type(symlist[0])=<class 'gdb.Field'>
#    if( isinstance(symlist,list) and len(symlist) > 0 ):
#        print(f"{type(symlist[0])=}")
    for b in symlist:
        # type(b)=<class 'gdb.Field'>
        # type(b)=<class 'gdb.Symbol'>
        if( debug_all() ):
            vdb.util.bark() # print("BARK")
            print("b = '%s'" % (b,) )
            print("b.type = '%s'" % (b.type,) )
            print("b.type.code = '%s'" % (vdb.util.gdb_type_code(b.type.code),) )
            print("b.name = '%s'" % (b.name,) )
            try:
                print("b.type.fields() = '%s'" % (b.type.fields(),) )
            except:
                print("fields() failed")

        bval = None
        baddr = None
        try:
            # First call, not recursing into an existing variable...
            if( pval is None ):
#                print(f"{b.is_argument=}")
#                print(f"{b.is_constant=}")
#                print(f"{b.is_function=}")
#                print(f"{b.is_variable=}")
                if( not b.is_argument and not b.is_variable ):
#                    print(f"Skipping {b.print_name}")
                    continue
#                print(f"{type(b)=}")
                bval = b.value(frame)
                xbaddr= bval.address
                if( xbaddr is not None ):
                    int(xbaddr)
                    baddr = xbaddr
#                print("bval = '%s'" % (bval,) )
            else:
#                print(f"{b.name=}")
#                print(f"{pval}")
                if( b.name is None ): # ignore anonymous structs/unions etc. for now
                    continue
                if( b.is_base_class ):
                    continue
                pstype = pval.type.strip_typedefs()
                if( pstype.code == gdb.TYPE_CODE_ENUM ):
                    bval = pval
                else:
                    bval = pval[b.name]
                xbaddr = bval.address
                if( xbaddr is not None ):
                    int(xbaddr)
                    baddr = xbaddr
            bval.fetch_lazy()
            if( bval.is_optimized_out ):
                continue
        except gdb.MemoryError:
            # Don't care about things that are inaccessible really
            pass
        except gdb.error as e:
#            print(f"{e=}")
#            vdb.print_exc()
            if( str(e).find("optimized out") == -1 ):
                vdb.print_exc()
                vdb.util.bark() # print("BARK")
                print("pval = '%s'" % (pval,) )
                print("pval.type = '%s'" % (pval.type,) )
                print("pval.type.code = '%s'" % (vdb.util.gdb_type_code(pval.type.code),) )
                print("pstype = '%s'" % (pstype,) )
                print("pstype.type.code = '%s'" % (vdb.util.gdb_type_code(pstype.type.code) ,) )
                print("b.name = '%s'" % (b.name,) )
                print("b = '%s'" % (b,) )
                print("b.type = '%s'" % (b.type,) )
                print("b.type.code = '%s'" % (vdb.util.gdb_type_code(b.type.code),) )
            else:
                # Has been optimized out, no point in digging deeper
                continue

        except KeyboardInterrupt:
            raise
        except:
            traceback.print_stack()
            vdb.print_exc()
            print("b.name = '%s'" % (b.name,) )
            print("pval = '%s'" % (pval,) )
            pass

        # We already know about the address, so probably been there through another path
        if( baddr is not None and int(baddr) in lng.var_addresses ):
#            print("-",end="",flush=True)
            return ret

        if( bval is None ):
            print("BUG: bval is none")
            traceback.print_stack()
            continue

        bval.fetch_lazy()
        xbval=bval
        # XXX FIXME This can get quickly slow as it exponentially blows up the read variables. Figure out a good way to
        # prevent duplications. Maybe a set of already read addresses? Maybe only ever try . when -> fails?
        try:
#            vdb.util.bark() # print("BARK")
#            print(f"{xbval=}")
            uxbval = bval.dereference()
#            print("bval.type.fields() = '%s'" % (bval.type.fields(),) )
            ret += gather_vars( frame, lng, uxbval.type.fields() , uxbval, prefix + b.name + "->", [], level )
        except KeyboardInterrupt:
            raise
        except:
#            vdb.print_exc()
            pass
        try:
#            vdb.util.bark() # print("BARK")
#            print(f"{xbval=}")
            ret += gather_vars( frame, lng, b.type.fields(), xbval, prefix + b.name + ".", [], level )
        except KeyboardInterrupt:
            raise
        except:
#            vdb.print_exc()
            pass

        try:
#            vdb.util.bark() # print("BARK")
#            print(f"{xbval=}")
            ret += gather_vars( frame, lng, b.type.target().unqualified().fields(), xbval, prefix + b.name + ".", [], level )
        except KeyboardInterrupt:
            raise
        except:
#            vdb.print_exc()
            pass

#        try:
#            bval = bval.referenced_value()
#        except:
#            pass

        if( debug_all() ):
            print("prefix = '%s'" % (prefix,) )
            print("b.name = '%s'" % (b.name,) )
            print("baddr = '%s'" % (baddr,) )
        if( baddr is not None ):
            lng.var_addresses[int(baddr)] = prefix + b.name

            # One expression relative to the base pointer
            boffset = int(baddr) - rbpval
            expr = f"{boffset:#0x}(%{rbp})"
            lng.var_expressions[expr] = prefix + b.name

            # And one relative to the stack pointer
            boffset = int(baddr) - rspval
            expr = f"{boffset:#0x}(%{rsp})"
            lng.var_expressions[expr] = prefix + b.name

        try:
#            print("b.name = '%s'" % (b.name,) )
#            print("b.is_argument = '%s'" % (b.is_argument,) )
            if( b.is_argument ):
                if( debug_all() ):
                    print("b = '%s'" % (b,) )
                # For arguments we take the current call register, but only up to the point where things are done in a
                # register, the rest will go to stack anyways
                # XXX We don't support float stuff yet
                if( regindex >= 0 and regindex < len(reglist) ):
                    if( debug_all() ):
                        vdb.util.bark() # print("BARK")
                        print("regindex = '%s'" % (regindex,) )
                        print("reglist[regindex] = '%s'" % (reglist[regindex],) )
                        print("bval = '%s'" % (bval,) )
                        print("bval.address = '%s'" % (bval.address,) )
                        print("bval.type = '%s'" % (bval.type,) )
                        print("bval.type.is_scalar = '%s'" % (bval.type.is_scalar,) )
                        print("bval.type.code = '%s'" % (vdb.util.gdb_type_code(bval.type.code),) )
                        print("type(lng.initial_registers) = '%s'" % (type(lng.initial_registers),) )
                        print("lng.initial_registers = '%s'" % (lng.initial_registers,) )
        
                    if( bval.type.code == gdb.TYPE_CODE_REF ):
                        lng.initial_registers.set( reglist[regindex] , int(bval.address), origin=f"gather_vars(CODE_REF)@{bval.address}")
                    elif( bval.type.code == gdb.TYPE_CODE_STRUCT and not bval.type.is_scalar ):
                        lng.initial_registers.set( reglist[regindex] , int(bval.address), origin=f"gather_vars(CODE_REF)@{bval.address}")
                    else:
#                        print(f"{vdb.util.gdb_type_code( bval.type.code )} : {reglist=}, {regindex=}")
                        lng.initial_registers.set( reglist[regindex] , int(bval), origin=f"gather_vars()@{bval.address}")
                    if( debug_all() ):
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
        except AttributeError:
#            vdb.print_exc()
            pass
        except:
            vdb.print_exc()
            print("bval = '%s'" % (bval,) )
            print("bval.address = '%s'" % (bval.address,) )
            print("bval.type = '%s'" % (bval.type,) )
            print("bval.type.is_scalar = '%s'" % (bval.type.is_scalar,) )
            print("bval.type.code = '%s'" % (vdb.util.gdb_type_code(bval.type.code),) )
            pass
    if( debug_all() ):
        print("ret = '%s'" % (ret,) )
        print("lng.var_addresses = '%s'" % (lng.var_addresses,) )
        for k,v in lng.var_addresses.items():
            print(f"{k:#0x} : {v}")
    return ret


# ls is the current listing to be updated,
# frame is the frame to update things from
# We want to mainly collect:
# - expressions known to contain ceratin variables (e.g. 0x18(%rsp) or so). These will stay the same for each invocation
# - actual addresses of stuff used in the function, this can be
#   - globals/statics. those addresses should never change
#   - locals on the stack. those can be different on each invocation
#
# This should work recursively so for an address we can see it is a.x.y.__ptr
def update_vars( ls, frame ):

    # This is manually added variables by user command
    va = function_vars.get( ls.function, {} ).copy()

    # Seed var_addresses with a copy
    ls.var_addresses = va.copy()
#    print("ls.var_addresses = '%s'" % (ls.var_addresses,) )
    ls.var_expressions = {}

    # ls.function is sometimes mangled, try to demangle it
    if( ls.function is not None ):
        try:
            ls.function = gdb.execute(f"demangle {ls.function}",False,True).strip()
        # It throws when it can't demangle, but we want to proceed with the mangled name then, better than nothing
        except gdb.error:
            pass

    fun = frame.function()
    if( fun ):
        try:
            funname = gdb.execute(f"demangle {fun.linkage_name}",False,True).strip()
        except gdb.error:
            funname = fun.linkage_name

    if( debug_all() ):
        print(f"{type(fun)=}")
        print(f"{fun.print_name=}")
        print(f"{fun.linkage_name=}")
        print(f"   {fun.name=}")
        print(f"{ls.function=}")
        print(f"{funname=}")
        print(f"{frame.name()=}")
        print(f"{(fun.name == ls.function)=}")
        print(f"{ls.function.endswith(fun.name)=}")
        print(f"{ls.function == funname=}")
        print(f"{frame=}")
        print(f"{fun.symtab=}")
        lookedup = gdb.lookup_symbol(ls.function)
        print(f"{lookedup=}")
        lookedup = gdb.lookup_global_symbol(ls.function)
        print(f"{lookedup=}")

    # only extract names from the block when we disassemble the current frames function
    # XXX Can we somehow look in the backtrace for other frames that might match? What if two frames in two different
    # threads do?

    if( fun is not None and funname == ls.function ):
        block = frame.block()
    else:
        block = None
#    print("block = '%s'" % (block,) )
#    for b in block:
#        print("b = '%s'" % (b,) )
#        print("b.is_argument = '%s'" % (b.is_argument,) )
#        if( b.value(frame).type.tag is None ):
#            print("b.value(frame) = '%s'" % (b.value(frame),) )
#        print("b.value(frame).address = '%s'" % (b.value(frame).address,) )

    if( fun is None ):
        funhead = "????"
    else:
        funhead = ls.function

    # This is still the user defined variables only, run gather_vars mainly to figure out the expressions for it
    for a,n in va.items():
#        print("a = '%s'" % (a,) )
#        print("n = '%s'" % (n,) )
        try:
            vv = frame.read_var(n)
#            print("vv = '%s'" % (vv,) )
#            print("vv.type = '%s'" % (vv.type,) )
#            when # will this be called? So far We did not see it anywhere
            # XXX do we want to output this anywhere?
#            gather_vars( frame, ls, vv.type.fields(), vv, n + "." )
            # Would it make more sense to just assemble a complete list and then run this?
            gather_vars( frame, ls, [ fake_symbol(vv,n) ], None, n + "." )

        except KeyboardInterrupt:
            raise
        except TypeError:
            pass
        except ValueError:
#            print(f"{n} not found in frame")
            # variable not recognized
            pass

    # Ask the block (a gdb debug info container thing) for all the local variables, including parameters
    if( block is not None ):
        gv = gather_vars( frame, ls, block )
        # sometimes the args are in a superblock
        if( block.function is None and block.superblock is not None ):
            gv += gather_vars( frame, ls, block.superblock )
    else:
        # XXX Not sure what this would gather anyways?
        gv = gather_vars( frame, ls, [] )

    if( debug_all() ):
        vdb.util.bark() # print("BARK")
        print("gv = '%s'" % (gv,) )

    if( len(gv) > 0 ):
        funhead += "(" + gv + ")"

    # Contains function signature and parameters location information, e.g.
    # main(int, char const**)( argc@0x7fffffffc8dc[-0x344(%rbp)] = 1, argv@0x7fffffffc8d0[-0x350(%rbp)] = 0x7fffffffcd38,)
    ls.function_header = funhead

    if( debug_all() ):
        print(f"{ls.function_header=}")
        tbl=[["Name","Address","Expression"]]
        # XXX Should we indicate if there is a duplication?
        funcmap = {}
        for va,vn in ls.var_addresses.items():
            oa,oe = funcmap.get(vn,(None,None))
            funcmap[vn] = (va,oe)
        for ve,vn in ls.var_expressions.items():
            oa,oe = funcmap.get(vn,(None,None))
            funcmap[vn] = (oa,ve)

        for vn,vx in funcmap.items():
            va,ve = vx
            va = f"{va:#0x}"
            tbl.append( [ vn, va, ve ] )
        vdb.util.print_table(tbl)


ilinere = re.compile('Line ([0-9]*) of "(.*)"')

@vdb.util.memoize()
def info_line( addr ):
    il = gdb.execute(f"info line *{addr:#0x}",False,True)
    m = ilinere.match(il)
    if( m is not None ):
        return ( m.group(2), m.group(1) )
#    print("il = '%s'" % (il,) )
    return (None,None)

def parse_from_gdb( arg, fakedata = None, arch = None, fakeframe = None, cached = True, do_flow = True ):

    vdb.log(f"parse_from_gdb(arg={arg}, fakedata, {arch=}, {fakeframe=}, {cached=}, {do_flow=})",level=5)
    global parse_cache
#    print(f"{len(parse_cache)=}")

    key = arg

    if( len(arg) == 0 ):
        if( gdb.selected_thread() is None ):
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

    if( fakeframe is not None ):
        frame = fakeframe
    else:
        try:
            frame = gdb.selected_frame()
        except:
            frame = fake_frame()

#    print("ret = '%s'" % ret )
    if( ret is not None and fakedata is None ):
        ret.frame = frame
        return fix_marker(ret,arg,frame,do_flow)
    ret = listing()
    ret.frame = frame
#    vdb.util.bark() # print("BARK")
#    print("key = '%s'" % (key,) )
#    print("parse_cache = '%s'" % (parse_cache,) )


    archname = configure_arch(arch)

    if( fakedata is None ):
        dis = gdb.execute(f'disassemble/r {arg}',False,True)
    else:
        dis = fakedata
#    linere = re.compile("^(=>)*\s*(0x[0-9a-f]*)\s*<\+([0-9]*)>:\s*([^<]*)(<[^+]*(.*)>)*")
    linere = re.compile(r"^(=>)*\s*(0x[0-9a-f]*)(\s*<\+([0-9]*)>:)*\s*([^<]*)(<[^+]*(.*)>)*")
    funcre = re.compile("for function (.*):")
    rangere = re.compile("Dump of assembler code from (0x[0-9a-f]*) to (0x[0-9a-f]*):")
    current_function=""

    markers = 0
    oldins = None

    for line in dis.splitlines():

        if( line in set(["End of assembler dump."]) ):
            continue
        if( line.startswith("Address range") ):
            continue
        if( len(line) == 0 ):
            continue

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

        m=re.search(linere,line)

        ins = None
        if( m ):
            ins = current_arch.instruction( line, m, oldins )

        if ins is not None :
            if( ins.marked ):
                markers += 1
            ret.add(ins)
            if( ret.start == 0 ):
                ret.start = ins.address
            else:
                ret.start = min(ret.start,ins.address)
            ret.end = max(ret.end,ins.address)

            oldins = ins
        else:
            print(f"Don't know what to do with '{line}'")
#			print("m = '%s'" % m )
    if( fakedata is None ):
        parse_cache[key] = ret

    if( markers == 0 ):
        ret = fix_marker(ret,arg,frame,do_flow)
    update_vars(ret,frame)

    if( do_flow ):
        register_flow(ret,frame)
    return ret


flow_vtable = {}



def gen_vtable( ):
#    vdb.util.bark() # print("BARK")
    global flow_vtable
#    print(f"{current_arch=}")
    start = "vt_flow_"
    for funname in dir(current_arch):
#        print(f"{funname=}")
        if( funname.startswith(start) ):
            fun = getattr( current_arch, funname )
            funname = funname[len(start):]
            flow_vtable[funname] = fun
#    print("flow_vtable = '%s'" % (flow_vtable,) )


def short_color( symbol ):
    symbol = symbol.split("@")
    symbol[0] = vdb.shorten.symbol(symbol[0],not debug_all() )
    symbol = vdb.color.concat( [ vdb.color.colorl( symbol[0],color_var.value) , "@" , "@".join(symbol[1:]) ] )
    return symbol

def extra_info( vname, spc, addr, extra ):
    symbol = ""
    if( vname is None ):
        _,_,symbol = vdb.memory.get_gdb_sym( addr )
        if( symbol is not None ):
            extra.value += f", esym = {symbol}"
            symbol = short_color(symbol)
        else:
            symbol = ""
        vname = ""
    else:
        vname = short_color(vname)

    if( vdb.memory.mmap.accessible(addr) ):
        if( spc != "@" ):
            spc += "@"
        extra.value += ",access"
        addrstr,pure = vdb.pointer.chain( addr, 32, 1, True, 1, False, asm_tailspec.value, do_annotate = False )
        if( not pure ):
            return (symbol, vdb.color.concat( [ vname, symbol ,spc , addrstr] ) )
        extra.value += ",pure"
    else:
        addrstr = f"{addr:#0x}"

    return (symbol, vdb.color.concat( [ vname ,symbol ,spc , vdb.color.colorl(addrstr,color_location.value) ] ) )

def current_registers( frame ):
    blacklist = set( [ "rip", "eip", "ip", "pc" ] )
    rset = register_set()
    for reg in frame.architecture().registers():
        if( reg.name in blacklist ):
            continue
        rset.set( reg.name, frame.read_register(reg), origin="frame" )
    return rset



def register_flow( lng, frame : "gdb frame" ):
    global flow_vtable
    if( len(flow_vtable) == 0 ):
        gen_vtable()
    if( len( lng.instructions) == 0 ):
        return None

    for i in lng.instructions:
        i.passes = 0
        i.possible_in_register_sets = []
        i.possible_out_register_sets = []
        i.possible_in_flag_sets = []
        i.possible_out_flag_sets = []
        i.extra = []
        i.reset_argspecs()

        # Will copy only ever on the very first call where we did not have a user defined reference
        if( i.parsed_reference is None ):
            i.parsed_reference = i.reference.copy()
        i.reference = []

    ins = lng.instructions[0]
#    print("lng.var_addresses = '%s'" % (lng.var_addresses,) )
    # Try to follow execution path to figure out possible register values (and maybe later flags)
    possible_registers = lng.initial_registers.clone()
#    print("possible_registers = '%s'" % (possible_registers,) )
    possible_flags = flag_set()

    rbp = frame.read_register(current_arch.base_pointer)
    if( rbp is not None ):
        if( vdb.memory.mmap.accessible(rbp) ):
            possible_registers.set( current_arch.base_pointer, rbp, origin="frame.bp" ,)

#    for ins in ret.instructions:
    flowstack = [ (None,None,None) ]

    passlimit = 2
    next = None

    # XXX make it perhaps possible to pre-populate it by an option so we can disable handling this way?
    unhandled_mnemonics = set()

    
    # at the end we advance to the next instruction or get one from a stack of conditional jump points (flowstack)
    while ins is not None:
#        print("ins = '%s'" % (ins,) )
        # Simple protection against any kinds of endless loops
        # XXX Better would be to check (additionally?) if the register and flag sets are the same as in previous runs
        ins.passes += 1

        # Assumes the last one is the target, might be different for different archs
#        print(f"{ins.args=}")
        # XXX x86 relies on this while arm parses them for the instruction already. Unify that.
        # As per convention, rip on x86 as an argument is the next instruction
        if( current_arch.name == "arm" ):
            if( ins.next is not None ):
                possible_registers.set( "pc", ins.next.address, origin="ins.next" )
            elif( len(ins.bytes) > 0 ):
                possible_registers.set( "pc", ins.address + len(ins.bytes),origin="len(ins.bytes)" )
        else:
            if( ins.next is not None ):
                possible_registers.set( "pc", ins.next.address, origin="ins.next" )
            elif( len(ins.bytes) > 0 ):
                possible_registers.set( "pc", ins.address + len(ins.bytes),origin="len(ins.bytes)" )

        if( ins.last_seen_registers is not None ):
            ls = register_set()
            ls.merge( ins.last_seen_registers, origin = "last_seen" )
            ls.merge(possible_registers)
            possible_registers = ls
            #   →  0x0000000000401152 0  <+12>:           48 83 7d f8 04    cmpq  $0x4,-0x8(%rbp) %=0x4,x@-0x8(%rbp),x@@0x7fffffffccc8,x@=0x1
            #                                                               cmpq $0x4,-0x8(%rbp) %=0x4,x@-0x8(%rbp)

        if( ins.marked ):
            cf = current_arch.current_flags(frame)
            if( cf is not None ):
                possible_flags.merge(cf)
            cr = current_registers(frame)
            if( debug_registers.value ):
                for r,(v,o) in cr.values.items():
                    ov,an,origin = possible_registers.get(r)
                    if( ov is not None and v != ov ):
                        ins.add_extra( f"Real register {r} has real value {v:#0x} from {o} but we deduced {ov:#0x} for {an} from {origin}")
            possible_registers.merge(cr)
            ins.last_seen_registers = possible_registers.clone()

        # XXX Refactor to have the register setting etc. just once
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
                        vdb.log(f"Synthesized mnemonic {ins.mnemonic} from {mn}, if their flow is not handled the same, create an additional one for {ins.mnemonic}",level=4)
                        flow_vtable[ins.mnemonic] = fun
                        ins.possible_in_register_sets.append( possible_registers.clone() )
                        ins.possible_in_flag_sets.append( possible_flags.clone() )
                        (possible_registers, possible_flags) = fun( ins, frame, possible_registers, possible_flags )
                        ins.possible_out_register_sets.append( possible_registers.clone() )
                        ins.possible_out_flag_sets.append( possible_flags.clone() )
                        break
                else:
                    ins.unhandled = True
                    # Store for later to be quicker
                    unhandled_mnemonics.add( ins.mnemonic )
            else:
                ins.unhandled = True

        if( ins.unhandled ):
            ins.possible_in_register_sets.append( possible_registers.clone() )
            ins.possible_in_flag_sets.append( possible_flags.clone() )

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
                    flowstack.append( (tgt,possible_registers.clone(), possible_flags.clone()) )

#        if( len(ins.constants) > 0 ):
#            for c in ins.constants:
#                xc = vdb.util.xint(c)
#                    print("vdb.memory.mmap.accessible(xc) = '%s'" % (vdb.memory.mmap.accessible(xc),) )
#                if( vdb.memory.mmap.accessible(xc) ):
#                    ch = vdb.pointer.chain( xc, vdb.arch.pointer_size, 1, True, 1, False, asm_tailspec.value )
#                    ins.reference.append(ch[0])
        printed_addrs = set()



        extra = None
#        vdb.util.bark() # print("BARK")
#        print("ins = '%s'" % (ins,) )
#        print("ins.arguments = '%s'" % (ins.arguments,) )
#        print("ins.args = '%s'" % (ins.args,) )
        # Check if we can output a bit more info about the register values used in this
        if( len(ins.arguments) > 0 ):
            cnt = 0
            target = None
            if( len(ins.arguments) > 1 ):
                target = ins.arguments[1]
            ins_references = []
            for aidx in range(0,len(ins.args)):
                a = ins.args[aidx]
                arg = ins.arguments[aidx]
                extra = string_ref(f"ARG[{aidx}]({arg.argspec}) = {arg}")
                if( debug_registers.value ):
                    ins.add_extra(extra)

                # regardless of argspec we always output based on expression (since that works even if we don't have any
                # register values)
                av = lng.var_expressions.get(a,None)
                extra.value += f", av = {av}"
#                print("av = '%s'" % (av,) )
#                print("a = '%s'" % (a,) )
#                print("lng.var_expressions = '%s'" % (lng.var_expressions,) )
                if( av is not None ):
#                    ins_references.append(  vdb.color.color(av,color_var.value) + "@" + vdb.color.color(a,color_location.value) )
                    ins_references.append( vdb.color.concat( [  vdb.color.colorl(av,color_var.value) ,"@", vdb.color.colorl(a,color_location.value) ] ) )

                try:
                    # If its a target we want to use the value after the instruction executed
                    if( "i" in arg.argspec ):
                        regset = ins.possible_in_register_sets
                    elif( "o" in arg.argspec ):
                        regset = ins.possible_out_register_sets
                    else:
                        # No register set specified, no value available
                        continue
                    if( len(regset) == 0 ): # in case no registers available this causes constants to be shown
                        regset = [ register_set() ]
                    argval = None
                    # Check via the possible register sets the value of the register
                    argaddr = None
                    # target is the target argument to the instruction, mainly here for the type (8/16/32/64 bit register)
                    # the override set is a special one that can be used by the register flow mechanism to override
                    # things used here to display some extra info
                    if( ins.override_register_set is not None ):
                        argval,argaddr = arg.value(ins.override_register_set,target)
                    if( argval is None ):
                        for prs in reversed(regset):
                            argval,argaddr= arg.value(prs,target)
                            if( argval is not None or argaddr is not None ):
                                break
                    addr = argaddr
                    if( argval is not None ):
                        extra.value += f", argval = {argval:#0x}, addr = {addr}"
                    else:
                        extra.value += f", argval = {argval}, addr = {addr}"
                    extra.value += f", argspec = {arg.argspec}"

#                    vdb.util.bark() # print("BARK")
#                    print("ins = '%s'" % (ins,) )
#                    print("addr = '%s'" % (addr,) )
#                    print("printed_addrs = '%s'" % (printed_addrs,) )
                    # We have a an address, which means the value from the argument was located at some memory
                    if( addr is not None and addr not in printed_addrs ):
                        printed_addrs.add(addr)

                        # Check if the memory address is known to host some (local) variable
                        av = lng.var_addresses.get(addr,None)
                        if( debug_all(ins) ):
                            print("###################")
                            print(f"{ins.address=:#0x}")
                            print(f"{addr=:#0x}")
                            print("type(addr) = '%s'" % (type(addr),) )
                            print("av = '%s'" % (av,) )
                        extra.value += f", ava = {av}"

                        if( addr is not None ):
                            if( "@" in arg.argspec ):
                                _,ei = extra_info( av, "@", addr, extra )
                                ins_references.append(ei)
#                                ins_references.append(  vdb.color.color(av,color_var.value) + "@" + vdb.color.color(addr,color_location.value) )
                            if( argval is not None ):
                                if( "=" in arg.argspec and argval not in printed_addrs ):
                                    printed_addrs.add(argval)
                                    _,ei = extra_info( av, "=", argval, extra )
                                    ins_references.append( ei )
#                                    ins_references.append(  vdb.color.color(av,color_var.value) + "=" + vdb.color.color(val,color_location.value) )
                    # No address means its the value of a register or result of an operation
                    if( addr is None and argval is not None and argval not in printed_addrs ):
                        extra.value += "!addr&argval"
                        printed_addrs.add(argval)
                        if( "%" in arg.argspec ):
                            if( av is None ):
                                if( ins.parsed_target_name is None ):
                                    ins.parsed_target_name = ins.target_name
                                av = ins.parsed_target_name
                                if( av is not None ):
                                    if( av[0] == "<" and av[-1] == ">" ):
                                        av = av[1:-1]
                                ins.target_name = None
                                extra.value += f", av={av}"
                            sym,ei = extra_info( av, "%=", argval, extra )
                            ins_references.append( ei )
                            if( sym is not None and len(sym) != 0 ):
                                ins.target_name = None # The plaintext name has been replaced by the symbol expression
                        continue
                        _,_,symbol = vdb.memory.get_gdb_sym( argval )
                        extra.value += f", sym = {symbol}"
                        if( symbol is not None ):
                            symbol = vdb.shorten.symbol(symbol)
                            symbol = symbol.split("@")
                            symbol = vdb.color.color(symbol[0],color_var.value) + "@" + "@".join(symbol[1:])
                            fav = f"{argval:#0x}"
                            ins_references.append(symbol + "@" + vdb.color.color( fav, color_location.value ) )
                            ins.target_name = None # The plaintext name has been replaced by the symbol expression
                        else:
#                            vdb.util.bark() # print("BARK")
#                            print("arg = '%s'" % (arg,) )
#                            print(f"argval = {int(argval):#0x}")
#                            print("vdb.memory.mmap.accessible(argval) = '%s'" % (vdb.memory.mmap.accessible(argval),) )
                            if( vdb.memory.mmap.accessible(argval) ):
#                                vdb.util.bark() # print("BARK")
                                ch = vdb.pointer.chain( argval, vdb.arch.pointer_size, 1, True, 1, False, asm_tailspec.value )
#                                print("ch = '%s'" % (ch,) )
                                ins_references.append(ch[0])
                            else:
                                if( not arg.immediate ):
                                    fav = f"{argval:#0x}"
                                    ins_references.append( "%=" + vdb.color.color(fav,color_location.value) )
                except:
                    extra.value += "EXCEPTION"
                    vdb.print_exc()

                    if( debug_all(ins) ):
                        vdb.print_exc()
                    pass
#            for irx in range(0,len(ins_references)-1):
#                ins_references[irx] = ins_references[irx] + ","
            if( ins.passes > 1 ):
                if( ins.reference == ins_references ):
                    ins.reference = []
                else:
                    ins.reference.append(("ALT:",4))
            ins.reference += ins_references

        for opr in ins.parsed_reference:
            try:
                # some are in brackets
                br=""
                pr = opr[0].strip()
                if( pr[0] == "(" ):
                    br="("
                    pr = pr[1:]
                prv = pr.split()
                xr = vdb.util.xint(prv[0])
                if xr not in printed_addrs:
#                    print("extra = '%s'" % (extra,) )
                    sym,ei = extra_info(None, "~", xr, extra )
                    if( sym is None or len(sym) == 0 ):
#                        print("type(ei) = '%s'" % (type(ei),) )
#                        print("len(ei) = '%s'" % (len(ei),) )
                        ei = vdb.color.concat(ei,br)
                        ei = vdb.color.concat(ei,"".join(prv[1:]))
                    ins.reference.append(ei)
            except:
                ins.reference.append(opr)
                if( debug_all(ins) ):
                    vdb.print_exc()


        if( debug_registers.value ):
            ins._gen_extra()

        # Check if the next instruction would go over the pass limit
        ins = ins.next
        if( ins is not None and ins.passes >= passlimit ):
            ins = None

        # We don't want to pass multiple times over the marked one as here we know exactly what the values are
        if( ins is not None and ins.marked and ins.passes > 0 ):
            ins = None

        while( ins is None ):
            ins,possible_registers,possible_flags = flowstack.pop()
            if( ins is None ): # marker for the flowstack being empty
                break
            if( ins.marked and ins.passes > 0 ):
                ins = None

    # while(ins) done
    if( debug_all() ):
        print("unhandled_mnemonics = '%s'" % (unhandled_mnemonics,) )

def parse_from( arg, fakedata = None, context = None, arch = None ):
#    print(f"parse_from({arg=},,{context=},{arch=})")
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
            ret = parse_from_gdb(arg,fakedata,arch=arch)
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
            vdb.print_exc()
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
    fr.set(vreg, vaddr, f"add_variable({vname},{vreg},{vaddr})")

    print("function_vars = '%s'" % (function_vars,) )
    print("function_registers = '%s'" % (function_registers,) )

    invalidate_cache(None)


def disassemble( argv ):
    dotty = False
    context = None
    fakedata = None
    source = False
    arch = None

#    print(f"disassemble start: {len(parse_cache)=}")

    # XXX Change to argv/flags "api"
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
                    if( len(argv) > 1 ):
                        arch = argv[1]
                    argv=["fake"]
                    break
                elif( argv0[0] == "r" ):
                    gdb.execute("disassemble/r " + " ".join(argv))
                    return None
                elif( argv0[0] == "F" ):
                    invalidate_cache(None)
                    print("Flushed disassembler parse cache")
                    return None
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
                    return None
                else:
                    break

#    print("context = '%s'" % (context,) )
#    print("argv = '%s'" % (argv,) )

    asm_listing = parse_from(" ".join(argv),fakedata,context,arch)
    if( asm_sort.value ):
        asm_listing.sort()
    marked = None

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
        asm_listing.print(asm_showspec.value, context,marked, source)
        if( dotty ):
            g = asm_listing.to_dot(asm_showspec_dot.value)
            oid = id(asm_listing)
            g.write(f"dis.{oid}.dot")
            os.system(f"nohup dot -Txlib dis.{oid}.dot &")
    except:
        vdb.print_exc()
        pass
    return None


def get_single( bpos, showspec_filter = "abomjhHcdtT", extra_filter = "", do_flow = False ):
    ret,_ = get_single_tuple( bpos,showspec_filter,extra_filter,do_flow )
    return ret

def get_single_tuple( bpos, showspec_filter = "abomjhHcdtT", extra_filter = "", do_flow = False ):
    rets="<??>"
    reti=None
    try:
        da=vdb.arch.active().disassemble(int(bpos),count=1)
        da=da[0]
        fake = f"{da['addr']:#0x} <+0>: {da['asm']}"
        li = parse_from_gdb("?",fake,do_flow=do_flow)
        sspec = asm_showspec.value
        showspec_filter += extra_filter
        for x in showspec_filter:
            sspec = sspec.replace(x,"")
        ret = li.to_str(sspec,suppress_header = True)
        ret = ret.splitlines()
        rets = ret[1]
        reti = li.instructions[0]
    except:
        vdb.print_exc()
        pass
    return (rets,reti)

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
dis/F       - Flushes some internal caches
dis/c <CG>  - Loads callgrind information from file <CG>
dis/v       - dis/v argv r1 99 tells the disassembler to assume that the variable argv is stored in register r1 with value 99
dis/s       - Tries to output the source code location where possible

All further parameters are handled like for the built in disasemble command with the exception of addresses that are not
part of a function, unlike the disassemble command those are right away disassembled vdb-asm-nonfunction-bytes (default
16) bytes long
"""

    def __init__ (self):
        super ().__init__ ("dis", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION, replace = True)

    def do_invoke (self, argv ):

        try:
            global from_tty
            from_tty = self.from_tty
            disassemble( argv )
        except gdb.error as e:
            print("asm: %s" % e)
#        except:
#            vdb.print_exc()
#            raise
#            pass
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
        vdb.print_exc()
        pass

# TODO/Ideas
# Go through the code, check for push/pop and stackpointer modifications, try to estimate stack usagee
# Theoretically we should be able to start at the entry point and build a callgraph
# Special marker chars for breakpoints and similar
# For jump tables and pc/ip relative data loads we can mark things as "data" and possibly even the access size and then
# show it accordingly
# For the gather_vars and display stuff, consider the case where a variable doesn't live at an address but is a
# parameter passed in a register. Figure out a way that this is displayed and distinguishable from a variable that lives
# e.g. on the stack ( maybe again @ vs. = ? )
# context should still display header


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
