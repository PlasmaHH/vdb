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
import struct




rel_time = vdb.config.parameter("vdb-track-time-relative",True)
clear_at_start = vdb.config.parameter("vdb-track-clear-at-start",True)
sleep_time = vdb.config.parameter("vdb-track-interval-sleep",0.00)
sync_second = vdb.config.parameter("vdb-track-interval-sync-to-second",True)
skip_long = vdb.config.parameter("vdb-track-skip-long-intervals",False)


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

def wait( t ):
#    time.sleep(10)
    return
    for i in range(0,t):
        print(f"{t-i}...")
        time.sleep(1)

continues = 0

def schedule_continue( ):
#    vdb.util.bark() # print("BARK")
    global continues
    if( continues == 0 ):
#        vdb.util.bark() # print("BARK")
        continues += 1
        gdb.post_event(do_continue)

def do_continue( ):
#    vdb.util.bark() # print("BARK")
    wait(5)
    global continues
#    print("continues = '%s'" % (continues,) )
    continues -= 1
#    print("GDB EXECUTE CONTINUE")
    try:
        traceback.print_exc()
        gdb.execute("continue")
    # somehow we schedule two of them, for now just suppress the error
    except gdb.error:

        pass

def schedule_finish( ):
    global continues
    if( continues == 0 ):
        continues += 1
        gdb.post_event(do_finish)

def do_finish( ):
    wait(5)
    global continues
#    print("continues = '%s'" % (continues,) )
    continues -= 1
#    print("GDB EXECUTE finish")
    try:
        gdb.execute("finish")
    # somehow we schedule two of them, for now just suppress the error
    except gdb.error:
        pass



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
#    vdb.util.bark() # print("BARK")
#    print("bpev = '%s'" % (bpev,) )
#    print("bpev.inferior_thread = '%s'" % (bpev.inferior_thread,) )

    # hack to not endlessly loop on arm systems
    archname = gdb.selected_frame().architecture().name()
    if( archname.startswith("arm") ):
        pc = vdb.util.gint("$pc")
        if( pc >= 0xeffffffe ):
            print("ARM Lockup state detected, refusing track commands")
            return False


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
            vdb.util.bark() # print("BARK")
            if( exec_tracking_id("0",now) ):
                cont = True
            print("cont = '%s'" % (cont,) )
            # hack for catching possibly inlined return cases..
            for name,tr in trackings_by_number.items():
                if ( name < 0 ):
                    if( isinstance( tr, finish_breakpoint ) ):
                        tr.stop()
#            return False
        elif( type(bpev) == gdb.SignalEvent ):
            pass
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
#    vdb.util.bark() # print("BARK")
#    print("cont = '%s'" % (cont,) )

    if( cont ):
        schedule_continue()
#        gdb.post_event(do_continue)

tracking_data = {}

class pseudo_item:

    def __init__( self, name, expression, number ):
        self.name = name
        self.expression = expression
        self.number = number

class track_item:

    next_number = 1

    def get_next_number( ):
        ret = track_item.next_number
        track_item.next_number += 1
        return ret

    def __init__( self, expr, ue, ea, pe, name = None, pack_expression = None, unify = False ):
#        self.expression = " ".join(expr)
        self.expression = expr
        self.number = track_item.get_next_number()
        self.name = name
        self.use_execute = ue
        self.eval_after = ea
        self.python_eval = pe
        self.unify = unify
        self.has_array = False
        self.array_pre = None
        self.array_size = None
        self.array_post = None
        self.pack_expression = pack_expression
        self.pack_ids = {}
        self.seen_ids = set()
        if( self.unify ):
            # so far we only support struct packs for this
            names,_ = unpack_prepare(self.pack_expression)
            if( not "ID" in names ):
                raise RuntimeError(f"To unify pack expressions, we need a field called ID, fields specified: {names}")
        if( self.pack_expression is not None ):
            names,fullspec = unpack_prepare(self.pack_expression)
            global trackings_by_number
            for n in names:
                nn = track_item.get_next_number()
                self.pack_ids[n] = nn
                trackings_by_number[nn] = pseudo_item(n,self.expression,nn)

        if( self.python_eval ):
            self.expression = self.expression.replace( "$(", "gdb.parse_and_eval(" )
        elif( not self.use_execute ):
            m = re.match("(.*)\[@([0-9]*)\](.*)",self.expression)
            if( m is not None ):
                self.array_pre = m.group(1)
                self.array_size = int(m.group(2))
                self.array_post = m.group(3)
