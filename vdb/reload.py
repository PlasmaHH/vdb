#!/usr/bin/env python3

import vdb.command
import rich
import gdb
import sys
import vdb.util
import importlib
import re


class cmd_reload (vdb.command.command):
    """reloads all loaded vdb modules. This is a development tool and not perfect, in particular it will most likely
    cause other plugins commands to be overridden. Use with care.
"""

    def __init__ (self):
        super (cmd_reload, self).__init__ ("reload", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = False

    def do_invoke (self, argv ):
        fre = re.compile(".*")
        if( len(argv) > 0 ):
            fre = re.compile(argv[0])
        print("Reloading modules ", end="" )
        for name,mod in vdb.enabled_modules.items():
            if( mod is not None ):
                try:
                    m = fre.search(name)
                    if( m is None ):
                        continue
                    print(f"{name},",end="")
                    vdb.reloading = True
                    importlib.reload(mod)
                    vdb.start_second_stage( mod, name )
                except:
                    vdb.print_exc()
                finally:
                    vdb.reloading = False
        print()

        print("Reloading plugins ", end="")
        for plugin in vdb.imported_plugins:
            try:
                m = fre.search(str(plugin))
                if( m is None ):
                    continue
                print(f"{plugin},",end="")
                vdb.reloading = True
                importlib.reload(plugin)
            except:
                vdb.print_exc()
            finally:
                vdb.reloading = False
        print()

        self.dont_repeat()

cmd_reload()
# XXX We need a way to also load properly the assembler stuff

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
