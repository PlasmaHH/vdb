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

color_names = vdb.config.parameter("vdb-register-colors-names", "#4c0", gdb_type = vdb.config.PARAM_COLOUR)
reg_default = vdb.config.parameter("vdb-register-default","/e")
flag_colour = vdb.config.parameter("vdb-register-colors-flags", "#adad00", gdb_type = vdb.config.PARAM_COLOUR)
int_int = vdb.config.parameter("vdb-register-int-as-int",True)


flag_bits = [
( "ID", 0x15 ),
( "VIP", 0x14 ),
( "VIF", 0x13 ),
( "AC", 0x12 ),
( "VM", 0x11 ),
( "RF", 0x10 ),
( "NT", 0xe ),
( "IOPL", 0xc ),
( "OF", 0xb ),
( "DF", 0xa ),
( "IF", 0x9 ),
( "TF", 0x8 ),
( "SF", 0x7 ),
( "ZF", 0x6 ),
( "AF", 0x4 ),
( "PF", 0x2 ),
( "CF", 0x0 ),
		]

flag_descriptions = {
        0 : ( 1, "CF",  "Carry",             { 1 : "CY(Carry)",           0 : "NC(No Carry)" } ),
        2 : ( 1, "PF",  "Parity",            { 1 : "PE(Parity Even)",     0 : "PO(Parity Odd)" } ),
        4 : ( 1, "AF",  "Adjust",            { 1 : "AC(Auxiliary Carry)", 0 : "NA(No Auxiliary Carry" } ),
        6 : ( 1, "ZF",  "Zero",              { 1 : "ZR(Zero)",            0 : "NZ(Not Zero)" } ),
        7 : ( 1, "SF",  "Sign",              { 1 : "NG(Negative)",        0 : "PL(Positive)" } ),
        8 : ( 1, "TF",  "Trap",              None ),
        9 : ( 1, "IF",  "Interrupt enable",  { 1 : "EI(Enabled)",         0 : "DI(Disabled)" } ),
        10: ( 1, "DF",  "Direction",         { 1 : "DN(Down)",            0 : "UP(Up)" } ),
        11: ( 1, "OF",  "Overflow",          { 1 : "OV(Overflow)",        0 : "NV(Not Overflow)" } ),
        12: ( 2, "IOPL","I/O Priv level",    None ),
        14: ( 1, "NT",  "Nested Task",       None ),
        16: ( 1, "RF",  "Resume",            None ),
        17: ( 1, "VM",  "Virtual 8086 mode", None ),
        18: ( 1, "AC",  "Alignment check",   None ),
        19: ( 1, "VIF", "Virtual interrupt", None ),
        20: ( 1, "VIP", "Virt intr pending", None ),
        21: ( 1, "ID",  "CPUID available",   None ),
        }

mxcsr_bits = [
( "FZ", 0xf ),
( "R+", 0xe ),
( "R-", 0xd ),

( "RZ", 13 ),
( "RN", 13 ),

( "PM", 0xc ),
( "UM", 0xb ),
( "OM", 0xa ),
( "ZM", 0x9 ),
( "DM", 0x8 ),
( "IM", 0x7 ),
( "DAZ", 0x6 ),
( "PE", 0x5 ),
( "UE", 0x4 ),
( "OE", 0x3 ),
( "ZE", 0x2 ),
( "DE", 0x1 ),
( "IE", 0x0 ),
		]

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
        13 : ( 2, "R[ZN+-]", "Rounding", { 0: "RN(Round To Nearest)", 3 : "RZ(Round to Zero)", 1 : "R-(Round Negative)", 2: "R+(Round Positive)" }),
        15 : ( 1, "FZ", "Flush to Zero", None ),
        }


possible_registers = [
		( "rax", "eax", "ax"),
        ( "rbx", "ebx", "bx"),
        ( "rcx", "ecx", "cx"),
        ( "rdx", "edx", "dx"),
		( "rsi", "esi", "si"),
        ( "rdi", "edi", "di"),
		( "rbp", "ebp", "bp"),
        ( "rsp", "esp", "sp"),
		( "rip", "eip", "ip"),
		"r8" , "r9" , "r10", "r11",
		"r12", "r13", "r14", "r15",
		]

possible_prefixes = [
		"cs", "ds", "es", "fs", "gs", "ss"
		]

possible_fpu = [
	"st0", "st1", "st2", "st3", "st4", "st5", "st6", "st7",
	"fctrl", "fstat", "ftag", "fiseg", "fioff", "foseg", "fooff", "fop",
		]

