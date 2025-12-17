#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util
import vdb.event

import gdb
import gdb.types


# XXX Unfortunately gdb currently does not offer a "new connection" type of event, as such we have to try and figure out
# on based on other events that there was a new connection
last_used_connection_details = None
last_used_connection_type    = None
def store_inferior( conn ):
    if( conn is None ):
        conn = gdb.selected_inferior().connection
    global last_used_connection_details
    global last_used_connection_type
    print(f"Saving new remote connection {conn}, overwriting old {last_used_connection_details}")
    last_used_connection_type = conn.type
    last_used_connection_details = conn.details

@vdb.event.connection_removed()
def _conrem( oldconn ):
    store_inferior( oldconn.connection)

@vdb.event.before_first_prompt()
def _bfp():
    store_inferior( None )

def reconnect( argv, flags ):
    if( last_used_connection_details is None ):
        print("Cannot reconnect, no previous connection recorded")

    print(f"Reconnecting to {last_used_connection_details}")
    cmd = f"target {last_used_connection_type} {last_used_connection_details}"
    gdb.execute(cmd)


# readapex
"""
0xf8:0x8 : O.K.:0xE00FE003
0xf8:0xc : O.K.:0x14770015

0x0:0xf8 : O.K.:0xE00FE003
0x0:0xfc : O.K.:0x14770015
0x0:0x100 : O.K.:0x03800052
0x0:0x104 : O.K.:0xE000EE0C
0x0:0x108 : O.K.:0x00000000
0x0:0x204 : O.K.:0xE000EE1C
0x0:0x304 : O.K.:0xE000EE2C
0x0:0x404 : O.K.:0xE000EE3C
0x0:0x504 : O.K.:0xE000EE4C
0x0:0x604 : O.K.:0xE000EE5C
0x0:0x704 : O.K.:0xE000EE6C
0x0:0x804 : O.K.:0xE000EE7C
0x0:0x904 : O.K.:0xE000EE8C
0x0:0xa04 : O.K.:0xE000EE9C
0x0:0xb04 : O.K.:0xE000EEAC
0x0:0xc04 : O.K.:0xE000EEBC
0x0:0xd04 : O.K.:0xE000EECC
0x0:0xe04 : O.K.:0xE000EEDC
0x0:0xf04 : O.K.:0xE000EEEC
0x0:0x1004 : O.K.:0xE000EEFC
"""
def dap( ):

    # segger gdbserver commands...
    # - readmemap 0 <addr> num 0 (num 32bit values) from device memory, must be properly aligned
    #   todo: test if we can do that while the target is running (if yes, thats some rtt thing)
    #         test result says that via "monitor go" we can even just read memory as normal. Sadly reading registers
    #         that way does not work. We have to check if that read somehow interrupts the cpu or if it runs in parallel
#    base = 0xf8
    base = 0x0
#    base = 0xe000e000
#    base = 0xe0001000
#    base = 0xe00fe000
#    base = 0xfff46000
#    base = 0x10000000
    #        __##__##

    addr = 0x1000
    addr = 0xfff42000
    addr = 0xf8
    addr = 0x0
#    addr = 0xfffffff0
#    addr = 0xfff0f000
#    addr = 0xfff02000
#    addr = 0xe00fe000
#    addr = 0xfff46000
#    addr = 0xe0044000
#    addr = 0x0
#    addr = 0x08000000

#    num = 0x10000
    num = 0x100
#    num = 0xfffffffffffffff0

    seen = set()

    for i in range(0,num):
        if( False ):
            xbase = base
            xaddr = addr + i*4
#            xaddr = addr - i*4
        else:
            xbase = base + i
            xaddr = addr
#        r = gdb.execute( f"monitor readdp {xbase:#0x}", True, True )
        r = gdb.execute( f"monitor readap {xbase:#0x}", True, True )
#        r = gdb.execute( f"monitor readapex {xbase:#0x} {xaddr:#0x}", True, True )
#        r = gdb.execute( f"monitor readmemap {xbase:#0x} {xaddr:#0x} 1 0", True, True )
        r = r.strip()
        if( r not in seen or False ):
            print(f"{xbase:#0x}:{xaddr:#0x} : {r}")
            seen.add(r)


class cmd_reconnect(vdb.command.command):
    """
    Stores new inferiors connection information and provides an easy way to reconnect it the connection got lost
    """

    def __init__ (self):
        super ().__init__ ("reconnect", gdb.COMMAND_DATA)
        self.needs_parameters = False

    def do_invoke (self, argv:list[str] ):
        self.dont_repeat()

        argv,flags = self.flags(argv)
        if( len(argv) > 0 ):
            dap()
        else:
            reconnect(argv,flags)

cmd_reconnect()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
