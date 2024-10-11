#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.pointer
import vdb.event
import vdb.register

from itertools import chain

import gdb

import traceback
import re

from typing import List

# Also try to figure out memory that changed
# Use the same mechanism for disassembler to also display the variable names if we know about them?

# Support showspec like the registers command
def diff_regs( r0, r1 ):
    ret = {}
    for rname,rval0 in chain(r0.regs.items(),r0.rflags.items()):
        rval1 = r1.get_value(rname)
#        print(f"{str(rname)=}")
#        print(f"{rval1=}")
        rval0 = int(rval0[0])
        rval1 = int(rval1[0])
        if( rval0 != rval1 ):
            # XXX Make this arch independent
            if( str(rname) != "rip" ):
                ret[str(rname)] = rval1
#                print(f"{rname} => {rval1}")
    return ret

def diff_mmaps( r0, r1 ):
    ret = {}
    for rname,rval0 in r0.items():
        rval1 = r1.get(rname,None)
        if( rval1 is None ):
            continue
        rval0 = int(rval0)
        rval1 = int(rval1)
        if( rval0 != rval1 ):
#            print(f"{str(rname)} from {rval0} to {rval1}")
            ret[str(rname)] = rval1
    return ret



class instruction_state:

    def __init__( self ):
        self.pc = None
        self.asm_string = None
        self.changed_registers = None
        self.current_flags = None
        self.changed_memory = []
        # Get from the asm module the instruction object with its arguments and targets that will sort this out for the
        # active architecture
        self.accessible_memory = None
        self.instruction = None
        self.mmap_registers = {}

    def _dump( self ):
#        print(f"{self.pc=}")
#        print(f"{self.changed_registers=}")
#        print(f"{self.asm_string=}")
        print(f"{int(self.pc[0]):#0x}  {self.asm_string}   {self.changed_registers}")


pc_name_map = {
        "i386:x86-64" : "rip"
        }

# XXX We need to put this and the figuring out of the current architecture name from asm.py into arch.py for all to
# access ( here we know we have a frame, but we need a method with a loaded but not runnig/cored process)
def get_pc_name( ):
    archname = gdb.selected_frame().architecture().name()
    return pc_name_map.get(archname,"pc")

