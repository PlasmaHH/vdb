#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.pointer
import vdb.memory
import vdb.command
import vdb.arch
import textwrap

import gdb

import re
import traceback
import sys

color_names = vdb.config.parameter("vdb-register-colors-names", "#4c0", gdb_type = vdb.config.PARAM_COLOUR)
reg_default = vdb.config.parameter("vdb-register-default","/e")
flag_colour = vdb.config.parameter("vdb-register-colors-flags", "#adad00", gdb_type = vdb.config.PARAM_COLOUR)
int_int = vdb.config.parameter("vdb-register-int-as-int",True)
short_columns = vdb.config.parameter("vdb-register-short-columns",6)
text_len = vdb.config.parameter("vdb-register-text-len",80)
tailspec = vdb.config.parameter("vdb-register-tailspec", "axdn" )
mmapfake = vdb.config.parameter("vdb-register-mmaped-unavilable-zero",False, docstring="When the register memory is unavailable, use 0 for the value instead of blacklisting it")


flag_descriptions = {
        0 : ( 1, "CF",  "Carry",             { 1 : ("CY","(Carry)"),           0 : ("NC","(No Carry)") } ),
        2 : ( 1, "PF",  "Parity",            { 1 : ("PE","(Parity Even)"),     0 : ("PO","(Parity Odd)") } ),
        4 : ( 1, "AF",  "Adjust",            { 1 : ("AC","(Auxiliary Carry)"), 0 : ("NA","(No Auxiliary Carry)") } ),
        6 : ( 1, "ZF",  "Zero",              { 1 : ("ZR","(Zero)"),            0 : ("NZ","(Not Zero)") } ),
        7 : ( 1, "SF",  "Sign",              { 1 : ("NG","(Negative)"),        0 : ("PL","(Positive)") } ),
        8 : ( 1, "TF",  "Trap",              None ),
        9 : ( 1, "IF",  "Interrupt enable",  { 1 : ("EI","(Enabled)"),         0 : ("DI","(Disabled)") } ),
        10: ( 1, "DF",  "Direction",         { 1 : ("DN","(Down)"),            0 : ("UP","(Up)") } ),
        11: ( 1, "OF",  "Overflow",          { 1 : ("OV","(Overflow)"),        0 : ("NV","(Not Overflow)") } ),
        12: ( 2, "IOPL","I/O Priv level",    None ),
        14: ( 1, "NT",  "Nested Task",       None ),
        16: ( 1, "RF",  "Resume",            None ),
        17: ( 1, "VM",  "Virtual 8086 mode", None ),
        18: ( 1, "AC",  "Alignment check",   None ),
        19: ( 1, "VIF", "Virtual interrupt", None ),
        20: ( 1, "VIP", "Virt intr pending", None ),
        21: ( 1, "ID",  "CPUID available",   None ),
        }

mxcsr_descriptions = {
        0 : ( 1, "IE", "EF: Invalid operation", None ),
        1 : ( 1, "DE", "EF: Denormal", None ),
        2 : ( 1, "ZE", "EF: Divide-by-zero", None ),
        3 : ( 1, "OE", "EF: Overflow", None ),
        4 : ( 1, "UE", "EF: Underflow", None ),
        5 : ( 1, "PE", "EF: Precision", None ),
        6 : ( 1, "DAZ", "Denormals are Zero", None ),
        7 : ( 1, "IM", "MASK: Invalid Operation", None ),
        8 : ( 1, "DM", "MASK: Denormal", None ),
        9 : ( 1, "ZM", "MASK: Divide By Zero", None ),
        10 : ( 1, "OM", "MASK: Overflow", None ),
        11 : ( 1, "UM", "MASK: Underflow", None ),
        12 : ( 1, "PM", "MASK: Precision", None ),
        13 : ( 2, "R[ZN+-]", "Rounding", { 
                                            0 : ("RN","(Round To Nearest)"),
                                            1 : ("R-","(Round Negative)"),
                                            2 : ("R+","(Round Positive)"),
                                            3 : ("RZ","(Round to Zero)"),
                                            }),
        15 : ( 1, "FZ", "Flush to Zero", None ),
        }

bndcfgu_descriptions = {
        0 : ( 1, "EN", "Enabled", None ),
        1 : ( 1, "PRV","Preserved", None ),
        12: ( 52, "BASE", "Base", None )
        }

bndstatus_descriptions = {
        0 : ( 2, "ERR", "Error", None ),
        2 : ( 62,"BDE", "BDE Address", None ),
        }

apsr_descriptions = {
        31 : ( 1, "N"  , "Negative Condition", "bit[31] (sign) of a result" ),
        30 : ( 1, "Z"  , "Zero Condition", "Set if result is zero" ),
        29 : ( 1, "C"  , "Carry Flag", None ),
        28 : ( 1, "V"  , "Overflow Flag", None ),
        27 : ( 1, "Q"  , "Overflow or Saturation", None ),
        24 : ( 3, "RAZ", "RAZ/SBZP Flags.", None ),
        16 : ( 4, "GE" ,">= Flags", "See SEL instruction", None )
        }

ipsr_descriptions = {
        0 : ( 9, "ISR", "ISR_NUMBER Exception", {
                                                    0 : ( "TM","Thread mode"),
                                                    1 : ( "RS","Reserved"),
                                                    2 : ( "NMI",""),
                                                    3 : ( "HF", "Hard Fault"),
                                                    4 : ( "MM", "Mem Manage"),
                                                    5 : ( "BF", "Bus Fault"),
                                                    6 : ( "UF", "Usage Fault"),
                                                    11: ( "SV", "SVCall"),
                                                    12: ( "DB", "Debug"),
                                                    14: ( "PS", "PendSV"),
                                                    15: ( "ST", "SysTick"),
                                                    16: ( "IRQ0",""), # TODO Add all other IRQ too
                                                }),
        }

epsr_descriptions = {
        25 : ( 2, "ICI/IT", "", None ),
        10 : ( 6, "ICI/IT", "", None ),
        24 : ( 1, "T", "Thumb state", None ),
        }
primask_descriptions = {
        0 : ( 1, "PRIMASK", "", None ),
        }

faultmask_descriptions = {
        0 : ( 1, "FAULTMASK", "", None ),
        }

basepri_descriptions = {
        0 : ( 8, "BAEPRI", "", None ),
        }

control_descriptions = {
        0 : ( 1, "nPRIV", "Thread mode Privilege Level", { 
                                                          0 : ( "PR","Priveleged" ), 
                                                          1 : ( "UN","Unprivileged" ) 
                                                          }),
        1 : ( 1, "SPSEL", "Current Stack Pointer", { 
                                                    0 : ("MSP","is current SP" ),
                                                    1 : ("PSP","is current SP" ),
                                                    }),
        }
