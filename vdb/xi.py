#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.arch
import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.pointer
import vdb.event
import vdb.register
import vdb.asm

from itertools import chain

import gdb

import traceback
import time
import datetime
import re

from typing import List

# Also try to figure out memory that changed
# Use the same mechanism for disassembler to also display the variable names if we know about them?

debug = vdb.config.parameter("vdb-xi-debug", False )
silence = vdb.config.parameter("vdb-xi-silence", True )
location = vdb.config.parameter("vdb-xi-location", False )
show_frame = vdb.config.parameter("vdb-xi-frame",False )

# Support showspec like the registers command
def diff_regs( r0, r1 ):
    ret = {}
    for rname,rval0 in chain(r0.regs.items(),r0.rflags.items()):
        rval1 = r1.get_value(rname)
#        if( rval0 is None or rval1 is None ):
#            print(f"diff_regs has no value for {rname} in both frames: {rval0=}, {rval1=}")
#            continue
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
        self.pc = (0,0)
        self.asm_string = None
        self.changed_registers = {}
        self.final_registers = None
        self.current_flags = None
        self.changed_memory = []
        self.executed = False
        # Get from the asm module the instruction object with its arguments and targets that will sort this out for the
        # active architecture
        self.accessible_memory = None
        self.instruction = None
        self.mmap_registers = {}
        self.frameno = None
        if( debug.value ):
            self.time = time.time()
            self.si_time = None
            self.after_si_time = None
            self.point_time = None

    def _dump( self ):
        print(f"{self.pc=}")
        print(f"{self.asm_string=}")
        print(f"{self.changed_registers=}")
        print(f"{self.final_registers=}")
        print(f"{self.current_flags=}")
        print(f"{self.changed_memory=}")
        print(f"{self.executed=}")
        print(f"{self.accessible_memory=}")
        print(f"{self.instruction=}")
        print(f"{self.mmap_registers=}")
