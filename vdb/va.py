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
default_format = vdb.config.parameter( "vdb-va-default-format", "*")
max_overflow_int = vdb.config.parameter( "vdb-va-max-overflow-int", 42 )
max_overflow_vec = vdb.config.parameter( "vdb-va-max-overflow-vector", 42 )

wait_max_ins = vdb.config.parameter( "vdb-va-wait-max-instructions", 24 )

#= vdb.config.parameter( "vdb-va-", )
#= vdb.config.parameter( "vdb-va-", )

saved_iregs = [ "rdi", "rsi", "rdx", "rcx", "r8", "r9" ]
saved_vregs = [ "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7" ]
saved_fregs = [ "st7", "st6", "st5", "st4", "st3", "st2", "st1", "st0" ]

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
        return self.__getitem__(name)

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
        traceback.print_exc()
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
        val = val.cast(gdb.lookup_type("int32_t"))
    elif( fmt == "l" ): # 64bit signed integer
        val = val.cast(gdb.lookup_type("int64_t"))
    elif( fmt == "u" ): # 32bit unsinged integer
        val = val.cast(gdb.lookup_type("uint32_t"))
    elif( fmt == "j" ): # 64bit unsigned integer
        val = val.cast(gdb.lookup_type("uint64_t"))
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
            if( f in "01234567890. #+-Ih" ):
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

def get_va_list( arg, frame ):

    if( len(arg) == 0 ):
        if True:
            b = frame.block()
            while b is not None:
#                print("b.function = '%s'" % (b.function,) )
                va_list = None
                for s in b:
#                    print("s = '%s'" % (s,) )
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
            lre = re.compile("^[^\s]* =")
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

    return va_list


def va_print( arg ):

    arg, argdict = vdb.util.parse_vars( arg )
    frame = gdb.selected_frame()


    retaddrs = set()
    nf = frame
    olvl = -1
    while( nf is not None ):
        retaddrs.add( int(nf.pc()) )
        if( olvl == nf.level() ):
            break
        olvl = nf.level()
        nf = nf.older()

    va_list = get_va_list( arg, frame )


    allprovided = False

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

    gp_offset = argdict.getas(int,"gp_offset",gp_offset)
    fp_offset = argdict.getas(int,"fp_offset",fp_offset)
    reg_save_area = argdict.getas(gValue,"reg_save_area", reg_save_area)
    overflow_arg_area = argdict.getas(gValue,"overflow_arg_area", overflow_arg_area)

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
    if( format == "*" ):
        format = None

    num_fixed = int(gp_offset) // 8

    funcstr = ""

    if( frame.name() is not None ):
        funcstr += frame.name()
    else:
        funcstr = "func"

    if( format is not None ):
#        print("format = '%s'" % (format,) )
        funcstr += "( "
        cnt = 0
        ctype_p = gdb.lookup_type("char").pointer()
        l_gp_offset = int(gp_offset)
        l_fp_offset = int(fp_offset)

        ptrtype = vdb.arch.gdb_uintptr_t.pointer()
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
#                print("last_string = '%s'" % (last_string,) )
                format = format[:-1] + convert_format(last_string)
#                print("format = '%s'" % (format,) )
                maxi = len(format)-1
                i -= 1
#                print("format = '%s'" % (format,) )
                continue

            if( cnt > 0 ):
                funcstr += ", "

            if( f in "SPILUJ" ):
                regname = saved_iregs[gp_next]
                gp_next += 1
                rval = vdb.register.read(regname,frame)
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
                rname = saved_vregs[ vr_next ]
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
                rname = saved_fregs[ fp_next ]
                fp_next += 1
                rval = vdb.register.read(rname,frame)
                funcstr += vdb.color.color( rval, var_float_color.value )


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
        if( i >= len(saved_iregs) ):
            break
        try:
            irname = saved_iregs[i]
            rval = vdb.register.read(irname,frame)
            rval,rco = guess_intrep(rval)
            if( rco is None ):
                rco = fixed_int_color.value
            funcstr += vdb.color.color(str(rval),rco)
        except:
            traceback.print_exc()
            funcstr += vdb.color.color("?",fixed_int_color.value)
            break

    ptrtype = vdb.arch.gdb_uintptr_t.pointer()
    reg_save = reg_save_area.cast(ptrtype)

    funcstr += "\ngp vararg".ljust(pflen)
    funcstr += int_range( reg_save, num_fixed, len(saved_iregs) )

    overflow = overflow_arg_area.cast(ptrtype)

    funcstr += "\ngp vararg".ljust(pflen)
    funcstr += int_range( overflow, 2, max_overflow_int.value, retaddrs )



    num_fixed = int(fp_offset - 48) // 16

    funcstr += "\nfp fixed".ljust(pflen)

    for i in range(0,num_fixed):
        if( not first ):
            funcstr += ", "
        first = False
        try:
            irname = saved_vregs[i]
            rval = vdb.register.read(irname,frame)
            rval,rco = guess_vecrep(rval)
            if( rco is None ):
                rco = fixed_float_color.value
            funcstr += vdb.color.color(str(rval),rco)
        except:
            traceback.print_exc()

            funcstr += vdb.color.color("?",fixed_int_color.value)

    funcstr += "\nfp vararg".ljust(pflen)
    funcstr += vec_range(reg_save_area,fp_offset, 0,len(saved_vregs),2)

    # it looks like the offset here is depending on the valid number of arguments we got so far from the overflow area.
    # We can't possibly know
    funcstr += "\nfp vararg".ljust(pflen)
    funcstr += vec_range(overflow_arg_area,0, 0,max_overflow_vec.value,1,True)


