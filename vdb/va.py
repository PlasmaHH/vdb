#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.arch
import vdb.memory
import vdb.pointer

import gdb

import re
import traceback
import math


fixed_float_color = vdb.config.parameter( "vdb-va-colors-fixed-float",  "#838", gdb_type = vdb.config.PARAM_COLOUR )
var_float_color   = vdb.config.parameter( "vdb-va-colors-vararg-float", "#608", gdb_type = vdb.config.PARAM_COLOUR )
fixed_int_color   = vdb.config.parameter( "vdb-va-colors-fixed-int",    "#953", gdb_type = vdb.config.PARAM_COLOUR )
var_int_color     = vdb.config.parameter( "vdb-va-colors-vararg-int",   "#c43", gdb_type = vdb.config.PARAM_COLOUR )

# We have similar x86_64 specific stuff in the unwinder, we should have this at one place to better support other archs

int_limit = vdb.config.parameter( "vdb-va-int-limit",32*1024 )
min_ascii = vdb.config.parameter( "vdb-va-min-ascii", 2)
max_exponent = vdb.config.parameter( "vdb-va-max-exponent", 256 )
default_format = vdb.config.parameter( "vdb-va-default-format", "**")
max_overflow_int = vdb.config.parameter( "vdb-va-max-overflow-int", 42 )
max_overflow_vec = vdb.config.parameter( "vdb-va-max-overflow-vector", 42 )

wait_max_ins = vdb.config.parameter( "vdb-va-wait-max-instructions", 36 )
auto_wait = vdb.config.parameter( "vdb-va-auto-wait", True )

#= vdb.config.parameter( "vdb-va-", )
#= vdb.config.parameter( "vdb-va-", )


saved_all_regs = {
        "arm" :
            {
                "i": [ "r0", "r1", "r2", "r3" ],
                "v": [],
                "f": [],
            },
        "x86" :
            {
                "i": [ "rdi", "rsi", "rdx", "rcx", "r8", "r9" ],
                "v": [ "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7" ],
                "f": [ "st7", "st6", "st5", "st4", "st3", "st2", "st1", "st0" ],
            }
        }

saved_regs = None

class Value:

    def __init__(self,val):
        self.val = val

    def __getattr__( self, name ):
        if( name == "address" ):
            return self.val.address
        return self.val[name]

    def __getitem__( self, name ):
        return self.val[name]


class gValue( gdb.Value ):
    def __init__(self,val):
        try:
            if( type(val) == gdb.Value ):
                super().__init__(val)
            else:
                super().__init__(vdb.util.hexint(val))
        except:
            super().__init__(val)

    def __getattr__( self, name ):
        try:
            return self.__getitem__(name)
        except gdb.error:
            return None

def guess_vecrep( val, colorspec = None ):
    candlist = [ ( "v4_float", 4), ("v2_double", 2) ]
#    vdb.util.bark() # print("BARK")

    for vname, vnum in candlist:
        first = None
        cval = val[vname]
        nonnull = 0
#        print("vname = '%s'" % (vname,) )
        for idx in range(0,vnum):
            if( first is None ):
                first = cval[idx]
            if( cval[idx] != 0 ):
                nonnull += 1

#            print("cval[idx] = '%s'" % (cval[idx],) )
#        print("nonnull = '%s'" % (nonnull,) )
#        print("first = '%s'" % (first,) )
        if( first != 0 and nonnull == 1 ):
            break

    return ( str(first), None )

def guess_intrep( val ):
    try:
        val = int(val)
        if( val < int_limit.value ): # definetly always an int
            return ( str(val), None )
#        ca,mm,col,ascii = vdb.memory.mmap.color(val,colorspec = None )
        mm = vdb.memory.mmap.find(val)
#        print("val = '0x%x'" % (val,) )
#        print("mm = '%s'" % (mm,) )
        if( mm is not None and not mm.is_unknown() ): # It is a pointer to known memory
#            print("ca = '%s'" % (ca,) )
#            print("mm = '%s'" % (mm,) )
#            print("col = '%s'" % (col,) )
#            print("ascii = '%s'" % (ascii,) )
#            plen = vdb.arch.pointer_size // 4
#            s = f"0x{val:0{plen}x}"
            pc = vdb.pointer.chain( val, vdb.arch.pointer_size, 1, True, min_ascii.value )
            pc = pc[0]
