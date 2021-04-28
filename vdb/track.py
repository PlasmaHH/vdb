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

#def stop( bp ):
#    print("bp = '%s'" % bp )
#    return False

def ptr_color( addr ):
    try:
        ret = vdb.pointer.color(addr,vdb.arch.pointer_size)
        ret = ( ret[0], ret[4] )
    except:
        ret = addr
    return ret

class stoppoint:

    def __init__( self ):
        self.number = None
        self.key = ( None, None )
        self.type = None
        self.address = None
        self.location = None
        self.expression = None
        self.temporary = None
        self.enabled = None
        self.what = None
        self.subpoints = {}
        self.inferior = None

    def get_type( self ):
        return bp_type(self.type)

    def get_temporary( self ):
        return bp_disp(self.temporary)

    def get_enabled( self ):
        return bp_enabled(self.enabled)

    def _dump( self ):
        print("Dump SP")
        print("self.number = '%s'" % self.number )
        print("self.key = '%s'" % (self.key,) )
        print("self.type = '%s'" % self.type )
        print("self.address = '0x%x'" % self.address )
        print("self.location = '%s'" % self.location )
        print("self.expression = '%s'" % self.expression )
        print("self.temporary = '%s'" % self.temporary )
        print("self.enabled = '%s'" % self.enabled )
        print("self.what = '%s'" % (self.what,) )
        if( len(self.subpoints) > 0 ):
            print("Dump Sub SP")
            for sbk,sbp in self.subpoints.items():
                print("sbk = '%s'" % sbk )
                sbp._dump()
        print("END SP")

# XXX Check speed, we should cache it and react on certain events to refresh it, as potentially this is called with
# every breakpoint
def parse_breakpoints( ):
    rawmib = gdb.execute( "maint info break", False, True ).split("\n")
    foo = """
Num     Type                  Disp Enb Address            What
1       breakpoint            keep y   0x0000000000402233 in main(int, char const**) at vtrack.cxx:30 inf 1
        breakpoint already hit 1 time
1.1                                y   0x0000000000402233 in main(int, char const**) at vtrack.cxx:30 inf 1
-1      shlib events          keep n   0x00007ffff7fd0101 <dl_main+7169> inf 1
-1.1                               y   0x00007ffff7fd0101 <dl_main+7169> inf 1

"""
    mib = {}
    for mi in rawmib:
        mi = mi.split()
#        print("mi = '%s'" % mi )
        if( len(mi) == 0 or mi[0] == "Num" ):
            continue
        mk = mi[0].split(".")
        if( not mk[0].isdigit() ):
            continue
        if( len(mk) == 1 ):
            mk = (mk[0], None )
        else:
            mk = (mk[0], mk[1] )
        mib[mk] = mi

    ret = {}
    import vdb
    if( vdb.enabled("backtrace") ):
        import vdb.backtrace

    for mk,mi in mib.items():
#        print("mk = '%s'" % (mk,) )
#        print("mi = '%s'" % mi )
        if( mk[0][0] == "-" ):
            continue

        sp = stoppoint()
        sp.key = mk
        sp.number = mi[0]

        ixplus = 0
        if( mk[1] is None ):
            ixplus = 2
        else:
            ixplus = 0
        sp.address = vdb.util.mint(mi[2+ixplus])
        sp.enabled = (mi[1+ixplus] == "y")
        sp.what = " ".join(mi[3+ixplus:])

#        print("sp.what = '%s'" % sp.what )
        m = re.match("in (.*) at (.*):([0-9]*) inf ([0-9]*)",sp.what)
        if( m ):
            plain = ""
            color = ""

            plain = "in "
            plain += m.group(1)
            plain += " at "
            plain += m.group(2)
            plain += ":"
            plain += m.group(3)
            sp.what = plain
            if( vdb.enabled("backtrace") ):
                color = "in "
                color += vdb.color.color(m.group(1),vdb.backtrace.color_function.value)
                color += " at "
                color += vdb.color.color(m.group(2),vdb.backtrace.color_filename.value)
                color += ":"
                color += m.group(3)
                sp.what = (color,len(plain))

            sp.inferior = m.group(4)
        else:
            m = re.match(".*inf ([0-9]*)",sp.what)
            if( m ):
                sp.inferior = m.group(1)

#        print("sp.number = '%s'" % sp.number )
#        print("type(sp.number) = '%s'" % type(sp.number) )
        ret[sp.number] = sp

#    print("ret = '%s'" % ret )
    bps = gdb.breakpoints()
    for bp in bps:
#        print("type(bp.number) = '%s'" % type(bp.number) )
        sp = ret.get(str(bp.number))