#        print(f"{int(self.pc[0]):#0x}  {self.asm_string}   {self.changed_registers}")



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
        rname,raddr,rbit,rtype = rpos

        if( vdb.register.is_blacklisted( raddr ) ):
            continue

        val = vdb.memory.read_uncached(raddr,rbit//8)
        if( val is not None ):
            val = gdb.Value(val,rtype)
            ret[reg] = int(val)
    if( filter is not None ):
        print(f" {len(ret)} matches")
    return ret


breakpoint_hit = False
# XXX For performance reasons register this only during the xi run
@vdb.event.stop()
def bp_stop( bpev ):
    global breakpoint_hit
    if( isinstance( bpev, gdb.BreakpointEvent ) ):
#        print(f"{breakpoint_hit=} => True")
        breakpoint_hit = True
#    print(f"{bpev=}")

# ID, Data
xi_db = {}

class xi_listing:

    def __init__( self ):
        self.id = vdb.util.next_id("xi")
        self.time = time.time()
        self.listing = []
        self.minframe = 4096

    def add( self, xi ):
        self.listing.append(xi)

    def size( self ):
        return len(self.listing)

    def addresses( self ):
        beg = self.listing[0].pc[0]
        end = self.listing[-1].pc[0]
        return (beg,end)

    def get_history( self ):
        xi_history = {}
        for ix,i in enumerate(self.listing):
            xi_history.setdefault(int(i.pc[0]),[]).append( (ix,i) )
        return xi_history

    def as_table( self ):
        otbl = []
        if( debug.value ):
            otbl.append(["Time","SI Time", "PTime", "Rest", "Addr","asm","regs"])
        else:
            header = ["Addr"]
            if( show_frame.value ):
                header.append("Fr")
            if( location.value ):
                header.append("function")
            header += [ "asm", "regs" ]
            otbl.append(header)
        pcname = vdb.arch.get_pc_name()
        for ix,i in enumerate(self.listing):
            line : List = []
            otbl.append(line)
            if( debug.value ):
                tdif = 0
                if( (ix+1) < len(self.listing) ):
                    nxt = self.listing[ix+1]
                    tdif = nxt.time - i.time
                    line.append(tdif)
                else:
                    line.append( i.time )
                if( i.si_time is not None ):
                    line.append( i.si_time - i.time  )
                    line.append( i.point_time - i.si_time )
                    line.append( tdif - (i.si_time - i.time) - (i.point_time - i.si_time) )
                else:
                    line += ["","","" ]

            ipc = i.pc[0]
            pv,_,_,_,pl = vdb.pointer.color(ipc,vdb.arch.pointer_size)
            line.append( (pv,pl) )
            
            indent = ""
            if( show_frame.value ):
                line.append(i.frameno)
                if( i.frameno is not None ):
                    indent = "  " * (i.frameno - self.minframe)
            if( location.value ):
                syms = vdb.memory.get_symbols( ipc, 1 )
                sym = min(syms)
                line.append(f"{indent}{sym.data}")
            # Then flow was not active and we delayed getting the asm
            if( i.asm_string is None ):
                i.asm_string,i.instruction = vdb.asm.get_single_tuple( ipc, extra_filter="r",do_flow=False)
            alen = len( vdb.color.colors.strip_color(i.asm_string ) )
            line.append( ( i.asm_string,alen) )
            if( not i.executed ):
                line.append(vdb.color.colorl("Execution not captured","#cc2222") )
                continue
            for cr,cv in i.changed_registers.items():
                if( cr == pcname ):
                    continue
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
        return otbl




def xi( num, filter, full, events, flow ):
#    print("############################################")
#    vdb.util.bark() # print("BARK")
    regs = gdb.execute("registers",False,True)

    oldr = vdb.register.Registers()
    pcname = vdb.arch.get_pc_name()

    global breakpoint_hit
    breakpoint_hit = False

    if( full ):
        mmaps = vdb.register.mmapped_positions
        ommaps = get_mmaps(mmaps,filter)

    filter_warned = False

    xilist = xi_listing()
    xi_db[xilist.id] = xilist

    prog = vdb.util.progress_bar(num_completed = True, spinner = True)
    pt = prog.add_task(f"Executing {num} single steps", total = num )
    prog.start()
    inferior = gdb.selected_inferior()
    oldpid = inferior.pid
    next_update = 0
    try_si = True

    older = gdb.selected_frame()
    while older:
        first_frame = older
        older = older.older()

    for ui in range(0,num):
        prog.update( pt, completed = ui )
        now = time.time()
        if( now > next_update ):
            next_update = now + 0.1
            prog.refresh()
        try:
            if( breakpoint_hit ):
                print("Breakpoint hit")
                break

            ist = instruction_state()
            xilist.add(ist)
            pc = oldr.get_value(pcname)
            ist.pc = pc

            mem = vdb.memory.read( ist.pc[0], 2 )
            if( mem is None ):
                print( f"Cannot read address {int(ist.pc[0]):#0x}, refusing to execute it" )
                break

            with( vdb.util.silence(silence.value) ):
                gdb.execute("si",False,True)
            if( oldpid != inferior.pid ):
                print("Stopping xi, inferior has died")
                break

            if( try_si ): # This costs ~100µs on my system, out of ~700 total for each instruction
                try:
                    sig = gdb.convenience_variable("_siginfo")
                    if( sig is not None and sig["si_signo"] != 5 ): # TRAP
                        print("Stopping xi, non trap signal detected")
                        break
                except gdb.error as e:
                    try_si = False
                    pass

            ist.executed = True
            if( debug.value ):
                ist.si_time = time.time()

            r = vdb.register.Registers()

            if( show_frame.value ):
                # ~0.15ms per instruction
                ist.frameno = first_frame.level()
                xilist.minframe = min(xilist.minframe,ist.frameno)

            if( debug.value ): # Move this point for debugging timings
                ist.point_time = time.time()
            if( events ):
                vdb.event.exec_hook("step")

            if( full ):
                rmmaps = get_mmaps(mmaps,filter)
                if( len(rmmaps) == 0 and not filter_warned ):
                    print(f"WARNING: Filter {filter} returned no registers")
                    filter_warned = True
#                print(f"{rmmaps=}")
#                print(f"{ommaps['SCB.ICSR']=}")
#                print(f"{rmmaps['SCB.ICSR']=}")
                dm = diff_mmaps( ommaps, rmmaps )
                ommaps = rmmaps
#            print(f"{dm=}")
                ist.mmap_registers = dm

            # Depending on the arch chose the right register
#        fr_pc = gdb.selected_frame().pc()
#        print(f"{str(pc[0])=}")
#        print(f"{fr_pc=}")
#        print(f"{r.all=}")
#        print(f"{r.regs=}")
            dr = diff_regs(oldr,r)
            ist.changed_registers = dr
            ist.final_registers = r
            # XXX Needs arch independence. Check for complete list of possible flags from registers.py ?
            ist.current_flags=r._flags("eflags",r.rflags,vdb.register.flag_info,False,False,True,None)
            if( flow ):
                ist.asm_string,ist.instruction = vdb.asm.get_single_tuple( pc[0], extra_filter="r",do_flow=flow)
            # XXX Doing the whole flow thing is rather expensive, all we need is access to the register values of the
            # previous instructions output really to evaluate which memory was touched.
#        print(f"{ist.instruction.arguments=}")
#        print(f"{ist.instruction.args=}")

            if( flow ):
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
        except gdb.error as e:
            print(f"xi aborted due to gdb error: {e}")
            break
        except KeyboardInterrupt:
            print("Aborting xi")
            break
        except:
            print("Aborting xi")
            vdb.print_exc()
            print("Aborting xi")
            break

    prog.stop()
    print(regs)

    vdb.util.print_table(xilist.as_table(),use_rich=False)
    if( vdb.enabled("asm") ):
        vdb.asm.xi_history = xilist.get_history()


def xi_show( argv ):
    if( len(argv) == 0 ):
        print("Need to specify id to show")
        return
    xid = int(argv[0])
    xlst = xi_db.get(xid)
    if( xlst is None ):
        print(f"Cannot find xi listing for id {xid}")
        return
    vdb.util.print_table(xlst.as_table())

def xi_list( ):
    xtbl = [ ["ID", "Time", "Size", "Begin", "End" ] ]
    for xid,xlst in xi_db.items():
        line = []
        xtbl.append(line)
        line.append(xid)
        dt = datetime.datetime.fromtimestamp(xlst.time)
        line.append(dt)
        line.append(xlst.size())
        b,e = xlst.addresses()
        line.append(f"{int(b):#0x}")
        line.append(f"{int(e):#0x}")
    vdb.util.print_table(xtbl)

def xi_del( argv ):
    xid = int(argv[0])
    try:
        del xi_db[xid]
        print(f"Deleted ID {xid} from list")
    except KeyError:
        print(f"Could not find ID {xid}")

class cmd_xi (vdb.command.command):
    """
eXecute Instructions ( and save data along the way )
xi/f       full (local variables) info per frame
xi/e       execute a "step" hook/event on each step for other plugins
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
            flow = False

            if( len(argv) ):
                match argv[0]:
                    case "show":
                        argv = argv[1:]
                        xi_show(argv)
                        return
                    case "del":
                        argv = argv[1:]
                        xi_del(argv)
                        return
                    case "list":
                        xi_list()
                        return


            nargv = []
            for a in argv:
                if( not a.isdigit() ):
                    filter = a
                else:
                    nargv.append(a)
            argv = nargv


            if( "f" in flags ):
                full = True
            if( "F" in flags ):
                flow = True
            if( "e" in flags ):
                events = True

            if( filter is not None and not full ):
                print(f"WARNING: Peripheral filter {filter} will not be applied since we are not running in /f full mode")

            if( len(argv) > 0 ):
                num = int(argv[0])
            xi(num,filter,full,events,flow)
#            print (self.__doc__)
        except:
            vdb.print_exc()
            raise
        self.dont_repeat()

cmd_xi()
# TODO
# optional output of the function/context/symbol in one column
# Option /v ? to include vector registers in comparison(s). Respect aliasing and use concise display
# Even if we don't know the address of -0x8(%rbp) we could store it at the symbol to later get it back. But how do we
# handle if on loading we have to chose between two different ones?
# Add an optional column showing the stackframe number as well as the function name (without signature), maybe indented
# too

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
