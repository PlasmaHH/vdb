#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.layout
import vdb.color


import gdb
import gdb.types

import traceback

default_condensed = vdb.config.parameter("vdb-pahole-default-condensed",True)




color_list = vdb.config.parameter("vdb-pahole-colors-members", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" , gdb_type = vdb.config.PARAM_COLOUR_LIST )
color_empty = vdb.config.parameter("vdb-pahole-colors-empty", "#444" , gdb_type = vdb.config.PARAM_COLOUR )
color_type = vdb.config.parameter("vdb-pahole-colors-type", "#cc4400" , gdb_type = vdb.config.PARAM_COLOUR )
print_summary = vdb.config.parameter("vdb-pahole-summary", True )


def resolve_typedefs( gdb_type ):
#    print(f"resolve_typedefs({gdb_type=})")
    if( gdb_type.code == gdb.TYPE_CODE_PTR ):
        return resolve_typedefs( gdb_type.target() ).pointer()
    return gdb_type.strip_typedefs()

class pahole:
    def __init__( self ):
        self.last_used_bit = -1
        self.current_color_index = -1
        self.table = []
        self.current_line : list[str] = []
        self.table.append(self.current_line)
        self.condensed = False
        self.gap_bits = 0
        self.total_bits = 0
        self.bitfields = False

    def next_color( self ):
        self.current_color_index += 1
        self.current_color_index %= len(color_list.elements)
        return self.color()

    def color( self ):
        col = color_list.elements[self.current_color_index]
        return col

    def print( self ):
        vdb.util.print_table( self.table, "", "" )
        if( not print_summary.value ):
            return
        used_bits = self.total_bits - self.gap_bits
        perc = 100 * ( used_bits / self.total_bits )
        extra = ""
        if( self.bitfields ):
            minbits = (used_bits + 31) & ~31
            if( minbits < self.total_bits ):
                nperc = 100 * ( used_bits / minbits )
                extra = f", could condense to {used_bits}/{minbits}({nperc:.1f}%)"
            print(f"{used_bits}/{self.total_bits} bits used ({perc:.1f}%){extra}")
        else:
            used_bytes = used_bits//8
            total_bytes = self.total_bits//8
            minbytes = (used_bytes + 3) & ~3
            if( minbytes < total_bytes ):
                nperc = 100 * ( used_bytes / minbytes )
                extra = f", could condense to {used_bytes}/{minbytes}({nperc:.1f}%)"
            print(f"{used_bytes}/{total_bytes} bytes used ({perc:.1f}%){extra}")


    def append( self, cell ):
        self.current_line.append(cell)

    def split_range( self, rng ):
        rbyte = rng // 8
        rbit = rng % 8
        return ( rbyte, rbit )

    def new_line( self ):
        self.current_line = []
        self.table.append(self.current_line)

    def print_range( self, frm, to, color,etype,ename, print_size = False ):
#        print(f"print_range({frm=},{to=},{etype=},{ename=})")
        frmbyte, frmbit = self.split_range(frm)
        tobyte, tobit = self.split_range(to)
        force_bitend = False

        bitsbefore = None
        fullbytes = tobyte - frmbyte - 1
        bitsafter = None

        self.append(( "[ ", color ))
        self.append((vdb.util.Align.RIGHT,str(frmbyte),color))
        if( frmbit != 0  or (to-frm) % 8  != 7 ):
            self.append((":"+str(frmbit),color))
            self.bitfields = True
            force_bitend = True
            bitsbefore = 8 - frmbit
            if( bitsbefore == 8 ):
                bitsbefore = "_"
                fullbytes += 1
        else:
            fullbytes += 1
            self.append(None)

        if( self.condensed or frm % 8 != 0 or to-frm != 7 ):
            self.append(("- ",color))
            self.append((vdb.util.Align.RIGHT,str(tobyte),color))
            if( force_bitend or tobit != 7 ):
                self.append((":"+str(tobit),color))
                self.bitfields = True
                bitsafter = tobit+1
                if( bitsafter == 8 ):
                    bitsafter = "_"
                    fullbytes += 1
            else:
                fullbytes += 1
                self.append(None)
        else:
            self.append("")
            self.append("")
            self.append("")
        self.append(( "]",color) )
        self.append(" ")
        self.last_used_bit = to
        self.append( ( vdb.util.Align.RIGHT, etype, color_type.get() ) )
        self.append(" ")
        if( print_size ):
            if( bitsbefore is None and bitsafter is None ):
                szs = f"{fullbytes}"
            else:
                szs = f"{bitsbefore}.{fullbytes}.{bitsafter}"
            self.append( f"{ename} {szs}" )
        else:
            self.append( ename )
        self.new_line()

    def print_range_extended( self, frm, to, color,etype,ename ):
#        print(f"print_range_extended({frm=},{to=},{etype},{ename})")
        align = frm % 8
        if( align != 0 ): # Some bits until the next full byte
            align = 8 - align
            mto = min( to, frm+align-1 )
            self.print_range( frm, mto, color,etype,ename )
            frm += align

        while to >= frm:
            mto = min(to,frm+7)
            self.print_range( frm, mto, color,etype,ename )
            frm += 8

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

    def print_gap( self, next_bit ):
        self.gap_bits += (next_bit - self.last_used_bit )
        if( self.condensed ):
            self.print_range( self.last_used_bit+1, next_bit, color_empty.get(), "", "<unused>" , True)
        else:
            self.print_range_extended( self.last_used_bit+1, next_bit, color_empty.get(), "", "<unused>" )

    def print_layout( self, layout ):
        flat,size = layout.flatten()

        for _,subname,o in sorted(flat):
            subname = vdb.shorten.symbol(subname)
            col = self.next_color()

            if( o.bit_size is not None ):
                bsize = o.bit_size
            else:
                bsize = o.size * 8

            if( o.bit_offset - self.last_used_bit > 1 ):
                self.print_gap( o.bit_offset-1 )

            if( self.condensed ):
                self.print_range( o.bit_offset, o.bit_offset + bsize - 1, col, self.get_type(o.type),subname )
            else:
                self.print_range_extended( o.bit_offset, o.bit_offset + bsize - 1, col, self.get_type(o.type),subname )
            self.total_bits = max(self.total_bits,o.bit_offset + bsize)

        if( self.last_used_bit+1 < size ):
            self.print_gap( size - 1 )
        self.total_bits = max(self.total_bits,size)


        self.print()

def print_pahole( layout, condense ):
    pa = pahole()
    pa.condensed = condense
    pa.print_layout( layout )

class cmd_pahole(vdb.command.command):
    """Show the holes in a structure.

Parameter can be a typename or a variable.

pahole/c - condensed output showing each member on one line
pahole/e - expanded output, showing each byte on one line (the default)
"""

    def __init__ (self):
        super ().__init__ ("pahole", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)
        self.needs_parameters = True

    def do_invoke (self, argv ):

        condensed = default_condensed.value
        argv,flags = self.flags(argv)
        if( "c" in flags ):
            condensed = True
        elif( "e" in flags ):
            condensed = False

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
            if( ptype.code == gdb.TYPE_CODE_ARRAY ):
                sobj = sobj[0]
                stype = ptype.target()
                ptype = stype.strip_typedefs()
            if( ptype.code == gdb.TYPE_CODE_PTR ):
                sobj = sobj.dereference()
                stype = ptype.target()
                ptype = stype.strip_typedefs()
            if( ptype.code == gdb.TYPE_CODE_REF ):
#                sobj = sobj.dereference()
                stype = ptype.target()
                ptype = stype.strip_typedefs()
#            vdb.print_exc()

        if ptype.code not in { gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION }:
            raise gdb.GdbError('%s is not a struct/union type: %s' % (" ".join(argv), vdb.util.gdb_type_code(ptype.code)))
        try:
            xl = vdb.layout.object_layout(stype,sobj)
            print_pahole(xl,condensed)
        except:
            vdb.print_exc()

cmd_pahole()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
