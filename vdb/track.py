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
            elif( argv[0] == "set" ):
               init_set( argv[1:] )
            elif( argv[0] == "set.disable" ):
               del_set( argv[1:] )
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


track_storage = {}


class finish_breakpoint( gdb.FinishBreakpoint ):

    def __init__( self, frame, action ):
        super( finish_breakpoint, self).__init__(frame,True)
        self.action = action

    def stop( self ):
        self.action.fin_action( self.return_value )
        self.action.fin_bp = None
        return False

class track_action:

    # returns a gdb value or python result for the expression, depending on the type. Expression can end in /x or so.
    # Returns None when the expression returned none, or when the expression was $ret (return value special case)
    def get( self, expression, way = None ):
#        print("get()")
#        print("expression = '%s'" % (expression,) )
#        print("way = '%s'" % (way,) )
        if( expression[-2] == "/" ):
            way = expression[-1]
            expression = expression[:-2]

        if( way is None ):
            way = "v"

        ret = None
        if( expression == "$ret" ):
            return None

        if( way == "x" ):
            #gdb.execute => gdb.Value
            ret = gdb.execute(expression,False,True)
        elif( way == "X" ):
            #gdb.execute => gdb parse_and_eval($)
            gdb.execute(expression,False,True)
            ret = gdb.parse_and_eval("$")
        elif( way == "E" ):
            #python.run() => python result
            ex = expression
            if( ex.find("$(") != -1 ):
                ex = ex.replace( "$(", "gdb.parse_and_eval(" )
            ret=eval(ex,globals())
        elif( way == "v" ):
            # frame.value() => gdb.value
            frame = gdb.newest_frame() # maybe get the frame from the breakpoint object?
#            print("frame = '%s'" % (frame,) )
            ret = frame.read_var(expression)
        elif( way == "p" ):
            # gdb.parse-and_eval() => gdb.value
            ret = gdb.parse_and_eval(expression)
        else:
            raise Exception("Unknown type to get result: %s" % way )
        return ret

    def getn( self, expression, way = None ):
        try:
            return self.get(expression,way)
        except:
            return None


class filter_track_action(track_action):

    def __init__( self, filter_list, location, prefix, parameters ):
#        print("filter_list = '%s'" % (filter_list,) )
        ftype = filter_list[0]
        self.prefix = prefix
        if( ftype == "cmp" ):
            val = filter_list[1]
            ex = filter_list[2]
            if( val[0] == "{" and val[-1] == "}" ):
                pkey = val[1:-1]
                pval = parameters.get(pkey,None)
                if( pval is None ):
                    raise Exception("Need parameter %s in enable call" % pkey)
                self.value = pval
            else:
                self.value = val
            self.expression = ex
            self.compto = self.compare_to_value
        elif( ftype == "map" ):
            cmpmap = filter_list[1]
            ex = filter_list[2]

            self.expression = ex
            self.value_map = cmpmap
            self.compto = self.compare_to_map
        else:
            raise Exception("Unknown filter type %s" % ftype)

    def compare_to_value( self, rval ):
        lval = self.value
        # value is not available. Since we maybe want two filters accessing the same value in different ways, we ignore
        # that case here. One day we may want to add a facility for the user to specify
        if( lval is None or rval is None ):
            return True

        lval,rval = self.refine( lval,rval )
#        print("lval = '%s'" % (lval,) )
#        print("rval = '%s'" % (rval,) )

#        print("type(lval) = '%s'" % (type(lval),) )
#        print("type(rval) = '%s'" % (type(rval),) )
        return ( lval == rval )

    def compare_to_map( self, rval ):
#        print("track_storage = '%s'" % (track_storage,) )
#        print("self.prefix = '%s'" % (self.prefix,) )
#        print("rval = '%s'" % (rval,) )
        if( rval is None ):
            return True

        storage = track_storage.get( self.prefix, None )
#        print("storage = '%s'" % (storage,) )
        if( storage is not None ):
            setstorage = storage.get( self.value_map, None )
            for lval in setstorage:
#                print("lval = '%s'" % (lval,) )
                el,er = self.refine( lval, rval )
                if( el == er ):
                    return True
        return False

    def refine( self, lval, rval ):
        # Either we can convert both to double, or both to string, or leave both as if. Only converting one is not
        # possible
        # XXX in case we have two python result objects that convert to strings but we want to leave them as-is, what do
        # we do? The conversion is mainly for gdb results as string or gdb.Value and other incompatibilities
        try:
            d_l = float(lval)
            d_r = float(rval)
            return ( d_l, d_r )
        except:
            try:
                # nah, didn't work, lets try strings, that usually works
                s_l = str(lval)
                s_r = str(rval)
                return ( s_l, s_r )
            except:
                # ok, didn't work either, leave as is
                return ( lval, rval )


    def action( self ):