#    for r in saved_iregs:
#        rval = vdb.register.read(r,frame)
#        ldval = rval.cast(gdb.lookup_type("long double"))
#        print(f"{r} : 0x{int(rval):02x} {rval} {ldval}")

    funcstr += "\nfp fix/var".ljust(pflen)


    for st in saved_fregs:
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


def wait(arg ):

    arg, argdict = vdb.util.parse_vars( arg )
    frame = gdb.selected_frame()
    va_list = get_va_list( arg, frame )

    if( va_list is None ):
        print("Cannot wait for change of va_list, couldn't find it")


    va_list_val = frame.read_var(va_list)
    va_list_val = gValue(va_list_val)


    first_gp_offset = int(va_list_val.gp_offset)
    first_fp_offset = int(va_list_val.fp_offset)
    first_reg_save_area = int(va_list_val.reg_save_area)
    first_overflow_arg_area = int(va_list_val.overflow_arg_area)

#    print("first_gp_offset = '%s'" % (first_gp_offset,) )
#    print("first_fp_offset = '%s'" % (first_fp_offset,) )
#    print("first_reg_save_area = 0x%08x" % (first_reg_save_area,) )
#    print("first_overflow_arg_area = 0x%08x" % (first_overflow_arg_area,) )

    for i in range(0,wait_max_ins.value):
        # maybe also stop on frame change?
        with vdb.util.silence() as _:
            res=gdb.execute("stepi",False,False)
#            res=gdb.execute("p $pc",False,True)

        gp_offset = va_list_val.gp_offset
        fp_offset = va_list_val.fp_offset
        reg_save_area = va_list_val.reg_save_area
        overflow_arg_area = va_list_val.overflow_arg_area

#        print("gp_offset = '%s'" % (gp_offset,) )
#        print("fp_offset = '%s'" % (fp_offset,) )
#        print("reg_save_area = 0x%08x" % (reg_save_area,) )
#        print("overflow_arg_area = 0x%08x" % (overflow_arg_area,) )

        # Don't use fp_offset ... it is so rarely needed, and often gcc generates code that clobbers fixed parameters
        # before it sets this up, so only output a message if it wasn't up to date
#        if( gp_offset != first_gp_offset and reg_save_area != first_reg_save_area and overflow_arg_area != first_overflow_arg_area ):
        # Turns out we can't really use the adresses too in case someone calls e.g. two printf() after another, they
        # will be set already. Fortunately for us it seems gcc always changes this on va_arg() invocation and always
        # sets it after the adresses, so until we find a better heuristics use this (hint: better heuristics may be
        # actual watch points, which might be generically a good tool, also with the track stuff, surely they can share
        # some code)
        if( gp_offset != first_gp_offset ):
#        if( gp_offset != first_gp_offset and fp_offset != first_fp_offset and reg_save_area != first_reg_save_area ):
            print("va_list completely updated, va extraction has a higher chance of working now")
            if( first_fp_offset == fp_offset ):
                print("fp_offset did not update. Please single step (at the risk of clobbering fixed parameters) or inspect disasembly yourself to figure out a proper value")
            break
    else:
        print(f"Executed vdb-va-wait-max-instructions ({wait_max_ins.value}) instructions but still the va_list members did not all change. We may need a higher value or did miss the right point, check manually")

class cmd_va (vdb.command.command):
    """Take va and transform it into more useful views"""

    def __init__ (self):
        super (cmd_va, self).__init__ ("va", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            if( len(argv) == 1 ):
                if( argv[0] == "wait" ):
                    print("Waiting...")
                    wait(argv[1:])
                    return
            va_print(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_va()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
