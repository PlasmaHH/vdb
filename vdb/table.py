#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command

import gdb

import re
import rich
import rich.table

def array_table( var ):
    f = var.type.fields()[0]
    etype = var.type.target()
#    vdb.util.inspect(etype)

    table = rich.table.Table(expand=False,row_styles = ["on #222222",""])
    table.add_column("i")

    tnames = []
    for ef in etype.fields():
        if( ef.name is not None ):
            tnames.append(ef.name)
            table.add_column(ef.name,overflow="fold")

    for i in range(*f.type.range()):
        rowdata = [ str(i) ]
        evar = var[i]
        for tn in tnames:
            rowdata.append(str(evar[tn]))
        table.add_row( *rowdata )

    vdb.util.console.print(table)



def auto_table( argv ):
    varname = argv[0]
    var = gdb.parse_and_eval(varname)
#    vdb.util.inspect(var)
#    vdb.util.inspect(var.type)

    match var.type.code:
        case gdb.TYPE_CODE_ARRAY:
            array_table(var)
        case _:
            print(f"Type code {var.type.code} not supported yet")


class cmd_table (vdb.command.command):
    """Take data and transform it into more useful views"""

    def __init__ (self):
        super (cmd_table, self).__init__ ("table", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            if( len(argv) > 0 ):
                auto_table( argv )
            else:
                raise Exception("data got %s arguments, expecting 1 or more" % len(argv) )



        except:
            vdb.print_exc()
            raise
            pass

        self.dont_repeat()

cmd_table()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