#possible_vectors = [
#"xmm0","xmm1","xmm2","xmm3","xmm4","xmm5","xmm6","xmm7","xmm8","xmm9","xmm10","xmm11","xmm12","xmm13","xmm14","xmm15",
#"ymm0","ymm1","ymm2","ymm3","ymm4","ymm5","ymm6","ymm7","ymm8","ymm9","ymm10","ymm11","ymm12","ymm13","ymm14","ymm15"
#		]

gdb_uint64_t = gdb.lookup_type("unsigned long long")
gdb_uint8_t = gdb.lookup_type("unsigned char")

class Registers():

    def __init__(self):
        self.regs = {}
        self.segs = {}
        self.vecs = {}
        self.fpus = {}
        self.thread = 0
        self.type_indices = {}
        self.next_type_index = 1
        try:
            frame=gdb.selected_frame()
        except:
            return
#        self.frame = 22
        thread=gdb.selected_thread()
        self.thread = thread.num
        self.archsize = vdb.arch.pointer_size

        for reg in possible_registers:
            if( isinstance(reg,Iterable) and not isinstance(reg,str) ):
                for oreg in reg:
                    if( self.parse_register(frame,oreg,self.regs) is not None ):
                        break
            else:
                self.parse_register(frame,reg,self.regs)

        for reg in possible_prefixes:
            self.parse_register(frame,reg,self.segs)

        for i in range(0,32):
            v = None
            for rt in [ "z", "y", "x", "" ]:
                reg=f"{rt}mm{i}"
                try:
                    #					print("type(v)")
#					print("reg = '%s'" % reg )
                    v = frame.read_register(reg)
#					print("v = '%s'" % v )
                    break
                except:
                    continue
            if( v is not None ):
                t = v.type
                self.vecs[reg] = ( v, t )
        self.eflags = frame.read_register("eflags")

        for reg in possible_fpu:
            self.parse_register(frame,reg,self.fpus)

        self.mxcsr = self.read(frame,"mxcsr")

    def read( self, frame, reg ):
        try:
            return frame.read_register(reg)
        except ValueError:
            return None

    def parse_register( self,frame,reg,regs):
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

    def format_register( self,name, val,t, chained = False, int_as_int = False ):
        if( vdb.arch.gdb_uintptr_t is not None ):
            val=int( val.cast(vdb.arch.gdb_uintptr_t) )
        else:
            val=int( val.cast(gdb_uint64_t) )

        try:
            ret = vdb.color.color(f" {name:<6}",color_names.value)

            if( int_as_int ):
                if( self.archsize == 32 ):
                    ret += f" {int(val):>9} "
                else:
                    ret += f" {int(val):>19} "

            if( chained ):
                ret += vdb.pointer.chain(val,self.archsize)[0]
            else:
                ret += vdb.pointer.color(val,self.archsize)[0]
        except:
            ret = "ERR " + name + " : " + str(val)
            raise
        return ret

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


    def format_prefix( self,name, val, t ):
        val=int(val)
        try:
            ret = vdb.color.color(f" {name:<3}",color_names.value)+f"0x{val:08x}"
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

    def format_vector_extended( self, name, val, t ):
        empty = [ None ] * ( 1 + max( len(t.fields()), self.next_type_index ) )
        tbl = []
        valmatrix = { }

        maxval = 0
        import copy
        header = copy.deepcopy(empty)
        header[0] = ( vdb.color.color(f"{name:<6}",color_names.value), 6 )
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
        name,amnt = xvec[0]
        amnt = len(amnt)
        ret = ""
#		print("xvec = '%s'" % xvec )
        for i in range(0,amnt):
            for name,vals in xvec:
                if( i == 0 ):
                    ret += vdb.color.color(f" {name:<6}",color_names.value)
                else:
                    ret += f"       "
                try:
                    val=int(vals[i])
                    ret += f"0x{val:032x}"
                except:
                    val=vals[i]
                    ret += f"{val:32s}"
            ret += "\n"
        return ret

    def extract_vector( self,name, val, t ):
        ret = []
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
                xval.append("INVALID")

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

    def arch_prctl( self, code ):
        ret = vdb.memory.read("$rsp",8)

        if( ret is not None ):
            try:
                gdb.execute( f"call (int)arch_prctl({code},$rsp)", False, True )
                ap_ret = vdb.memory.read("$rsp",8)
                return ap_ret
            except:
                pass
            finally:
                vdb.memory.write("$rsp",ret)