#                print("m = '%s'" % (m,) )
#                print("m.group(1) = '%s'" % (m.group(1),) )
#                print("m.group(2) = '%s'" % (m.group(2),) )
#                print("m.group(3) = '%s'" % (m.group(3),) )
                self.has_array = True

                if( len(self.array_post) > 0 ):
                    if( self.array_post[0] == "." ):
                        self.array_post = self.array_post[1:]
                    elif( self.array_post.startswith("->") ):
                        self.array_post = self.array_post[2:]
#                self.execute_array(5)

    def execute_array( self, now ):
        ar = gdb.parse_and_eval(self.array_pre)
#        print("ar = '%s'" % (ar,) )
        data = []
        for ix in range(0,self.array_size):
            arf = ar[ix]
#            print("arf = '%s'" % (arf,) )
            further = arf[self.array_post]
            data.append(str(further))
        self.save_data( now, data )
#        import sys
#        sys.exit(-1)

    def execute_pack( self, now ):
        if( self.has_array ):
            val=gdb.parse_and_eval(self.array_pre)
        else:
            val=gdb.parse_and_eval(self.expression)
#        print("val = '%s'" % (val,) )
        names,fullspec = unpack_prepare(self.pack_expression)
#        print("names = '%s'" % (names,) )
#        print("fullspec = '%s'" % (fullspec,) )
#        print("val.address = '%s'" % (val.address,) )
        itemsize = struct.calcsize(fullspec)
#        print("itemsize = '%s'" % (itemsize,) )

        number = 1
        if( self.has_array ):
            number = self.array_size

        retd = {}
        if( val.address is None ):
            current_address = int(val)
        else:
            current_address = int(val.address)
#        gdb.execute(f"hd {current_address:#0x} {itemsize*number}")
        allrawdata = vdb.memory.read_uncached(current_address,itemsize*number)
#        print("len(allrawdata) = '%s'" % (len(allrawdata),) )
        for i in range(0,number):
#            print("i = '%s'" % (i,) )
#            print("itemsize = '%s'" % (itemsize,) )
#            print(f"Reading @{current_address:#0x}")
#            rawdata = vdb.memory.read(current_address,itemsize)
            rawdata = allrawdata[i*itemsize:i*itemsize+itemsize]
#            print("len(rawdata) = '%s'" % (len(rawdata),) )
#            print("type(rawdata) = '%s'" % (type(rawdata),) )
#            print("rawdata = '%s'" % (rawdata,) )
            fields = struct.unpack(fullspec,rawdata)
#            print("names = '%s'" % (names,) )
#            print("fields = '%s'" % (fields,) )
            ret = zip(names,fields)
#            current_address += itemsize
            if( self.unify ):
                dret = dict(ret)
                ret = zip(names,fields) # dict(ret) "uses" it up, need to regenerate
                xid = dret["ID"]
                if( xid in self.seen_ids ):
#                    print(f"Skipping {xid} with {dret}")
                    continue
                self.seen_ids.add(xid)
                if( xid == 0 ):
                    continue

            for n,v in ret:
#                print("n = '%s'" % (n,) )
#                print("v = '%s'" % (v,) )
#            v = f"V[{n}] = '{v}'"
                if( not self.has_array ):
                    id = self.pack_ids[n]
                    self.save_data(now,v,id)
                else:
                    retd.setdefault(n,[]).append(v)