fpscr_descriptions = {
        31 : ( 1, "N"  , "Negative Condition", "bit[31] (sign) of a result" ),
        30 : ( 1, "Z"  , "Zero Condition", "Set if result is zero" ),
        29 : ( 1, "C"  , "Carry Flag", None ),
        28 : ( 1, "V"  , "Overflow Flag", None ),
        24 : ( 1, "FZ" , "Flush to zero", { 
                                           0 : ("-FZ", "Flush to Zero Mode disabled"),
                                           1 : ("+FZ", "Flush to Zero Mode enabled"),
                                           }),
        22 : ( 2, "RND", "Rounding Control", {
                                            0b00 : ("RN", "Round to nearest"),
                                            0b01 : ("RP", "Round to plus Inf"),
                                            0b10 : ("RM", "Round to minus Inf"),
                                            0b11 : ("RZ", "Round to zero")
                                            }),
        20 : ( 2, "STRIDE", "Vector Stride", {
                                            0b00 : ("1", "Stride 1"),
                                            0b11 : ("2", "Stride 2")
                                            }),
        16 : ( 3, "LEN", "Register per Vector", {
                                            0 : ("1",""),
                                            1 : ("2",""),
                                            2 : ("3",""),
                                            3 : ("4",""),
                                            4 : ("5",""),
                                            5 : ("6",""),
                                            6 : ("7",""),
                                            7 : ("8",""),
                                            }),
        12 : ( 1, "IXE", "Inexact Ex Enabled", None ),
        11 : ( 1, "UFE", "Underflow Ex Enabled", None ),
        10 : ( 1, "OFE", "Overflow Ex Enabled", None ),
         9 : ( 1, "DZE", "Div by Zero Ex Enabled", None ),
         8 : ( 1, "IOE", "Invalid Operation Ex Enabled", None ),
         4 : ( 1, "IXC", "Inexact Exception Occured", None ),
         3 : ( 1, "UFC", "Underflow Exception Occured", None ),
         2 : ( 1, "OFC", "Overflow Exception Occured", None ),
         1 : ( 1, "DZC", "Div by Zero Exception Occured", None ),
         0 : ( 1, "IOC", "Invalid Operation Exception Occured", None ),
        }

flag_info = {
            "eflags"    : ( "", 21, flag_descriptions, None ),
            "mxcsr"     : ( "", 15, mxcsr_descriptions, None ),
            "bndcfgu"   : ( "", 12, bndcfgu_descriptions, ( "raw", "config" ) ),
            "bndstatus" : ( "",  4, bndstatus_descriptions, ( "raw", "status" ) ),
            # From Cortex M3 Documentation, if others vary we need to figure that out somehow
            "apsr"      : ( "", 31, apsr_descriptions, None ),
            "ipsr"      : ( "",  9, ipsr_descriptions, None ),
            "epsr"      : ( "", 26, epsr_descriptions, None ),
            "primask"   : ( "",  1, primask_descriptions, None ),
            "faultmask" : ( "",  1, faultmask_descriptions, None ),
            "basepri"   : ( "",  7, basepri_descriptions, None ),
            "control"   : ( "",  2, control_descriptions, None ),
            "fpscr"     : ( "", 31, fpscr_descriptions, None ),
            "xPSR"      : ( "", 31, apsr_descriptions | ipsr_descriptions | epsr_descriptions , None ),
            "xpsr"      : ( "", 31, apsr_descriptions | ipsr_descriptions | epsr_descriptions , None ),
            }
possible_flags = [
        "eflags", "flags", "mxcsr", "bndcfgu", "bndstatus", "apsr", "ipsr", "epsr", "primask", 
        "faultmask", "basepri", "control", "fpscr", "xPSR", "xpsr"
        ]

abbrflags = [ 
        "mxcsr"
        ]

possible_registers = [
		( "rax", "eax", "ax", "al"),
        ( "rbx", "ebx", "bx", "bl"),
        ( "rcx", "ecx", "cx", "cl"),
        ( "rdx", "edx", "dx", "dl"),
		( "rsi", "esi", "si", "sil"),
        ( "rdi", "edi", "di", "dil"),
		( "rbp", "ebp", "bp", "bpl"),
        ( "rsp", "esp", "sp", "spl"),
		( "rip", "eip", "ip", "pc"),
        "r0","r1","r2","r3","r4","r5","r6","r7", # other than x86
		"r8" , "r9" , "r10", "r11",
		"r12", "r13", "r14", "r15",
		"r16", "r17", "r18", "r19",
        "r20", "r21", "r22", "r23",
        "r24", "r25", "r26", "r27",
        "r28", "r29", "r30", "r31",
        "lr","cpsr","fpscr",
        "sp","pc", "ctr"
		]

register_sizes = {
        64 : [ "rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp","rip",
                "r0","r1","r2","r3","r4","r5","r6","r7", # other than x86
                "r8" , "r9" , "r10", "r11",
                "r12", "r13", "r14", "r15",
                "r16", "r17", "r18", "r19",
                "r20", "r21", "r22", "r23",
                "r24", "r25", "r26", "r27",
                "r28", "r29", "r30", "r31",
                ],
        32 : [ "eax","ebx","ecx","edx","esi","edi","ebp","esp","eip",
                "r0d","r1d","r2d","r3d","r4d","r5d","r6d","r7d", # other than x86
                "r8d" , "r9d" , "r10d", "r11d",
                "r12d", "r13d", "r14d", "r15d",
                "r16d", "r17d", "r18d", "r19d",
                "r20d", "r21d", "r22d", "r23d",
                "r24d", "r25d", "r26d", "r27d",
                "r28d", "r29d", "r30d", "r31d",
                ],
        16 : [ "ax","bx","cx","dx","si","di","bp","sp","ip",
                "r0w","r1w","r2w","r3w","r4w","r5w","r6w","r7w", # other than x86
                "r8w" , "r9w" , "r10w", "r11w",
                "r12w", "r13w", "r14w", "r15w",
                "r16w", "r17w", "r18w", "r19w",
                "r20w", "r21w", "r22w", "r23w",
                "r24w", "r25w", "r26w", "r27w",
                "r28w", "r29w", "r30w", "r31w",
                ],
         8 : [ "al","bl","cl","dl","sil","dil","bpl","spl",
                "r0b","r1b","r2b","r3b","r4b","r5b","r6b","r7b", # other than x86
                "r8b" , "r9b" , "r10b", "r11b",
                "r12b", "r13b", "r14b", "r15b",
                "r16b", "r17b", "r18b", "r19b",
                "r20b", "r21b", "r22b", "r23b",
                "r24b", "r25b", "r26b", "r27b",
                "r28b", "r29b", "r30b", "r31b",
                ]
        }

# same format as flag_info basically
mmapped_descriptions = {}
mmapped_positions    = {}
mmapped_blacklist = {}

possible_prefixes = [
		"cs", "ds", "es", "fs", "gs", "ss"
		]

possible_fpu = [
	"st0", "st1", "st2", "st3", "st4","", "st5", "st6", "st7","",
	"fctrl", "fstat", "ftag", "fiseg", "", "fioff", "foseg", "fooff", "fop",
    "d0","d1","d2","d3","d4","","d5","d6","d7","d8","","d9",
    "d10","d11","d12","","d13","d14","d15","d16","","d17","d18","d19","",
    "s0","s1","s2","s3","s4","","s5","s6","s7","s8","","s9",
    "s10","s11","s12","","s13","s14","s15","s16","","s17","s18","s19",
		]

possible_specials = [
        "pkru"
        ]


size_per_reg = {}
def gen_size_per_reg( ):
    global size_per_reg
    for sz,rnl in register_sizes.items():
        for rn in rnl:
            size_per_reg[rn] = sz

def register_size( name ):
    # XXX Quick hack to get arm to work, the real fix will be to split up all kinds of informations by arch
    if( vdb.arch.name().startswith("arm") ):
        return vdb.arch.pointer_size

    if( len(size_per_reg) == 0 ):
        gen_size_per_reg()
    return size_per_reg.get(name,None)


def read( reg, frame = None ):
    try:
        if( frame is None ):
            frame = gdb.selected_frame()
        return frame.read_register(reg)
    except gdb.error:
        return None
    except ValueError:
        return None

# for x86 eax/rax r10/r10d etc stuff where we want to just handle "whole" registers
def altname( regname ):
    if( regname[0] == "e" ):
        return "r" + regname[1:]
    if( regname[0] == "r" and regname[-1] == "d" ):
        return regname[:-1]
    return None

# move this deeper into the memory part so we can use it there too for e.g. hexdump
def blacklist( regs, cond = None ):
    if( not isinstance(regs,(list,set,tuple) ) ):
        regs = [ regs ]

    for reg in regs:
        mmapped_blacklist[reg] = cond