#            print("type(pc) = '%s'" % (type(pc),) )
#            print("pc = '%s'" % (pc,) )
            return (pc, "")
#            return ( s, col )
#        if( val > 0x7f0000000000 ):
#            pc = vdb.pointer.chain( val, vdb.arch.pointer_size, 1, True, minascii )
#            pc = pc[0]
#            return (pc, "")
        return ( str(val), None )
    except:
        vdb.print_exc()
        return ( str(val), None )

def int_range( saved, frm, to, stopvalues = set() ):
    ret = ""

#    print("stopvalues = '%s'" % (stopvalues,) )
    for i in range(frm,to):
        try:
            rval = saved[i]
#        print("int(rval) = '%s'" % (int(rval),) )
            if( int(rval) in stopvalues ):
                break
            rval,rco = guess_intrep(rval)
            if( rco is None ):
                rco = var_int_color.value
            ret += ", "
            ret += vdb.color.color(rval,rco)
        except gdb.MemoryError:
            break
    return ret

def vec_range( saved, offset, frm, to, step, skip = False ):
    ctype_p = gdb.lookup_type("char").pointer()
    r_c = saved.cast(ctype_p)
    r_c += offset

    dtype = gdb.lookup_type("double")
    dtype_p = dtype.pointer()
    dregp = r_c.cast(dtype_p)

    ret = ""
    for i in range(frm,to,step):
        try:

            m,e = math.frexp(dregp[i])
#        print("e = '%s'" % (e,) )
            if( abs(e) > max_exponent.value ):
                if( skip ):
                    continue
                break
            ret += ", "
            ret += vdb.color.color( str(dregp[i]), var_float_color.value )
        except gdb.MemoryError:
            break
    return ret

def intformat( val, fmt ):
    if( type(val) == str ):
        return val
    fmt = fmt.lower()
#    print("val = '%s'" % (val,) )
#    print("fmt = '%s'" % (fmt,) )
    if( fmt == "i" ): # 32bit signed integer
        val = val.cast(vdb.arch.sint(32))
    elif( fmt == "l" ): # 64bit signed integer
        val = val.cast(vdb.arch.sint(64))
    elif( fmt == "u" ): # 32bit unsinged integer
        val = val.cast(vdb.arch.uint(32))
    elif( fmt == "j" ): # 64bit unsigned integer
        val = val.cast(vdb.arch.uint(64))
#    print("val = '%s'" % (val,) )
#    print("type(val) = '%s'" % (type(val),) )
#    print("val.type = '%s'" % (val.type,) )
    return val

modfrom = "diocC uxX sS eEfFgGaA pn"
modto   = "iiiii uuu ss ffffffff pp"
longto  = "lllll jjj ss dddddddd pp"

modmap = {}
longmap = {}

for i in range(0,len(modfrom) ):
    modmap[modfrom[i]] = modto[i]
    longmap[modfrom[i]] = longto[i]

def convert_format( fmt ):
    next_fmt = False
    next_long = False
#    print("fmt = '%s'" % (fmt,) )
    ret = ""
    for f in fmt:
#        print("f = '%s'" % (f,) )
        if( next_fmt ):
            # h for short, check whats actually passed
            if( f in "01234567890.* #+-Ih" ):
                pass
            elif( f == "%" ):
                next_fmt = False
            elif( f in "lqLjzZt" ):
                next_long = True
            else:
#                print("Checking for replacement")
                if( next_long ):
                    to = longmap.get(f,None)
                else:
                    to = modmap.get(f,None)
                if( to is None ):
                    print(f"Unsupported printf format modifier '{f}'")
                    ret += i
                else:
#                    print(f"{f} => {to}")
                    ret += to
                next_fmt = False
        else:
            if( f == "%" ):
                next_fmt = True
                next_long = False
    return ret