#            gdb.execute( "set *(void**)($rsp) = $__vdb_save_value" )
#            gdb.execute( "p *(void**)($rsp)" )

    def ex_prefixes( self ):
        try:
            fs_base = self.arch_prctl(0x1003)
            if( fs_base is not None ):
                fs_base = int.from_bytes(fs_base,"little")
                self.segs["fs"] = ( fs_base, None )
            gs_base = self.arch_prctl(0x1004)
            if( gs_base is not None ):
                gs_base = int.from_bytes(gs_base,"little")
                self.segs["gs"] = ( gs_base, None )
        except:
            traceback.print_exc()
            pass
        return self.prefixes()


    def ex_vectors( self ):
        return self.vectors( extended = True )

    def ex_ints( self ):
        return self.ints(True,1)

    def ints( self, extended = False, wrapat = 6 ):
        ret = ""
        cnt=0
        for name,valt in self.regs.items():
            val,t =valt
            cnt += 1
            ret += self.format_register(name,val,t,extended, int_int.value )
            if( cnt % wrapat == 0 ):
                ret += "\n"

        if( not ret.endswith("\n") ):
            ret += "\n"
        return ret

    def prefixes( self ):
        ret = ""
        cnt=0
        for name,valt in self.segs.items():
            val,t =valt
            cnt += 1
            ret += self.format_prefix(name,val,t)
            if( cnt % 6 == 0 ):
                ret += "\n"
        return ret
# mxcsr          0x1fa0              [ PE IM DM ZM OM UM PM ]

    def floats( self ):
        ret = ""
        cnt=0
        for name,valt in self.fpus.items():
            val,t =valt
            cnt += 1
            ret += self.format_float(name,val,t)
            if( cnt % 6 == 0 ):
                ret += "\n"
            if( cnt % 8 == 0 ):
                ret += "\n"

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
                raise Exception("Unsupported code %s for vector member" % (vdb.util.gdb_type_code(v.type.code) ) )
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

    def ex_mxcsr( self ):
        return self._mxcsr(True)
    
    def _mxcsr( self, extended = False ):
        ret=""
        if( self.mxcsr is not None ):
            val = int(self.mxcsr)

            if( extended ):
                ret += vdb.color.color(f" mxcsr ",color_names.value)+f"0x{val:08x}"
                ret += "\n"
                ret += "\n"
                ret += self.format_flags( "mxcsr", int(self.mxcsr), 15, mxcsr_descriptions )
            else:

                ret += " "
                short = " [ "
                for flag,bit in mxcsr_bits:
                    ex = val >> bit
                    if( flag == "RZ" ):
                        ex &= 3
                        if( ex == 3 ):
                            ex = "X"
                        elif( ex == 0 ):
                            ex = "_"
                        else:
                            ex = "?"
                    elif( flag == "RN" ):
                        ex &= 3
                        if( ex == 3 ):
                            ex = "_"
                        elif( ex == 0 ):
                            ex = "X"
                        else:
                            ex = "?"
                    else:
                        ex &= 1
                    col = ( ex != 0 )
                    if( col ):
                        ret += vdb.color.color(f"{flag}[{ex}] ","#adad00")
                        short += flag + " "
                    else:
                        ret += f"{flag}[{ex}] "
                ret += "\n"
                ret += short  + "]\n"
                ret += "\n"
                ret += vdb.color.color(f" mxcsr ",color_names.value)+f"0x{val:016x}"
                ret += "\n"
        return ret




    def vectors( self, extended = False ):
        ret=""
        cnt=0
        xvec = []

        rtbl = []
        for name,valt in self.vecs.items():
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
                rtbl += ( self.format_vector_extended( name, val, t ) )
            else:
                xvec.append( (name, self.extract_vector(name,val,t)) )
                if( cnt % 4 == 0 ):
                    ret += self.format_vector(xvec)
                    xvec = []

        if( extended ):
            ret += vdb.util.format_table(rtbl,padbefore=" ", padafter="")
        return ret

    def format_flags( self, name, flags, count, descriptions ):
        ret = ""
        ret += vdb.color.color(f" {name} ",color_names.value)+f"0x{flags:016x}"
        ret += "\n"
        ftbl = []
        ftbl.append( ["Bit","Mask","Abrv","Description","Val","Meaning"] )

        bit = 0