#        print("filter track action()")
#        print("track_storage = '%s'" % (track_storage,) )
        rval = self.getn( self.expression )
        ret = self.compto(rval)
        return ret

 
class store_track_action(track_action):

    def __init__( self, store_list, location, prefix ):
        vdb.util.requires( len(store_list) == 2, "store action parameter list must have exactly 2 parameters, has %s" % len(store_list) )
        self.expression = store_list[0]
        self.storage_map = store_list[1]
        self.map_key = prefix

    def action( self ):
        val = self.get( self.expression )

        global track_storage
        store = track_storage.setdefault( self.map_key, {} )
        storeset = store.setdefault(self.storage_map,set())
        storeset.add( val )
#        print(f"{self.expression} = {val} => {self.storage_map}")
#        print("track_storage = '%s'" % (track_storage,) )
        return True

class delete_track_action:

    def __init__( self, del_list, location, prefix ):
        self.expression = del_list[0]
        self.storage_map = del_list[1]
        self.map_key = prefix

    def action( self ):
#        print("delete action()")
        store = track_storage.setdefault( self.map_key, {} )
#        print("self.map_key = '%s'" % (self.map_key,) )
#        print("store = '%s'" % (store,) )
        if( store is not None ):
#            print("self.storage_map = '%s'" % (self.storage_map,) )
            storeset = store.get(self.storage_map,None)
#            print("storeset = '%s'" % (storeset,) )
            if( storeset is not None ):
                val = self.get( self.expression )
#                print("val = '%s'" % (val,) )
#                print("storeset = '%s'" % (storeset,) )
                storeset.discard( val )
#                print("storeset = '%s'" % (storeset,) )
        return True

class hexdump_track_action( track_action ):

    def __init__( self, location, tuple_list ):
        print(f"hexdump_track_action with {len(tuple_list)} alternatives:")
        self.address = None
        self.length  = None
        self.tuple_list = tuple_list
        self.buffer = None
        self.size = None
        self.buffer_expression = None
        self.size_expression = None
        self.location = location
        for buf,sz in tuple_list:
            print(f"hexdump({buf},{sz})")

    def dump( self ):
        ps,pu = vdb.pointer.chain( self.buffer, vdb.arch.pointer_size, 3, test_for_ascii = True )
#        print("ps = '%s'" % (ps,) )
#        print("pu = '%s'" % (pu,) )
        print(f"{self.location} : {self.buffer_expression} = {ps}, {self.size_expression} = {self.size}");
        vdb.hexdump.hexdump( self.buffer, self.size )
    # called on breakpoint hit
    # 
    def action( self ):
#        print("hexdump.action()")
        for buf,sz in self.tuple_list:
            try:
#                print("buf = '%s'" % (buf,) )
#                print("sz = '%s'" % (sz,) )
                self.buffer = self.get( buf )
                self.size = self.get(sz)
                self.buffer_expression = buf
                self.size_expression = sz

#                print("self.buffer_expression = '%s'" % (self.buffer_expression,) )
#                print("self.size_expression = '%s'" % (self.size_expression,) )
            except:
                traceback.print_exc()
                # ok, something went wrong, silently ignore it and try the next tuple
                pass
            break
        if( self.buffer_expression == "$ret" or self.size_expression == "$ret" ):
            # neeed a "fin action"
            return None
        else:
            self.dump()
            return True
    
    # called (optionally) on finish
    def fin_action( self, retval ):
#        print("fin_action")
#        print("retval = '%s'" % (retval,) )
        if( self.buffer_expression == "$ret" ):
            self.buffer = retval
        if( self.size_expression == "$ret" ):
            self.size = retval
#        self.finbp.delete()
        self.dump()

class track_breakpoint( gdb.Breakpoint ):

    def __init__( self, location, track_item ):
        super( track_breakpoint, self ).__init__(location)
        self.track_item = track_item
#        print("track_item = '%s'" % (track_item,) )
#        print("location = '%s'" % (location,) )

    def stop( self ):
#        print("track_breakpoint.stop()")
        self.track_item.stop()
        return False

class extended_track_item:

    def __init__( self, location, action_list, prefix, parameters ):
#        print("Extended Track Item:")
#        print(f"Location: {location}")
#        print(f"{len(action_list)} action items...")
        self.actions = []
        for action,param in action_list:
