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


bptypes = { 
        gdb.BP_BREAKPOINT : "breakpoint",
        gdb.BP_HARDWARE_WATCHPOINT : "hw watchpoint",
        gdb.BP_READ_WATCHPOINT : "read watchpoint",
        gdb.BP_ACCESS_WATCHPOINT : "access watchpoint",
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
    cont = False
    try:
        bps = bpev.breakpoints
        now = time.time()
        for bp in bps:
#            print("bp = '%s'" % bp )
#            print("bp.number = '%s'" % bp.number )
            tr = trackings.get(bp.number,None)
            if( tr is not None ):
                cont = True
                for t in tr:
                    t.execute(now)
    except Exception as e:
        print("e = '%s'" % e )
        pass
    if( cont ):
        gdb.post_event(do_continue)

tracking_data = {}

class track_item:

    def __init__( self, expr ):
        self.expression = " ".join(expr)

    def execute( self, now ):
        try:
            val=gdb.parse_and_eval(self.expression)
            td = tracking_data.setdefault(now,{})
            td[self.expression] = str(val)
        except:
            pass

def track( argv ):
    bpnum = int(argv[0])
    expr = argv[1:]

    global trackings
    trackings.setdefault(bpnum,[]).append(track_item( expr ))


def show( ):
    bps = gdb.breakpoints()
    ftbl = []
    ftbl.append( [ "Num","Type","Disp","Enb","Address","What" ] )

    if( len(bps) == 0 ):
        print("No breakpoints or watchpoints.")
        return None

    for bp in bps:
#        print("bp = '%s'" % bp )
        unparsed,locs = gdb.decode_line(bp.location)
        if( len(locs) == 1 ):
            addr = locs[0]
            addr = ptr_color(addr.pc)
        else:
            addr = "<MULTIPLE>"
        ftbl.append( [ bp.number, bp_type(bp.type), bp_disp(bp.temporary), bp_enabled(bp.enabled), addr, bp.location ] )
#        print("locs = '%s'" % (locs,) )
        if( len(locs) > 1 ):
            cnt = 0
            for loc in locs:
                cnt += 1
                ftbl.append( [f"{bp.number}.{cnt}",None,None,None,ptr_color(loc.pc)] )

#        print("gdb.decode_line(bp.location) = '%s'" % (gdb.decode_line(bp.location),) )
#        bp.__dict__["stop"] = stop
    ftbl = vdb.util.format_table(ftbl,""," ")
    print(ftbl)

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
            if( len(argv) == 0 ):
                show()
            elif( argv[0] == "show" ):
                show()
            elif( argv[0] == "data" ):
                data()
            elif( len(argv) > 1 ):
                track(argv)
            else:
                print("Usage: track [show] or track <num> <expression>")
        except:
            traceback.print_exc()
            raise
            pass

cmd_track()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