#        for bit in range(0,count):
        while bit <= count:
            mask = 1 << bit
            ex = flags >> bit
            ex &= 1

            short = ""
            text = "Reserved"
            meaning = None

            tbit = f"{bit:02x}"
            desc = descriptions.get(bit,None)
            if( desc is not None ):
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
                    ex = (flags >> bit) & ((1 << sz)-1)
                if( ex != 0 ):
                    short = ( vdb.color.color(short,flag_colour.value), len(short))
                if( mp is not None ):
                    meaning = mp.get(ex,"??")

            mask = f"0x{mask:04x}"


            ftbl.append( [ tbit, mask, short, text, ex, meaning ] )
            bit += 1

        ret = vdb.util.format_table( ftbl )
        return ret

    def ex_flags( self ):
        return self.format_flags( "eflags", int(self.eflags), 21, flag_descriptions )

    def flags( self ):
        ret=""

        eflags = int(self.eflags)
        ret += vdb.color.color(f" eflags ",color_names.value)+f"0x{eflags:016x}"
        ret += "\n"

        ret += " "
        for flag,bit in flag_bits:
            ex = eflags >> bit
            if( flag == "IOPL" ):
                ex &= 3
            else:
                ex &= 1
            if( ex == 0 ):
                ret += f"{flag}[{ex}] "
            else:
                ret += vdb.color.color(f"{flag}[{ex}] ",flag_colour.value)

#
#		ret += "OF[{}] ""DF[{}] ""IF[{}] ""TF[{}]".format( ((eflags >> 0xB) & 1 ), ((eflags >> 0xA) & 1 ),  ((eflags >> 9) & 1), ((eflags >> 8) & 1 ))
#		ret += "SF[{}] ""ZF[{}] ""AF[{}] ""PF[{}] ""CF[{}] ".format( ((eflags >> 7) & 1 ), ((eflags >> 6) & 1 ), ((eflags >> 4) & 1 ), ((eflags >> 2) & 1 ), (eflags & 1))
#		ret += "ID[{}] ""VIP[{}] ""VIF[{}] ""AC[{}]".format( ((eflags >> 0x15) & 1 ), ((eflags >> 0x14) & 1 ),  ((eflags >> 0x13) & 1 ), ((eflags >> 0x12) & 1 ))
#		ret += "VM[{}] ""RF[{}] ""NT[{}] ""IOPL[{}]".format( ((eflags >> 0x11) & 1 ), ((eflags >> 0x10) & 1 ), ((eflags >> 0xE) & 1 ), ((eflags >> 0xC) & 3 ))


        ret += "\n"
        ret += " "
        ret += str(self.eflags) + "\n"



        return ret
    
    def print( self, showspec ):
        for s in showspec:
            if( s == "i" ):
                print(self.ints())
            elif( s == "I" ):
                print(self.ex_ints())
            elif( s == "v" ):
                print(self.vectors())
            elif( s == "V" ):
                print(self.ex_vectors())
            elif( s == "f" ):
                print(self.floats())
            elif( s == "F" ):
                print(self.ex_floats())
            elif( s == "x" ):
                print(self.flags())
            elif( s == "X" ):
                print(self.ex_flags())
            elif( s == "p" ):
                print(self.prefixes())
            elif( s == "P" ):
                print(self.ex_prefixes())
            elif( s == "m" ):
                print(self._mxcsr())
            elif( s == "M" ):
                print(self.ex_mxcsr())
            elif( s == "." ):
                pass
            elif( s == "?" ):
                print("Recognized showspec characters: iIvVfFxXpP.?")
            else:
                print("Invalid showspec '%s'" % s )


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

    def do_invoke (self, argv ):
        try:
            r = Registers()
            if( r.thread == 0 ):
                print("No running thread to read registers from")
                return

            vdb.memory.print_legend("Ama")

            if( len(argv) == 0 ):
                argv.append(reg_default.value)
            if( len(argv) == 1 ):
                if( argv[0].startswith("/") ):
                    if( argv[0] == "/s" ):
                        r.print("ipx")
                    elif( argv[0] == "/e" ):
                        r.print("Ipx")
                    elif( argv[0] == "/a" ):
                        r.print("ixfpmv")
                    elif( argv[0] == "/f" ):
                        r.print("IXFPMV")
                    else:
                        r.print(argv[0][1:])
                else:
                    self.usage()
            else:
                print("Invalid argument(s) to registers: '%s'" % arg )
                self.usage()
        except Exception as e:
            traceback.print_exc()

cmd_registers()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