def is_blacklisted( raddr ):
#    print(f"is_blacklisted({raddr})")
    cond = mmapped_blacklist.get( raddr, is_blacklisted )
    if( cond is is_blacklisted ):
        return False

    # unconditionally blacklisted
    if( cond is None ):
        return True

    if( callable(cond) ):
        return cond(raddr)

    addr, expected = cond

    # register string e.g. DBGMCU.CR.TRACE_EN
    if( isinstance( addr, str ) ):
        if( registers is None ):
            update()
        rres = registers.get_reg( addr )
        if( rres is None ):
            # The register is not present, we assume that this from a generic setup and if that register doesnt exist,
            # the "bad" memory area doesn't depend on it either and is accesssible
            return False
        else:
            val,mmp = rres
    else:
        # XXX We don't do anything with it here, like compare, we should probably also somehow specify the size
        data = vdb.memory.read_uncached( addr, 1 )
        return ( val != data )

#    print(f"{val=}")
#    print(f"{expected=}")
    return ( val != expected )

class Registers():

    def __init__(self):
        self.regs = {}
        self.segs = {}
        self.vecs = {}
        self.fpus = {}
        self.rflags = {}
        self.groups = {}
        self.thread = 0
        self.all = {}
        self.all_values = {}
        self.others = {}
        self.type_indices = {}
        self.next_type_index = 1

        self.frame = None
        try:
            self.frame = gdb.selected_frame()
        except:
            return
        thread=gdb.selected_thread()
        self.thread = thread.num
        self.archsize = vdb.arch.pointer_size

        self.collect_registers()

    def get( self, name ):
        """Gets gdb register descriptor"""
        return self.all.get(name,None)

    def get_value( self, name ):
#        print(f"get_value({name})")
        desc = self.all.get(str(name),None)
#        print(f"{str(desc)=}")
        if( desc is None ):
            return None
        val = self.all_values.get(desc)
        return val

    def in_group( self, name, group ):
        groups = self.groups.get(name,None)
        if( groups is not None ):
            return group in groups
        return False

    def collect_registers( self ):

        # XXX Can be made even faster by caching those groups, they won't change when the arch doesn't change
        for grp in self.frame.architecture().register_groups():
#            print("grp = '%s'" % (grp,) )
            for reg in self.frame.architecture().registers(grp.name):
                self.groups.setdefault(reg.name,set()).add( grp.name )
#                print(f"{grp} : {reg}")
#        sw = vdb.util.stopwatch()
#        print(f"registers we don't know where to put them yet (archsize {self.archsize}):")
#        cnt = 0
        for reg in self.frame.architecture().registers():
            self.all[reg.name] = reg
#            cnt += 1
#            sw.start()
            v = self.frame.read_register(reg)
#            sw.pause()
            self.all_values[reg] = ( v, v.type )
            # try to figure out which register type this is by first sorting according to its type
            if( reg.name in possible_flags ):
                self.rflags[reg] = ( v, v.type )
            elif( reg.name in possible_specials ):
                self.others[reg] = ( v, v.type )
            elif( self.in_group(reg.name,"vector") or v.type.code == gdb.TYPE_CODE_UNION ):
                self.vecs[reg] = ( v, v.type )
            elif( v.type.code == gdb.TYPE_CODE_FLT ):
                self.fpus[reg] = ( v, v.type )
                if( reg.name not in possible_fpu ):
                    possible_fpu.append(reg.name)
            elif( v.type.code == gdb.TYPE_CODE_FLAGS ):
                self.rflags[reg] = ( v, v.type )
            elif( reg.name in possible_fpu ):
                self.fpus[reg] = ( v, v.type )
            elif( v.type.sizeof*8 < self.archsize and v.type.code == gdb.TYPE_CODE_INT ): # assume non archsize integers are prefixes
#                print("v.type.sizeof*8 = '%s'" % (v.type.sizeof*8,) )
#                print("self.archsize = '%s'" % (self.archsize,) )
                self.segs[reg] = ( v, v.type )
            elif( self.in_group(reg.name,"general") or reg.name in possible_registers ):
                self.regs[reg] = ( v, v.type )
            else:
                self.others[reg] = ( v, v.type )
#        sw.stop()
#        print(f"{sw.get()=}")
#        print(f"{cnt=}")



    def get_pos( self, reg ):
#        print(f"Register.get_pos( {reg=} )")
        # cut off sub-int part if necessary
        parts = reg.split(".")
        fullreg = ".".join(parts[:2])
#        print(f"{fullreg=}")
#        print(f"{len(mmapped_positions)=}")
        mmp = mmapped_positions.get(fullreg,None)
#        print(f"{mmp=}")
        if( len(parts) > 2 ):
            part = parts[2]
        else:
            part = None
#        print(f"{mmp=}")
#        print(f"{type(mmp)=}")
#        print(f"{mmapped_descriptions.keys()=}")
#        print("len(mmapped_positions) = '%s'" % (len(mmapped_positions),) )
#        if( mmp is None ):
#            print(f"Unable to find memory position for register {reg}")
        return (mmp,part)

    def get_reg( self, reg ):
