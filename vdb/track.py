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

    previous_type = None
    for mk,mi in mib.items():
#        print("mk = '%s'" % (mk,) )
#        print("mi = '%s'" % mi )
        if( mk[0][0] == "-" ):
            continue

        sp = stoppoint()
        sp.key = mk
        sp.number = mi[0]

        ixplus = 0
        address_there = True
        if( mk[1] is None ):
            ixplus = 2
            sp.type = mi[1]
            if( sp.type == "hw" ):
                sp.type += " " + mi[2]
                mi[1] += " " + mi[2]
                del mi[2]
                address_there = False

            previous_type = sp.type
            sp.temporary = mi[2]
        else:
            ixplus = 0
        sp.enabled = (mi[1+ixplus] == "y")
#        print("sp.type = '%s'" % sp.type )

        if( sp.type == "catchpoint" or sp.type == "watchpoint" ):
            address_there = False
        if( previous_type == "watchpoint" ):
            address_there = False

        if( address_there ):
            sp.address = vdb.util.mint(mi[2+ixplus])
        else:
            ixplus -= 1
            sp.address = ""
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
            m = re.match("(.*) inf ([0-9]*)",sp.what)
            if( m ):
                sp.what = m.group(1)
                sp.inferior = m.group(2)

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


# the tracking.number integer
trackings_by_number = { }
# the bpid string ( maybe 1 or 1.1 or something )
trackings_by_bpid = { }
do_sub_trackings = False

def do_continue( ):
    gdb.execute("continue")

def by_id( bpid ):
    return trackings_by_bpid.get(bpid,[])

def by_number( num ):
    t = trackings_by_number.get(num,None)
    if( t is None ):
        return []
    else:
        return [t]

def exec_tracking( tr , now ):
    cont = False

    if( tr is not None ):
        for t in tr:
            cont = True
            t.execute(now)
    return cont        

def exec_tracking_id( bpid , now ):
    tr = by_id(bpid)
    return exec_tracking( tr, now)

def exec_tracking_number( number, now ):
    tr = by_number( number )
    return exec_tracking( tr, now)

@vdb.event.stop()
def stop( bpev ):

    cont = False
    if( len(trackings_by_number) == 0 ):
        return

    now = time.time()
    try:
        if( do_sub_trackings ):
            pc = vdb.util.gint("$pc")

            tbps = parse_breakpoints()
            for tbp in tbps.values():
                for sbp in tbp.subpoints.values():
                    if( sbp.address == pc ):
                        if( exec_tracking_id(sbp.number,now) ):
                            cont = True
    except Exception as e:
        print("e = '%s'" % e )
#        traceback.print_exc()
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
                if( exec_tracking_id(str(bp.number),now) ):
                    cont = True
    except Exception as e:
        print("e = '%s'" % e )
#        traceback.print_exc()
        pass
    if( cont ):
        gdb.post_event(do_continue)

tracking_data = {}



class track_item:

    next_number = 1

    def __init__( self, expr, ue, ea, pe, name = None ):
        self.expression = " ".join(expr)
        self.number = track_item.next_number
        self.name = name
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
                ex = self.expression
                if( ex.find("$(") != -1 ):
                    ex = ex.replace( "$(", "gdb.parse_and_eval(" )
                val=eval(ex,globals())
            elif( self.use_execute ):
                val=gdb.execute(self.expression,False,True)
                if( self.eval_after ):
                    val = gdb.parse_and_eval("$")
            else:
                val=gdb.parse_and_eval(self.expression)
            td = tracking_data.setdefault(now,{})
#            td[self.expression] = str(val)
            td[self.number] = str(val)
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

    ename = None
    if( len(argv) > 1 and argv[1] == "=" ):
        ename = argv[0]
        argv = argv[2:]
    elif( argv[0][-1] == "=" ):
        ename = argv[0][:-1]
        argv = argv[1:]

    print("ename = '%s'" % (ename,) )

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

    global trackings_by_bpid
    global trackings_by_number

    nti = track_item( expr, execute, eval_after, do_eval , ename)
#    trackings.setdefault(str(bpnum),[]).append(track_item( expr, execute, eval_after, do_eval ))
    trackings_by_bpid.setdefault(str(bpnum),[]).append( nti )
    trackings_by_number[nti.number] = nti
    cleanup_trackings()

def cleanup_trackings( ):
    global trackings_by_bpid
    newtrackings = {}
    subcount = 0
    for tk,tr in trackings_by_bpid.items():
        if( not tk.isdigit() ):
            subcount += 1
        if( len(tr) > 0 ):
            newtrackings[tk] = tr
    trackings_by_bpid = newtrackings
    global do_sub_trackings
    if( subcount == 0 ):
        do_sub_trackings = False
    else:
        do_sub_trackings = True

