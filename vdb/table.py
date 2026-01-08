#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command

import gdb

import re
import rich
import rich.table

def rich_print_array( var, level, num = None ):
    if( num is None ):
        f = var.type.fields()[0]
        iter_range = f.type.range()
    else:
        iter_range = (0,num)

    etype = var.type.target()
#    vdb.util.inspect(etype)

    table = rich.table.Table(row_styles = ["on #222222",""])
    table.add_column("i")

    tnames = []
    has_fields = False
    match etype.code:
        case gdb.TYPE_CODE_STRUCT:
            has_fields = True
            for ef in etype.fields():
                if( ef.name is not None ):
                    tnames.append(ef.name)
                    table.add_column(ef.name,overflow="fold")
        case _:
            table.add_column(str(etype))
            print(f"{vdb.util.gdb_type_code(etype.code)=}")

    for i in range(*iter_range):
        rowdata = [ str(i) ]
        evar = var[i]
        if( has_fields ):
            for tn in tnames:
                rowdata.append(str(evar[tn]))
        else:
            rowdata.append(str(evar))
        table.add_row( *rowdata )

#    vdb.util.console.print(table)
    return table

def rich_print_struct( var , level ):

    show_header = True
    if( level > 1 ):
        show_header = False
    # Add overflow = fold?? can we do that on the table level?
    table = rich.table.Table( collapse_padding = True, show_header = show_header, show_edge = False)
    table.add_column("Name",overflow="fold")
    table.add_column("Type",overflow="fold")
#    table.add_column("Sz",overflow="fold")
#    table.add_column("DBG",overflow="fold")
    table.add_column("Value",overflow="fold")
    etype = var.type

    for ef in etype.fields( ):
        rowdata = []
        if( ef.name is not None ):
            rowdata.append(ef.name)
        else:
            rowdata.append("<anonymous>")
        if( ef.is_base_class ):
            rowdata.append("::")
        else:
            # XXX make configurable
            sstr = vdb.shorten.symbol(str(ef.type))
            rowdata.append( sstr )
#        rowdata.append( str(ef.is_base_class) )
#        rowdata.append( str(ef.type.sizeof) )
        rowdata.append( rich_print_recursive( var[ef], level + 1 ) )
        table.add_row( *rowdata )
    return table


def rich_print_typedef( var , level ):
    vtype = var.type.strip_typedefs()
    return rich_print_recursive( var.cast(vtype), level + 1 )

def rich_print_pointer( var , level ):
    data = vdb.pointer.chain( var )
    rdata = rich.text.Text.from_ansi( data[0] )
    return rdata


def rich_print_recursive( var , level ):

    match var.type.code:
        case gdb.TYPE_CODE_ARRAY:
            return rich_print_array(var, level + 1)
        case gdb.TYPE_CODE_STRUCT:
            return rich_print_struct(var, level + 1)
        case gdb.TYPE_CODE_TYPEDEF:
            return rich_print_typedef(var, level + 1)
        case gdb.TYPE_CODE_INT:
            return str(var)
        case gdb.TYPE_CODE_FLT:
            # XXX might want to format it
            return str(var)
        case _:
            return (f"Type code {vdb.util.gdb_type_code(var.type.code)} not supported yet")

def rich_print( argv ):
    varname = argv[0]
    arraylen = None
    try:
        arraylen = int(argv[1])
    except IndexError:
        pass

    var = gdb.parse_and_eval(varname)

    content = None
    print(f"{vdb.util.gdb_type_code(var.type.code)=}")
    if( var.type.code == gdb.TYPE_CODE_PTR ):
        if( arraylen is not None ):
            content = rich_print_array( var, arraylen,0 )
        else:
            content = rich_print_pointer( var,0 )
    else:
        content = rich_print_recursive( var,0 )

    vdb.util.console.print(content)

class cmd_table (vdb.command.command):
    """Take data and transform it into more useful views using rich tables"""

    def __init__ (self):
        super (cmd_table, self).__init__ ("table", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = True

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)
        rich_print( argv )
        self.dont_repeat()

cmd_table()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