#        print("bp.number = '%s'" % bp.number )
#        print("sp = '%s'" % sp )
#        print("bp = '%s'" % bp )
        sp.type = bp.type
        sp.enabled = bp.enabled
        sp.temporary = bp.temporary
        sp.location = bp.location
        sp.expression = bp.expression

        if( sp.address is None ):
            unparsed,locs = gdb.decode_line(bp.location)
            if( len(locs) == 1 ):
                addr = locs[0]
                addr = addr.pc
            else:
                addr = "<MULTIPLE>"

            sp.address = addr

        for i in range(1,1000):
            sk = "%s.%s" % ( sp.number , i )
            esp = ret.get(sk,None)
            if( esp is None ):
                break
            sp.subpoints[sk] = esp
            del ret[sk]

#    print("Dump RET")
#    for k,r in ret.items():
#        print("")
#        r._dump()
    return ret    



trackings = { }
do_sub_trackings = False

def do_continue( ):
    gdb.execute("continue")

def exec_tracking( number, now ):
    cont = False
    tr = trackings.get(str(number),None)
    if( tr is not None ):
        for t in tr:
            cont = True
            t.execute(now)
    return cont        

@vdb.event.stop()
def stop( bpev ):
#    print("TRACK STOP")
    cont = False
    if( len(trackings) == 0 ):
        return

    now = time.time()
    try:
        if( do_sub_trackings ):
            pc = vdb.util.gint("$pc")

            tbps = parse_breakpoints()
            for tbp in tbps.values():
                for sbp in tbp.subpoints.values():
                    if( sbp.address == pc ):
                        if( exec_tracking(sbp.number,now) ):
                            cont = True
    except Exception as e:
        print("e = '%s'" % e )
        pass


    try:
        if( type(bpev) == gdb.StopEvent ):
            return
        else:
            bps = bpev.breakpoints
#            print("bps = '%s'" % (bps,) )
            for bp in bps:
#                print("bp = '%s'" % bp )
#                print("bp.number = '%s'" % bp.number )
                if( exec_tracking(bp.number,now) ):
                    cont = True
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

#    bps = gdb.breakpoints()
    bps = parse_breakpoints()
    for _,bp in bps.items():
        ex_bp.add(bp.number)
        for _,sbp in bp.subpoints.items():
            ex_bp.add(sbp.number)

#    print("argv[0] = '%s'" % argv[0] )
    bpnum = None
    for _,bp in bps.items():
#        print("bp.number = '%s'" % bp.number )
        if( bp.number == argv[0] ):
            bpnum = bp.number
            break
        if( bp.location == argv[0] ):
            print("Already have breakpoint with that expression, reusing it")
            bpnum = bp.number
            break
        for _,sbp in bp.subpoints.items():
#            print("sbp.number = '%s'" % sbp.number )
            if( sbp.number == argv[0] ):
                bpnum = sbp.number
                break
        if( bpnum is not None ):
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
        ex_bp = n_bp
        bpnum = nbp.pop()
#    print("bpnum = '%s'" % bpnum )

    expr = argv[1:]

    if( bpnum not in ex_bp ):
        print(f"Unknown breakpoint {bpnum}, refusing to attach track to nothing")
        return

    global trackings
    trackings.setdefault(str(bpnum),[]).append(track_item( expr, execute, eval_after, do_eval ))
    cleanup_trackings()

def cleanup_trackings( ):
    global trackings
    newtrackings = {}
    subcount = 0
    for tk,tr in trackings.items():
        if( not tk.isdigit() ):
            subcount += 1
        if( len(tr) > 0 ):
            newtrackings[tk] = tr
    trackings = newtrackings
    global do_sub_trackings
    if( subcount == 0 ):
        do_sub_trackings = False
    else:
        do_sub_trackings = True

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
    cleanup_trackings()

def show_track( ftbl, number ):
    tracks = trackings.get(str(number),None)
    if( tracks is not None ):
        for track in tracks:
            ftbl.append( [None] * 7 + [track.number,track.expression] )

def show( ):

    parse_breakpoints()
    bps = parse_breakpoints()
    ftbl = []
    ftbl.append( [ "Num","Type","Disp","Enb","Address","What","Inferior","TrackNo","TrackExpr" ] )

    if( len(bps) == 0 ):
        print("No breakpoints, catchppoints or watchpoints.")
        return None

    for _,bp in bps.items():
        ftbl.append( [ bp.number, bp.get_type(), bp.get_temporary(), bp.get_enabled(), ptr_color(bp.address), bp.what, bp.inferior ] )
        show_track(ftbl,bp.number)

        for _,sbp in bp.subpoints.items():
            ftbl.append( [ sbp.number, None, None, sbp.get_enabled(), ptr_color(sbp.address), sbp.what, bp.inferior ] )
            show_track(ftbl,sbp.number)

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
