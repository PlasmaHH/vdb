#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util
import vdb.pointer
import vdb.event

import gdb

import re
import traceback
import time
import datetime




rel_time = vdb.config.parameter("vdb-track-time-relative",True)
clear_at_start = vdb.config.parameter("vdb-track-clear-at-start",True)


bptypes = { 
        gdb.BP_BREAKPOINT : "breakpoint",
        gdb.BP_HARDWARE_WATCHPOINT : "hw watchpoint",
        gdb.BP_READ_WATCHPOINT : "read watchpoint",
        gdb.BP_ACCESS_WATCHPOINT : "acc watchpoint",
        gdb.BP_WATCHPOINT : "watchpoint"
        }

def bp_type( no ):
    return bptypes.get(no,no)

bpenabled = {
        0 : "n",
        1 : "y"
        }

def bp_enabled( en ):
    return bpenabled.get(en,en)

bpdisp = {
        0 : "keep",
        1 : "del",
        }
def bp_disp( d ):
    return bpdisp.get(d,d)

def stop( bp ):
    print("bp = '%s'" % bp )
    return False

def ptr_color( addr ):
    ret = vdb.pointer.color(addr,vdb.arch.pointer_size)
#    print("ret = '%s'" % (ret,) )
    return ( ret[0], vdb.arch.pointer_size // 4 + 2 )

trackings = { }

def do_continue( ):
    gdb.execute("continue")

@vdb.event.stop()
def stop( bpev ):
#    print("TRACK STOP")
    cont = False
    if( len(trackings) == 0 ):
        return
    if( type(bpev) == gdb.StopEvent ):
        return

    try:
        bps = bpev.breakpoints
        bps = gdb.breakpoints()
#        print("bps = '%s'" % (bps,) )
        now = time.time()
        for bp in bps:
#            print("bp = '%s'" % bp )
#            print("bp.number = '%s'" % bp.number )
            tr = trackings.get(bp.number,None)
            if( tr is not None ):
                for t in tr:
                    cont = True
                    t.execute(now)
    except Exception as e:
        print("e = '%s'" % e )
        pass
    if( cont ):
        gdb.post_event(do_continue)

tracking_data = {}



class track_item:

    next_number = 1

    def __init__( self, expr, ue, ea, pe ):
        self.expression = " ".join(expr)
        self.number = track_item.next_number
        self.use_execute = ue
        self.eval_after = ea
        self.python_eval = pe
        track_item.next_number += 1

    def execute( self, now ):
        try:
#            print("self.python_eval = '%s'" % self.python_eval )
#            print("self.use_execute = '%s'" % self.use_execute )
#            print("self.eval_after = '%s'" % self.eval_after )
#            print("self.expression = '%s'" % self.expression )
            if( self.python_eval ):
                val=eval(self.expression)
            elif( self.use_execute ):
                val=gdb.execute(self.expression,False,True)
                if( self.eval_after ):
                    val = gdb.parse_and_eval("$")
            else:
                val=gdb.parse_and_eval(self.expression)
            td = tracking_data.setdefault(now,{})
            td[self.expression] = str(val)
        except Exception as e:
            print("e = '%s'" % e )
#            traceback.print_exc()
            pass

def track( argv, execute, eval_after, do_eval ):
    ex_bp = set()

    bps = gdb.breakpoints()
    for bp in bps:
        ex_bp.add(bp.number)

    try:
        bpnum = int(argv[0])
    except ValueError as e:
        for bp in bps:
            if( bp.location == argv[0] ):
                print("Already have breakpoint with that expression, reusing it")
                bpnum = bp.number
                break
        else:
            print(f"Attempting to set breakpoint for '{argv[0]}'")
            gdb.execute(f"break {argv[0]}")
            n_bp = set()

            bps = gdb.breakpoints()
            for bp in bps:
                n_bp.add(bp.number)
            nbp = n_bp - ex_bp
            if( len(nbp) == 0 ):
                print(f"Failed to set breakpoint for {argv[0]}, cannot attach track either")
                return
            bpnum = nbp.pop()
            ex_bp = n_bp

    expr = argv[1:]

    if( bpnum not in ex_bp ):
        print(f"Unknown breakpoint {bpnum}, refusing to attach track to nothing")
        return

    global trackings
    trackings.setdefault(bpnum,[]).append(track_item( expr, execute, eval_after, do_eval ))


def do_del( argv ):
    for arg in argv:
        num = int(arg)
        found = False
        for bpnum,tracking in trackings.items():
            for track in tracking:
                if( track.number == num ):
                    print(f"Deleted tracking {num}")
                    found = True
                    tracking.remove(track)
                    break
            if( found ):
                break
        if( not found ):
            print(f"Tracking {num} not found")


def show( ):
    bps = gdb.breakpoints()
    ftbl = []
    ftbl.append( [ "Num","Type","Disp","Enb","Address","What","TrackNo","TrackExpr" ] )

    if( len(bps) == 0 ):
        print("No breakpoints or watchpoints.")
        return None

    for bp in bps:
        locs = []
        what = None
#        print("bp = '%s'" % bp )
        if( bp.location is not None ):
            what = bp.location
            unparsed,locs = gdb.decode_line(bp.location)
            if( len(locs) == 1 ):
                addr = locs[0]
                addr = ptr_color(addr.pc)
            else:
                addr = "<MULTIPLE>"
        else:
            addr = None
            what = bp.expression
        ftbl.append( [ bp.number, bp_type(bp.type), bp_disp(bp.temporary), bp_enabled(bp.enabled), addr, what ] )
#        print("locs = '%s'" % (locs,) )
        if( len(locs) > 1 ):
            cnt = 0
            for loc in locs:
                cnt += 1
                ftbl.append( [f"{bp.number}.{cnt}",None,None,bp_enabled(bp.enabled),ptr_color(loc.pc)] )
        tracks = trackings.get(bp.number,None)
        if( tracks is not None ):
            for track in tracks:
                ftbl.append( [None] * 6 + [track.number,track.expression] )

#        print("gdb.decode_line(bp.location) = '%s'" % (gdb.decode_line(bp.location),) )
#        bp.__dict__["stop"] = stop
    ftbl = vdb.util.format_table(ftbl,""," ")
    print(ftbl)


def clear( ):
    global tracking_data
    tracking_data = {}
    print("Cleared all tracking data")

@vdb.event.run()
@vdb.event.start()
def auto_clear( ):
    if( clear_at_start.value is True ):
        clear()


def data( ):
    first = 0
    datatable = []
    datakeys = []
    for tk in sorted(trackings.keys()):
        for tracking in trackings[tk]:
            datakeys.append( tracking.expression )

    datatable.append( ["Time"] + datakeys )
    datatable.append( [] )
    for ts in sorted(tracking_data.keys()):
        if( first == 0 ):
            first = ts
        if( rel_time.value ):
            showts = ts-first
            showts = f"{showts:0.11f}"
        else:
            dt = datetime.datetime.fromtimestamp(ts)
            showts = dt.strftime("%Y.%m.%d %H:%M:%S.%f")
        line = [ showts ]
        tdata = tracking_data[ts]
        for dk in datakeys:
            td = tdata.get(dk,None)
            if( td is None ):
                line.append(None)
            else:
                line.append(td)


        datatable.append( line )

    dt = vdb.util.format_table(datatable)
    print(dt)

class cmd_track (vdb.command.command):
    """Track one or more expressions per breakpoint"""

    def __init__ (self):
        super (cmd_track, self).__init__ ("track", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            execute = False
            eval_after_execute = False
            python_eval = False
            if( argv[0][0] == "/" ):
                argv0 = argv[0][1:]
                argv = argv[1:]

                if( argv0 == "E" ):
                    python_eval = True
                elif( argv0 == "x" ):
                    execute = True
                elif( argv0 == "X" ):
                    execute = True
                    eval_after_execute = True

            if( len(argv) == 0 ):
                show()
            elif( argv[0] == "show" ):
                show()
            elif( argv[0] == "data" ):
                data()
            elif( argv[0] == "del" ):
                do_del(argv[1:])
            elif( argv[0] == "clear" ):
               clear()
            elif( len(argv) > 1 ):
                track(argv,execute,eval_after_execute,python_eval)
            else:
                print("Usage: track [show] or track <num|location> <expression>")
        except:
            traceback.print_exc()
            raise
            pass

cmd_track()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
