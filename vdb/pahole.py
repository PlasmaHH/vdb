#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.layout
import vdb.color


import gdb
import gdb.types

import traceback

default_condensed = vdb.config.parameter("vdb-pahole-default-condensed",False)




color_list = vdb.config.parameter("vdb-pahole-colors-members", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,on_set = vdb.config.split_colors)



def print_pahole( layout, condense ):
#        print("PRINT RESULT")
    cidx = -1
    if( condense ):
        cidx = -2
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
    for bd in layout.bytes:
        if( bd.prefix is None ):
            ent = "<unused>"
        else:
            ent = bd.name()
#        print("ent = '%s'" % ent )

        if( len(ent) > 2 and ent.startswith("::") ):
            ent = ent[2:]
        ent = vdb.shorten.symbol(ent)

        # XXX extra colour for empty
        if( ent != current_entity ):
            current_entity = ent
            cidx += 1
            cidx %= len(color_list.elements)
        cos = vdb.color.color(f"[{cnt:3d}]",color_list.elements[cidx])
        if( bd.prefix is not None ):
#            print("bd.type = '%s'" % bd.type )
#            print("type(bd.type) = '%s'" % type(bd.type) )
#            print("bx = '%s'" % bx )
            enttypename = bd.pahole_enttypename
            ename = vdb.color.color(f"{enttypename:>{max_type_len}}","#cc4400")
        else:
            ename = " " * max_type_len
            ent = "<unused>"
        if( condense ):
            txt = f"{ename} {ent}"
            if( txt != previous_text ):
                if( previous_text is not None ):
                    xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",color_list.elements[cidx])
                    print(f"{xcos} {previous_text}")
                start = cnt
                previous_text = txt
        else:
            print(f"{cos} {ename} {ent}")
        end = cnt
        cnt += 1

    cidx += 1
    cidx %= len(color_list.elements)
    if( condense ):
        xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",color_list.elements[cidx])
        print(f"{xcos} {previous_text}")

class cmd_pahole(vdb.command.command):
    """Show the holes in a structure.
This command takes a single argument, a type name.
It prints the type and displays comments showing where holes are."""

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
        stype = gdb.lookup_type (argv[0])
        ptype = stype.strip_typedefs()
        if ptype.code != gdb.TYPE_CODE_STRUCT and ptype.code != gdb.TYPE_CODE_UNION:
            raise gdb.GdbError('%s is not a struct/union type: %s' % (" ".join(argv), ptype.code))
        try:
#            tl = vdb.layout.type_layout(ptype)
            xl = vdb.layout.object_layout(stype)
#            print_pahole(tl,condensed)
            print_pahole(xl,condensed)
        except Exception as e:
            traceback.print_exc()

cmd_pahole()