#        print(f"Register.get_reg( {reg=} )")
        mmp,part = self.get_pos(reg)
        return self.get_reg_at( mmp, part )

    def get_reg_at( self, mmp, part = None ):
        if( mmp is not None ):
            if( part is None ):
                rname,raddr,rbit,rtype = mmp
                mc = vdb.memory.read_uncached( raddr, rbit//8 )
                if( mc is None ):
                    raise RuntimeError(f"Accessing {raddr:#0x} for {rname} failed, maybe you need to set mem inaccessible-by-default off?")
                val = gdb.Value(mc,rtype)
                return ( val, mmp )
            else:
#                print(f"{mmp=}")
#                print(f"{part=}")
                mdesc = mmapped_descriptions.get(mmp[0])
#                print(f"{mdesc=}")
                for bit,desc in mdesc[2].items():
                    if( desc[1] == part ):
                        val = 42
                        rname,raddr,rbit,rtype = mmp
                        mc = vdb.memory.read_uncached( raddr, rbit//8 )
                        if( mc is None ):
                            return (None,None)
                        val = gdb.Value(mc,rtype)
                        val, mask = self.bitextract( bit, desc[0], int(val) )
                        return( val, mmp )
                return (None, None)
        else:
            return ( None, None )

    def set_reg_at( self, mmp, val, part = None ):
#        print(f"set_reg_at( {mmp=}, {val=}, {part=}")
        rname,raddr,rbit,rtype = mmp
        val = int(val)
#            print("raddr = '%s'" % (raddr,) )
#            print("rbit = '%s'" % (rbit,) )
#            print("rtype = '%s'" % (rtype,) )
        data = val.to_bytes(rbit//8,"little")
        msgval = val
#            print("data = '%s'" % (data,) )

        if( part is not None ):
            oldval,_ = self.get_reg_at( mmp )
            mdesc = mmapped_descriptions.get(rname)
#            print(f"{mdesc=}")
            parts = mdesc[2]
#            print(f"{parts=}")
            # XXX We might want to change that format so we dont have to search that much
            for bit,p in parts.items():
                if( p[1] == part ):
#                    print(f"{p=}")
#                    print(f"{bit=}")
#                    print(f"{mdesc[1]=}")
#                    print(f"{int(oldval)=:#0x}")
                    sz = p[0]
#                    print(f"{sz=}")
                    maxval = (1<<sz)-1
                    if( val > maxval ):
                        raise Exception(f"{val} is too big for field of {sz} bits")
#                    print(f"{maxval=}")
                    ex, mask = self.bitextract( bit, sz, int(oldval) )

                    valmask = ~mask
#                    print(f"{valmask=:#0x}")
                    newval  = valmask & int(oldval)
#                    print(f"{newval=:#0x}")
                    newshifted = val << bit
#                    print(f"{newshifted=:#0x}")
                    newval |= newshifted
#                    print(f"{newval=:#0x}")
#                    print(f"{ex=}")
#                    print(f"{mask=:#0x}")
                    data = newval.to_bytes(rbit//8,"little")
                    msgval = newval
                    break
            else:
                print(f"{mmp[0]}.{part} could not be found, not touching the register")
                return


        print(f"set {{uint{rbit}_t}}{raddr:#0x}={msgval:#0x}")
        vdb.memory.write( raddr, data )
#        print(f"set {{{rtype}}}{raddr:#0x}={val:#0x}")

    def set_bit( self, reg, bit, val ):
#        print(f"set_bit({reg},{bit},{val})")

        bit = int(bit)
        bal = int(val)
        mask = 1 << bit
        if( val == 0 ):
            self.and_reg(reg,~mask)
        else:
            self.or_reg(reg,mask)

    def set_reg( self, reg, val ):
        # TODO Add support for non memory mapped registers, also wiht $ and % prefix
#        print(f"set_reg({reg},{val})")
        mmp,part = self.get_pos(reg)
#        print(f"{mmp=}")
#        print(f"{part=}")
        if( mmp is not None ):
            self.set_reg_at(mmp,val,part)

    def or_reg( self, reg, val ):
#        print(f"or_reg({reg=},{val=})")

        oval,mmp = self.get_reg(reg)
        if( oval is None ):
            return
#        print("oval = '%s'" % (oval,) )
#        print("val = '%s'" % (val,) )
        self.set_reg_at(mmp,oval|val)

    def and_reg( self, reg, val ):
#        print(f"and_reg({reg=},{val=})")

        oval,mmp = self.get_reg(reg)
        if( oval is None ):
            return
#        print("oval = '%s'" % (oval,) )
#        print("val = '%s'" % (val,) )
        self.set_reg_at(mmp,oval&val)

    def set( self, argv ):
#        print(f"Register.set({argv=})")
#        vdb.util.bark() # print("BARK")
#        print(f"{argv=}")

        ix = argv.index("=")
#        print(f"{ix=}")
        reg = argv[0]
        val = " ".join(argv[ix+1:])
        op = argv[1]

#        print(f"{reg=}")
#        print(f"{op=}")
#        print(f"{val=}")

        val=vdb.util.gint(val)

        if( reg.find(":") > -1 ):
            reg,bit = reg.split(":")
            self.set_bit(reg,bit,val)
        elif( op == "&" ):
            self.and_reg(reg,val)
        elif( op == "|" ):
            self.or_reg(reg,val)
        else:
            self.set_reg(reg,val)

    def _dump( self ):
        print("self.regs:")
        for r,v in self.regs.items():
            print(f"{r} : {v[0]} ({v[1]})")
        print("self.segs:")
        for r,v in self.segs.items():
            print(f"{r} : {v[0]} ({v[1]})")
        print("self.vecs:")
        for r,v in self.vecs.items():
            print(f"{r} : VALUE ({v[1]})")
        print("self.fpus:")
        for r,v in self.fpus.items():
            print(f"{r} : {v[0]} ({v[1]})")
        print("self.groups:")
        for r,g in self.groups.items():
            print(f"{r} : {g}")
        print("self.thread = '%s'" % self.thread )
        print("self.type_indices = '%s'" % self.type_indices )
        print("self.next_type_index = '%s'" % self.next_type_index )
#        print("self.archsize = '%s'" % self.archsize )
#        print("self.eflags = '%s'" % self.eflags )
#        print("self.mxcsr = '%s'" % self.mxcsr )

    def read( self, reg, frame = None ):
        return read(reg,frame)

    def parse_register( self,frame,reg,regs):
        if( len(reg) == 0 ):
            regs[reg] = (None,None)
            return None
        try:
            v = frame.read_register(reg)
#			print("reg = '%s'" % reg )
#			print("v = '%s'" % v )
            t = v.type
            regs[reg] = ( v, t )
#            print("v = '%s'" % v )
#            print("t = '%s'" % t )
            return (v,t)
        except:
            return None

    def format_register( self, regdesc, val,t, chained = False, int_as_int = False,suffix = None ):
#        print("regdesc = '%s'" % regdesc )
#        print("regdesc.name = '%s'" % regdesc.name )
#        print("val = '%s'" % val )
#        print("val.type = '%s'" % val.type )
#        print("val.type.tag = '%s'" % val.type.tag )
#        print("val.type.code = '%s'" % vdb.util.gdb_type_code(val.type.code) )
#        print("vdb.arch.gdb_uintptr_t = '%s'" % vdb.arch.gdb_uintptr_t )
        if( vdb.arch.uintptr_t is not None ):
            val=int( val.cast(vdb.arch.uintptr_t) )
        else:
            val=int( val.cast(vdb.arch.uint(64) ) )

        try:
            name = regdesc.name
            if suffix is not None:
                name += "." + suffix
            retn = vdb.color.color(f"{name}",color_names.value)
            retnl = len(name)

            retv = ""
            retvl = 0
            if( int_as_int ):
                if( self.archsize == 32 ):
                    retv  = f"{int(val):>10} "
                    retvl = 11
                else:
                    retv  = f"{int(val):>20} "
                    retvl = 21

            if( chained ):
                retv += vdb.pointer.chain(val,self.archsize,tailspec=tailspec.value)[0]
                # We need a nice way to adjust retl here, probably need to modify pointer.chain()
            else:
                r,_,_,_,rl = vdb.pointer.color(val,self.archsize)
                retv += r
                retvl += rl
        except:
            retv = "ERR " + regdesc.name + " : " + str(val)
            retvl = len(retv)
            raise
        return ( retn, retnl, retv, retvl )

    def format_float( self,name, val,t ):
        try:
            if( t.name == "int" ):
                val=int(val)
                ret = vdb.color.color(f" {name:<6}",color_names.value)+f"0x{val:016x}"
            else:
                val=float(val)
                ret = vdb.color.color(f" {name:<6}",color_names.value)+f"{val: 16g}"
        except:
            ret = str(val)
        return ret


    def format_prefix( self,regdesc, val, t ):
        val=int(val)
        try:
            ret = vdb.color.color(f" {regdesc.name:<3}",color_names.value)+f"0x{val:08x}"
        except:
            ret = str(val)
        return ret

    def get_type_index( self, type_name ):
        ti = self.type_indices.get(type_name,None)
        if( ti is None ):
            ti = self.next_type_index
            self.next_type_index += 1
            self.type_indices[type_name] = ti
        return ti

    def format_vector_extended( self, regdesc, val, t ):
        empty = [ None ] * ( 1 + max( len(t.fields()), self.next_type_index ) )
        tbl = []
        valmatrix = { }

        maxval = 0
        import copy
        header = copy.deepcopy(empty)
        header[0] = ( vdb.color.color(f"{regdesc.name:<6}",color_names.value), 6 )
        tbl.append(header)
        for f in t.fields() :
            cnt = 1
            idx = self.get_type_index( f.name )
            header[idx] = f.name
            hexdump = False
            if( f.name.find("int8") != -1 ):
                hexdump = True
#            print("f.type = '%s'" % f.type )
#            print("f.type.tag = '%s'" % f.type.tag )
#            print("f.type.code = '%s'" % vdb.util.gdb_type_code(f.type.code) )
            if( f.type.code == gdb.TYPE_CODE_ARRAY ):
                elements = f.type.range()[1] + 1
            else:
                elements = 0
                valmatrix[(1,idx)] = str(val[f.name])
            columns = max(1,elements // 4)
            
            row = 0

            for vi in range( 0, elements ):
                fval = val[f.name][vi]
                if( hexdump ):
                    row = 1 + ( (cnt-1) // 8)
                    os = valmatrix.get((row,idx),"")
                    fval = int(fval.cast(vdb.arch.uint(8)))
                    os += f"{fval:02X} "
                    if( cnt % 4 == 0 ):
                        os += " "
                    fval = os
                else:
#                print(f"{fval} = val[{f.name}][{vi}]")
#                    row = cnt
                    row = 1 + (cnt-1) // columns
                    os = valmatrix.get((row,idx),"")
                    fval = os + " " + str(fval)
                valmatrix[(row,idx)] = fval
                cnt += 1
            maxval = max(maxval,row)

#        print("maxval = '%s'" % maxval )
#        print("empty = '%s'" % empty )
#        print("(empty*maxval) = '%s'" % ([empty]*maxval) )
        import copy
        for i in range(0,maxval):
            tbl += copy.deepcopy([empty])
#        tbl = copy.deepcopy(tbl)
#        print("len(tbl) = '%s'" % len(tbl) )
        for cr,val in valmatrix.items():
            row,col = cr
#            print("row = '%s'" % row )
#            print("col = '%s'" % col )
#            print("len(tbl[row]) = '%s'" % len(tbl[row]) )
#            tbl[row][col] = str((row,col))
            tbl[row][col] = str(val)


        return tbl

    def format_vector( self, xvec ):
        regdesc,amnt = xvec[0]
        amnt = len(amnt)
        ret = ""
#		print("xvec = '%s'" % xvec )
        for i in range(0,amnt):
            for regdesc,vals in xvec:
#                print("self.read(regdesc.name).type.sizeof = '%s'" % self.read(regdesc.name).type.sizeof )
                if( i == 0 ):
                    ret += vdb.color.color(f" {regdesc.name:<6}",color_names.value)
                else:
                    ret += f"       "
                try:
                    val=int(vals[i])

                    if( self.read(regdesc.name).type.sizeof >= 16 ):
                        ret += f"0x{val:032x}"
                    else:
                        ret += f"0x{val:016x}"
                except:
                    val=vals[i]
                    ret += f"{val:32s}"
            ret += "\n"
        return ret

    def extract_vector( self,name, val, t ):
        ret = []
#        print("name = '%s'" % name )
#        print("val.type.name = '%s'" % val.type.name )
#        print("val.type.sizeof = '%s'" % val.type.sizeof )

        vector_fields = []
        for f in t.fields():
            vector_fields.append(f)
        vector_field = self.filter_vector_fields(vector_fields)

        if( vector_field.type.code == gdb.TYPE_CODE_ARRAY ):
            elements = vector_field.type.range()[1]+1
        else:
            elements = 1
#        print("elements = '%s'" % elements )

        xval=[]
        # vector_fields should contain the biggest/best one, lets cycle through them and assemble 128bit value.

        tname = vector_field.name
        for i in range(0,elements):
            #			print("BARK")
            try:
                xval.append(int(val[tname][i].cast(vdb.arch.uint(64))))
            except:
                try:
                    xval.append(int(val[tname].cast(vdb.arch.uint(64))))
                except:
                    xval.append("INVALID")
                    print("tname = '%s'" % (tname,) )
                    print("i = '%s'" % (i,) )
                    vdb.print_exc()

        yval=[]
#        print("len(xval) = '%s'" % len(xval) )
#        print("xval = '%s'" % xval )
        if( elements < 2 ):
            return xval
        for i in range(0,elements,2):
#            print("i = '%s'" % i )
            yval.append( xval[i] + (xval[i+1]<<64) )
#        print("yval = '%s'" % yval )
        return yval



    def ex_floats( self, filter ):
        print("NOT YET IMPLEMENTED")
        return self.floats(filter)

    def arch_prctl( self, code ):
        ret = vdb.memory.read_uncached("$sp",8)

        if( ret is not None ):
            try:
                gdb.execute( f"call (int)arch_prctl({code},$sp)", False, True )
                ap_ret = vdb.memory.read_uncached("$sp",8)
                return ap_ret
            except:
                pass
            finally:
                vdb.memory.write("$sp",ret)
#            gdb.execute( "set *(void**)($rsp) = $__vdb_save_value" )
#            gdb.execute( "p *(void**)($rsp)" )

    def ex_prefixes( self, filter ):
        try:
            fs_base = self.read("fs_base")
            if( fs_base is None ):
                fs_base = self.arch_prctl(0x1003)
                if( fs_base is not None ):
                    fs_base = int.from_bytes(fs_base,"little")
            if( fs_base is not None ):
                self.segs[self.get("fs")] = ( fs_base, None )
            gs_base = self.read("gs_base")
            if( gs_base is None ):
                gs_base = self.arch_prctl(0x1004)
                if( gs_base is not None ):
                    gs_base = int.from_bytes(gs_base,"little")
            if( gs_base is not None ):
                self.segs[self.get("gs")] = ( gs_base, None )
        except:
            vdb.print_exc()
            pass
        return self.prefixes(filter)

    def format_special( self, name ):
        if( name == "pkru" ):
            ret = ""
#            pkru = self.get(name)
            pkru = self.read(name)
            ival = int(pkru)
            ret += vdb.color.color(f" {name} ",color_names.value)+f"0x{ival:08x}"
            ret += "\n"
            ptbl = []
            mask = 1
            k = ["Key"]
            a = ["A"]
            w = ["W"]
            for i in range(0,16):
                k.insert(1,i )
                if( ival & mask == 0 ):
                    a.insert(1,"" )
                else:
                    a.insert(1,"X")
                mask *= 2
                if( ival & mask == 0 ):
                    w.insert(1,"" )
                else:
                    w.insert(1,"X")
                mask *= 2

            ptbl.append(k)
            ptbl.append(a)
            ptbl.append(w)
            ret += vdb.util.format_table( ptbl )
            ret += "\n"
            return ret
        return None

    def format_ints( self, filter, regs, extended = False, wrapat = None ):
        if( wrapat is None ):
            wrapat = short_columns.value
        ret = ""
        cnt=0

        rtbl = []
        rtline = []
        if( filter is not None ):
            filter = re.compile(filter)
        for regdesc,valt in regs.items():
            if( filter is not None ):
                if( filter.search(regdesc.name) is None ):
                    continue
            special = self.format_special(regdesc.name)
            if( special is not None ):
                cnt += 1
                ret += special
            else:
                val,t =valt
                if( val.type.code == gdb.TYPE_CODE_STRUCT ):
                    for f in val.type.fields():
                        fv = val[f]
                        if( cnt % wrapat == 0 ):
                            rtbl.append(rtline)
                            rtline = []
#                            ret += "\n"
                        cnt += 1
                        rnv,rnl,rvv,rvl = self.format_register(regdesc,fv,t,extended, int_int.value, suffix = f.name )
#                        ret += rnv + rvv
                        rtline.append( (rnv,rnl) )
                        rtline.append( (rvv,rvl) )
                else:
                    cnt += 1
                    rnv,rnl,rvv,rvl = self.format_register(regdesc,val,t,extended, int_int.value )
#                    ret += rnv + rvv
#                    print("rv = '%s'" % (rv,) )
#                    print("rl = '%s'" % (rl,) )
                    rtline.append( (rnv,rnl) )
                    rtline.append( (rvv,rvl) )
            if( cnt % wrapat == 0 ):
                rtbl.append(rtline)
                rtline = []
#                ret += "\n"


        if( len(rtline) > 0 ):
            rtbl.append(rtline)

#        ret += "\nTABLE\n"
        ret += vdb.util.format_table(rtbl,padbefore=" ", padafter="")

        if( not ret.endswith("\n") ):
            ret += "\n"
        return ret

    def ints( self, filter, extended = False, wrapat = None ):
        return self.format_ints( filter, self.regs, extended, wrapat )

    def other( self, filter, extended = False, wrapat = None ):
        return self.format_ints( filter, self.others, extended, wrapat )

    def prefixes( self, filter ):
        ret = ""
        cnt=0
        if( filter is not None ):
            filter = re.compile(filter)
        for regdesc,valt in self.segs.items():
            if( filter is not None ):
                if( filter.search(regdesc.name) is None ):
                    continue
            val,t =valt
            cnt += 1
            ret += self.format_prefix(regdesc,val,t)
            if( cnt % 6 == 0 ):
                ret += "\n"
        return ret
# mxcsr          0x1fa0              [ PE IM DM ZM OM UM PM ]

    def floats( self, filter ):
        ret = ""
        if( filter is not None ):
            filter = re.compile(filter)
        for name in possible_fpu:
            if( filter is not None ):
                if( filter.search(name) is None ):
                    continue
#        for name,valt in self.fpus.items():
#            valt = self.fpus.get(reg,None)
            if( len(name) == 0 ):
                valt = (None,None) # newline
            else:
                valt = self.fpus.get(self.get(name),None)
            if( valt is None):
                continue
            val,t = valt
            if( val is None ):
                if( len(ret) > 0 and ret[-1] != "\n" ):
                    ret += "\n"
            else:
                ret += self.format_float(name,val,t)

        if( not ret.endswith("\n") ):
            ret += "\n"
        return ret

    def filter_vector_fields( self, vector ):
        # Lets try to find a proper field
        # - all fields that do not start with v# are most interesting as they likely are just one
        # - from the other ones chose those that are the biggest
        # - then leave those out that are floating point
        # If still any is left, chose by random?
#        print("vector = '%s'" % vector )
        others = []
        vecs = []
        for v in vector:
            # The one that is a single field, return it
            if( v.type.code == gdb.TYPE_CODE_INT ):
                return v
#            print("v.name = '%s'" % v.name )
#            print("v.type = '%s'" % v.type )
#            print("v.type.sizeof = '%s'" % v.type.sizeof )
#            print("v.type.code = '%s'" % vdb.util.gdb_type_code(v.type.code) )
#            print("v.type.range() = '%s'" % (v.type.range(),) )
            if( v.type.code == gdb.TYPE_CODE_ARRAY ):
                if( v.name.startswith("v") ):
                    vecs.append(v)
                else:
                    others.append(v)
            else:
                raise Exception("Unsupported code %s for vector member %s" % (vdb.util.gdb_type_code(v.type.code), v.name ) )
        if( len(others) > 0 ):
            vector = others
        else:
            vector = vecs

        vecs = []
        for v in vector:
#            print("v.name = '%s'" % v.name )
            if( v.name.find("double") == -1 and v.name.find("float") == -1 ):
                vecs.append(v)
        vector = vecs

        vecs = []
        for v in vector:
            if( v.type.target().sizeof <= 8 ):
                vecs.append(v)
        vector = vecs

        vector.sort( key = lambda x : x.type.target().sizeof, reverse=True )

#        print("vector = '%s'" % vector )

        # Now there should be just one left

        return vector[0]

    def vectors( self, filter, extended = False ):
        ret=""
        cnt=0
        xvec = []

        if( filter is not None ):
            filter = re.compile(filter)
        rtbl = []
        for regdesc,valt in self.vecs.items():
            if( filter is not None ):
                if( filter.search(regdesc.name) is None ):
                    continue
            val,t =valt
            cnt += 1

#            print("name = '%s'" % name )
#            print("val = '%s'" % val )
#            print("t = '%s'" % t )
#            print("t.fields() = '%s'" % t.fields() )
#            print("t.fields() = '%s'" % t.fields() )
#            for f in t.fields():
#                print("f.name = '%s'" % f.name )

            if( extended ):
                rtbl += ( self.format_vector_extended(regdesc , val, t ) )
            else:
                xvec.append( (regdesc, self.extract_vector(regdesc,val,t)) )
                if( cnt % 4 == 0 ):
                    ret += self.format_vector(xvec)
                    xvec = []
        if( len(xvec) > 0 ):
            ret += self.format_vector(xvec)

        if( extended ):
            ret += vdb.util.format_table(rtbl,padbefore=" ", padafter="")
        return ret

    def format_flags_mini( self, name, rawname, val, desc ):
        """Never returns colour"""
#        print("name = '%s'" % (name,) )
#        print("rawname = '%s'" % (rawname,) )

        if( rawname is None ):
#            oval = val
            val=str(val)
#            print("val = '%s'" % (val,) )
            try:
#                val=oval
                val=int(val)
                if( len(desc) == 0 ):
                    ret=f"{val:#0x}"
                    return ret
                ret = []
                for bit,d in desc.items():
                    ex,mask = self.bitextract( bit, d[0], val )
                    mval = val & mask
                    if( mval > 0 ):
                        ret.append(d[1])
#                    print("mval = '%s'" % (mval,) )
#                    print("bit = '%s'" % (bit,) )
#                    print("d = '%s'" % (d,) )
                ret = " ".join(ret)
#                print("oval = '%s'" % (oval,) )
                return "[ " + ret + " ] "
            except ValueError:
                return val

        ret = " "
#        print("val = '%s'" % (val,) )
#        print("rawname = '%s'" % (rawname,) )
#        print("val[rawname[1]] = '%s'" % (val[rawname[1]],) )
        for f in val[rawname[1]].type.fields():
            sv = val[rawname[1]][f]
            ret += f"{f.name}[{sv}] "

        return "[" + ret + "]"

    def format_flags_short( self, flags, name, abbrval, count, descriptions, rawname ):
#        print("UT")
#        print(f"format_flags_short( {flags=},
#        count,descriptions,rawname = flag_info.get(name)
        regdesc = self.get(name)
#        print("name = '%s'" % (name,) )
#        print("regdesc = '%s'" % (regdesc,) )
#        flags,valtype = rflags.get(regdesc)

        if( rawname is not None ):
            iflags = int(flags[rawname[0]])
        else:
            iflags = int(flags)
        ret = ""
        retlen = 0

        bit = 0

        while bit <= count:
            mask = 1 << bit
            ex = iflags >> bit
            ex &= 1

            short = ""
            shortlen = 0

            tbit = f"{bit:02x}"
            desc = descriptions.get(bit,None)
            if( desc is not None ):
                dshort = desc[1]
#                text = desc[2]
                mp = desc[3]
                sz = desc[0]
                if( sz > 1 ):
                    tbit = f"{bit:02x}-{bit+sz-1:02x}"
                    ex,mask = self.bitextract(bit,sz,iflags)
                short = f"{dshort}[{ex}]"
                if( abbrval ):
                    if( mp is not None ):
                        ms,ml = mp.get(ex,(None,None))
                        if( ms is not None ):
                            short = f"{dshort}[{ms},{ex}]"

                shorteln = len(short)
#                print("iflags = '%s'" % (iflags,) )
#                print("mask = '%s'" % (mask,) )
#                print("ex = '%s'" % (ex,) )
                if( ex != 0 ):
                    short,shortlen = vdb.color.colorl(short,flag_colour.value)

            # bit order
            if( len(short) > 0 ):
                ret,relen = vdb.color.concat( vdb.color.concat( (short,shortlen)," ") , (ret,retlen) )
            bit += 1

        return [(ret,retlen)]

    def bitextract( self, bit, sz, iflags ):
#        print(f"bitextract({bit},{sz},{iflags:#0x})")
        sbit=bit
#        print("bit = '%s'" % (bit,) )
        mask = omask = 1 << bit
        bit += (sz-1)
#        print(f"{mask=:#0x}")
        for mb in range(0,sz):
            mask |= omask
            omask = omask << 1
#            print(f"{mask=:#0x}")
        iflags &= mask
        ex = (iflags >> sbit)
        return (ex,mask)

    def format_flags( self, flags,name, count, descriptions, rawname ):

        if( rawname is not None ):
            iflags = int(flags[rawname[0]])
        else:
            iflags = int(flags)

        ftbl = []
        ftbl.append( ["Bit",(vdb.util.Align.RIGHT,"Mask"),"Abrv","Description","Val","Meaning"] )

        bit = 0
        con_start = 0
        con_end = 0
        con_mask = 0
#        for bit in range(0,count):
        while bit <= count:
#            vdb.util.bark() # print("BARK")
#            print("bit = '%s'" % (bit,) )
            mask = 1 << bit
            ex = iflags >> bit
            ex &= 1

            short = ""
            text = "Reserved"
            meaning = None

            tbit = f"{bit:02x}"
            desc = descriptions.get(bit,None)
            if( desc is not None ):
#                vdb.util.bark() # print("BARK")
#                print("bit = '%s'" % (bit,) )
#                print("desc = '%s'" % (desc,) )
#                print("con_start = '%s'" % (con_start,) )
#                print("con_end = '%s'" % (con_end,) )
#                print("con_mask = '%s'" % (con_mask,) )
                if( con_mask != 0 ):
                    if( con_start == con_end ):
                        con_tbit = f"{con_start:02x}"
                    else:
                        con_tbit = f"{con_start:02x}-{con_end:02x}"
                    scon_mask = f"0x{con_mask:04x}"
#                    vdb.util.bark() # print("BARK")
                    ftbl.append( [ con_tbit, (vdb.util.Align.RIGHT,scon_mask), short, text, "", meaning ] )
                    con_mask = 0

                short = desc[1]
                text = desc[2]
                mp = desc[3]
                sz = desc[0]
                if( text is None ):
                    text = ""
                if( sz > 1 ):
                    ex,mask = self.bitextract( bit,sz,iflags)
#                    print("bit = '%s'" % (bit,) )
                    tbit = f"{bit:02x}-{bit+sz-1:02x}"
#                    omask = mask = 1 << bit
#                    bit += (sz-1)
#                    for mb in range(0,sz):
#                        mask |= omask
#                        omask = omask << 1
#                        print(f"{mask=:#0x}")
#                    ex = (iflags >> bit) & ((1 << sz)-1)
                if( ex != 0 ):
                    short = ( vdb.color.color(short,flag_colour.value), len(short))
                if( mp is not None ):
                    if( isinstance(mp,str) ):
                        meaning = mp
                    else:
                        ms,ml= mp.get(ex,("","??"))
                        meaning = ms+" "+ml

                mask = f"0x{mask:04x}"
                wraprest = []
                if( len(text) > text_len.value ):
                    wraps = textwrap.wrap(text,text_len.value)
                    text = wraps[0]
                    wraprest = wraps[1:]
                if( ex > 9 ):
                    ex=f"{ex:#0{sz//4}x}"
#                vdb.util.bark() # print("BARK")
                ftbl.append( [ tbit, (vdb.util.Align.RIGHT,mask), short, text, ex, meaning ] )
                for w in wraprest:
                    ftbl.append( [ None, None, None, w, None, None ] )
                bit += sz
            else:
#                vdb.util.bark() # print("BARK")
#                print("con_mask = '%s'" % (con_mask,) )
#                print("con_start = '%s'" % (con_start,) )
#                print("con_end = '%s'" % (con_end,) )
                if( con_mask == 0 ):
                    con_mask = mask
                    con_start = bit
                    con_end = bit
                else:
                    con_end += 1
                    con_mask |= mask

                bit += 1

        ftbl.append(None)
        return ftbl

    def flags( self, filter, extended , short , mini ):
        ret = self._flags( filter, self.rflags, flag_info, extended, short, mini, None )
        ret = vdb.util.format_table( ret )
        return ret

    def _flags( self, filter, rflags, flag_inf, extended , short , mini, addr_map ):
#        print(f"_flags( {filter=}, {rflags=}, flag_inf, {extended=}, {short=}, {mini=}, {addr_map=}  )")
        flagtable = []

        if( filter is not None ):
            filter = re.compile(filter)
        for fr,v in rflags.items():
            if( filter is not None ):
                if( filter.search(fr.name) is None ):
                    continue
            fv,ft = v
            abbr = False
            if( fr.name in abbrflags ):
                abbr = True

            _,count,desc,rawfield = flag_inf.get(fr.name,(None,None,None))
            
            if( rawfield is not None ):
                ival = int(fv[rawfield[0]])
            else:
                ival = int(fv)
            if( ival < 0 ):
                ival += 2**32 # XXX Adapt for 64 bit arch or generalize (what if the register has different bits than arch size anyways?)

            if( count <= 32 ):
                valstr = f"{ival:#010x}"
            else:
                valstr = f"{ival:#018x}"
            line = [ (fr.name,color_names.value), valstr ]
            flagtable.append(line)
            if( addr_map is not None ):
                addr = addr_map.get(fr.name,None)
                if( addr is not None ):
                    flagtable.append( [ None, (addr,0,0) ] )

            if( mini ):
                fvm = self.format_flags_mini( fr.name, rawfield, fv, desc )
                line.append(fvm)

            if( short ):
                line += self.format_flags_short(fv,fr.name,abbr,count,desc,rawfield)

            if( extended ):
                flagtable += self.format_flags(fv,fr.name,count,desc,rawfield)

        return flagtable

    class mmap_register:
        def __init__( self, name ):
            self.name = name

    class mmap_reg:
        def __init__( self ):
            self.item_list = []

        def add( self, name, value ):
            self.item_list.append( ( Registers.mmap_register(name),(value,None) ) )

        def items( self ):
            return self.item_list

    def get_mmapped( self, reg ):
#        print(f"{reg=}")
        rpos = mmapped_positions.get(reg)
#        print(f"{rpos=}")
        if( rpos is None ):
            return (None,None)
        rname,raddr,rbit,rtype = rpos
        if( is_blacklisted(raddr) ):
            return (None,None)
        val = vdb.memory.read_uncached(raddr,rbit//8)
        if( val is None ): # unable to read or otherwise not accessible
            if( not mmapfake.value ):
                print(f"{reg}@{raddr:#0x} blacklisted: memory not accessible")
                blacklist(raddr)
                return (None,None)
            else:
                val = b"\0\0\0\0"
        val = gdb.Value(val,rtype)
        return (val,raddr)


    def mmapped( self, filter, full = False, short=False, mini=False ):
#        print(f"Register.mmapped(, {filter=},...)")
        show_address = False
        pfilter = filter
        if( filter is not None and len(filter) > 0 ):
            if( filter[0] == "&" ):
                show_address = True
                filter = filter[1:]
            if( len(filter) > 0 ):
                filter = re.compile(filter)
            else:
                filter = None
        itlist = Registers.mmap_reg()

        # might be an expression down to the bit(s) or otherwise an exact match
        if( pfilter is not None ):
            val,mmp = self.get_reg( pfilter )
            if( val is not None ):
                # ok it matches, but is it really a bit?
                if( len(pfilter.split(".")) == 3 ):
                    return f"{int(val):#0x}"

        addrmap = {}

        for reg,rpos in mmapped_positions.items():
            if( filter is not None ):
                if( filter.search(reg) is None ):
                    continue
            val,raddr = self.get_mmapped(reg)
            if( val is None ):
                continue

            itlist.add(reg,val)
            p,_ = vdb.pointer.chain(raddr)
            addrmap[reg] = p
        if( not show_address ):
            addrmap = None
        #ret=self._flags( it, mmapped_descriptions, True, True, True )
        ret=[]
        if( full ):
            ret+=self._flags( None, itlist, mmapped_descriptions, True, False, False, addrmap )
        if( short ):
            ret+=self._flags( None, itlist, mmapped_descriptions, False, True, False, addrmap )
        if( mini ):
            ret+=self._flags( None, itlist, mmapped_descriptions, False, False, True, addrmap )


        return vdb.util.format_table(ret)
#        print("mmapped_descriptions = '%s'" % (mmapped_descriptions,) )

    def print_if( self, msg ):
        if( len(msg) > 0 ):
            print(msg)

    def print( self, showspec, filter = None ):
        for s in showspec:
            if( s == "i" ):
                self.print_if(self.ints(filter,extended=False))
            elif( s == "I" ):
                self.print_if(self.ints(filter,extended=True,wrapat=1))
            elif( s == "v" ):
                self.print_if(self.vectors(filter,extended=False))
            elif( s == "V" ):
                self.print_if(self.vectors(filter,extended=True))
            elif( s == "f" ):
                self.print_if(self.floats(filter))
            elif( s == "F" ):
                self.print_if(self.ex_floats(filter))
            elif( s == "y" ):
                self.print_if(self.flags(filter,extended=False,short=False,mini=True))
            elif( s == "x" ):
                self.print_if(self.flags(filter,extended=False,short=True,mini=False))
            elif( s == "X" ):
                self.print_if(self.flags(filter,extended=True,short=False,mini=False))
            elif( s == "o" ):
                self.print_if(self.other(filter,extended=False))
            elif( s == "O" ):
                self.print_if(self.other(filter,extended=True,wrapat=1))
            elif( s == "p" ):
                self.print_if(self.prefixes(filter))
            elif( s == "P" ):
                self.print_if(self.ex_prefixes(filter))
            elif( s == "m" ):
                self.print_if(self.mmapped(filter,short=True))
            elif( s == "M" ):
                self.print_if(self.mmapped(filter,full=True))
            elif( s == "d" ):
                self.print_if(self.mmapped(filter,mini=True))
            elif( s == "." ):
                pass
            elif( s == "?" ):
                print("Recognized showspec characters: iIvVfFxXpP.?")
            else:
                print("Invalid showspec '%s'" % s )

registers = None

@vdb.event.new_objfile()
def reset( self ):
    global registers
    registers = None

def update( ):
#        print("Updating registers...",file=sys.stderr)
#        with open("register.log","a") as f:
#            traceback.print_stack(file=f)
    try:
        nrr = Registers()
        global registers
        registers = nrr
    except Exception as e:
        print("When trying to make sense out of registers, we encountered an exception: %s" % e )
        vdb.print_exc()


class cmd_registers(vdb.command.command):
    """Show the registers nicely (default is /e)

The following shortcuts exist:

registers/s  - Show just the important registers and flags with their hex values
registers/e  - Show the important registers in a recursively expanded way, depending on their usual type maybe as integers or pointer chains
registers/a  - Show all registers in their short hex form
registers/E  - Show all registers in the expanded form if possible, for fpu and vector registers this may mean all possible representations

You can also use registers/<showspec> to chose the components and their order yourself. Currently recognized showspec characters are iIvVfFxXpPoO.
For more information and showspecs see the documentation.

We recommend having an alias reg = registers in your .gdbinit
"""

    def __init__ (self):
        super (cmd_registers, self).__init__ ("registers", gdb.COMMAND_DATA)


    def maybe_update( self ):
        # XXX We always update, do we really need to do that? Should only ever change after stop? Or whats in nonstop
        # mode?
#        global registers
#        print("registers = '%s'" % registers )
#        if( registers is not None ):
#            print("registers.thread = '%s'" % registers.thread )
#        if( registers is None or registers.thread == 0 ):
#            print("Need to call update")
        update()

    def usage( self ):
        super().usage()
        Registers().print("?")

    def complete( self, text, word ):
        if( word is None and len(text) == 0 ):
            return []

        try:
            global registers
            allregs = []
            allregs = mmapped_positions.keys()
#            print()
#            print("==============================")
#            vdb.util.bark() # print("BARK")
#            vdb.util.bark() # print("BARK")
#            print("len(allregs) = '%s'" % (len(allregs),) )
#            print("word = '%s'" % (word,) )
#            print("text = '%s'" % (text,) )

            if( text[-1] == "." ):
                mword = word
                if( mword is None ):
                    mword = ""
                tx = text.split()
#                print("tx = '%s'" % (tx,) )
                if( len(tx) > 1 ):
                    mword = tx[-1] + mword
#                print("mword = '%s'" % (mword,) )
                om=self.matches(mword,allregs)
                m=[]
                plen = len(mword)
                for o in om:
                    m.append( o[plen:] )
            else:
                m=self.matches(word,allregs)
#            print("m = '%s'" % (m,) )
            return m
        except:
            vdb.print_exc()
            pass
        return []

    def do_invoke (self, argv, legend = True ):
#        print(f"do_invoke({argv})")
        global registers
        try:
            self.maybe_update()

            if( registers is None or registers.thread == 0 ):
                print("No running thread to read registers from")
                return

            if( len(argv) == 0 ):
                argv += reg_default.value.split()

            argv,flags = self.flags(argv)

#            print(f"{argv=}")
#            print(f"{flags=}")

            filter = None

            # We want the setting to work like:
            # reg r14=55
            # reg/m SC.*UAR|=5
            # reg/m SC.*UAR|= 5
            # reg/m SC.*UAR |=5
            # reg/m SC.*UAR |= 5

            # make sure there is a space between all of them
#            print(f"{argv=}")
            args = " ".join(argv)
#            print(f"{args=}")
            for sep in [ "&=", "|=", "=" ]:
                args = args.replace(sep,f" {sep} ")
            args = args.strip()
#            print(f"{args=}")
            if(len(args) > 0 ):
                argv = args.split()
            else:
                argv = []
#            print(f"{argv=}")

            if( len(argv) > 0 ): # first is a regexp for filtering registers for display, extract that out of the setting expression
                filter = argv[0].split(":")[0]

#            print("========")
#            print(f"{argv=}")
#            print(f"{flags=}")
#            print(f"{filter=}")

            # Not a setter expression and no flags, set flags to something default
            if( not "=" in args ):
                if(  len(flags) == 0 ):
                    _,flags = self.flags(reg_default.value.split())
                if( len(argv) > 1 ):
                    filter = "|".join(argv)
                if( legend ):
                    vdb.memory.print_legend("Ama")

            # First display without any setting commands
            if( len(flags) > 0 ):
                if( flags == "s" ):
                    registers.print("ipx",filter)
                elif( flags == "e" ):
                    registers.print("Ipx",filter)
                elif( flags == "a" ):
                    registers.print("ixofpmv",filter)
                elif( flags == "E" ):
                    registers.print("IXOFPMV",filter)
                elif( flags == "_d" ):
                    registers._dump()
                else:
                    registers.print(flags,filter)

            # A setting expression
            if( "=" in argv ):
                if( len(argv) < 3 ):
                    print("Invalid argument(s) to registers: '%s'" % argv )
                    self.usage()
                else:
                    registers.set(argv)
            # no setting expression
#            elif( len(argv) > 1 ):
                # This one should recurse
#                argv = argv[1:]
#                print(f"{flags=}")
#                print(f"{argv=}")
#                print("WOULD RECURSE")
#                self.do_invoke( [ f"/{flags}" ] + argv, legend = False )
#            else:
        except Exception as e:
                vdb.print_exc()

        # Identify the cases where we can re-use the information gathered. Maybe refactor Registers() to always read
        # values on demand?

        registers = None

cmd_registers()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
