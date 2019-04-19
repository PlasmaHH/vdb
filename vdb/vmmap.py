#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.command

import gdb

import re
import traceback

def show_region( addr ):
    ga = gdb.parse_and_eval(f"(void*){addr}")
    print(ga)
    ca,mm,_,_ = vdb.memory.mmap.color(addr)
    if( mm is None ):
        print(f"Nothing known about address 0x{addr:16x}")
        return None
    print( f"Address {ca} is in {str(mm)}" )


class cmd_vmmap (vdb.command.command):
    """Run the backtrace without filters"""

    def __init__ (self):
        super (cmd_vmmap, self).__init__ ("vmmap", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            colorspec = "sma"
            if( len(argv) == 0 ):
                pass
            elif( len(argv) == 1 ):
                try:
                    if( argv[0] == "refresh" ):
                        vdb.memory.mmap.parse()
                        return
                    addr = gdb.parse_and_eval(argv[0])
                    addr = int(addr)
                    return show_region( addr )
                except:
                    traceback.print_exc()
                    pass
                colorspec = argv[0]
            else:
                raise Exception("vmmap got %s arguments, expecting 0 or 1" % len(argv) )
            vdb.memory.check_colorspec(colorspec)
            vdb.memory.print_legend(colorspec)
            vdb.memory.mmap.print(colorspec)
        except:
            traceback.print_exc()
            raise
            pass

cmd_vmmap()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