def get_mmaps( mmaps, filter ):
    if( filter is None ):
        print(f"Reading {len(mmaps)} values...")
    else:
        print(f"Reading up to {len(mmaps)} values...",end="")
    if( filter is not None ):
        filter = re.compile(filter)
    ret = {}
    for reg,rpos in mmaps.items():
        if( filter is not None ):
            if( filter.search(reg) is None ):
                continue
        raddr,rbit,rtype = rpos

        if( vdb.register.is_blacklisted( raddr ) ):
            continue

        val = vdb.memory.read_uncached(raddr,rbit//8)
        if( val is not None ):
            val = gdb.Value(val,rtype)
            ret[reg] = int(val)
    if( filter is not None ):
        print(f" {len(ret)} matches")
    return ret



def xi( num, filter, full, events ):
    regs = gdb.execute("registers",False,True)

    alli = []
    oldr = vdb.register.Registers()
    pcname = get_pc_name()


    if( full ):
        mmaps = vdb.register.mmapped_positions
        ommaps = get_mmaps(mmaps,filter)

    for ui in range(0,num):
#        print("===========")
        ist = instruction_state()
        alli.append(ist)
        gdb.execute("si",False,True)
        r = vdb.register.Registers()
        if( events ):
            vdb.event.exec_hook("step")

        if( full ):
            rmmaps = get_mmaps(mmaps,filter)
#            print(f"{ommaps['SCB.ICSR']=}")
#            print(f"{rmmaps['SCB.ICSR']=}")
            dm = diff_mmaps( ommaps, rmmaps )
            ommaps = rmmaps
#            print(f"{dm=}")
            ist.mmap_registers = dm

        # Depending on the arch chose the right register
        pc = oldr.get_value(pcname)
#        fr_pc = gdb.selected_frame().pc()
#        print(f"{str(pc[0])=}")
#        print(f"{fr_pc=}")
#        print(f"{r.all=}")
#        print(f"{r.regs=}")
        dr = diff_regs(oldr,r)
        ist.changed_registers = dr
        # XXX Needs arch independence. Check for complete list of possible flags from registers.py ?
        ist.current_flags=r._flags("eflags",r.rflags,vdb.register.flag_info,False,False,True,None)
        ist.pc = pc
        ist.asm_string,ist.instruction = vdb.asm.get_single_tuple( pc[0], extra_filter="r",do_flow=True )
#        print(f"{ist.instruction.arguments=}")
#        print(f"{ist.instruction.args=}")

        for arg in ist.instruction.arguments:
            if( arg.dereference ):
                nr = vdb.asm.register_set()
                # XXX python should probably have some lambda magic for that
                # Also, here we have an incompatibility between asm and register that seem to do very similar
                # bookkeeping and surely can benefit from shared code

                for k,v in r.regs.items():
                    nr.values[str(k)] = (int(v[0]),None)
#                print(f"{nr=}")
#                print(f"{nr.get('rip')=}")
                val = arg.value( nr )
                if( val is not None ):
#                    print(f" MEM {arg} => {val}")
                    ist.changed_memory.append(val)
#                print(f"{val=}")
#            arg._dump()
#            print(f"{arg=}")
        oldr = r

    print(regs)
    otbl = []
    otbl.append(["Addr","asm","regs"])
    xi_history = {}
    for ix,i in enumerate(alli):
        xi_history.setdefault(int(i.pc[0]),[]).append(ix)
        line : List = []
        otbl.append(line)
        pv,_,_,_,pl = vdb.pointer.color(i.pc[0],vdb.arch.pointer_size)
        line.append( (pv,pl) )
        alen = len( vdb.color.colors.strip_color(i.asm_string ) )
        line.append( ( i.asm_string,alen) )
        for cr,cv in i.changed_registers.items():
            if( cr == "eflags" ):
                ff=i.current_flags
                ff=ff[0][2]
#                ff= self._flags( filter, self.rflags, flag_info, extended, short, mini, None )
                line.append(f"eflags={ff}")
            else:
                # XXX Make this depend on the type
                if( cv < 0 ):
                    cv += 2**32
                line.append(f"{cr}={cv:#0x}")
        for val,addr in i.changed_memory:
#            print(f"XMEM {addr} => {val}")
#            print(f"{val=}")
#            print(f"{addr=}")
            if( addr is not None ):
                addr = f"{addr:#0x}"
            else:
                addr = "<unknown>"
            if( val is not None ):
                val = f"{val:#0x}"
            else:
                val = "<inaccessible>"
            line.append(f"{addr}={val}")
        for r,val in i.mmap_registers.items():
            line.append(f"{r}={val:#0x}")

#            line.append(str(addr))
#        i._dump()
    vdb.util.print_table(otbl)
    if( vdb.enabled("asm") ):
        vdb.asm.xi_history = xi_history

class cmd_xi (vdb.command.command):
    """
eXecute Instructions ( and save data along the way )
"""

    def __init__ (self):
        super ().__init__ ("xi", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            num = 1
            full = False
            events = False
            filter = None

            nargv = []
            for a in argv:
                if( not a.isdigit() ):
                    filter = a
                else:
                    nargv.append(a)
            argv = nargv


            if( "f" in flags ):
                full = True
            if( "e" in flags ):
                events = True

            if( len(argv) > 0 ):
                num = int(argv[0])
            xi(num,filter,full,events)
#            print (self.__doc__)
        except:
            vdb.print_exc()
            raise
        self.dont_repeat()

cmd_xi()
# TODO
# optional output of the function/context/symbol in one column
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
