#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.unwinder
import gdb.types

import os
import traceback
import time
import re

color_active_task = vdb.config.parameter("vdb-rtos-colors-active-task",    "#0a4", gdb_type = vdb.config.PARAM_COLOUR)
color_marked_task = vdb.config.parameter("vdb-rtos-colors-marked-task",    "#09e", gdb_type = vdb.config.PARAM_COLOUR)

# We want to support different flavours and auto detect which one is being used

class FrameId(object):
    def __init__(self, sp, pc):
        self.sp = sp
        self.pc = pc

    def __str__( self ):
        return f"FrameId({self.sp},{self.pc})"

class fake_unwinder(gdb.unwinder.Unwinder):
    def __init__( self ):
        self._enabled = False
        self._name = "rtos_fake_unwinder"
        self.fake_sp = None
        self.fake_pc = None
        self.fake_lr = None
        self.cached_ui = None
        self.level = 0

    def __call__(self,pending_frame):
#        vdb.util.bark() # print("BARK")
        try:
            if( self._enabled ):
                return self.do_call(pending_frame)
            else:
                return None
        except:
            print("fake_unwind __call__")
            vdb.print_exc()
        return None

    def reset( self ):
        self.level = 0
        self.fake_sp = None
        self.fake_pc = None
        self.fake_lr = None
        self.cached_ui = None

    def set( self, sp, pc, lr ):
        self.fake_sp = sp
        self.fake_pc = pc
        self.fake_lr = lr

    def take_over( self, pf, ui, lst ):
        for l in lst:
            ui.add_saved_register( l, pf.read_register(l) )

    def do_call(self,pending_frame):
#        print()
#        print("======================")
#        vdb.util.bark() # print("BARK")
#        print("pending_frame.level() = '%s'" % (pending_frame.level(),) )
#        print("self.level = '%s'" % (self.level,) )
#        if( self.level == 1):
#            self.level += 1
#            return self.cached_ui
#            return None
        sp = pending_frame.read_register("sp")
        pc = pending_frame.read_register("pc")
        try:
            lr = pending_frame.read_register("lr")
            int(lr)
        except gdb.error:
            lr = None
#        print("sp = '%s'" % (sp,) )
#        print("pc = '%s'" % (pc,) )
#        print("type(lr) = '%s'" % (type(lr),) )
#        if( lr is not None ):
#            print("lr.is_lazy = '%s'" % (lr.is_lazy,) )
#            print(f"{int(lr)=:#0x}")
#            gdb.execute(f"p (void*){lr}")
#        print("self.fake_sp = '%s'" % (self.fake_sp,) )
#        print("self.fake_pc = '%s'" % (self.fake_pc,) )
#        print("self.fake_lr = '%s'" % (self.fake_lr,) )

        if( self.level >= 1 ):
            return None
        # the frame id must be the one of the current ones sp/pc
        fid = FrameId(sp,pc)
#        print("fid = '%s'" % (fid,) )
        ui = pending_frame.create_unwind_info(FrameId(sp,pc))

        # Fake a different 0th frame by using for this frame recovered pc and sp that will then in the next call be used
        # for the FrameId
        
        # The registers we set now are those that are "active" in the newly faked frame, so the fake pc and sp. LR is
        # being ignored here because we are called again and don't really use it
        if( self.level == 0 ):
            if( self.fake_pc is not None ):
                pc = self.fake_pc
            if( self.fake_sp is not None ):
                sp = self.fake_sp
            if( self.fake_lr is not None ):
                lr = self.fake_lr

        ui.add_saved_register( "sp", sp )
        ui.add_saved_register( "msp", sp )
        ui.add_saved_register( "psp", sp )
        if( self.level < 1 ):
            ui.add_saved_register( "lr",lr)

        ui.add_saved_register( "pc", pc )

        self.take_over( pending_frame, ui, [ "xpsr" ] )

#        regs = pending_frame.architecture().registers()
#        for r in regs:
#            print("r = '%s'" % (r,) )
#            if( str(r) == "sp" or str(r) == "pc" ):
#                continue
#            rv = pending_frame.read_register(r)
#            if( r is not None ):
#                ui.add_saved_register( r, rv )
        self.level += 1
        self.cached_ui = ui
#        print("ui = '%s'" % (ui,) )
#        if( self.level == 2 ):
#            return None
#        self.enabled = False
#        vdb.util.bark() # print("BARK")
#        return None
        return ui


unwinder = None

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
        otp=gdb.lookup_type("OS_TASK_STRUCT").pointer()
        current = gdb.parse_and_eval("OS_Global.pCurrentTask")
        pTask = self.OS_Global["pTask"]
        while( pTask != 0 ):
            t = task()
            if( pTask == current ):
                t.current = True
            try:
                t.name = pTask["sName"]
            except gdb.error:
                pTask=pTask.cast(otp)
                t.name = pTask["sName"]
            try:
                t.id = int(pTask)
                t.priority = int(pTask["Priority"])
                t.stack = pTask["pStack"]
                t.status = int(pTask["Stat"])

                x = t.stack["Base"]
                t.pc = t.stack["Base"]["OS_REG_PC"]
                t.pc = gdb.parse_and_eval(f"(void*){t.pc}")