# Tries to find a va_list variable in the debug info
def get_va_list( arg, frame ):

    if( len(arg) == 0 ):
        if True:
            b = frame.block()
            while b is not None:
                print("b.function = '%s'" % (b.function,) )
                va_list = None
                for s in b:
                    print("s = '%s'" % (s,) )
                    val=frame.read_var(s)
                    if( val.type.name == "va_list" ):
                        va_list = s
                        break
                if( b.function is not None ):
                    break
                if( va_list is not None ):
                    break
                b = b.superblock

            else:
                va_list = None
        else:
            lre = re.compile(r"^[^\s]* =")
            locals = gdb.execute("info locals",False,True)
            for line in locals.splitlines():
                m=lre.match(line)
                if( m is not None ):
                    varname = line.split("=")[0].strip()
                    val=frame.read_var(varname)
#                print("varname = '%s'" % (varname,) )
#                print("val = '%s'" % (val,) )
#                print("val.type = '%s'" % (val.type,) )
                    if( val.type.name == "va_list" ):
                        va_list = varname
#                    print("va_list = '%s'" % (va_list,) )
                        break
#            print("line = '%s'" % (line,) )
#            print("m = '%s'" % (m,) )
            else:
                va_list = None
    else:
        va_list = arg[0]

    if( va_list is not None ):
        va_list_val = frame.read_var(va_list)
    else:
        va_list_val = None

    return va_list,va_list_val

def setup_regs( ):
    arch = vdb.arch.short_name()
    global saved_regs
    saved_regs = saved_all_regs[arch]


# encapsulates all we need to know to recover the call. These are very implementation and architecture defined. We
# assume gcc here.
class va_args:

    def __init__( self ):
        # Total number of fixed arguments before the ellipsis starts
        self.num_fixed = None
        # Start on the stack of the general purpose type arguments (int, pointer etc.) of 8 byte each
        self.gp_start = None
        # Start on the stack of the floating point type arguments of 8 byte each
        self.fp_start = None
        # Start on the stack of the vector register arguments of 16 byte each
        self.vec_start = None
        # Arguments on the stack, order and size depends on the format string
        self.overflow_start = None
"""

values before anything:

$3 = {
  {
    gp_offset = 858927408,
    fp_offset = 926299444,
    overflow_arg_area = 0x7ffff78aa556 <__glibc_morecore+24>,
    reg_save_area = 0x4746454443424140
  }
}



"""
def recover_args_x86( arg, argdict ):
    return
    print(f"recover_args_x86( {arg=}, {argdict=} )")
    frame = gdb.selected_frame()
    va_list = get_va_list( arg, frame )

    # XXX This is all calculated for 64 bit, no 32bit support right now
    register_bytes = 8

    saved_registers = vdb.register.Register()

    # We might already be past the point where the registes have been re-used, be careful
#    for reg in saved_regs["i"]:
#        saved_registers[reg] = int(frame.read_register(reg))

#    vdb.util.pprint(saved_registers)

    va = va_args()
    if( va_list is None ):
        print("va_list is none, trying to guess whats going on")
    else:
        print("va_list found, copying info")
        # XXX We should store the fixed parameter registers here since the single stepping through the setup of the
        # va_list will kind of destroy them (well not really as it gets copied into there but for certain decisions its
        # useful to have them before a complete va_list structure )
        print(f"{gdb.selected_frame()=}")
        if( auto_wait.value ):
            wait( arg, True )
            print(f"{frame.is_valid()=}")
            frame.select()
        print(f"{gdb.selected_frame()=}")
        va_list_val = frame.read_var(va_list)

        # fp/gp offset tell us how many of the saved registers are not used for the varargs but for the "real" arguments
        # instead.
        # Let the user override values if necessary

        # XXX btw. arg->gp_offset is not correctly shown in ASM !
        gp_offset = va_list_val["gp_offset"]
        gp_offset = argdict.getas(int,"gp_offset",gp_offset)

        fp_offset = va_list_val["fp_offset"]
        fp_offset = argdict.getas(int,"fp_offset",fp_offset)

        gp_num = gp_offset // register_bytes

        # basically the amount of max gp registers
        fp_num = ( fp_offset - 6*register_bytes )// register_bytes

        reg_save_area = va_list_val["reg_save_area"]
        reg_save_area = argdict.getas(int,"reg_save_area",reg_save_area)

        # When we are optimized the arguments to the real function are saved nowhere but in the registers.
        print("function( ")
        for i,(r,v) in enumerate( saved_registers.items() ):
            if( i >= gp_num ):
                break
            # Format as pointer or integer, depending on heuristics
            print(f"??gp{i} : {r}:{v:#0x},")

        # Now a number of possible gp saved registers. Since we already "used up" gp_num ones, its this much left
        registers_left = len(saved_regs["i"]) - gp_num
        print(f"{registers_left=}")
        for i in range(0,registers_left):
            gp_addr = reg_save_area + gp_offset + register_bytes * i
            var = vdb.memory.read_var( gp_addr, vdb.arch.uint(64).name )
            print(f"{gp_addr=:#0x} : {var}")


    print(f"{va_list=}")

