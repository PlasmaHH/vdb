#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.util
import vdb.pointer


import gdb
import gdb.types

import re
import time


default_limit = vdb.config.parameter("vdb-llist-default-list-limit", 128 )
min_chain    = vdb.config.parameter("vdb-llist-min-chain-len", 2 )
scan_offset  = vdb.config.parameter("vdb-llist-scan-max-offset", 4 )
scan_results = vdb.config.parameter("vdb-llist-scan-max-results", 5 )
scan_spintype = vdb.config.parameter("vdb-llist-progress-spinner", "ascii" )

verbose = False

def get_next( var, next ):
#    vdb.util.bark() # print("BARK")
#    print("var = '%s'" % (var,) )
#    print("next = '%s'" % (next,) )
    try:
        try:
            nx = int(next)
#            print("var = '%s'" % (var,) )
#            print("nx = '%s'" % (nx,) )
            var = var.cast( vdb.pointer.gdb_void_ptr_ptr )
            n = var + nx
#            print("n = '%s'" % (n,) )
            n = n.dereference()
#            print("n = '%s'" % (n,) )
        except:
            n = var[next]
        n.fetch_lazy()
    except gdb.MemoryError:
        n = None
#    print("n = '%s'" % (n,) )
    return n

assignre = re.compile("(-?)([a-zA-Z0-9]*)=(.*)")

# XXX Think of a way we can have this as a generic util funcion...
def expand_fields( fields, keys ):
    expanded = True
    kkeys = keys.copy()
    kkeys["var"] = "{var}"
    while(expanded):
        expanded = False
        ret = []
        for a,f,v,s in fields:
#            print("a = '%s'" % (a,) )
#            print("f = '%s'" % (f,) )
#            print("v = '%s'" % (v,) )
#            print("kkeys = '%s'" % (kkeys,) )
            na = a.format(**kkeys)
            if( na != a ):
                expanded = True
                if( na.find("{var}") != -1 ):
                    v = True
#            print(f"{a} => {na}")
            ret.append( ( na,f,v,s ) )
        fields = ret
    return ret

def show_list( argv, bidirectional ):
    var = argv[0]
    next = argv[1]
    additional_fields = []
    previous = None


    expansions = {}
    for af in argv[2:]:
        if( af.startswith("prev=") ):
            af = af[5:]
            previous = af
            expansions["prev"] = af
        m = assignre.match(af)
        fn = af
        suppress = False
        if( m is not None ):
            neg = m.group(1)
            if( neg == "-" ):
                suppress = True
            fn = m.group(2)
            af = m.group(3)
            expansions[fn] = af
        if( af.find("{var}") != -1 ):
            additional_fields.append((af,fn,True,suppress))
        else:
            additional_fields.append((af,fn,False,suppress))

#    print("additional_fields = '%s'" % (additional_fields,) )
#    print("expansions = '%s'" % (expansions,) )
    additional_fields = expand_fields( additional_fields, expansions )
#    print("additional_fields = '%s'" % (additional_fields,) )


    gvar = gdb.parse_and_eval( var )
#    print("gvar = '%s'" % (gvar,) )
#    print("gvar.address = '%s'" % (gvar.address,) )
#    print("gvar.type = '%s'" % (gvar.type,) )

    otable = []

    header = [ ("No",",,bold"), ("Address",",,bold"), (next,",,bold") ]

    for af,fn,_,sup in additional_fields:
        if( not sup ):
            header.append( ( fn, ",,bold" ) )
    header.append( ("Comment",",,bold",0,0) )
    otable.append( header )

    indices = {}

    cnt = 0
    pvar = None

    if( bidirectional and  previous is None ):
        print("Cannot use bidirectional/backwards mode with no prev= pointer given")
        bidirectional = False

    # Just go backwards as far as we can and pretend we started there already (will break in the case of the forward
    # pointers being broken, try to detect that later )
    if( bidirectional ):
        bvar = gvar
        cnt = 1
        prevar = None
        while( bvar is not None ):
