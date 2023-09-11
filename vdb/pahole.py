#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.layout
import vdb.color


import gdb
import gdb.types

import traceback

default_condensed = vdb.config.parameter("vdb-pahole-default-condensed",False)




color_list = vdb.config.parameter("vdb-pahole-colors-members", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" , gdb_type = vdb.config.PARAM_COLOUR_LIST )
color_empty = vdb.config.parameter("vdb-pahole-color-empty", "#444" , gdb_type = vdb.config.PARAM_COLOUR_LIST )
color_type = vdb.config.parameter("vdb-pahole-color-type", "#cc4400" , gdb_type = vdb.config.PARAM_COLOUR_LIST )



def print_pahole( layout, condense ):
#        print("PRINT RESULT")
    cidx = -1
    if( condense ):
        cidx = -1
    cnt = 0
    current_entity = None
    max_type_len = 0
    previous_text = None
    start = 0
    end = 0
    for bd in layout.bytes:
        if( bd.object is not None ):
            bx = bd.object.type.strip_typedefs()
            enttypename = bx.name
            if( enttypename is None ):
                enttypename = str(bx)
            enttypename = vdb.shorten.symbol(enttypename)
#            max_type_len = max(max_type_len,len(enttypename))
            max_type_len = max(max_type_len,len(vdb.color.colors.strip_color(enttypename)))
            bd.pahole_enttypename = enttypename
    txtunused = "<unused>"
    ccolor = color_empty.get()
    ccolor = color_list.elements[cidx]
    pcolor=ccolor
    for bd in layout.bytes:
        if( bd.prefix is None ):
            ent = None
        else:
            ent = bd.name()
#        print("ent = '%s'" % ent )

        if( ent is not None ):
            if( len(ent) > 2 and ent.startswith("::") ):
                ent = ent[2:]
            ent = vdb.shorten.symbol(ent)
        else:
            ent = txtunused

        if( ent != current_entity ):
            current_entity = ent
            if( ent != txtunused ):
                cidx += 1
                cidx %= len(color_list.elements)
        if( ent != txtunused ):
            ccolor = color_list.elements[cidx]
        else:
            ccolor = color_empty.get()
        cos = vdb.color.color(f"[{cnt:3d}]",ccolor)
        if( bd.prefix is not None ):
#            print("bd.type = '%s'" % bd.type )
#            print("type(bd.type) = '%s'" % type(bd.type) )
#            print("bx = '%s'" % bx )
            enttypename = bd.pahole_enttypename
            ename = vdb.color.color(f"{enttypename:>{max_type_len}}",color_type.get())
        else:
            ename = " " * max_type_len
            ent = txtunused
        if( condense ):
            txt = f"{ename} {ent}"
            if( txt != previous_text ):
                if( previous_text is not None ):
                    xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",pcolor)
                    if( previous_text.endswith(txtunused) ):
                        print(f"{xcos} {previous_text} {1+end-start}")
                    else:
                        print(f"{xcos} {previous_text}")
                start = cnt
                previous_text = txt
                pcolor = ccolor
        else:
            print(f"{cos} {ename} {ent}")
        end = cnt
        cnt += 1

    if( condense ):
        xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",pcolor)
        print(f"{xcos} {previous_text}")

class cmd_pahole(vdb.command.command):
    """Show the holes in a structure.

Parameter can be a typename or a variable.

pahole/c - condensed output showing each member on one line
pahole/e - expanded output, showing each byte on one line (the default)
"""

    def __init__ (self):
        super (cmd_pahole, self).__init__ ("pahole", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def do_invoke (self, argv ):
#        print("argv = '%s'" % argv )
        if len(argv) == 0 :
            raise gdb.GdbError('pahole takes 1 arguments.')
        condensed = default_condensed.value
        if( argv[0] == "/c" ):
            condensed = True
            argv=argv[1:]
        if( argv[0] == "/e" ):
            condensed = False
            argv=argv[1:]

        if len(argv) != 1:
            raise gdb.GdbError('pahole takes 1 arguments.')
        sobj = None
        ptype = None
        try:
            stype = gdb.lookup_type (argv[0])
            ptype = stype.strip_typedefs()
        except gdb.error as e:
            sobj = gdb.parse_and_eval(argv[0])
            stype = sobj.type
            ptype = stype.strip_typedefs()
            if( ptype.code == gdb.TYPE_CODE_PTR ):
                sobj = sobj.dereference()
                stype = ptype.target()
                ptype = stype.strip_typedefs()
#            traceback.print_exc()

        if ptype.code != gdb.TYPE_CODE_STRUCT and ptype.code != gdb.TYPE_CODE_UNION:
            raise gdb.GdbError('%s is not a struct/union type: %s' % (" ".join(argv), vdb.util.gdb_type_code(ptype.code)))
        try:
            xl = vdb.layout.object_layout(stype,sobj)
            print_pahole(xl,condensed)
        except Exception as e:
            traceback.print_exc()

cmd_pahole()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
