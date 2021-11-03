#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.command

import gdb

import re
import traceback

def show_region( addr, colorspec ):
    ga = gdb.parse_and_eval(f"(void*){addr}")
    print(ga)
    ca,mm,_,_ = vdb.memory.mmap.color(addr,colorspec = colorspec)
    if( mm is None ):
        print(f"Nothing known about address 0x{addr:16x}")
        return None
    print( f"Address {ca} is in {str(mm)}" )


class cmd_vmmap (vdb.command.command):
    """Module holding information about memory mappings

vmmap         - show information about the known memory maps (of the memory module), colored by types
vmmap/s       - short version of that information
vmmap refresh - re-read the information by triggering the memory module (happens at most stop events too)
vmmap <expr>  - Checks the expression/address memory map and displays all details we know about it
vmmap <cspec> - uses this colorspec
    """

    def __init__ (self):
        super (cmd_vmmap, self).__init__ ("vmmap", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            colorspec = None
            short = False
            if( len(argv) == 0 ):
                pass
            elif( len(argv) >= 1 ):
                try:
                    if( argv[0] == "/s" ):
                        short = True
                        argv = argv[1:]
                    if( len(argv) > 0 ):
                        if( argv[0] == "refresh" ):
                            vdb.memory.mmap.parse()
                            return

                        addr = None
                        try:
                            addr = gdb.parse_and_eval(argv[0])
                            addr = int(addr)
                            argv = argv[1:]
                        except:
#                            traceback.print_exc()
                            pass
                        if( len(argv) > 0 ):
                            colorspec = argv[0]
                            vdb.memory.check_colorspec(colorspec)
                        if( addr is not None ):
                            return show_region( addr, colorspec )
                except:
                    traceback.print_exc()
                    pass
            else:
                raise Exception("vmmap got %s arguments, expecting 0 or 1" % len(argv) )
            vdb.memory.check_colorspec(colorspec)
            vdb.memory.print_legend(colorspec)
            vdb.memory.mmap.print(colorspec,short)
        except:
            traceback.print_exc()
            raise
            pass

cmd_vmmap()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
