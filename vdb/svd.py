#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util
import vdb.register

import gdb
import gdb.types

import os
import traceback


auto_scan = vdb.config.parameter("vdb-svd-auto-scan",True,docstring="scan configured directories on start")
scan_dirs = vdb.config.parameter("vdb-svd-directories",".,~/Downloads/",gdb_type=vdb.config.PARAM_ARRAY )
scan_recur= vdb.config.parameter("vdb-svd-scan-recursive",True,docstring="Whether to scan directories recursively")
scan_background = vdb.config.parameter("vdb-svd-scan-background",True,docstring="Do the scan in the background")


try:
    from defusedxml.ElementTree import parse
except:
    from xml.etree.ElementTree import parse

def svd_load(idname):
    d = devices.get(idname,None)
    if( d is None ):
        print(f"Uncrecognized µC name '{idname}', list of known ones:")
        svd_list()
        return
    d.load()

amap = {
        "read-write" : "RW",
        "write-only" : "W",
        "read-only" : "R"
        }

def access_map( am ):
    return amap.get(am,am)

devices = {}
class svd_device:

    class cpu_description:
        cpu_map = {
                "CM33" : "Cortex-M33"
                }
        def __init__( self ):
            self.name = None
            self.revision = None

        def get_name( self ):
            ret = ""
            if( self.name is None ):
                ret += "<Unknown>"
            else:
                ret += self.cpu_map.get(self.name,self.name)

            if( self.revision is not None ):
                ret += " "
                ret += self.revision
            return ret

    class register:

        def __init__( self ):
            self.name = None
            self.mmap_address = None
            self.bit_size = None
            self.description = {}
            self.description_text = None
            self.reset_value = None # Later we might want to highlight changes
            self.access = None
            self.type = None

        def _parse_field( self, node ):
            pos  = None
            sz   = None
            name = None
            desc = None
            access = None

            for n in node:
                match(n.tag):
                    case "name":
                        name = n.text
                    case "description":
                        desc = n.text
                    case "bitOffset":
                        pos = vdb.util.rxint(n.text)
                    case "bitWidth":
                        sz = vdb.util.rxint(n.text)
                    case _:
                        pass
            self.description[pos] = ( sz, name, desc, None, access_map(access) )

        def _parse_fields( self, node ):
            for f in node:
                match(f.tag):
                    case "field":
                        self._parse_field(f)
#            print("self.name = '%s'" % (self.name,) )
#            print("self.description = '%s'" % (self.description,) )

        def parse_xml( self, node, base_address ):
            for n in node:
                match(n.tag):
                    case "name":
                        self.name = n.text
                    case "addressOffset":
                        self.mmap_address = base_address + vdb.util.rxint(n.text)
                    case "resetValue":
                        self.reset_value = vdb.util.rxint(n.text)
                    case "size":
                        self.bit_size = vdb.util.rxint(n.text)
                        self.type=vdb.arch.uint(self.bit_size)
                    case "access":
                        self.access = n.text
                    case "description":
                        self.description_text = n.text
                    case "fields":
                        self._parse_fields(n)
                    case _:
#                        print("n.tag = '%s'" % (n.tag,) )
                        pass
#            print(self)

        def __str__( self ):
            ret = f"{self.name}@{self.mmap_address:#0x}[{self.bit_size}])"
            return ret

    def __init__( self ):
        self.name = None
        self.registers = []
        self.register_names = set()

    def load( self, unload = True ):
        print(f"Loading {len(self.registers)} register descriptions")
        if( unload ):
            vdb.register.mmapped_descriptions = {}
            vdb.register.mmapped_positions = {}
        for r in self.registers:
            # TODO The 32 must be limited to the real relevant value
            vdb.register.mmapped_descriptions[r.name] = (r.bit_size, r.description, None )
            vdb.register.mmapped_positions[r.name] = ( r.mmap_address, r.bit_size, r.type )

    def _parse_name( self, node ):
        self.name = node.text
        self.cpu = svd_device.cpu_description()

    def _parse_cpu( self, node ):
        for tag in node:
            match(tag.tag):
                case "name":
                    self.cpu.name = tag.text
                case "revision":
                    self.cpu.revision = tag.text
                case _:
#                    print("tag.tag = '%s'" % (tag.tag,) )
                    pass

    def _parse_register( self, node, base_address ):
        reg = svd_device.register()
        reg.parse_xml(node,base_address)
        if( reg.name in self.register_names ):
            print(f"Duplicate register name {reg.name}")
        self.registers.append(reg)

    def _parse_registers( self, node, base_address ):
        for r in node:
            match(r.tag):
                case "register":
                    self._parse_register(r,base_address)
                case _:
                    print("r.tag = '%s'" % (r.tag,) )

    def _parse_peripheral( self, node ):
        base_address = None
        for n in node:
            match(n.tag):
                case "registers":
                    self._parse_registers(n,base_address)
                case "baseAddress":
                    base_address = vdb.util.rxint(n.text)
                case _:
#                    print("n.tag = '%s'" % (n.tag,) )
                    pass

    def _parse_peripherals( self, node ):
        for p in node:
            match(p.tag):
                case "peripheral":
                    self._parse_peripheral(p)
                case _:
#                    print("p.tag = '%s'" % (p.tag,) )
                    pass

    def parse_from_xml( self, xml ):
        for node in xml:
            match(node.tag):
                case "name":
                    self._parse_name(node)
                case "cpu":
                    self._parse_cpu(node)
                case "peripherals":
                    self._parse_peripherals(node)
                case _:
#                    print("node.tag = '%s'" % (node.tag,) )
                    pass

def parse_device(xml):
    ndev = svd_device()
    ndev.parse_from_xml(xml)
    return ndev

def svd_load_file(fname,at):
    if( at is None ):
        print(f"Loading {fname}")
    print(f"Loading {fname}")
    xml = parse(fname)
    root = xml.getroot()
    ndev=parse_device(root)
    global devices
    devices[ndev.name] = ndev

def svd_list():
    otbl = []
    otbl.append( ["Name","CPU","Registers"] )
    for d in devices.values():
        line = []
        line.append(d.name)
        line.append(d.cpu.get_name() )
        line.append(len(d.registers))

        otbl.append(line)
    vdb.util.print_table(otbl)

def do_svd_scan_one(dirname,at):
    pathlist = []
    dirname = os.path.expanduser(dirname)
    for root, dirs, files in os.walk(dirname,followlinks=True):
        for f in files:
            if( f.endswith(".svd") ):
                fullpath = root + "/" + f
                pathlist.append(fullpath)
    for i,p in enumerate(pathlist):
        if( at is not None ):
            at.set_progress(f"[svd {i}/{len(pathlist)}]")
        try:
            svd_load_file(p,at)
        except:
            traceback.print_exc()
            print(f"Failed to load {p}")


def do_svd_scan(at):
    vdb.util.bark() # print("BARK")
    print("at = '%s'" % (at,) )
    if( at is not None ):
        at.set_progress("[svd #/#]")
    for d in scan_dirs.elements:
        try:
            do_svd_scan_one(d,at)
        except:
            traceback.print_exc()
            print(f"Failed to scan directory '{d}'")

lazy_task = None
def svd_scan():
    # later chose between background and foreground
    if( scan_background.value ):
        vdb.util.bark() # print("BARK")
        global lazy_task
        lazy_task = vdb.util.async_task( do_svd_scan )
        lazy_task.start()
    else:
        do_svd_scan(None)

def start():
    if( not auto_scan.value ):
        print("svd not auto scanning due to vdb-svd-auto-scan False")
        return
    svd_scan()

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