#            print(f"Action '{action}' with {len(param)} parameters")
            ai = None
            if( action == "hex" ):
                ai = hexdump_track_action( location, param )
            elif( action == "filter" ):
                ai = filter_track_action( param, location, prefix, parameters )
            elif( action == "store" ):
                ai = store_track_action( param, location, prefix )
            elif( action == "delete" ):
                ai = delete_track_action( param, location, prefix )
            else:
                print(f"Unknown action item {action}")
            if( ai is not None ):
                self.actions.append(ai)
        self.bp = track_breakpoint( location, self )

    def clear( self ):
        self.bp.delete()
        self.bp = None

    def stop( self ):
#        print("eti.stop()")
#        gdb.execute("bt")
        for ai in self.actions:
            # @returns true if all went fine, false if it went wrong, and None if we need to call fin_action
            # For filter actions this basically means true when the filter could match, False if it didn't. 
            # So in case of a false, we break, either because of a non matching filter, or because something went too
            # wrong to continue
            ret = ai.action()
#            print("ret = '%s'" % (ret,) )
            if( ret is False ):
                break
            if( ret is None ):
                frame = gdb.newest_frame()
                ai.fin_bp = finish_breakpoint( frame, ai )

#
# track set = A dictionary location/function : [ list of action items ]
# action item = tuple of action type and a single item of parameters for that action  (typically a list)
# - different actions:

# hex : takes list of pairs to dump. They are alternatives for getting the same information, that is when one fails due
# to exception, only then the next in the list is used

# store : stores an expression in a set (?) for later retrieval through filters
# delete : deletes from a store (if possible) ?

# track : tracks this item/expression (just as it would be in a standard track expression) (XXX: How to specify # execute/parse/python ?

# filter : aborts handling of the list of actions when the filter is "false". Contains different types of "filter # expressions"
#       - cmp : compares one (user supplied) value to an expression of some kind. Or Two expressions even?
#       - map : compares if the value is in a named map (previously stored via some other action?)


# XXX maybe... cmp/xXE should work the same as for track for cmp/track/store/hex/etc ? should mixing of types be
# possible here? maybe then as cmp/xXx means x for #0, X for #1 and x for #2 ?
# more clear would be /x at the end of the expression. If the expression itself needs to end on /x just do /x/x (or
# whatever type of evaluation you need)
# XXX very future idea: sometimes you may want to check a passed by non-const reference parameter at the point of the
# function return, maybe we want to support that too? 

ssl_set = {
            "SSL_read" : # A function/location to set the breakpoint
                [   # a list of "actions" with their parameters, a non matching "filter" will stop evaluation
                    ( "filter", [ "map", "ssl_fd_filter", "s->rbio->num" ] ),
                    ( "hex", [
                            ( "buf", "$ret" ), # hex expects address and length
                            ( "$rdi", "$ret" ) # only if the above doesn't work, try to fall back to these
                            ]
                            ),
                ],
            "SSL_write" : [ ( "hex", [ ( "buf", "num" ), ( "$rdi", "$rsi" ) ] ) ],
            "connect" : [
#                    ( "filter", [ "cmp", "{port}", "ntohs( ((sockaddr_in*)addr)->sin_port )" ] ),
                    ( "filter", [ "cmp", "{port}", "ntohs( ((uint16_t*)addr)[1] )/p" ] ),
                    ( "filter", [ "cmp", "{ip}", "( ((sockaddr_in*)addr)->sin_addr)" ] ),
                    ( "store", [ "fd", "ssl_fd_filter" ] )
                ],
            "close" : [
                    ( "delete", [ "fd", "ssl_fd_filter" ] )
                ]
            }

sets = { "ssl" : ssl_set }

set_data = {}
def init_set( argv ):
    setname = argv[0]
    paramlist = argv[1:]
    tset = sets.get(setname,None)

    global set_data
    eset = set_data.get( setname, None )
    if( eset ):
        print("Set '%s' already enabled, overwriting with new filters" % setname )
        del_set( argv[:1] )

    etis = []
    set_data[ setname ] = etis

    # XXX later support some "disable" commands
#    print("argv = '%s'" % (argv,) )
    if( tset is None ):
        print("Could not find set '%s'" % setname )
    parameters = {}
    for a in paramlist:
        try:
            k,v = a.split("=")
        except:
            print("Failed to parse %s, expecting key=value format" % a )
            return
#        print("k = '%s'" % (k,) )
#        print("v = '%s'" % (v,) )
        parameters[k] = v

    for k,v in ssl_set.items():
        eti = extended_track_item( k, v, setname + ".", parameters )
        etis.append(eti)
    print("Enabled set '%s'" % setname)

def del_set( argv ):
    setname = argv[0]
    etis = set_data.get(setname,None)
    if( etis is None ):
        print("Set '%s' not found, cannot disable" % setname)
        return

    for ei in etis:
        ei.clear()

    etis.clear()
    del set_data[setname]

    print("Disabled set '%s'" % setname)
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
