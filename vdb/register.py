#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.pointer
import vdb.memory
import vdb.command
import vdb.arch

import gdb

import re
import traceback
from collections.abc import Iterable
import sys

color_names = vdb.config.parameter("vdb-register-colors-names", "#4c0", gdb_type = vdb.config.PARAM_COLOUR)
reg_default = vdb.config.parameter("vdb-register-default","/e")
flag_colour = vdb.config.parameter("vdb-register-colors-flags", "#adad00", gdb_type = vdb.config.PARAM_COLOUR)
int_int = vdb.config.parameter("vdb-register-int-as-int",True)
short_columns = vdb.config.parameter("vdb-register-short-columns",6)


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

flag_info = {
            "eflags" : ( 21, flag_descriptions, None ),
            "mxcsr"  : ( 15, mxcsr_descriptions, None ),
            "bndcfgu" : ( 12, bndcfgu_descriptions, ( "raw", "config" ) ),
            "bndstatus" : ( 4, bndstatus_descriptions, ( "raw", "status" ) )
            }
possible_flags = [
        "eflags", "flags", "mxcsr", "bndcfgu", "bndstatus"
        ]

abbrflags = [ 
        "mxcsr"
        ]

possible_registers = [
		( "rax", "eax", "ax"),
        ( "rbx", "ebx", "bx"),
        ( "rcx", "ecx", "cx"),
        ( "rdx", "edx", "dx"),
		( "rsi", "esi", "si"),
        ( "rdi", "edi", "di"),
		( "rbp", "ebp", "bp"),
        ( "rsp", "esp", "sp"),
		( "rip", "eip", "ip", "pc"),
        "r0","r1","r2","r3","r4","r5","r6","r7",
		"r8" , "r9" , "r10", "r11",
		"r12", "r13", "r14", "r15",
		"r16", "r17", "r18", "r19",
        "r20", "r21", "r22", "r23",
        "r24", "r25", "r26", "r27",
        "r28", "r29", "r30", "r31",
        "lr","cpsr","fpscr",
        "sp","pc", "ctr"
		]

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

gdb_uint64_t = gdb.lookup_type("unsigned long long")
gdb_uint8_t = gdb.lookup_type("unsigned char")


def read( reg, frame = None ):
    if( frame is None ):
        frame = gdb.selected_frame()
    try:
        return frame.read_register(reg)
    except ValueError:
        return None

# for x86 eax/rax r10/r10d etc stuff where we want to just handle "whole" registers
def altname( regname ):
    if( regname[0] == "e" ):
        return "r" + regname[1:]
    if( regname[0] == "r" and regname[-1] == "d" ):
        return regname[:-1]
    return None

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
        self.others = {}
        self.type_indices = {}
        self.next_type_index = 1

        try:
            frame=gdb.selected_frame()
        except:
            return
        thread=gdb.selected_thread()
        self.thread = thread.num
        self.archsize = vdb.arch.pointer_size

        self.collect_registers()

    def get( self, name ):
        return self.all.get(name,None)

    def in_group( self, name, group ):
        groups = self.groups.get(name,None)
        if( groups is not None ):
            return group in groups
        return False

    def collect_registers( self ):
        frame=gdb.selected_frame()
        for grp in frame.architecture().register_groups():
#            print("grp = '%s'" % (grp,) )
            for reg in frame.architecture().registers(grp.name):
                self.groups.setdefault(reg.name,set()).add( grp.name )
#                print(f"{grp} : {reg}")
#        print(f"registers we don't know where to put them yet (archsize {self.archsize}):")
        for reg in frame.architecture().registers():
            self.all[reg.name] = reg
            v = frame.read_register(reg)
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
        print("self.archsize = '%s'" % self.archsize )
#        print("self.eflags = '%s'" % self.eflags )
#        print("self.mxcsr = '%s'" % self.mxcsr )

    def read( self, reg, frame = None ):
        return read(reg,frame)

    def parse_register( self,frame,reg,regs):
        if( len(reg) == 0 ):
            regs[reg] = (None,None)
            return
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
        if( vdb.arch.gdb_uintptr_t is not None ):
            val=int( val.cast(vdb.arch.gdb_uintptr_t) )
        else:
            val=int( val.cast(gdb_uint64_t) )

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
                retv += vdb.pointer.chain(val,self.archsize)[0]
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
                    fval = int(fval.cast(gdb_uint8_t))
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
                xval.append(int(val[tname][i].cast(gdb_uint64_t)))
            except:
                try:
                    xval.append(int(val[tname].cast(gdb_uint64_t)))
                except:
                    xval.append("INVALID")
                    print("tname = '%s'" % (tname,) )
                    print("i = '%s'" % (i,) )
                    traceback.print_exc()

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



    def ex_floats( self ):
        print("NOT YET IMPLEMENTED")
        return self.floats()

    def arch_prctl( self, code ):
        ret = vdb.memory.read("$sp",8)

        if( ret is not None ):
            try:
                gdb.execute( f"call (int)arch_prctl({code},$sp)", False, True )
                ap_ret = vdb.memory.read("$sp",8)
                return ap_ret
            except:
                pass
            finally:
                vdb.memory.write("$sp",ret)
