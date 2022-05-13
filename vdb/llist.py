#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.util
import vdb.pointer


import gdb
import gdb.types

import traceback
import re


default_limit = vdb.config.parameter("vdb-llist-default-list-limit", 128 )

def get_next( var, next ):
#    vdb.util.bark() # print("BARK")
#    print("var = '%s'" % (var,) )
#    print("next = '%s'" % (next,) )
    try:
        n = var[next]
        n.fetch_lazy()
    except gdb.MemoryError:
        n = None
#    print("n = '%s'" % (n,) )
    return n

assignre = re.compile("([a-zA-Z0-9]*)=(.*)")

# XXX Think of a way we can have this as a generic util funcion...
def expand_fields( fields, keys ):
    expanded = True
    kkeys = keys.copy()
    kkeys["var"] = "{var}"
    while(expanded):
        expanded = False
        ret = []
        for a,f,v in fields:
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
            ret.append( ( na,f,v ) )
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
        if( m is not None ):
            fn = m.group(1)
            af = m.group(2)
            expansions[fn] = af
        if( af.find("{var}") != -1 ):
            additional_fields.append((af,fn,True))
        else:
            additional_fields.append((af,fn,False))

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

    for af,fn,_ in additional_fields:
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

        for af,fn,fmt in additional_fields:
            try:
                if( fmt ):
                    varstr = f"(({gvar.type}){gvar})"
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
#                print("pae = '%s'" % (pae,) )
                traceback.print_exc()
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

class cmd_llist(vdb.command.command):
    """Handle (mostly output) linked list like structures

llist <list> <next>    - Output the <list> by using member <next> as the next item pointer.
"""

    def __init__ (self):
        super (cmd_llist, self).__init__ ("llist", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def do_invoke (self, argv ):

        bidirectional = False
        argv0 = argv[0]
        if( argv0[0] == "/" ):
            argv = argv[1:]
            if( "b" in argv0 ):
                bidirectional = True

        try:
            show_list( argv, bidirectional )
        except gdb.error as e:
            traceback.print_exc()
            pass

cmd_llist()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
