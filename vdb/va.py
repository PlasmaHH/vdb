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

modfrom = "diocC uxX sS eEfFaA pn"
modto   = "iiiii uuu ss dddddd pp"
longto  = "lllll jjj ss dddddd pp"

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
                to = modmap.get(f,None)
                if( to is None ):
                    print("Unsupported printf format modifier")
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


def va_print( arg ):

    arg, argdict = vdb.util.parse_vars( arg )
    frame = gdb.selected_frame()

    allprovided = False

    if( "gp_offset" in argdict and "fp_offset" in argdict and "reg_save_area" in argdict and "overflow_arg_area" in argdict ):
        allprovided = True

    if( len(arg) == 0 ):
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
            if( not allprovided ):
                print("Could not automatically detect the va_list variable, please provide it")
                return
            else:
                va_list is None
    else:
        va_list = arg[0]


    retaddrs = set()
    nf = frame
    olvl = -1
    while( nf is not None ):
        retaddrs.add( int(nf.pc()) )
        if( olvl == nf.level() ):
            break
        olvl = nf.level()
        nf = nf.older()

    if( va_list is not None ):
        va_list_val = frame.read_var(va_list)
        va_list_val = gValue(va_list_val)

        gp_offset = va_list_val.gp_offset
        fp_offset = va_list_val.fp_offset
        reg_save_area = va_list_val.reg_save_area
        overflow_arg_area = va_list_val.overflow_arg_area

    else:
        print("Whoopsie, va_list is None, that should not happen at this point")
        return

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
        print(f"reg_save_area is pointing to unknown memroy, results are likely wrong.")

    mm = vdb.memory.mmap.find(int(overflow_arg_area))
    if( mm is None or mm.is_unknown() ):
        print(f"overflow_arg_area is pointing to unknown memroy, results are likely wrong.")

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
        funcstr += "( "
        cnt = 0
        ctype_p = gdb.lookup_type("char").pointer()
        l_gp_offset = int(gp_offset)
        l_fp_offset = int(fp_offset)

        ptrtype = vdb.arch.gdb_uintptr_t.pointer()
        ireg_save = reg_save_area.cast(ptrtype)

        dtype = gdb.lookup_type("double")
        dtype_p = dtype.pointer()
        dreg_save = reg_save_area.cast(dtype_p)

        last_string = None

        maxi = len(format)-1

        i = -1
        while i < maxi:
            i += 1
            f = format[i]
                
            if( f == "*" ):
#                print("last_string = '%s'" % (last_string,) )
                format = format[:-1] + convert_format(last_string)
                maxi = len(format)-1
                i -= 1
#                print("format = '%s'" % (format,) )
                continue

            if( cnt > 0 ):
                funcstr += ", "

            if( f in "SPILUJ" ):
                regname = saved_iregs[cnt]
                rval = vdb.register.read(regname,frame)
                if( f == "S" ):
                    rval = rval.cast(ctype_p)
                    funcstr += vdb.color.color( rval, fixed_int_color.value )
                    last_string = str(rval)
                else:
                    funcstr += vdb.color.color( rval, fixed_int_color.value )
            elif( f in "spiluj" ):
                if( l_gp_offset < 48 ):
                    lidx = l_gp_offset // 8
                    rval = ireg_save[lidx]
                    l_gp_offset += 8
                else:
                    rval="??"
                if( f == "s" ):
                    try:
                        rval = rval.cast(ctype_p)
                    except AttributeError:
                        pass
                    funcstr += vdb.color.color( rval, var_int_color.value )
                else:
                    rval = intformat(rval,f)
                    funcstr += vdb.color.color( rval, var_int_color.value )
            elif( f in "FD" ):
                pass
            elif( f in "fd" ):
                if( l_fp_offset < 176 ): # confirm value
                    lidx = l_fp_offset // 8
                    rval = dreg_save[lidx]
                    l_fp_offset += 16
                    funcstr += vdb.color.color( rval, var_float_color.value )
                else:
                    rval = "??"

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



class cmd_va (vdb.command.command):
    """Take va and transform it into more useful views"""

    def __init__ (self):
        super (cmd_va, self).__init__ ("va", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            va_print(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_va()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
