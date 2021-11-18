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

def guess_intrep( val, colorspec = None ):
    try:
        val = int(val)
        if( val < 32*1024 ): # definetly always an int
            return ( str(val), None )
        ca,mm,col,ascii = vdb.memory.mmap.color(val,colorspec = colorspec)
        minascii = 2
        if( mm is not None and not mm.is_unknown() ): # It is a pointer to known memory
#            print("ca = '%s'" % (ca,) )
#            print("mm = '%s'" % (mm,) )
#            print("col = '%s'" % (col,) )
#            print("ascii = '%s'" % (ascii,) )
#            plen = vdb.arch.pointer_size // 4
#            s = f"0x{val:0{plen}x}"
            pc = vdb.pointer.chain( val, vdb.arch.pointer_size, 1, True, minascii )
            pc = pc[0]
#            print("type(pc) = '%s'" % (type(pc),) )
#            print("pc = '%s'" % (pc,) )
            return (pc, "")
#            return ( s, col )
        if( val > 0x7f0000000000 ):
            pc = vdb.pointer.chain( val, vdb.arch.pointer_size, 1, True, minascii )
            pc = pc[0]
            return (pc, "")
        return ( str(val), None )
    except:
        return ( str(val), None )

def int_range( saved, frm, to, stopvalues = set() ):
    ret = ""

#    print("stopvalues = '%s'" % (stopvalues,) )
    for i in range(frm,to):
        rval = saved[i]
#        print("int(rval) = '%s'" % (int(rval),) )
        if( int(rval) in stopvalues ):
            break
        rval,rco = guess_intrep(rval)
        if( rco is None ):
            rco = var_int_color.value
        ret += ", "
        ret += vdb.color.color(rval,rco)
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
#        print("dregp[i] = '%s'" % (dregp[i],) )
        m,e = math.frexp(dregp[i])
#        print("e = '%s'" % (e,) )
        if( abs(e) > 256 ):
            if( skip ):
                continue
            break
        ret += ", "
        ret += vdb.color.color( str(dregp[i]), var_float_color.value )
    return ret

def intformat( val, fmt ):
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

def va_print( arg ):

    arg, argdict = vdb.util.parse_vars( arg )
    va_list = arg[0]

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
#    print("retaddrs = '%s'" % (retaddrs,) )

    va_list_val = frame.read_var(va_list)
#    g = gValue(va_list_val)

#    print("g = '%s'" % (g,) )
#    print("g.gp_offset = '%s'" % (g.gp_offset,) )
    va_list_val = gValue(va_list_val)
#    print("va_list_val.address = '%s'" % (va_list_val.address,) )
#    print("va_list_val.gp_offset = '%s'" % (va_list_val.gp_offset,) )
#    print("va_list_val.fp_offset = '%s'" % (va_list_val.fp_offset,) )
#    print("va_list_val.overflow_arg_area = '%s'" % (va_list_val.overflow_arg_area,) )
#    print("va_list_val.reg_save_area = '%s'" % (va_list_val.reg_save_area,) )

    print("Possible function call(s):")

#    print("g.gp_offset = '%s'" % (g.gp_offset,) )
#    print("type(g.gp_offset) = '%s'" % (type(g.gp_offset),) )

    gp_offset = argdict.getas(int,"gp_offset",va_list_val.gp_offset)
    fp_offset = argdict.getas(int,"fp_offset",va_list_val.fp_offset)
#    reg_save_area = argdict.getas(vdb.util.hexint,"reg_save_area", va_list_val.reg_save_area)
    reg_save_area = argdict.getas(gValue,"reg_save_area", va_list_val.reg_save_area)
    overflow_arg_area = argdict.getas(gValue,"overflow_arg_area", va_list_val.overflow_arg_area)

    print(f"Using gp_offset={gp_offset}, fp_offset={fp_offset}")

    format = argdict.get( "format", None)


#    print("reg_save_area = '%s'" % (reg_save_area,) )

#    print("reg_save_area = '%s'" % (reg_save_area,) )
#    print("type(reg_save_area) = '%s'" % (type(reg_save_area),) )

#    print("gp_offset = '%s'" % (gp_offset,) )
#    print("type(gp_offset) = '%s'" % (type(gp_offset),) )


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

        for f in format:
            if( cnt > 0 ):
                funcstr += ", "
            if( f in "SPILUJ" ):
                regname = saved_iregs[cnt]
                rval = vdb.register.read(regname,frame)
                if( f == "S" ):
                    rval = rval.cast(ctype_p)
                    funcstr += vdb.color.color( rval, fixed_int_color.value )
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
                    rval = rval.cast(ctype_p)
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
    funcstr += int_range( reg_save, num_fixed, 6 )

    overflow = overflow_arg_area.cast(ptrtype)

    funcstr += "\ngp vararg".ljust(pflen)
    funcstr += int_range( overflow, 2, 42, retaddrs )



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
    funcstr += vec_range(reg_save_area,fp_offset, 0,32,2)

    # it looks like the offset here is depending on the valid number of arguments we got so far from the overflow area.
    # We can't possibly know
    funcstr += "\nfp vararg".ljust(pflen)
    funcstr += vec_range(overflow_arg_area,0, 0,30,1,True)


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
            if( len(argv) > 0 ):
                va_print(argv)
            else:
                raise gdb.error("Need parameter")

        except:
            traceback.print_exc()
            raise
            pass

cmd_va()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python