#        print("retd = '%s'" % (retd,) )

        if( self.has_array ):
            for n,vt in retd.items():
                id = self.pack_ids[n]
                self.save_data(now,vt,id)

    def save_data( self, now, data, number = None ):
        if( number is None ):
            number = self.number
        td = tracking_data.setdefault(now,{})
        td[number] = data

    def execute( self, now ):
        try:
#            vdb.util.bark() # print("BARK")
#            print("self.python_eval = '%s'" % self.python_eval )
#            print("self.use_execute = '%s'" % self.use_execute )
#            print("self.eval_after = '%s'" % self.eval_after )
#            print("self.expression = '%s'" % self.expression )
#            print("self.pack_expression = '%s'" % (self.pack_expression,) )
#            print("self.has_array = '%s'" % (self.has_array,) )

            if( self.pack_expression is not None ):
                return self.execute_pack(now)
            if( self.has_array ):
                return self.execute_array(now)
            if( self.python_eval ):
                val=eval(self.expression,globals())
            elif( self.use_execute ):
                val=gdb.execute(self.expression,False,True)
                if( self.eval_after ):
                    val = gdb.parse_and_eval("$")
            else:
                val=gdb.parse_and_eval(self.expression)
            val = str(val)
            if( val[-1] == "\n" ):
                val = val[:-1]
            self.save_data(now,str(val))
        except Exception as e:
            print("e = '%s'" % e )
            traceback.print_exc()
            pass

def extract_ename( argv ):
    ename = None
    if( len(argv) > 1 and argv[1] == "=" ):
        ename = argv[0]
        argv = argv[2:]
    elif( argv[0][-1] == "=" ):
        ename = argv[0][:-1]
        argv = argv[1:]
    # TODO parse ename when there is no space like "alldata=alldata[@35].second"
    return (ename,argv)

def track( argv, execute, eval_after, do_eval ):
    vdb.util.bark() # print("BARK")
    print(f"track({argv=},{execute=},{eval_after=},{do_eval=}")
    ex_bp = set()

#    bps = gdb.breakpoints()
    bps = parse_breakpoints()
    for _,bp in bps.items():
        ex_bp.add(bp.number)
        for _,sbp in bp.subpoints.items():
            ex_bp.add(sbp.number)
    ename,argv = extract_ename(argv)

#    print("ename = '%s'" % (ename,) )

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
        if( argv[0] == "*" ):
            print("Setting catch-all track item for all stop events")
            bpnum = 0
        else:
            print(f"Attempting to set breakpoint for '{argv[0]}'")
            gdb.execute(f"break {argv[0]}")
            n_bp = set()

            bps = gdb.breakpoints()
            for bp in bps:
                n_bp.add(str(bp.number))
            nbp = n_bp - ex_bp
#            print("ex_bp = '%s'" % (ex_bp,) )
#            print("n_bp = '%s'" % (n_bp,) )
#            print("nbp = '%s'" % (nbp,) )
            if( len(nbp) == 0 ):
                print(f"Failed to set breakpoint for {argv[0]}, cannot attach track either")
                return
            ex_bp = n_bp
            bpnum = nbp.pop()
#    print("bpnum = '%s'" % bpnum )

    expr = argv[1:]

    if( bpnum != 0 and bpnum not in ex_bp ):
        print(f"Unknown breakpoint {bpnum}, refusing to attach track to nothing")
        return

    global trackings_by_bpid
    global trackings_by_number

    for e in expr:
        nti = track_item( e, execute, eval_after, do_eval , ename)
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
    # TODO Also clear the unification cache
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
        for dk in sorted(trackings_by_number.keys()):
#            print("dk = '%s'" % (dk,) )
            td = tdata.get(dk,None)