#            gdb.execute( "set *(void**)($rsp) = $__vdb_save_value" )
#            gdb.execute( "p *(void**)($rsp)" )

    def ex_prefixes( self ):
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
            traceback.print_exc()
            pass
        return self.prefixes()

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

    def format_ints( self, regs, extended = False, wrapat = None ):
        if( wrapat is None ):
            wrapat = short_columns.value
        ret = ""
        cnt=0

        rtbl = []
        rtline = []
        for regdesc,valt in regs.items():
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

    def ints( self, extended = False, wrapat = None ):
        return self.format_ints( self.regs, extended, wrapat )

    def other( self, extended = False, wrapat = None ):
        return self.format_ints( self.others, extended, wrapat )

    def prefixes( self ):
        ret = ""
        cnt=0
        for regdesc,valt in self.segs.items():
            val,t =valt
            cnt += 1
            ret += self.format_prefix(regdesc,val,t)
            if( cnt % 6 == 0 ):
                ret += "\n"
        return ret
# mxcsr          0x1fa0              [ PE IM DM ZM OM UM PM ]

    def floats( self ):
        ret = ""
        for name in possible_fpu:
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

    def vectors( self, extended = False ):
        ret=""
        cnt=0
        xvec = []

        rtbl = []
        for regdesc,valt in self.vecs.items():
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

        if( extended ):
            ret += vdb.util.format_table(rtbl,padbefore=" ", padafter="")
        return ret

    def format_flags_mini( self, name, val ):
        count,descriptions,rawname = flag_info.get(name)

        if( rawname is None ):
            return str(val)

        ret = " "
        for f in val[rawname[1]].type.fields():
            sv = val[rawname[1]][f]
            ret += f"{f.name}[{sv}] "


        return "[" + ret + "]"

    def format_flags_short( self, name, abbrval ):
        count,descriptions,rawname = flag_info.get(name)
        regdesc = self.get(name)
        flags,valtype = self.rflags.get(regdesc)

        if( rawname is not None ):
            iflags = int(flags[rawname[0]])
        else:
            iflags = int(flags)
        ret = ""

        bit = 0

        while bit <= count:
            mask = 1 << bit
            ex = iflags >> bit
            ex &= 1

            short = ""

            tbit = f"{bit:02x}"
            desc = descriptions.get(bit,None)
            if( desc is not None ):
                dshort = desc[1]
#                text = desc[2]
                mp = desc[3]
                sz = desc[0]
                if( sz > 1 ):
                    tbit = f"{bit:02x}-{bit+sz-1:02x}"
                    bit += (sz-1)
                    omask = mask
                    for mb in range(0,sz):
                        mask |= omask
                        omask = omask << 1
                    ex = (iflags >> bit) & ((1 << sz)-1)
                short = f"{dshort}[{ex}]"
                if( abbrval ):
                    if( mp is not None ):
                        ms,ml = mp.get(ex,(None,None))
                        if( ms is not None ):
                            short = f"{dshort}[{ms},{ex}]"

                if( ex != 0 ):
                    short = vdb.color.color(short,flag_colour.value)

            mask = f"0x{mask:04x}"
            # bit order
            if( len(short) > 0 ):
                ret = str(short) + " " + ret
            bit += 1

        return ret

    def format_flags( self, name ):
        count,descriptions,rawname = flag_info.get(name)
        regdesc = self.get(name)
        flags,valtype = self.rflags.get(regdesc)

        if( rawname is not None ):
            iflags = int(flags[rawname[0]])
        else:
            iflags = int(flags)

        ftbl = []
        ftbl.append( ["Bit","Mask","Abrv","Description","Val","Meaning"] )

        bit = 0
        con_start = 0
        con_end = 0
        con_mask = 0
#        for bit in range(0,count):
        while bit <= count:
            mask = 1 << bit
            ex = iflags >> bit
            ex &= 1

            short = ""
            text = "Reserved"
            meaning = None

            tbit = f"{bit:02x}"
            desc = descriptions.get(bit,None)
            if( desc is not None ):
                if( con_mask != 0 ):
                    if( con_start == con_end ):
                        con_tbit = f"{con_start:02x}"
                    else:
                        con_tbit = f"{con_start:02x}-{con_end:02x}"
                    scon_mask = f"0x{con_mask:04x}"
                    ftbl.append( [ con_tbit, scon_mask, short, text, "", meaning ] )
                    con_mask = 0

                short = desc[1]
                text = desc[2]
                mp = desc[3]
                sz = desc[0]
                if( sz > 1 ):
                    tbit = f"{bit:02x}-{bit+sz-1:02x}"
                    bit += (sz-1)
                    omask = mask
                    for mb in range(0,sz):
                        mask |= omask
                        omask = omask << 1
                    ex = (iflags >> bit) & ((1 << sz)-1)
                if( ex != 0 ):
                    short = ( vdb.color.color(short,flag_colour.value), len(short))
                if( mp is not None ):
                    ms,ml= mp.get(ex,("","??"))
                    meaning = ms+ml

                mask = f"0x{mask:04x}"
                ftbl.append( [ tbit, mask, short, text, ex, meaning ] )
            else:
                if( con_mask == 0 ):
                    con_mask = mask
                    con_start = bit
                    con_end = bit
                else:
                    con_end += 1
                    con_mask |= mask

            bit += 1

        ret = vdb.util.format_table( ftbl )
        return ret

    def flags( self, extended = False ):
        ret=""

