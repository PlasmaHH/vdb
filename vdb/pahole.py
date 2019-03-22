#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.layout
import vdb.color


import gdb
import gdb.types

import traceback

default_condensed = vdb.config.parameter("vdb-pahole-default-condensed",False)

def print_pahole( layout, condense ):
#        print("PRINT RESULT")
    color_list = ["#f00","#0f0","#00f","#ff0","#f0f","#0ff" ]
    cidx = -1
    if( condense ):
        cidx = -2
    cnt = 0
    current_entity = None
#    print("layout.max_type_len = '%s'" % layout.max_type_len )
#    print("layout.max_name_len = '%s'" % layout.max_name_len )
    previous_text = None
    start = 0
    end = 0
    for bd in layout.bytes:
        if( bd.prefix is None ):
            ent = "<unused>"
        else:
            ent = bd.name()
        if( len(ent) > 2 and ent.startswith("::") ):
            ent = ent[2:]

        # XXX extra colour for empty
        if( ent != current_entity ):
            current_entity = ent
            cidx += 1
            cidx %= len(color_list)
        cos = vdb.color.color(f"[{cnt:3d}]",color_list[cidx])
        if( bd.type is not None ):
            enttypename = bd.type.name
            if( enttypename is None ):
                enttypename = str(bd.type)
#                print(("[%%3d] : %%%ss     %%-%ss %%s" % (layout.max_type_len,layout.max_name_len)) % (cnt,enttypename,ent,code))
            ename = vdb.color.color(f"{enttypename:>{layout.max_type_len}}","#cc4400")
#                ("[%%3d] : %%%ss     %%-%ss %%s" % (layout.max_type_len,layout.max_name_len)) % (cnt,enttypename,ent,code))
        else:
            ename = " " * layout.max_type_len
            ent = "<unused>"
        if( condense ):
            txt = f"{ename} {ent}"
            if( txt != previous_text ):
                if( previous_text is not None ):
                    xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",color_list[cidx])
                    print(f"{xcos} {previous_text}")
                start = cnt
                previous_text = txt
        else:
            print(f"{cos} {ename} {ent}")
        end = cnt
#            print(("[%%3d] : %%%ss     %%-%ss %%s" % (layout.max_type_len,layout.max_name_len)) % (cnt,"",ent,"<code>"))
        cnt += 1

    cidx += 1
    cidx %= len(color_list)
    if( condense ):
        xcos = vdb.color.color(f"[{start:3d}-{end:3d}]",color_list[cidx])
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
            tl = vdb.layout.type_layout(ptype)
            print_pahole(tl,condensed)
        except Exception as e:
            traceback.print_exc()

cmd_pahole()