#            print("bvar = '%s'" % (bvar,) )
            p = get_next( bvar, previous )
#            print("p = '%s'" % (p,) )
            if( p is None ):
                gvar = prevar
                break
            prevar = bvar
            bvar = p
            cnt -= 1

#    indices[0x0000000127de9f80] = 5
    while gvar is not None:
        try:
            gvar.fetch_lazy()
        except gdb.MemoryError:
            gvar = None
            break
        indices[int(gvar)] = cnt

        line = []
        otable.append(line)

        line.append( cnt )
        line.append( vdb.pointer.colors(gvar) )
        n = get_next( gvar, next )

        pcnt = None
        if( n is not None ):
            line.append( vdb.pointer.colors(int(n)) )
            pcnt = indices.get(int(n),None)
        else:
            line.append( "…" )

        for af,fn,fmt,sup in additional_fields:
            pae = None
            try:
                if( sup ):
                    continue
                if( fmt ):
#                    print("type(gvar) = '%s'" % (type(gvar),) )
#                    print("gvar = '%s'" % (gvar,) )
                    varstr = f"(({gvar.type}){int(gvar)})"
                    pae = af.format(var=varstr)
                    afv = gdb.parse_and_eval(pae)
                else:
                    afv = gvar[af]

                tcode = afv.type.code
                if( tcode == gdb.TYPE_CODE_TYPEDEF ):
                    tcode = afv.type.strip_typedefs().code

                if( tcode == gdb.TYPE_CODE_PTR ):
                    cv,cl = vdb.pointer.colors(afv)
                    _,_,sym = vdb.memory.get_gdb_sym(int(afv))
                    if( sym is not None ):
                        cv += " " + sym
                        cl += 1 + len(sym)
#                    print("afv = '%s'" % (afv,) )
#                    print("sym = '%s'" % (sym,) )
                    line.append( (cv,cl) )
                else:
                    line.append( str(afv) )
            except Exception as e:
                print("pae = '%s'" % (pae,) )
                vdb.print_exc()
                line.append( f"<{type(e).__module__}.{type(e).__name__}>")

        if( pcnt is not None ): # loops back
            line.append(f"Loops back to {pcnt}")
            break

        if( previous is not None ):
            try:
                prev = gvar[previous]
                if( pvar is not None and pvar != prev ):
                    line.append( "Previous does not point to last element!" )
            except:
                pass


        pvar = gvar
        gvar = n
        cnt += 1
        if( gvar == 0 ):
            break
        if( cnt >= default_limit.value ):
            otable.append( ["…","…","…"] )
            break

    outp = vdb.util.format_table(otable)
    print(outp)

def chainlen( addr, offset, bdoffset, bidirectional ):
    cnt = 0
    seen = set()
    chain = []
    backchain = []
    while( addr ):
        if( int(addr) in seen ):
            break
        chain.append(int(addr))
        seen.add(int(addr))
        cnt += 1
        ptrbytes = vdb.arch.pointer_size // 8
        naddr = addr + offset * ptrbytes
        try:
            nval = naddr.cast(vdb.pointer.gdb_void_ptr_ptr).dereference()
            nval.fetch_lazy()
        except gdb.MemoryError:
            nval = None
        except:
            vdb.print_exc()
            nval = None
        # in the bidirectional case, check if the object at nval has a previous pointer, pointing back
        if( bidirectional and nval is not None ):
            baddr = nval - bdoffset * ptrbytes
            try:
                bval = baddr.cast(vdb.pointer.gdb_void_ptr_ptr).dereference()
                bval.fetch_lazy()
            except gdb.MemoryError:
                bval = None
            except:
                vdb.print_exc()
                bval = None
            if( bval is None or bval != addr ):
                nval = None
            else:
                backchain.append( baddr )
#                print(f"[{offset},{bdoffset}] {int(addr):#0x} points to {int(baddr):#0x} and {int(bval):#0x} points back to {int(addr):#0x} => {nval}")
        addr = nval
#    print("cnt = '%s'" % (cnt,) )
    return ( cnt, chain, backchain )