#        if( self.eflags is not None ):
#            if( extended ):
#                ret += self.format_flags( "eflags" )
#            else:
#                ret += " "
#                ret += self.format_flags_short("eflags",False)
#        else:
#            ret += "NO SUPPORTED FLAGS FOUND\n"

#        ret += "\n"
#        ret += self._mxcsr( extended )

        for fr,v in self.rflags.items():
            ret += "\n"
            fv,ft = v
            abbr = False
            if( fr.name in abbrflags ):
                abbr = True

            _,_,rawfield = flag_info.get(fr.name,(None,None,None))
            
            if( rawfield is not None ):
                ival = int(fv[rawfield[0]])
            else:
                ival = int(fv)

            fvm = self.format_flags_mini( fr.name, fv )
            ret += vdb.color.color(f" {fr.name} ",color_names.value)+f"0x{ival:016x} {fvm}"
            ret += "\n"

            if( extended ):
                ret += self.format_flags(fr.name)
            else:
                ret += " "
                ret += self.format_flags_short(fr.name,abbr)
            ret += "\n"

        return ret

    def print( self, showspec ):
        for s in showspec:
            if( s == "i" ):
                print(self.ints(extended=False))
            elif( s == "I" ):
                print(self.ints(extended=True,wrapat=1))
            elif( s == "v" ):
                print(self.vectors(extended=False))
            elif( s == "V" ):
                print(self.vectors(extended=True))
            elif( s == "f" ):
                print(self.floats())
            elif( s == "F" ):
                print(self.ex_floats())
            elif( s == "x" ):
                print(self.flags(extended=False))
            elif( s == "X" ):
                print(self.flags(extended=True))
            elif( s == "o" ):
                print(self.other(extended=False))
            elif( s == "O" ):
                print(self.other(extended=True,wrapat=1))
            elif( s == "p" ):
                print(self.prefixes())
            elif( s == "P" ):
                print(self.ex_prefixes())
            elif( s == "." ):
                pass
            elif( s == "?" ):
                print("Recognized showspec characters: iIvVfFxXpP.?")
            else:
                print("Invalid showspec '%s'" % s )

registers = None

@vdb.event.new_objfile()
def reset( self ):
#    print("Resetting global register object")
    global registers
    registers = None

class cmd_registers(vdb.command.command):
    """Show the registers nicely (default is expanded)
short    - Show just the important registers and flags with their hex values
expanded - Show the important registers in a recursively expanded way, depending on their usual type maybe as integers
all      - Show all registers in their short hex form
full     - Show all registers in the expanded form if possible, for fpu and vector registers this may mean all possible
representations
"""

    def __init__ (self):
        super (cmd_registers, self).__init__ ("registers", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def usage( self ):
        print(self.__doc__)

    def update( self ):
#        print("Updating registers...",file=sys.stderr)
        with open("register.log","a") as f:
            traceback.print_stack(file=f)
        try:
            nrr = Registers()
            global registers
            registers = nrr
        except Exception as e:
            print("When trying to make sense out of registers, we encountered an exception: %s" % e )
            traceback.print_exc()

    def maybe_update( self ):
        global registers
#        print("registers = '%s'" % registers )
#        if( registers is not None ):
#            print("registers.thread = '%s'" % registers.thread )
#        if( registers is None or registers.thread == 0 ):
#            print("Need to call update")
        self.update()

    def do_invoke (self, argv ):
#        print("do_invoke()")
        global registers
        try:
            self.maybe_update()

            if( registers is None or registers.thread == 0 ):
                print("No running thread to read registers from")
                return

            vdb.memory.print_legend("Ama")

            if( len(argv) == 0 ):
                argv.append(reg_default.value)
            if( len(argv) == 1 ):
                if( argv[0].startswith("/") ):
                    if( argv[0] == "/s" ):
                        registers.print("ipx")
                    elif( argv[0] == "/e" ):
                        registers.print("Ipx")
                    elif( argv[0] == "/a" ):
                        registers.print("ixfpmv")
                    elif( argv[0] == "/f" ):
                        registers.print("IXFPMV")
                    elif( argv[0] == "/_d" ):
                        registers._dump()
                    else:
                        registers.print(argv[0][1:])
                else:
                    self.usage()
            else:
                print("Invalid argument(s) to registers: '%s'" % arg )
                self.usage()
        except Exception as e:
            traceback.print_exc()

        # Identify the cases where we can re-use the information gathered. Maybe refactor Registers() to always read
        # values on demand?

        registers = None

cmd_registers()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