#            t.lr = t.stack["Base"]["OS_REG_LR"]
                t.lr = t.stack["Base"]["OS_REG_R14"]
                t.lr = gdb.parse_and_eval(f"(void*){t.lr}")
            except gdb.error:
                break
            ret.append(t)
            pTask = pTask["pNext"]

        return ret

    def version( self ):
        return self.ver


    def name( self ):
        try:
            return self.nm.string()
        except:
            return None

    def print_task_list( self, tlist, with_bt = None, id_filter = None ):
        tbl = []
        tbl.append( [ "ID","Name","Stack","Prio","Status","pc","lr" ] )
        global unwinder
        if( with_bt is not None and unwinder is None ):
            unwinder = fake_unwinder()
            gdb.unwinder.register_unwinder(None,unwinder,replace=True)

        for t in tlist:
            # XXX status can optionally refer to a wait object
            col=None
            if( t.current ):
                col = color_active_task.value
            if( id_filter == t.id ):
                col = color_marked_task.value

            tbl.append( [ vdb.color.colorl(f"{int(t.id):#0x}",col), t.name.string("iso-8859-15"), f"{int(t.stack):#0x}", t.priority, self._status_string(t.status), t.pc, t.lr ] )
        if( with_bt is not None ):
#            print("unwinder.enabled = '%s'" % (unwinder.enabled,) )
            frame = gdb.selected_frame()
            psp = frame.read_register("psp")
            msp = frame.read_register("msp")
            pc = frame.read_register("pc")
            rt = vdb.util.format_table(tbl).split("\n")
            char_ptr = gdb.lookup_type("char").pointer()
            void_ptr_ptr = gdb.lookup_type("void").pointer().pointer()
            header = True
            cnt=0
#            print("rt = '%s'" % (rt,) )
#            gdb.execute("reg sp")
            for r in rt:
#                print("#############################################################")
                print(r)
                if( header ):
                    header = False
                    continue
                if( cnt < len(tlist) ):
                    t = tlist[cnt]
                    if( id_filter is None or id_filter == t.id ):
                        cur = t.current
                        if( cur ):
                            unwinder.enabled = False
                            gdb.execute(with_bt)
#                        unwinder.enabled = True
                        else:
                            tsp = t.stack.cast(char_ptr)
                            vlr= t.stack.cast(void_ptr_ptr)
#                            gdb.execute(f"hd/p {int(tsp)} 96")
                            tcand = None
                            for i in range(0,128):
                                vcand = vlr + i
                                cdif = vcand.dereference() - t.lr
                                if( cdif == 0 ):
                                    tcand = vcand.cast(char_ptr)
                                    if( False ):
                                        print("i = '%s'" % (i,) )
                                        print("cdif = '%s'" % (cdif,) )
                                        print("vcand = '%s'" % (vcand,) )
                                        print("tsp = '%s'" % (tsp,) )
                                        print("int(vcand)-int(tsp) = '%s'" % (int(vcand)-int(tsp),) )
                                        gdb.execute(f"hd/p {int(tcand)}-128 256")
                                    break
                            # try to recover a better stack pointer by searching for the pushed lr
                            if( tcand is not None ):
                                tsp = tcand
                                # thats for three other parameters, I guess we have to somehow figure out how many 
                                tsp += 12
#                                tsp += 20
                            else:
                                tsp += 40
                                tsp += 32
#                            gdb.execute(f"hd/p {int(tsp)} 32")
#                        add=int(time.time()) % 100
#                        print("add = '%s'" % (add,) )
#                        tsp += add
                            tpc = t.pc
                            tlr = t.lr

#                        print("tsp = '%s'" % (tsp,) )
#                        print("tpc = '%s'" % (tpc,) )
#                        print("tlr = '%s'" % (tlr,) )
#                        print(f"frame view {int(tsp)} {int(tpc)}")
#                        print(f"frame view {int(tsp):#0x} {int(tpc):#0x}")
#                        gdb.execute(f"frame view {int(tsp)} {int(tpc)}")
#                        gdb.execute(f"set $psp={int(tsp)}")
#                        gdb.execute(f"set $msp={int(tsp)}")
#                        gdb.execute(f"set $pc={int(tpc)}")
                            unwinder._enabled = True
#                            for i in range(0,32):
#                                xsp = tsp - 16*4 + i*4
#                                unwinder.set( xsp, tpc, tlr )
#                                print(f"++++++++++++++++++++++++++++ with xsp = {xsp}")
#                                gdb.execute("maintenance flush register-cache") # clear cache, cause to call again
#                                gdb.execute(with_bt)
#                                unwinder.reset()
                            unwinder.set( tsp, tpc, tlr )
#                        gdb.execute("fr 0")
#                        gdb.execute("fr 1")
                            gdb.execute("maintenance flush register-cache") # clear cache, cause to call again
#                            print("Flushed register cache")
                            btdata=gdb.execute(with_bt,False,True)
                            btdata=btdata.split("\n")
                            btdata=btdata[2:]
                            print("\n".join(btdata))
                            unwinder.reset()
                            unwinder._enabled = False
#                        gdb.execute("reg sp")
#                        gdb.execute(f"set $msp={int(msp)}")
#                        gdb.execute(f"set $psp={int(psp)}")
#                        gdb.execute(f"set $pc={int(pc)}")
                cnt += 1

        else:
            vdb.util.print_table(tbl)

embos = None

def embos_rtos( argv ):
    global embos
    if( embos is None ):
        try:
            embos = os_embos()
        except gdb.error as e:
            print(f"Failed to detect embOS: {e}")
            return
    tl=embos.get_task_list()
    ver = embos.version()
    name = embos.name()
    print(f"{name} ver {ver}")
    with_bt = None
    if( len(argv) > 0 ):
        if( argv[0].startswith("bt") ):
            with_bt = argv[0]
            argv = argv[1:]
    id_filter=None
    if( len(argv) > 0 ):
        id_filter=vdb.util.gint(argv[0])
    embos.print_task_list(tl,with_bt,id_filter)



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
            vdb.print_exc()
        finally:
            global unwinder
            if( unwinder is not None ):
                unwinder._enabled = False

cmd_rtos()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
