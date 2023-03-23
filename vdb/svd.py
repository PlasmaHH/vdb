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
import re


auto_scan = vdb.config.parameter("vdb-svd-auto-scan",True,docstring="scan configured directories on start")
scan_dirs = vdb.config.parameter("vdb-svd-directories","~/Downloads/",gdb_type=vdb.config.PARAM_ARRAY )
scan_recur= vdb.config.parameter("vdb-svd-scan-recursive",True,docstring="Whether to scan directories recursively")
scan_background = vdb.config.parameter("vdb-svd-scan-background",False,docstring="Do the scan in the background")
scan_filter = vdb.config.parameter("vdb-svd-scan-filter","",docstring="Regexp to filter file names before loading")


verbose = False
try:
#    test_xml_etree()
    import defusedxml.ElementTree as ET
#    from defusedxml.ElementTree import parse
except:
    import xml.etree.ElementTree as ET
#    from xml.etree.ElementTree import parse

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
            self.display_name = None
            self.mmap_address = None
            self.bit_size = None
            self.description = {}
            self.description_text = None
            self.reset_value = None # Later we might want to highlight changes
            self.access = None
            self.type = None

        def _dump( self ):
            addr=self.mmap_address
            if( addr is None ):
                addr = 0
            print(f"{self.display_name} {self.name} @{addr:#0x}[{self.bit_size}]")
            for pos,t5 in self.description.items():
                sz,name,desc,_,amap = t5
                print(f"    {name}[{sz}]\t{desc} {amap=}")

        def _parse_field( self, node ):
            pos  = None
            sz   = None
            name = None
            desc = None
            access = None

            if( node.tag != "field"):
                raise RuntimeError(f"_parse_field() accepts only 'field' but got '{node.tag}'")

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
                    case "access":
                        access=n.text
                    case "enumeratedValues":
                        # TODO the register description already can handle something like this, parse it and check for
                        # compatibility and when to output what and when to output what
                        pass
                    case "bitRange":
                        n.text = n.text.strip()
                        if( n.text[0] != "[" or n.text[-1] != "]" ):
                            print(f"Unknown bitRange format '{n.text}'")
                            continue
                        st,en = n.text[1:-1].split(":")
                        st = int(st)
                        en = int(en)
                        if( st > en ):
                            t=st
                            st=en
                            en=t
                        pos = st
                        sz = (en-st)+1
                    # TODO here we have to take the name and generate multiple register fields out of it ( same for
                    # registers ). See e.g. https://siliconlabs.github.io/Gecko_SDK_Doc/CMSIS/SVD/html/group__dim_element_group__gr.html
                    case "dimIncrement":
                        pass
                    case "dimIndex":
                        pass
                    case "dim":
                        pass
                    case "writeConstraint": # TODO need to figure out what this is
                        pass
                    case "readAction": # afaik we can ignore this for our needs
                        pass
                    case _:
                        print("n.tag = '%s'" % (n.tag,) )
                        print("n.text = '%s'" % (n.text,) )
                        pass
            self.description[pos] = ( sz, name, desc, None, access_map(access) )

        def _parse_fields( self, node ):
            for f in node:
                match(f.tag):
                    case "field":
                        self._parse_field(f)
#            print("self.name = '%s'" % (self.name,) )
#            print("self.description = '%s'" % (self.description,) )

        def get_short_name( self ):
            if( self.display_name is None ):
                return self.name
            if( len(self.display_name) < len(self.name) ):
                return self.display_name
            return self.name

        
        def parse_xml( self, node, base_address ):
            for n in node:
                match(n.tag):
                    case "name":
                        self.name = n.text
                    case "displayName":
                        self.display_name = n.text
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
        self.cpu = svd_device.cpu_description()
        self.group_bit_size = None

    def load( self, unload = True ):
        print(f"Loading {len(self.registers)} register descriptions")
        if( unload ):
            vdb.register.mmapped_descriptions = {}
            vdb.register.mmapped_positions = {}
        skip=0
        for r in self.registers:
            name=r.get_short_name()
            if( verbose ):
                r._dump()
            if( r.mmap_address is None ):
                skip += 1
            else:
                bitsize = r.bit_size
                rtype=r.type
                if( bitsize is None ):
                    print(f"{r.name} has no bit_size")
                # TODO configureable? intresting at all?
#                if( bitsize is None ):
#                    bitsize = 32
#                    rtype=vdb.arch.uint(bitsize)

                vdb.register.mmapped_descriptions[name] = (bitsize, r.description, None )
                vdb.register.mmapped_positions[name] = ( r.mmap_address, bitsize, rtype )
        if( skip > 0 ):
            print(f"Skipped {skip} registers due to unkonwn mapping position.")

    def _parse_name( self, node ):
        self.name = node.text

    def _parse_group( self, node ):
        for tag in node:
            match(tag.tag):
                case "registers":
                    self._parse_registers(tag,0)
                case "peripherals":
                    self._parse_peripherals(tag)
                case "size":
                    self.group_bit_size = int(tag.text)
