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

import re
import traceback
import time
import datetime
import struct

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
                print(f"{rname} => {rval1}")
    return ret

class instruction_state:

    def __init__( self ):
        self.pc = None
        self.asm_string = None
        self.changed_registers = None
        self.changed_memory = None
        # Get from the asm module the instruction object with its arguments and targets that will sort this out for the
        # active architecture
        self.accessible_memory = None

    def _dump( self ):
#        print(f"{self.pc=}")
#        print(f"{self.changed_registers=}")
#        print(f"{self.asm_string=}")
        print(f"{int(self.pc[0]):#0x}  {self.asm_string}   {self.changed_registers}")

def xi( num ):
    gdb.execute("registers")

    alli = []
    oldr = vdb.register.Registers()
    for i in range(0,num):
        print("===========")
        ist = instruction_state()
        alli.append(ist)
        gdb.execute("si",False,True)
        r = vdb.register.Registers()

        # Depending on the arch chose the right register
        pc = oldr.get_value("rip")
#        fr_pc = gdb.selected_frame().pc()
#        print(f"{str(pc[0])=}")
#        print(f"{fr_pc=}")
#        print(f"{r.all=}")
#        print(f"{r.regs=}")
        dr = diff_regs(oldr,r)
        ist.changed_registers = dr
        ist.pc = pc
        ist.asm_string = vdb.asm.get_single( pc[0] )
        oldr = r

    for i in alli:
        i._dump()

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
            if( len(argv) > 0 ):
                num = int(argv[0])
            xi(num)
#            print (self.__doc__)
        except:
            traceback.print_exc()
            raise
        self.dont_repeat()

cmd_xi()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
