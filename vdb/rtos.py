#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.types

import os
import traceback
import time
import re

color_active_task = vdb.config.parameter("vdb-rtos-colors-active-task",    "#0a4", gdb_type = vdb.config.PARAM_COLOUR)

# We want to support different flavours and auto detect which one is being used

class task:
    """
    Generic task that has certain things just not set when the OS does not support it
    """
    def __init__( self ):
        self.name = None
        self.id = None
        self.priority = None
        self.status = None
        self.stack = None
        self.current = False
        self.pc = None

class os_embos( ):

    TS_READY            = (0x00 << 3)
    TS_WAIT_EVENT       = (0x01 << 3)
    TS_WAIT_MUTEX       = (0x02 << 3)
    TS_WAIT_ANY         = (0x03 << 3)
    TS_WAIT_SEMA        = (0x04 << 3)
    TS_WAIT_MEMPOOL     = (0x05 << 3)
    TS_WAIT_MEMPOOL_old = (0x05 << 5)
    TS_WAIT_QNE         = (0x06 << 3)
    TS_WAIT_MBNF        = (0x07 << 3)
    TS_WAIT_MBNE        = (0x08 << 3)
    TS_WAIT_EVENTOBJ    = (0x09 << 3)
    TS_WAIT_QNF         = (0x0A << 3)

    TS_MASK_SUSPEND_CNT = (0x03 << 0)
    TS_MASK_TIMEOUT     = (0x01 << 2)
    TS_MASK_STATE       = (0xF8 << 0)

    status_map = {
            TS_READY                           : "Ready",
            TS_READY | TS_MASK_TIMEOUT         : "Delayed",
            TS_WAIT_ANY                        : "Blocked",
            TS_WAIT_ANY | TS_MASK_TIMEOUT      : "(TO) Blocked",
            TS_WAIT_EVENT                      : "Waiting for Task Event" ,
            TS_WAIT_EVENT | TS_MASK_TIMEOUT    : "(TO) Waiting for Task Event" ,
            TS_WAIT_EVENTOBJ                   : "Waiting for Event Object" ,
            TS_WAIT_EVENTOBJ | TS_MASK_TIMEOUT : "(TO) Waiting for Event Object" ,
            TS_WAIT_MBNE                       : "Waiting for message in Mailbox" ,
            TS_WAIT_MBNE | TS_MASK_TIMEOUT     : "(TO) Waiting for message in Mailbox" ,
            TS_WAIT_MBNF                       : "Waiting for space in Mailbox" ,
            TS_WAIT_MBNF | TS_MASK_TIMEOUT     : "(TO) Waiting for space in Mailbox" ,
            TS_WAIT_MEMPOOL                    : "Waiting for Memory Pool" ,
            TS_WAIT_MEMPOOL | TS_MASK_TIMEOUT  : "(TO) Waiting for Memory Pool" ,
            TS_WAIT_QNE                        : "Waiting for message in Queue" ,
            TS_WAIT_QNE | TS_MASK_TIMEOUT      : "(TO) Waiting for message in Queue" ,
            TS_WAIT_QNF                        : "Waiting for space in Queue" ,
            TS_WAIT_QNF | TS_MASK_TIMEOUT      : "(TO) Waiting for space in Queue" ,
            TS_WAIT_MUTEX                      : "Waiting for Mutex" ,
            TS_WAIT_MUTEX | TS_MASK_TIMEOUT    : "(TO) Waiting for Mutex" ,
            TS_WAIT_SEMA                       : "Waiting for Semaphore" ,
            TS_WAIT_SEMA | TS_MASK_TIMEOUT     : "(TO) Waiting for Semaphore" ,

            }

    def __init__( self ):
        self.OS_Global = gdb.parse_and_eval("&OS_Global")

        ov = gdb.parse_and_eval("((unsigned short*)&OS_Version)[0]")
        ov = int(ov)
        main = ov // 10000
        mino = ( ov // 100 ) % 100
        pl   = ov % 25
        rv   = ( ov % 100 ) // 25
        self.ver = f"{main}.{mino}.{pl}.{rv}"

        self.nm = gdb.parse_and_eval("OS_sCopyright")

    def _status_string( self, st ):
        if( st & self.TS_MASK_SUSPEND_CNT):
            return "Suspended"
        ret = self.status_map.get(st,st)
        return ret


    def get_task_list( self ):
        ret = []
        current = gdb.parse_and_eval("OS_Global.pCurrentTask")
        pTask = self.OS_Global["pTask"]
        while( pTask != 0 ):
            t = task()
            ret.append(t)
            if( pTask == current ):
                t.current = True
            t.name = pTask["sName"]
            t.id = int(pTask)
            t.priority = int(pTask["Priority"])
            t.stack = pTask["pStack"]
            t.status = int(pTask["Stat"])

            t.pc = t.stack["Base"]["OS_REG_PC"]
            t.pc = gdb.parse_and_eval(f"(void*){t.pc}")

            t.lr = t.stack["Base"]["OS_REG_LR"]
            t.lr = gdb.parse_and_eval(f"(void*){t.lr}")
            pTask = pTask["pNext"]

        return ret

    def version( self ):
        return self.ver


    def name( self ):
        return self.nm.string()

    def print_task_list( self, tlist ):
        tbl = []
        tbl.append( [ "ID","Name","Stack","Prio","Status","pc","lr" ] )
        for t in tlist:
            # XXX status can optionally refer to a wait object
            col=None
            if( t.current ):
                col = color_active_task.value
            tbl.append( [ vdb.color.colorl(f"{int(t.id):#0x}",col), t.name.string(), f"{int(t.stack):#0x}", t.priority, self._status_string(t.status), t.pc, t.lr ] )
        vdb.util.print_table(tbl)

embos = None

def embos_rtos( argv ):
    global embos
    if( embos is None ):
        embos = os_embos()
    tl=embos.get_task_list()
    ver = embos.version()
    name = embos.name()
    print(f"{name} ver {ver}")
    embos.print_task_list(tl)



def rtos( argv ):
    # TODO here check which flavour is being used
    embos_rtos(argv)

class cmd_rtos(vdb.command.command):
    """

"""

    def __init__ (self):
        super (cmd_rtos, self).__init__ ("rtos", gdb.COMMAND_DATA)

    def do_invoke (self, argv ):
        self.dont_repeat()

        try:
            rtos(argv)
        except Exception as e:
            traceback.print_exc()

cmd_rtos()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