def va_print( argv ):

    setup_regs()

    arg, argdict = vdb.util.parse_vars( argv )

    match vdb.arch.short_name():
        case "arm":
            args = recover_args_arm(arg,argdict)
        case "x86":
            args = recover_args_x86(arg,argdict)
        case "_":
            raise RuntimeError(f"Unsuported architecture: {vdb.arch.short_name()}")

    frame = gdb.selected_frame()


    # Walk through the current stack to gather all addresses that are function return addresses. We use these later on
    # as possible sentinels to stop printing
    retaddrs = set()
    nf = frame
    olvl = -1
    while( nf is not None ):
        retaddrs.add( int(nf.pc()) )
        if( olvl == nf.level() ):
            break
        olvl = nf.level()
        nf = nf.older()

    saved_registers = vdb.register.Registers()
#    saved_registers._dump()

    # We might already be past the point where the registes have been re-used, be careful
#    for reg in saved_regs["i"]:
#        saved_registers[reg] = int(frame.read_register(reg))

#    vdb.util.pprint(saved_registers)
    try:
        if( auto_wait.value ):
            va_list,va_list_val = wait( arg, frame, True )
        else:
            va_list,va_list_val = get_va_list( arg, frame )
    except RuntimeError:
        print("Cannot print va list, possibly no debug info loaded")
        va_list = None
    if( frame.level() != 0 ):
        print("Warning: not on innermost frame, register only arguments might be wrong")
    frame.select()

    allprovided = False

    print(f"{va_list=}")
    print(f"{argdict=}")

    if( "gp_offset" in argdict and "fp_offset" in argdict and "reg_save_area" in argdict and "overflow_arg_area" in argdict ):
        allprovided = True

    if( va_list is not None ):
        va_list_val = frame.read_var(va_list)
        va_list_val = gValue(va_list_val)

        gp_offset = va_list_val.gp_offset
        fp_offset = va_list_val.fp_offset
        reg_save_area = va_list_val.reg_save_area
        overflow_arg_area = va_list_val.overflow_arg_area

    elif( not allprovided ):
        print("Could not automatically detect the va_list variable, please provide it")
        return
    else:
        gp_offset = fp_offset = reg_save_area = overflow_arg_area = None

    num_fixed = None
    # This is when we call stuff on arm, provide sensible defaults here
    if( gp_offset is None ):
        gp_offset = -8
    if( fp_offset is None ):
        fp_offset = 0
    if( overflow_arg_area is None ):
        overflow_arg_area = 0

    gp_offset = argdict.getas(int,"gp_offset",gp_offset)
    fp_offset = argdict.getas(int,"fp_offset",fp_offset)
    reg_save_area = argdict.getas(gValue,"reg_save_area", reg_save_area)
    overflow_arg_area = argdict.getas(gValue,"overflow_arg_area", overflow_arg_area)

    if( reg_save_area is None ):
        reg_save_area = va_list_val.__ap

    if( gp_offset > 32*8 or gp_offset < 0 or gp_offset == 0 or gp_offset%8 != 0):
        print(f"Warning! Unlikely gp_offset value ({gp_offset}), results are likely wrong. Recommend rerunning with gp_offset=8")

    if( fp_offset > 32*8 or fp_offset < 0 or fp_offset == 0 or fp_offset%16 != 0):
        print(f"Warning! Unlikely fp_offset value ({fp_offset}), results are likely wrong. Recommend rerunning with fp_offset=48")

    mm = vdb.memory.mmap.find(int(reg_save_area))
    if( mm is None or mm.is_unknown() ):
        print(f"reg_save_area is pointing to unknown memory, results are likely wrong.")

    mm = vdb.memory.mmap.find(int(overflow_arg_area))
    if( mm is None or mm.is_unknown() ):
        print(f"overflow_arg_area is pointing to unknown memory, results are likely wrong.")

    print(f"Using gp_offset={gp_offset}, fp_offset={fp_offset}")
    print("Possible function call(s):")

    format = argdict.get( "format", default_format.value )
    print(f"{format=}")

    # * means "show everything"
    # ** means "try to recover a format string, otherweise show everything
    if( format == "*" ):
        format = None
    elif( format == "**" ):
        # Assumption is that a its under the first parameters that are in the registers, so go through the saved ones.
        format = None

    if( num_fixed is None ):
        num_fixed = int(gp_offset) // ( vdb.arch.pointer_size // 8)
    if( num_fixed < 0 ):
        num_fixed = -num_fixed
        num_fixed += 1
    print(f"{num_fixed=}")
    print(f"{gp_offset=}")
    print(f"{fp_offset=}")

    funcstr = ""

    if( frame.name() is not None ):
        funcstr += frame.name()
    else:
        funcstr = "func"

    print(f"{format=}")
    if( format is not None ):
        funcstr += "( "
        cnt = 0
        ctype_p = gdb.lookup_type("char").pointer()
        l_gp_offset = int(gp_offset)
        l_fp_offset = int(fp_offset)

        ptrtype = vdb.arch.uintptr_t.pointer()
        ireg_save = reg_save_area.cast(ptrtype)
        ireg_over = overflow_arg_area.cast(ptrtype)

        dtype = gdb.lookup_type("double")
        dtype_p = dtype.pointer()
        dreg_save = reg_save_area.cast(dtype_p)
        dreg_over = overflow_arg_area.cast(dtype_p)

        last_string = None

        maxi = len(format)-1

        i = -1
        fp_next = 0
        vr_next = 0
        gp_next = 0
        while i < maxi:
            i += 1
            f = format[i]

            if( f == "*" ):
                print("last_string = '%s'" % (last_string,) )
                format = format[:-1] + convert_format(last_string)
                print("format = '%s'" % (format,) )
                maxi = len(format)-1
                i -= 1
