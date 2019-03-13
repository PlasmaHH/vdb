#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.pointer
import vdb.memory

import gdb

import shlex
import re
import traceback

color_names = vdb.config.parameter("vdb-register-colors-names", "#4c0", gdb_type = vdb.config.PARAM_COLOUR)


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

possible_registers = [ 
		"rax", "rbx", "rcx", "rdx", 
		"rsi", "rdi",
		"rbp", "rsp",
		"rip",
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

class Registers():

    def __init__(self):
        self.regs = {}
        self.segs = {}
        self.vecs = {}
        self.fpus = {}
        self.thread = 0
        try:
            frame=gdb.selected_frame()
        except:
            return
        self.frame = 22
        thread=gdb.selected_thread()
        self.thread = thread.num
        self.archsize = 64

        for reg in possible_registers:
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

        self.mxcsr = frame.read_register("mxcsr")

    def parse_register( self,frame,reg,regs):
        try:
            v = frame.read_register(reg)
#			print("reg = '%s'" % reg )
#			print("v = '%s'" % v )
            t = v.type
            regs[reg] = ( v, t )
        except:
            pass

    def format_register( self,name, val,t, chained = False ):
        val=int( val.cast(gdb_uint64_t) )
        try:
            ret = vdb.color.color(f" {name:<6}",color_names.value)
#            print("name = '%s'" % name )

            if( chained ):
                ret += vdb.pointer.chain(val,self.archsize)
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

    def format_vector( self, xvec ):
        name,amnt = xvec[0]
        amnt = len(amnt)
        ret = ""
#		print("xvec = '%s'" % xvec )
        for i in range(0,amnt):
            for name,vals in xvec:
                val=int(vals[i])
                if( i == 0 ):
                    ret += vdb.color.color(f" {name:<6}",color_names.value)+f"0x{val:032x}"
                else:
                    ret += f"       0x{val:032x}"
            ret += "\n"
        return ret

    def extract_vector( self,name, val, t ):
        ret = []
#		print("val.type.name = '%s'" % val.type.name )
#		print("val.type.sizeof = '%s'" % val.type.sizeof )
#		print("val = '%s'" % val )
#		for f in val.type.fields():
#			print("f.name = '%s'" % f.name )
#		val=42
#		val=int(val["uint128"])
        sub64 = (val.type.sizeof*8)//64
        sub128 = (val.type.sizeof*8)//128
        tname=f"v{sub64}_int64"
        xval=[]
        for i in range(0,sub64):
            #			print("BARK")
            try:
                xval.append(int(val[tname][i].cast(gdb_uint64_t)))
            except:
                xval.append("INVALID")

        yval=[]
        for i in range(0,sub64,2):
            yval.append( xval[i] + (xval[i+1]<<64) )
        return yval


    def ex_ints( self ):
        ret = ""
        cnt=0
        for name,valt in self.regs.items():
            val,t =valt
            cnt += 1
            ret += self.format_register(name,val,t,True)
#            ret += " RECURSION"
            ret += "\n"
        return ret


    def ex_floats( self ):
        print("NOT YET IMPLEMENTED")
    def ex_vectors( self ):
        print("NOT YET IMPLEMENTED")

    def ints( self ):
        ret = ""
        cnt=0
        for name,valt in self.regs.items():
            val,t =valt
            cnt += 1
            ret += self.format_register(name,val,t)
            if( cnt % 6 == 0 ):
                ret += "\n"

        cnt=0
        ret += "\n"

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
        ret += "\n"
        return ret

    def vectors( self ):

        ret=""
        val = int(self.mxcsr)

        ret += " "
        short = " [ "
        for flag,bit in mxcsr_bits:
            ex = val >> bit
#			print("ex = '%s'" % ex )
            col = ( ex != 0 )
#			print("col = '%s'" % col )
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

        cnt=0
        xvec = []
        for name,valt in self.vecs.items():
            val,t =valt
            cnt += 1
#			ret += self.format_vector(name,val,t)
            xvec.append( (name, self.extract_vector(name,val,t)) )
            if( cnt % 4 == 0 ):
                ret += self.format_vector(xvec)
                xvec = []

        return ret


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
                ret += vdb.color.color(f"{flag}[{ex}] ","#adad00")

#
#		ret += "OF[{}] ""DF[{}] ""IF[{}] ""TF[{}]".format( ((eflags >> 0xB) & 1 ), ((eflags >> 0xA) & 1 ),  ((eflags >> 9) & 1), ((eflags >> 8) & 1 ))
#		ret += "SF[{}] ""ZF[{}] ""AF[{}] ""PF[{}] ""CF[{}] ".format( ((eflags >> 7) & 1 ), ((eflags >> 6) & 1 ), ((eflags >> 4) & 1 ), ((eflags >> 2) & 1 ), (eflags & 1))
#		ret += "ID[{}] ""VIP[{}] ""VIF[{}] ""AC[{}]".format( ((eflags >> 0x15) & 1 ), ((eflags >> 0x14) & 1 ),  ((eflags >> 0x13) & 1 ), ((eflags >> 0x12) & 1 ))
#		ret += "VM[{}] ""RF[{}] ""NT[{}] ""IOPL[{}]".format( ((eflags >> 0x11) & 1 ), ((eflags >> 0x10) & 1 ), ((eflags >> 0xE) & 1 ), ((eflags >> 0xC) & 3 ))


        ret += "\n"
        ret += " "
        ret += str(self.eflags) + "\n"



        return ret


class cmd_registers(gdb.Command):
    """Show the registers nicely (default is expanded)
short    - Show just the important registers and flags with their hex values
expanded - Show the important registers in a recursively expanded way, depending on their usual type maybe as integers
all      - Show all registers in their short hex form
full     - Show all registers in the expanded form if possible, for fpu and vector registers this may mean all possible
representations
"""

    def __init__ (self):
        super (cmd_registers, self).__init__ ("registers", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def invoke (self, arg, from_tty):
        try:
            argv=shlex.split(arg)
            r = Registers()
            if( r.thread == 0 ):
                print("No running thread to read registers from")
                return

            vdb.memory.print_legend("Ama")

            if( len(argv) == 0 ):
                print(r.ex_ints())
                print(r.flags())
            elif( len(argv) == 1 ):
                if( argv[0] == "short" ):
                    print(r.ints())
                    print(r.flags())
                if( argv[0] == "expanded" ):
                    print(r.ex_ints())
                    print(r.flags())
                if( argv[0] == "all" ):
                    print(r.ints())
                    print(r.flags())
                    print(r.floats())
                    print(r.vectors())
                if( argv[0] == "full" ):
                    print(r.ex_ints())
                    print(r.flags())
                    print(r.ex_floats())
                    print(r.ex_vectors())
            else:
                print("Invalid argument(s) to registers: '%s'" % arg )
        except Exception as e:
            traceback.print_exc()

cmd_registers()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
