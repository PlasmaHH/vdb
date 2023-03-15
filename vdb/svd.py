#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config

import gdb
import gdb.types

import traceback


auto_scan = vdb.config.parameter("vdb-svd-auto-scan",True,docstring="scan configured directories on start")
scan_dirs = vdb.config.parameter("vdb-svd-directories",".",gdb_type=vdb.config.PARAM_ARRAY )
scan_recur= vdb.config.parameter("vdb-svd-scan-recursive",True,docstring="Whether to scan directories recursively")


try:
    from defusedxml.ElementTree import parse
except:
    from xml.etree.ElementTree import parse

def svd_load(fname):
    pass

def svd_list():
    pass

def svd_scan():
    pass

class cmd_svd(vdb.command.command):
    """Manage SVD file loading and the interaction with the register display

svd list      - Lists known CPU definitions
svd load <ID> - Loads svd CPU definitions
svd scan      - Scan configured list of directories and (re)reads the found svd definitions
"""

    def __init__ (self):
        super (cmd_svd, self).__init__ ("svd", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def do_invoke (self, argv ):

        if len(argv) < 1:
            raise gdb.GdbError('svd takes arguments.')

        try:
            subcmd = argv[0]
            match(subcmd):
                case "load":
                    if( len(argv) < 2 ):
                        raise RuntimeError("load needs CPU parameter")
                    svd_load(argv[1])
                case "list":
                    svd_list()
                case "scan":
                    svd_scan()
                case _:
                    self.usage()
        except Exception as e:
            traceback.print_exc()

cmd_svd()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