#                print("format = '%s'" % (format,) )
                continue

            if( cnt > 0 ):
                funcstr += ", "

            if( f in "SPILUJ" ):
                regname = saved_regs["i"][gp_next]
                gp_next += 1
                rval = saved_registers.get_value(regname)[0]
                rval = gdb.Value(rval)
#                print(f"{regname=} : {rval}")
#                rval = vdb.register.read(regname,frame)
                if( f == "S" ):
                    rval = rval.cast(ctype_p)
                    funcstr += vdb.color.color( rval, fixed_int_color.value )
                    last_string = str(rval)
                elif( f == "P" ):
                    funcstr += vdb.pointer.chain( rval, vdb.arch.pointer_size, 1, True, min_ascii.value )[0]
                else:
                    funcstr += vdb.color.color( rval, fixed_int_color.value )
            elif( f in "spiluj" ):
                if( l_gp_offset < 48 ):
                    lidx = l_gp_offset // 8
                    rval = ireg_save[lidx]
                    l_gp_offset += 8
                else:
                    rval = ireg_over[gp_next]
                    gp_next += 1
                if( f == "s" ):
                    try:
                        rval = rval.cast(ctype_p)
                    except AttributeError:
                        pass
                    funcstr += vdb.color.color( rval, var_int_color.value )
                elif( f == "p" ):
                    funcstr += vdb.pointer.chain( rval, vdb.arch.pointer_size, 1, True, min_ascii.value )[0]
                else:
                    rval = intformat(rval,f)
                    funcstr += vdb.color.color( rval, var_int_color.value )
            elif( f == "F" ):
                rname = saved_regs["v"][ vr_next ]
                vr_next += 1
                rval = vdb.register.read(rname,frame)
                rval,rco = guess_vecrep(rval)
                funcstr += vdb.color.color( rval, var_float_color.value )
            elif( f == "f" ):
                if( l_fp_offset < 16*11 ): # confirm value
                    lidx = l_fp_offset // 8
                    rval = dreg_save[lidx]
                    l_fp_offset += 16
                else:
                    rval = dreg_over[gp_next]
                    gp_next += 1
                funcstr += vdb.color.color( rval, var_float_color.value )
            elif( f == "d" or f == "D" ):
                rname = saved_regs["f"][ fp_next ]
                fp_next += 1
                rval = vdb.register.read(rname,frame)
                funcstr += vdb.color.color( rval, var_float_color.value )
            else:
                print(f"Unsupported format string {f}")


            cnt += 1

        funcstr += ")"
        print(funcstr)
        return None

    funcstr = funcstr.rjust(12)
    funcstr += "( "



    pflen = len(funcstr)

    funcstr += "\ngp fixed".ljust(pflen)


    first = True

    for i in range(0,num_fixed):
        if( not first ):
            funcstr += ", "
        first = False
        if( i >= len(saved_regs["i"]) ):
            break
        try:
            irname = saved_regs["i"][i]
            print(f"{irname=}")
            rval = saved_registers.get_value(irname)[0]
            print(f"{rval}")
            rval,rco = guess_intrep(rval)
            if( rco is None ):
                rco = fixed_int_color.value
            funcstr += vdb.color.color(str(rval),rco)
        except:
            vdb.print_exc()
            funcstr += vdb.color.color("?",fixed_int_color.value)
            break

    ptrtype = vdb.arch.uintptr_t.pointer()
    reg_save = reg_save_area.cast(ptrtype)

    funcstr += "\ngp vararg (reg)".ljust(pflen)
    funcstr += int_range( reg_save, num_fixed, len(saved_regs["i"]) )

    overflow = overflow_arg_area.cast(ptrtype)

    funcstr += "\ngp vararg (stack)".ljust(pflen)
    funcstr += int_range( overflow, 2, max_overflow_int.value, retaddrs )



    num_fixed = int(fp_offset - 48) // 16

    funcstr += "\nfp fixed".ljust(pflen)

    for i in range(0,num_fixed):
        if( not first ):
            funcstr += ", "
        first = False
        try:
            irname = saved_regs["v"][i]
            rval = vdb.register.read(irname,frame)
            rval,rco = guess_vecrep(rval)
            if( rco is None ):
                rco = fixed_float_color.value
            funcstr += vdb.color.color(str(rval),rco)
        except IndexError:
            break
        except:
            vdb.print_exc()
            funcstr += vdb.color.color("?",fixed_int_color.value)

    funcstr += "\nfp vararg".ljust(pflen)
    funcstr += vec_range(reg_save_area,fp_offset, 0,len(saved_regs["v"]),2)

    # it looks like the offset here is depending on the valid number of arguments we got so far from the overflow area.
    # We can't possibly know
    funcstr += "\nfp vararg".ljust(pflen)
    funcstr += vec_range(overflow_arg_area,0, 0,max_overflow_vec.value,1,True)