#            print("td = '%s'" % (td,) )
            if( td is None ):
                line.append(None)
            else:
                line.append(td)


        datatable.append( line )

    dt = vdb.util.format_table(datatable)
    print(dt)

def get_track_items( argv, execute, eval_after, do_eval, as_struct, un ):
    vdb.util.bark() # print("BARK")
    print("argv = '%s'" % (argv,) )
    ename,argv = extract_ename(argv)
    print("argv = '%s'" % (argv,) )
    print("ename = '%s'" % (ename,) )
    expr = argv
    print("expr = '%s'" % (expr,) )
    pack = None
    if( as_struct ):
        pack = argv[-1]
        expr = argv[:-1]
    ret = []
    for e in expr:
        nti = track_item( e, execute, eval_after, do_eval , ename, pack_expression = pack, unify = un )
        ret.append(nti)
    return ret

class cmd_track (vdb.command.command):
    """Track one or more expressions per breakpoint

track/[ExX] <id|location> <expression>

track   - pass expression to parse_and_eval
track/E - interpret expression as python code to evaluate
track/x - execute expression and use resulting gdb value
track/X - execute expression and then run parse_and_eval on the result ($)

id           is the id of an existing breakpoint
location    can be any location that gdb understands for breakpoints
expression  is the expression expected by any of the above formats. Upon hitting the breakpoint, it will be evaluated and then automatically continued. The special expression $ret is used to denote a return value of a finish expression.

The expression can also be prefixed with foo= so that in the generated table the name will be foo instead of the expression so that you can easier identify the meaning of it

If no breakpoint can be found with an existing location, we try to set one at that location, otherwise we try to re-use the same location
Note: while it works ok for breakpoints and watchpoints, using catchpoints is somewhat difficult and often does not work

Available subcommands:
show     - show a list of trackpoints (similar to info break)
data     - show the list of data collected so far
clear    - clear all data collected so far 
del <id> - delete the trackpoint with the given trackpoint id
set <name>     - work with tracking sets (see documentation for them)

You should have a look at the data and graph modules, which can take the data from here and draw graphics and histograms
"""

    def __init__ (self):
        super (cmd_track, self).__init__ ("track", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            execute = False
            eval_after_execute = False
            python_eval = False
            as_struct = False
            argv,flags = self.flags(argv)
            unify = False

            if( "u" in flags ):
                unify = True
            if( "E" in flags ):
                python_eval = True
            elif( "x" in flags ):
                execute = True
            elif( "X" in flags ):
                execute = True
                eval_after_execute = True
            if( "s" in flags ):
                as_struct = True

            if( len(argv) == 0 ):
                show()
            elif( "i" in flags ):
#                interval( argv[1:], execute,eval_after_execute,python_eval )
                interval( argv[0], get_track_items( argv[1:], execute,eval_after_execute,python_eval,as_struct,unify ) )
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
        self.dont_repeat()

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
#        vdb.util.bark() # print("BARK")
        global trackings_by_number
        trackings_by_number[self.number] = self
        self.saved_number = self.number

    # This is a bit ugly with the lifetime and such but no idea currently at what place to better do it
    def __del__(self ):
        global trackings_by_number
        trackings_by_number.pop(self.saved_number,None)
#        vdb.util.bark() # print("BARK")

    def out_of_scope( self ):
        vdb.util.bark() # print("BARK")
#        try:
#            print("self.return_value = '%s'" % (self.return_value,) )
#        except:
#            traceback.print_exc()
#        print("self.return_value = '%s'" % (self.return_value,) )

    def stop( self ):
        now = time.time()
        self.action.fin_action( self.return_value, now )
        self.action.fin_bp = None
#        vdb.util.bark() # print("BARK")
        schedule_continue()
#        gdb.post_event(do_continue)
        global trackings_by_number
        del trackings_by_number[self.number]
#        print("STOP RETURNS False")
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


    def action( self, now ):
#        print("filter track action()")
#        print("track_storage = '%s'" % (track_storage,) )
        rval = self.getn( self.expression )
        ret = self.compto(rval)
        return ret

class display_track_item:

    def __init__( self, expression ):
        self.expression = expression
        self.name = None

class data_track_action( track_action ):

    def __init__( self, data_list, location, prefix ):
        print("data_list = '%s'" % (data_list,) )
        self.data_list = []
        global trackings_by_number
        for dl in data_list:
            tn = track_item.get_next_number()
            self.data_list.append( (dl,tn) )
            dti = display_track_item( prefix + location + "." + dl )
            trackings_by_number[tn] = dti

    def store_data( self, ex, val, number, now ):
        if( val is not None ):
            print(f"{ex} = {val}")
            td = tracking_data.setdefault(now,{})
            td[number] = str(val)

    def action( self,now ):
        ret = True
        for dl,tn in self.data_list:
            if( dl == "$ret" ):
                ret = None
                self.ret_number = tn
            else:
                self.store_data( dl, self.getn(dl), tn, now )

        return ret

    def fin_action( self, retval, now ):
        self.store_data("$ret",retval,self.ret_number, now)

class store_track_action(track_action):

    def __init__( self, store_list, location, prefix ):
        vdb.util.requires( len(store_list) == 2, "store action parameter list must have exactly 2 parameters, has %s" % len(store_list) )
        self.expression = store_list[0]
        self.storage_map = store_list[1]
        self.map_key = prefix

    def action( self,now ):
        vdb.util.bark() # print("BARK")
#        print("self.expression = '%s'" % (self.expression,) )
        if( self.expression == "$ret" ):
            return None
        val = self.get( self.expression )
#        print("val = '%s'" % (val,) )
        self.store_data(val)
        return True

    def store_data( self, val ):
#        print("val = '%s'" % (val,) )
        global track_storage
        store = track_storage.setdefault( self.map_key, {} )
        storeset = store.setdefault(self.storage_map,set())
        storeset.add( val )
#        print(f"{self.expression} = {val} => {self.storage_map}")
#        print("track_storage = '%s'" % (track_storage,) )

    def fin_action( self, retval, now ):
#        print("retval = '%s'" % (retval,) )
        self.store_data(retval)

class delete_track_action:

    def __init__( self, del_list, location, prefix ):
        self.expression = del_list[0]
        self.storage_map = del_list[1]
        self.map_key = prefix

    def action( self,now ):
#        print("delete action()")
        global track_storage
        store = track_storage.setdefault( self.map_key, {} )
#        print("self.map_key = '%s'" % (self.map_key,) )
#        print("store = '%s'" % (store,) )
        if( store is not None ):
#            print("self.storage_map = '%s'" % (self.storage_map,) )
            storeset = store.get(self.storage_map,None)
#            print("storeset = '%s'" % (storeset,) )
            if( storeset is not None ):
                val = storeset.get( self.expression )
#                print("val = '%s'" % (val,) )
#                print("storeset = '%s'" % (storeset,) )
                storeset.discard( val )
#                print("storeset = '%s'" % (storeset,) )
        return True

class hexdump_track_action( track_action ):

    def __init__( self, location, tuple_list ):
#        print(f"hexdump_track_action with {len(tuple_list)} alternatives:")
        self.address = None
        self.length  = None
        self.tuple_list = tuple_list
        self.buffer = None
        self.size = None
        self.buffer_expression = None
        self.size_expression = None
        self.location = location
#        for buf,sz in tuple_list:
#            print(f"hexdump({buf},{sz})")

    def dump( self ):
        ps,pu = vdb.pointer.chain( self.buffer, vdb.arch.pointer_size, 3, test_for_ascii = True )
#        print("ps = '%s'" % (ps,) )
#        print("pu = '%s'" % (pu,) )
        print(f"{self.location} : {self.buffer_expression} = {ps}, {self.size_expression} = {self.size}")
        vdb.hexdump.hexdump( self.buffer, self.size )
    # called on breakpoint hit
    # 
    def action( self,now ):
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
    def fin_action( self, retval, now ):
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
#        vdb.util.bark() # print("BARK")
#        print(f"track_breakpoint.stop() [{self.expression}|{self.location}]")
        ret = self.track_item.stop()
#        print("ret = '%s'" % (ret,) )
        if( ret is None ):
            schedule_finish()
#            gdb.post_event(do_finish)
#            print("track_breakpoint.stop() RETURNS True")
            return True
#        print("track_breakpoint.stop() RETURNS False")
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
            elif( action == "data" ):
                ai = data_track_action( param, location, prefix )
            else:
                print(f"Unknown action item {action}")
            if( ai is not None ):
                self.actions.append(ai)
        self.bp = track_breakpoint( location, self )

    def clear( self ):
        self.bp.delete()
        self.bp = None

    def stop( self ):
        now = time.time()
        oret = True
#        print("eti.stop()")
#        gdb.execute("bt")
        for ai in self.actions:
            # @returns true if all went fine, false if it went wrong, and None if we need to call fin_action
            # For filter actions this basically means true when the filter could match, False if it didn't. 
            # So in case of a false, we break, either because of a non matching filter, or because something went too
            # wrong to continue
            ret = ai.action(now)
#            print("ret = '%s'" % (ret,) )
            if( ret is False ):
                break
            if( ret is None ):
                frame = gdb.newest_frame()
                ai.fin_bp = finish_breakpoint( frame, ai )
                oret = None
        return oret

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
                    ( "data", [ "buf", "$rdi", "$ret" ] ),
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


memleak_set = {
        "malloc" :
        [
            ( "store", [ "$ret", "ret" ] ),
            ( "data", [ "size" ] )
            ]
        }


sets = { "ssl" : ssl_set,
        "memleak" : memleak_set
        }

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
        return None

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

    for k,v in tset.items():
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


def unpack_prepare( fmt ):
    fullspec = "="
    names = []
    fields = fmt.split(",")
    for f in fields:
        name,spec = f.split(":")
        fullspec += spec
        if( len(name) > 0 ):
            names.append(name)
    return (names,fullspec)



def unpack( fmt, data ):
    names,fullspec = unpack_prepare(fmt)
    fields = struct.unpack(fullspec,data)
    ret = dict(zip(names,fields))
#    print("ret = '%s'" % (ret,) )
    return ret


unpack("ID:H,Time:I",b"ABCDEF")

next_t = None

def prompt():
    vdb.prompt.display()

def event( ):
    now = time.time()
    if( now >= next_t ):
#        print()
#        print("now = '%s'" % (now,) )
#        print("next_t = '%s'" % (next_t,) )
        gdb.execute("interrupt",False,True)
#        vdb.util.bark() # print("BARK")
    else:
        print(f"\rNow: {time.time()}",end="",flush=True)
        if( sleep_time.get() == 0 ):
            rest = next_t - now
#            print("\nrest = '%s'\n" % (rest,),flush=True )
            time.sleep( rest )
        else:
            time.sleep( sleep_time.get() )
        gdb.post_event(event)

#    gdb.execute("\n")


next_interrupt = False
# Called from other plugins to schedule an interrupt
def interrupt( ):
    global next_interrupt
    next_interrupt = True

#def interval( argv, execute, eval_after, do_eval ):
def interval( iv, nti ):
    if( not vdb.util.is_started()):
        print("Program has not started yet, cannot continue")
        return
    max_cnt = 0
    cnt = 0

    if( iv.find(",") != -1 ):
        ivv = iv.split(",")
        iv = float(ivv[0])
        max_cnt = int(ivv[1])
    else:
        iv = float(iv)

    global next_t
    if( sync_second.value ):
        next_t = int(time.time()) + iv
        while( time.time() > next_t ):
            next_t += iv
    else:
        next_t = time.time() + iv
    global trackings_by_number
    for n in nti:
        trackings_by_number[n.number] = n
    global next_interrupt
    next_interrupt = False
    t0 = 0
    t1 = 0
    while True:
        if( next_interrupt ):
            break
        if( max_cnt and cnt >= max_cnt ):
            break
#        print("next_t = '%s'" % (next_t,) )
        gdb.post_event(event)
        t1 = time.time()
        dt = t1 - t0
        print(f"Spent {dt}s processing track data")
        gdb.execute("continue")
        t0 = time.time()
        si=gdb.parse_and_eval("$_siginfo")
#        print("si = '%s'" % (si,) )
        try:
            if( si["si_signo"] == 2 and si["_sifields"]["_kill"]["si_pid"] == 0 ):
                print("Detected possible SIGINT, stopping interval track")
                break
        except:
            pass
        for n in nti:
            n.execute(time.time())
        if( skip_long.value ):
            while( time.time() > next_t ):
                next_t += iv
        else:
            next_t += iv
        cnt += 1
    print("Terminating interval tracking...")
    prompt()


# FIXME
# interval tracking someimes stops the process a significant amount of time. We might want to experiment with gathering
# the data, continuing and then processing it in a different thread. If we are not set finished due to whatever, then we
# can stall a configurable amount of times
#
# For the "old" tracks, we can only read one variable per track item, but at least for the timing ones we want more,
# probably for the breakpoint ones too. Will this again blur the lines to the sets? Will it finally make sense to just
# have sets, and implement the simpler commands through sets internally? Would the overhead be negligable?

# Some thoughts...
#
# We should somehow unify all kinds of track commands to specify independently:
# - What event to track 
#   - breakpoint (mostly python support in gdb)
#   - watchpoint (no real possibility to figure out that we have been hit)
#   - periodic triggers ( needs to be implemented with the post event and time check trick )
# - what data to track
#   - gdb expression/value
#   - python code
#   - some raw data interpreted as our special named unpack tuple ( e.g. "ID:H,Time:I" yields a named tuple of ID and Time
#
# The track sets currently are working completely independently. Maybe it makes sense to make them feature rich enough
# to have the currently simple tasks be internalls converted/implemented as track sets. There should however be no
# significant performance impact.
#
# A unified data format for track data and possibly other data that then other modules can process.
# Are simply lists of named tuples or even dicts fast and flexible enough? Currently the track data has kind of as its
# "key" the timestamp, and all the expressions with their values ( if any ) are pairs of datapoints, but not for every
# timestamp such a datapoint is available.
# For the new "raw data" module we would have to first read the key/value pairs ( named tuples ) and then stuff them
# into either a list, or in case its ID based, use one of the fields as a key for a dict.
#
# ID based data is read and then unified based on the ID since we might read stuff multiple times.
# Can we assign timestamps? Maybe interpolate since the last read dataset?
#
# Data transformation functionality. Not sure what exactly is needed here but somtimes the above modules won't quite
# produce what is needed for the next ones. Maybe math operations on multiple ones? Or FFT? Interpolation? (box car)
# averaging? 
# Somehow we want to integrate user code into here too. Some python lookup magic?
#
# graphing/statistics
# ( All should probably support linear, log2, log10 (or log arbitrary?)
# - linear plot. One X value identified by e.g. timestamp ( most useful for track data ).
# - histogram. Mostly useful for non timestamped data?
# - point cloud maybe? 2D/3D?
# - polar coordinates?
# Everything with lines should have the ability to plot points and control interpolation
#
# This all is a lot of configuration and we probably don't want to put everything into one command so maybe we can do
# some setup commands and enable commands? That way we can somewhat work around the one window limitation of mathplotlib
# and put up multiple plots in one window.
#



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
