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


def resolve_typedefs( gdb_type ):
#    print(f"resolve_typedefs({gdb_type=})")
    if( gdb_type.code == gdb.TYPE_CODE_PTR ):
        return resolve_typedefs( gdb_type.target() ).pointer()
    return gdb_type.strip_typedefs()

class pahole:
    def __init__( self ):
        self.last_used_bit = 0
        self.current_color_index = -1
        self.table = []
        self.current_line : list[str] = []
        self.table.append(self.current_line)
        self.flat_objects = []

    def next_color( self ):
        self.current_color_index += 1
        self.current_color_index %= len(color_list.elements)
        return self.color()

    def color( self ):
        col = color_list.elements[self.current_color_index]
        return col

    def print( self ):
        vdb.util.print_table( self.table, "", "" )

    def append( self, cell ):
        self.current_line.append(cell)

    def split_range( self, rng ):
        rbyte = rng // 8
        rbit = rng % 8
        return ( rbyte, rbit )

    def new_line( self ):
        self.current_line = []
        self.table.append(self.current_line)

    def print_range( self, frm, to, color,etype,ename ):
        frmbyte, frmbit = self.split_range(frm)
        tobyte, tobit = self.split_range(to)

        self.append(( "[ ", color ))
        self.append((vdb.util.Align.RIGHT,str(frmbyte),color))
        if( frmbit != 0 ):
            self.append((":"+str(frmbit),color))
        else:
            self.append(None)
        self.append(("- ",color))
        self.append((vdb.util.Align.RIGHT,str(tobyte),color))
        if( tobit != 7 ):
            self.append((":"+str(tobit),color))
        else:
            self.append(None)
        self.append(( "]",color) )
        self.append(" ")
        self.last_used_bit = to
        self.append( ( vdb.util.Align.RIGHT, etype, color_type.get() ) )
        self.append(" ")
        self.append( ename )
        self.new_line()

    def print_range_extended( self, frm, to, color,etype,ename ):
        self.print_range( frm, to, color,etype,ename )

    def get_type( self, typ ):
        bx = typ.strip_typedefs()
        bx = resolve_typedefs(bx)
        if( bx.name is None ):
            enttypename = str(bx)
        else:
            enttypename = bx.name
        enttypename = vdb.shorten.symbol(enttypename)
        enttypename = vdb.color.colors.strip_color(enttypename)
        return enttypename

#        self.append(( vdb.util.Align.RIGHT,enttypename, color_type.get() ))
#        self.append(" ")

    def print_gap( self, next_bit, condense ):
        if( condense ):
            self.print_range( self.last_used_bit+1, next_bit, color_empty.get(), "", "<unused>" )
        else:
            self.print_range_extended( self.last_used_bit+1, next_bit, color_empty.get(), "", "<unused>" )

    def flatten( self, obj, prefix ):
        for o in obj.subobjects:
            if( not o.final ):
                self.flatten( o,prefix + "::" + o.name)
                continue
            # If it is final and a base class its an empty base, leave it out
            if( o.is_base_class ):
                continue

            self.flat_objects.append( ( o.bit_offset, prefix + "::" + o.name, o ) )


    def print_object( self, obj, condense ):
#        print(f"print_object({obj},{condense}")
        self.flatten(obj,obj.name)

        for _,subname,o in sorted(self.flat_objects):
            col = self.next_color()

            if( o.bit_size is not None ):
                bsize = o.bit_size
            else:
                bsize = o.size * 8

            if( o.bit_offset - self.last_used_bit > 1 ):
                self.print_gap( o.bit_offset-1, condense )

            if( condense ):
                self.print_range_extended( o.bit_offset, o.bit_offset + bsize - 1, col, self.get_type(o.type),subname )
            else:
                self.print_range( o.bit_offset, o.bit_offset + bsize - 1, col, self.get_type(o.type),subname )


        self.print()

def print_pahole( layout, condense ):
    pa = pahole()
    pa.print_object( layout.object, condense )

class cmd_pahole(vdb.command.command):
    """Show the holes in a structure.

Parameter can be a typename or a variable.

pahole/c - condensed output showing each member on one line
pahole/e - expanded output, showing each byte on one line (the default)
"""

    def __init__ (self):
        super ().__init__ ("pahole", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

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
        except gdb.error:
            sobj = gdb.parse_and_eval(argv[0])
            stype = sobj.type
            ptype = stype.strip_typedefs()
            if( ptype.code == gdb.TYPE_CODE_PTR ):
                sobj = sobj.dereference()
                stype = ptype.target()
                ptype = stype.strip_typedefs()
#            traceback.print_exc()

        if ptype.code not in { gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION }:
            raise gdb.GdbError('%s is not a struct/union type: %s' % (" ".join(argv), vdb.util.gdb_type_code(ptype.code)))
        try:
            xl = vdb.layout.object_layout(stype,sobj)
            print_pahole(xl,condensed)
        except:
            traceback.print_exc()

cmd_pahole()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