def do_del( argv ):
    for arg in argv:
        num = int(arg)
        found = False
        for bpnum,tracking in trackings_by_bpid.items():
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
        else:
            del trackings_by_number[num]
    cleanup_trackings()

def show_track( ftbl, number ):
    tracks = trackings_by_bpid.get(str(number),None)
    if( tracks is not None ):
        for track in tracks:
            ftbl.append( [None] * 7 + [track.number,track.name,track.expression] )

def show( ):

    parse_breakpoints()
    bps = parse_breakpoints()
    ftbl = []
    ftbl.append( [ "Num","Type","Disp","Enb","Address","What","Inferior","TrackNo","TrackName","TrackExpr" ] )

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

    dataexpressions = []
    datanames = []
    names = 0
    for tk in sorted(trackings_by_number.keys()):
        for tracking in by_number(tk):
            dataexpressions.append( tracking.expression )
            datanames.append( tracking.name )
            if( tracking.name ):
                names += 1

    if( names > 0 ):
        datatable.append( ["Name"] + datanames )
    datatable.append( ["Time"] + dataexpressions )
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
#        print("tdata = '%s'" % (tdata,) )
        for dk in trackings_by_number.keys():
#            print("dk = '%s'" % (dk,) )
            td = tdata.get(dk,None)
            if( td is None ):
                line.append(None)
            else:
                line.append(td)


        datatable.append( line )

    dt = vdb.util.format_table(datatable)
    print(dt)

class cmd_track (vdb.command.command):
    """Track one or more expressions per breakpoint

track/[ExX] <id|location> <expression>

track   - pass expression to parse_and_eval
track/E - interpret expression as python code to evaluate
track/x - execute expression and use resulting gdb value
track/X - execute expression and then run parse_and_eval on the result ($)
track/s - work with tracking sets (see documentation for them)

id           is the id of an existing breakpoint
location    can be any location that gdb understands for breakpoints
expression  is the expression expected by any of the above formats. Upon hitting the breakpoint, it will be evaluated and then automatically continued. The special expression $ret is used to denote a return value of a finish expression.

If no breakpoint can be found with an existing location, we try to set one at that location, otherwise we try to re-use the same location
Note: while it works ok for breakpoints and watchpoints, using catchpoints is somewhat difficult and often does not work

Available subcommands:
show     - show a list of trackpoints (similar to info break)
data     - show the list of data collected so far
clear    - clear all data collected so far 
del <id> - delete the trackpoint with the given trackpoint id

You should have a look at the data and graph modules, which can take the data from here and draw graphics and histograms
"""

    def __init__ (self):
        super (cmd_track, self).__init__ ("track", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            execute = False
            eval_after_execute = False
            python_eval = False
            if( len(argv) > 0 and argv[0][0] == "/" ):
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
                print (self.__doc__)
        except:
            traceback.print_exc()
            raise
            pass

cmd_track()

"""
Notes for track sets
X - need generic feature giving columns a name independent from the expression
- add a feature to generically get the return value of a "finish" expression of a breakpoint
- a set contains advanced track expressions for multiple functions that act together
  - these expresions have a "display" method, like hexdump of a buffer
  - each expression yields one or more values for the track record (like buffer size)
  - maybe we can even find a generic way to sort the calls into multiple contexts (e.g. per ssl connection?)
  - all the hexdump etc. output is displayed, saved or both
First example is SSL:
    SSL_write(buf,num): easy, just variables
    SSL_read(buf) => num, needs the return value feature
    SSL context object "s" to figure out the connection. s->rbio->num is the socket maybe?
hex/xyz showspec should be supported and also implemented in the hexdump module directly. default the fastest possible
"""

ssl_set = { 
            "SSL_read" : # A function/location to set the breakpoint
                [   # a list of "actions" with their parameters, a non matching "filter" will stop evaluation
                    ( "filter", [ "set", "ssl_fd_filter", "s->rbio->num" ] ),
                    ( "hex",
                            [ "buf", "$ret" ], # hex expects address and length
                            [ "$rdi", "$rsi" ] # only if the above doesn't work, try to fall back to these
                            ),
                ],
            "SSL_write" : [ ( "hex", [ "buf", "num" ], ["$rdi", "$rsi" ] ) ],
            "connect" : [
                    ( "filter", [ "cmp", "{port}", "ntohs( ((sockaddr_in*)addr)->sin_port )" ] ),
                    ( "filter", [ "cmp", "{ip}", "( ((sockaddr_in*)addr)->sin_addr)" ] ),
                    ( "store", [ "fd", "ssl_fd_filter" ] )
                ]
            }

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