#    for r in saved_regs["i"]:
#        rval = vdb.register.read(r,frame)
#        ldval = rval.cast(gdb.lookup_type("long double"))
#        print(f"{r} : 0x{int(rval):02x} {rval} {ldval}")

    funcstr += "\nfp fix/var".ljust(pflen)


    for st in saved_regs["f"]:
        rval = vdb.register.read(st,frame)
        if( rval == 0 ):
            break
        funcstr += ", "
        funcstr += vdb.color.color( str(rval), var_float_color.value )
#    reg_save = va_list_val["reg_save_area"].cast(dtype_p)
#    for i in range(0,8):
#        rval = vdb.register.read(r,frame)
#        print(f"(double)reg_save[{i}] = {reg_save[i]}")

    funcstr += "\n".ljust(pflen)
    funcstr += ")"
    print(funcstr)


def wait( arg, frame, auto = False ):
    print(f"wait( {arg=} )")

    arg, argdict = vdb.util.parse_vars( arg )
#    frame = gdb.selected_frame()

    try:
        va_list,va_list_val = get_va_list( arg, frame )
    except RuntimeError:
        va_list = None

    if( va_list is None ):
        print("Cannot wait for change of va_list, couldn't find it (possibly no debug info loaded)")
        return None,None

    va_list_val = gValue(va_list_val)

    first_gp_offset = int(va_list_val.gp_offset)
    first_fp_offset = int(va_list_val.fp_offset)
    first_reg_save_area = int(va_list_val.reg_save_area)
    first_overflow_arg_area = int(va_list_val.overflow_arg_area)

