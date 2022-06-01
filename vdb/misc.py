#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.track
import vdb.command

import gdb

import re
import traceback

class cmd_toggle(vdb.command.command):
    """Toggles a setting that must be a bool"""

    def __init__ (self):
        super ().__init__ ("toggle", gdb.COMMAND_SUPPORT, gdb.COMPLETE_NONE)

    def do_invoke (self, argv ):
        try:
            if( len(argv) > 0 ):
                for cfg in argv:
                    try:
                        par = gdb.parameter(cfg)
                        if( not isinstance(par,bool) ):
                            print(f"Config needs to be of type bool to be toggleable, '{cfg}' isn't")
                        else:
                            par = not par
                            gdb.set_parameter(cfg,{True:"on",False:"off"}[par])
                    except:
                        traceback.print_exc()
                        print(f"gdb does not know parameter '{cfg}'")
            else:
                raise Exception("toggle got %s arguments, expecting 1 or more" % len(argv) )

        except:
            traceback.print_exc()
            raise

        self.dont_repeat()

cmd_toggle()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