#                case _:
#                    print("tag.tag = '%s'" % (tag.tag,) )
        self.group_bit_size = None

    def _parse_groups( self, node ):
        for tag in node:
            match(tag.tag):
                case "group":
                    self._parse_group(tag)

    def _parse_cpu( self, node ):
        dp_name=None
        for tag in node:
            match(tag.tag):
                case "groups":
                    self._parse_groups(tag)
                case "name":
                    self.cpu.name = tag.text
                case "displayName":
                    dp_name = tag.text
                case "revision":
                    self.cpu.revision = tag.text
                case _:
#                    print("tag.tag = '%s'" % (tag.tag,) )
                    pass
        if( dp_name is not None and self.cpu.name is not None ):
            self.cpu_description.cpu_map[self.cpu.name] = dp_name
#        if( dp_name is not None and self.cpu.name is None ):
#            print("Display name cpu only {dp_name}")

    def _parse_register( self, node, base_address ):
        reg = svd_device.register()
        reg.parse_xml(node,base_address)
        if( reg.name in self.register_names ):
            print(f"Duplicate register name {reg.name}")
        if( reg.bit_size is None and self.group_bit_size is not None ):
            reg.bit_size = self.group_bit_size
        self.registers.append(reg)

    def _parse_registers( self, node, base_address ):
        for r in node:
            match(r.tag):
                case "register":
                    self._parse_register(r,base_address)
                case "cluster":# TODO Wait, whats that? We need to support them for the stm32-svd tinygo files
                    pass
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
    if( ndev.name is None ):
        ndev.name = ndev.cpu.name
    return ndev

def svd_load_file(fname,at):
    if( at is None ):
        print(f"Loading {fname}… ",end="")

    with open(fname,"r") as f:
        data = f.read()
        data = data.replace(" & "," &amp; ");
    if( len(data) < 16 ):
        print("File too small, does it contain anything?")
        return None

    xml = ET.fromstring(data)
    root = xml
    ndev=parse_device(root)
    if( ndev.name is None ):
        print(" contains no named CPU, discarding")
    else:
        print(f"=> {ndev.name}")
        global devices
        devices[ndev.name] = ndev

def svd_list( flt = None):
    otbl = []
    otbl.append( ["Name","CPU","Registers"] )
    if( flt is not None ):
        flt_re = re.compile(flt)
    for d in devices.values():
        if( flt is not None ):
            m = flt_re.search(d.name)
            if( m is None ):
                m = flt_re.search(d.cpu.get_name())
                if( m is None ):
                    continue
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
    filter_re = None
    if( scan_filter.value is not None and len(scan_filter.value) > 0 ):
        filter_re = re.compile(scan_filter.value)
    for i,p in enumerate(pathlist):
        if( filter_re is not None and filter_re.search(p) is None ):
            continue
        if( at is not None ):
            at.set_progress(f"[svd {i}/{len(pathlist)}]")
        try:
            svd_load_file(p,at)
        except:
            traceback.print_exc()
            print(f"Failed to load {p}")

def do_svd_scan(at):
#    print("at = '%s'" % (at,) )
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
        global lazy_task
        lazy_task = vdb.util.async_task( do_svd_scan )
        lazy_task.start()
    else:
        do_svd_scan(None)

# XXX mv to some "at first promp" logic
def start():
    if( not auto_scan.value ):
        print("svd not auto scanning due to vdb-svd-auto-scan False")
        return
    svd_scan()

def get( ar, ix, alt ):
    try:
        return ar[ix]
    except:
        return alt

class cmd_svd(vdb.command.command):
    """Manage SVD file loading and the interaction with the register display

svd list      - Lists known CPU definitions
svd load <ID> - Loads svd CPU definitions
svd scan      - Scan configured list of directories and (re)reads the found svd definitions
"""

    def __init__ (self):
        super (cmd_svd, self).__init__ ("svd", gdb.COMMAND_DATA)

    def complete( self, text, word ):
#        print("text = '%s'" % (text,) )
#        print("word = '%s'" % (word,) )
        if( word is None and len(text) == 0 ):
            return []
        subcommands = [ "load", "list", "scan" ]
        if( text == word ):
            return self.matches(word,subcommands)
        elif( text.startswith("load ") ):
#            print("devices.keys() = '%s'" % (devices.keys(),) )
            return self.matches(word,devices.keys())
        return []

    def do_invoke (self, argv ):
        self.dont_repeat()

        if len(argv) < 1:
            raise gdb.GdbError('svd takes arguments.')

        try:
            global verbose
            verbose = False
            if( argv[0] == "/v" ):
                verbose = True
                argv=argv[1:]

            subcmd = argv[0]
            match(subcmd):
                case "load":
                    if( len(argv) < 2 ):
                        raise RuntimeError("load needs CPU parameter")
                    svd_load(argv[1])
                case "list":
                    svd_list(get(argv,1,None))
                case "scan":
                    svd_scan()
                case _:
                    self.usage()
        except Exception as e:
            traceback.print_exc()

cmd_svd()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