#    print("first_gp_offset = '%s'" % (first_gp_offset,) )
#    print("first_fp_offset = '%s'" % (first_fp_offset,) )
#    print("first_reg_save_area = 0x%08x" % (first_reg_save_area,) )
#    print("first_overflow_arg_area = 0x%08x" % (first_overflow_arg_area,) )

    frame_sp = int(frame.read_register("rsp"))

    for i in range(0,wait_max_ins.value):
        # maybe also stop on frame change? What happens when we get sucked into another thread or ISR?
#        print()

        gp_offset = int(va_list_val.gp_offset)
        fp_offset = int(va_list_val.fp_offset)
        reg_save_area = int(va_list_val.reg_save_area)
        overflow_arg_area = int(va_list_val.overflow_arg_area)

        print(f"{frame.level()=}")
        print(f"{frame_sp=:#0x}")
        print("gp_offset = '%s'" % (gp_offset,) )
        print("fp_offset = '%s'" % (fp_offset,) )
        print("reg_save_area = 0x%08x" % (reg_save_area,) )
        print("overflow_arg_area = 0x%08x" % (overflow_arg_area,) )

        # Don't use fp_offset ... it is so rarely needed, and often gcc generates code that clobbers fixed parameters
        # before it sets this up, so only output a message if it wasn't up to date
#        if( gp_offset != first_gp_offset and reg_save_area != first_reg_save_area and overflow_arg_area != first_overflow_arg_area ):
        # Turns out we can't really use the adresses too in case someone calls e.g. two printf() after another, they
        # will be set already. Fortunately for us it seems gcc always changes this on va_arg() invocation and always
        # sets it after the adresses, so until we find a better heuristics use this (hint: better heuristics may be
        # actual watch points, which might be generically a good tool, also with the track stuff, surely they can share
        # some code)

#        if( gp_offset != first_gp_offset ):
        if( gp_offset != first_gp_offset and fp_offset != first_fp_offset and reg_save_area != first_reg_save_area ):
            if( not auto ):
                print("va_list completely updated, va extraction has a higher chance of working now")
            break

        if( frame.level() != 0 ):
            print("Can only reliably single step to fill va_list in innermost frame but we are not (anymore)")
            if(
            gp_offset <= 64 # 8 * n for n parameters before the varargs, more than 8 should be too unusual
            and
            fp_offset < 128 # 48 +  n * 16 for float/double args. long double is in xmm
            ):
#            print("fp and gp fine")
                # XXX This logic only works if we are the frame that sets up va_list, if we get it passed then I guess sp
                # might be further off? But then the address should be in some register?
                # so sp = oldsp - 0xd8 (reserve space for local data on the stack)
                # reg save is the area where we store the argument registers
                rdif = frame_sp - reg_save_area
                # overflow arg area is all the additional args that by calling convention did not go into the registers but
                # on the stack
                # al contains the number of vector registers used, float and double go there
                # long doubles are stored as extended floating points on the stack (16 byte)
                odif = overflow_arg_area - frame_sp
                print(f"{rdif=}")
                print(f"{odif=}")
                if( rdif > 0 and rdif < 256
                and
                odif > 0 and odif < 64
                ):
                    if( not auto ):
                        print("All variables look good, we should be able to continue")
                    break


        # Do the step after the check in case the position where the user had its breakpoint is setup correctly
        print("VA SINGLE STEP")
        with vdb.util.silence() as _:
            res=gdb.execute("stepi",False,False)
    else:
        print(f"Executed vdb-va-wait-max-instructions ({wait_max_ins.value}) instructions but still the va_list members did not all change. We may need a higher value or did miss the right point, check manually")
    return va_list,va_list_val

class cmd_va (vdb.command.command):
    """In a C-style vararg function like printf, this tries to parse and recover the passed arguments. This is most
    useful if you do not have any debug information for those functions.

va               - Try to figure out everything automatically
va var=val       - Runs with special variable var set to val. See documentation for all the variables.
"""

    def __init__ (self):
        super (cmd_va, self).__init__ ("va", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = False

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)
        if( len(argv) == 1 ):
            if( argv[0] == "wait" ):
                print("Waiting...")
                wait(argv[1:])
                return
        va_print(argv)
        self.dont_repeat()

cmd_va()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