def chainstring( chain ):
    total = 0
    res = ""
    arrow = vdb.pointer.arrow_right.value
    first = True
    for c in chain:
        if( not first ):
            res += arrow
            total += len(arrow)
        s,l = vdb.pointer.colors( c )
        res += s
        total += l
        first = False
    return (res,total)

def scan( argv, bidirectional ):
#    vdb.util.bark() # print("BARK")
    start = gdb.parse_and_eval( argv[0] )
    if( argv[1].startswith("0x") ):
        end = gdb.parse_and_eval( argv[1] )
        size = end-start
    else:
        size = gdb.parse_and_eval( argv[1] )

    ptrbytes = vdb.arch.pointer_size // 8

    results = []

    bdrange = scan_offset.value
    if( not bidirectional ):
        bdrange = 1

    work = scan_offset.value * bdrange * ( size / ptrbytes )
    txt = f"Scanning address range {int(start):#0x} - {int(start+size):#0x} ( %s found )"

    prog = vdb.util.progress_bar(num_completed = False, speed = True, download = True)
    pt = prog.add_task( txt, total = int(work) )
    prog.start()

    cnt_mod = 2500
    t0 = time.time()
    last_cnt = 0
    next_cnt = 2500
    # old indicator: 7.3s
    try:
        cnt = 0
        for offset in range( 0, scan_offset.value ):
            for bdoffset in range( 0, bdrange ):
                for sadd in range( 0,size,ptrbytes ):
                    cl,cn,bcn = chainlen( start + sadd, offset, bdoffset, bidirectional )
                    if( cl >= min_chain.value ):
                        results.append( (cl, cn, bcn, start+sadd, offset, bdoffset ) )
                    cnt += 1
                    if( cnt >= next_cnt ):
                        prog.update( pt, completed = cnt, description = txt % len(results) )
                        t1 = time.time()
                        td = t1-t0
                        t0 = t1
                        # strive for approx 20fps
                        factor = 0.05 / td
#                        print(f"{factor=}")
                        cnt_mod = cnt - last_cnt
#                        print(f"{cnt_mod=}")
                        cnt_mod = int( factor * cnt_mod )

#                        print(f"{cnt_mod=}")
                        last_cnt = cnt
                        next_cnt = cnt + cnt_mod
#                        print(f"{td=}")
    except KeyboardInterrupt:
        print()
        print(f"Stopping scan, displaying {len(results)} partial results")
    prog.stop()

    results.sort(reverse=True)
   
    otable = []
    h2 = "Start"
    if( verbose ):
        h2 = "Chain"

    header = [ ( "Chainlen", ",,bold" ), (h2, ",,bold" ), ("Offset", ",,bold") ]
    if( bidirectional ):
        header.append( ("Back Offset", ",,bold") )
    otable.append( header )
    for i in range(0,min(scan_results.value,len(results))):
        line = []
        otable.append(line)
        cl,cn,bcn, st,of,bdo = results[i]
        line.append( cl )
        if( verbose ):
            line.append( chainstring( cn ) )
        else:
            line.append( vdb.pointer.colors( st ) )
        line.append( of )
        if( bidirectional ):
            line.append( bdo )
            if( verbose ):
                otable.append( [ "", chainstring(bcn) ] )

    vdb.util.print_table( otable )

class cmd_llist(vdb.command.command):
    """Handle (mostly output) linked list like structures

llist <list> <next>    - Output the <list> by using member <next> as the next item pointer.
"""

    def __init__ (self):
        super (cmd_llist, self).__init__ ("llist", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def do_invoke (self, argv ):

        bidirectional = False
        argv0 = argv[0]
        try:
            global verbose
            verbose = False
            argv,flags = self.flags(argv)
            if( "v" in flags ):
                verbose = True
            if( "b" in flags ):
                bidirectional = True
            if( "s" in flags ):
                return scan( argv, bidirectional )

            show_list( argv, bidirectional )
        except gdb.error as e:
            vdb.print_exc()
            pass

cmd_llist()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
