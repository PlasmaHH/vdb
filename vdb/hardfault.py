#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import sys
import threading
import select
import time
import re

import gdb

import vdb.command
import vdb.color
import vdb.util
import vdb.register

import rich.console

def get_reasons( flags, val ):
    if( val is None ):
        return "None"
    ret = []
    val = int(val)
    for mask,txt in flags.items():
        if( mask & val != 0 ):
            ret.append( f"[{txt[0]}] {txt[1]}" )
    return ret

def hardfault_info():
    print("Hard Fault interesting registers:")
    gdb.execute("reg/M &BFSR|UFSR|MMFSR|HFSR|BFAR")
    registers = vdb.register.Registers()

    ufsr_flags = {
                    0x10000   : ( "UNDEFINSTR", "Undefined instruction" ),
                    0x20000   : ( "INVSTATE"  , "Invalid state" ),
                    0x40000   : ( "INVPC"     , "Invalid PC" ),
                    0x80000   : ( "NOCP"      , "No coprocessor" ),
                    0x100000  : ( "STKOF"     , "Stack overflow" ),
                    0x1000000 : ( "UNALIGNED" , "Unaligned access" ),
                    0x2000000 : ( "DIVBYZERO" , "Divide by zero" ),
                }

    bfsr_flags = {
                    0x0100 : ( "IBUSERR"     , "Instruction bus error." ),
                    0x0200 : ( "PRECISERR"   , "Precise error." ),
                    0x0400 : ( "IMPRECISERR" , "Imprecise error." ),
                    0x0800 : ( "UNSTKERR"    , "Unstack error." ),
                    0x1000 : ( "STKERR"      , "Stack error." ),
                    0x2000 : ( "LSPERR"      , "Lazy state preservation error." ),
                    0x8000 : ( "BFARVALID"   , "BFAR valid." ),
                }


    mmfsr_flags = {
                    0x0001 : ( "IACCVIOL"   ,"Instruction access violation." ),
                    0x0002 : ( "DACCVIOL"   ,"Data access violation flag." ),
                    0x0008 : ( "MUNSTKERR"  ,"MemManage unstacking error flag." ),
                    0x0010 : ( "MSTKERR"    ,"MemManage stacking error flag." ),
                    0x0020 : ( "MLSPERR"    ,"MemManage lazy state preservation error flag." ),
                    0x0080 : ( "MMARVALID"  ,"MMFAR valid." ),
                }

    print("Analyzing hard fault reasons and conditions...")

    ufsr,_ = registers.get_mmapped( "SCB.UFSR" )
    ufsr_reasons = get_reasons( ufsr_flags, ufsr )
    if( len(ufsr_reasons) > 0 ):
        print(f"Usage Fault Reason: {','.join(ufsr_reasons)}")

    bfsr,_ = registers.get_mmapped( "SCB.BFSR" )
    bfarvalid = ( bfsr & 0x8000 ) != 0
    bfsr_reasons = get_reasons( bfsr_flags, bfsr )
    if( len(bfsr_reasons) > 0 ):
        print(f"Bus Fault Reason: {','.join(bfsr_reasons)}")

    mmfsr,_ = registers.get_mmapped( "SCB.MMFSR" )
    mmfarvalid = ( mmfsr & 0x80 ) != 0
    mmfsr_reasons = get_reasons( mmfsr_flags, mmfsr )
    if( len(mmfsr_reasons) > 0 ):
        print(f"MemManage Fault Reason: {','.join(mmfsr_reasons)}")

    if( bfarvalid ):
        bfar,_ = registers.get_mmapped("SCB.BFAR")
        bfar = int(bfar)
        print(f"BUS Fault while trying to access memory at {bfar:#0x}")
    else:
        print("BFAR not valid")

    if( mmfarvalid ):
        mmfar,_ = registers.get_mmapped("SCB.MMFAR")
        mmfar = int(mmfar)
        print(f"MemManage Fault while trying to access memory at {mmfar:#0x}")
    else:
        print("MMFAR not valid")

    gdb.execute("bt")


# SCB.CCR check for data and instruction caching

class cmd_hardfault (vdb.command.command):
    """
    Control hardfault comms
"""

    def __init__ (self):
        super ().__init__ ("hardfault", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            if( len(argv) == 0 ):
                hardfault_info()
                return

            match argv[0]:
                case "start":
                    start_hardfault(flags,argv[1:])
                case "stop":
                    stop_hardfault(flags,argv[1:])
                case "status":
                    status_hardfault(flags,argv[1:])
                case "dash":
                    link_dash(flags,argv[1:])
                case _:
                    print(f"Unrecognized command {argv[0]}")
                    self.usage()

        except:
            vdb.print_exc()
            raise
        self.dont_repeat()

cmd_hardfault()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
