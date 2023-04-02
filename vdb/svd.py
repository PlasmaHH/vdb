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
import sys


auto_scan = vdb.config.parameter("vdb-svd-auto-scan",True,docstring="scan configured directories on start")
scan_dirs = vdb.config.parameter("vdb-svd-directories","~/svd/",gdb_type=vdb.config.PARAM_ARRAY )
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
        "read-only" : "R",
        None : "",
#        "RW" : "RW",
#        "W" : "W",
#        "R" : "R"
        }

def access_map( am ):
#    if( am not in amap ):
#        print("am = '%s'" % (am,) )
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
            self.endian = None
            self.size = None

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
        __slots__ = "name","display_name","mmap_address","bit_size","description","reset_value","access","peripheral_name"

        _identity_pool = {}

        def _i_get( k ):
            r = svd_device.register._identity_pool.get(k,None)
            if( r is None ):
                svd_device.register._identity_pool[k] = k
                r = k
#            print("id(r) = '%s'" % (id(r),) )
#            print("sys.getrefcount(r) = '%s'" % (sys.getrefcount(r),) )
            return r

        def __init__( self ):
            self.name = None
            self.display_name = None
            self.mmap_address = None
            self.bit_size = None
            self.description = {}
#            self.description_text = None
            self.reset_value = None # Later we might want to highlight changes
            self.access = None
#            self.type = None
#            self.group = None
            self.peripheral_name = None

        def _dump( self ):
            addr=self.mmap_address
            if( addr is None ):
                addr = 0
            print(f"{self.peripheral_name} {self.display_name} {self.name} @{addr:#0x}[{self.bit_size}] => {self.get_key_name()}")
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
                        access=access_map(n.text)
#                        access=n.text
#                        access=svd_device.register._i_get(n.text)
#                        print("sys.getrefcount(access) = '%s'" % (sys.getrefcount(access),) )
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
                        if( n.tag not in { "modifiedWriteValues", "lsb", "msb" } ):
                            print(f"Never before seen register field tag <{n.tag}>{n.text}</{n.tag}>")
                        pass
            self.description[pos] = ( sz, name, desc, None, access_map(access) )

        def _parse_fields( self, node ):
            for f in node:
                match(f.tag):
                    case "field":
                        self._parse_field(f)
#            print("self.name = '%s'" % (self.name,) )
#            print("self.description = '%s'" % (self.description,) )

        def get_key_name( self ):
            sname = self.get_short_name()
#            print("self.peripheral_name = '%s'" % (self.peripheral_name,) )
            if( self.peripheral_name is not None ):
                sname = self.peripheral_name + "." + sname
            return sname

        def get_short_name( self ):
            if( self.display_name is None ):
                return self.name
            if( len(self.display_name) < len(self.name) ):
                return self.display_name
            return self.name

        
        def parse_xml( self, node, base_address,def_bit_size ):
            if( len(node.attrib) > 0 ):
                print("node.attrib = '%s'" % (node.attrib,) )
            self.bit_size = def_bit_size
            for n in node:
                match(n.tag):
                    case "name":
                        self.name = n.text
                    case "displayName":
                        self.display_name = n.text
                    case "addressOffset":
                        self.mmap_address = int(base_address + vdb.util.rxint(n.text))
                    case "resetValue":
                        self.reset_value = vdb.util.rxint(n.text)
                    case "size":
                        self.bit_size = vdb.util.rxint(n.text)
#                        print("sys.getsizeof(self.bit_size) = '%s'" % (sys.getsizeof(self.bit_size),) )
#                        self.type=vdb.arch.uint(self.bit_size)
#                        print("sys.getsizeof(self.bit_size) = '%s'" % (sys.getsizeof(self.bit_size),) )
                    case "access":
                        self.access = access_map(n.text)
                    case "description":
                        pass # Save some memory
#                        self.description_text = n.text
                    case "fields":
                        self._parse_fields(n)
                    case _:
#                        print("n.tag = '%s'" % (n.tag,) )
                        pass
            if( self.bit_size is None ):
                self._dump()
                print("NO BIT_SIZE")
#            print(self)

        def __str__( self ):
            ret = f"{self.name}@{self.mmap_address:#0x}[{self.bit_size}])"
            return ret

    def __init__( self ):
        self.name = None
        self.description = None
        self.registers = []
        self.register_names = set()
        self.cpu = svd_device.cpu_description()
        self.group_bit_size = None
        self.origin = None # file name, set externally after parsing completed
        self.peripherals = {}
        self.memory_estimation = None

    def load( self, unload = True ):
        print(f"Loading {len(self.registers)} register descriptions")
        if( unload ):
            vdb.register.mmapped_descriptions = {}
            vdb.register.mmapped_positions = {}
        skip=0
        for r in self.registers:
            name=r.get_key_name()
            if( verbose ):
                r._dump()
            if( r.mmap_address is None ):
                skip += 1
            else:
                bitsize = r.bit_size
#                rtype=r.type
                rtype=vdb.arch.uint(r.bit_size)
                if( bitsize is None ):
                    print(f"{r.name} has no bit_size")
                # TODO configureable? intresting at all?
#                if( bitsize is None ):
#                    bitsize = 32
#                    rtype=vdb.arch.uint(bitsize)

                vdb.register.mmapped_descriptions[name] = (bitsize, r.description, None )
#                print(f"{name} => @{r.mmap_address}[{bitsize}] = {rtype}")
                vdb.register.mmapped_positions[name] = ( r.mmap_address, bitsize, rtype )
        if( skip > 0 ):
            print(f"Skipped {skip} registers due to unkonwn mapping position.")

    def _parse_name( self, node ):
        self.name = node.text

    def _parse_group( self, node ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
        deferred_list_r=[]
        deferred_list_p=[]
        for tag in node:
            match(tag.tag):
                # TODO check file formats, we are missing base address and peripheral name here. Whats our parent data?
                case "registers":
                    deferred_list_r.append( (self._parse_registers,tag,0) )
#                    self._parse_registers(tag,0)
                case "peripherals":
                    deferred_list_p.append( (self._parse_peripheral,tag) )
#                    self._parse_peripherals(tag)
                case "size":
                    self.group_bit_size = int(tag.text)
                case _:
                    if( tag.tag not in { } ):
                        print(f"Never before seen group tag <{tag.tag}>{tag.text}</{tag.tag}>")

        for f,p in deferred_list_p:
            f(p)
        for f,p0,p1 in deferred_list_r:
            f(p0,p1,None)
#        self.group_bit_size = None

    def _parse_groups( self, node ):
        for tag in node:
            match(tag.tag):
                case "group":
                    self._parse_group(tag)
                case _:
                    if( tag.tag not in { } ):
                        print(f"Never before seen groups tag <{tag.tag}>{tag.text}</{tag.tag}>")


    def _parse_cpu( self, node ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
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
                case "endian":
                    self.endian = tag.text
                case _:
                    if( tag.tag not in { "fpuPresent","mpuPresent","nvicPrioBits","vendorSystickConfig","vtorPresent", "fpuDP", "sauNumRegions", "sauRegionsConfig", "dspPresent","icachePresent", "pmuPresent","dcachePresent", "pmuNumEventCnt", "itcmPresent","dtcmPresent" } ):
                        print(f"Never before seen cpu tag <{tag.tag}>{tag.text}</{tag.tag}>")

        if( dp_name is not None and self.cpu.name is not None ):
            self.cpu_description.cpu_map[self.cpu.name] = dp_name
#        if( dp_name is not None and self.cpu.name is None ):
#            print("Display name cpu only {dp_name}")

    def _parse_cluster_register( self, node, base_address, peripheral_name, grp_prefix,prefix,suffix ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
        reg = svd_device.register()
        reg.parse_xml(node,base_address,self.group_bit_size)
#        print("reg.get_short_name() = '%s'" % (reg.get_short_name(),) )
        if( reg.name is not None ):
            reg.name = grp_prefix + "." + prefix + reg.name + suffix
        if( reg.display_name is not None ):
            reg.display_name = grp_prefix + "." + reg.display_name
#        print("reg.get_short_name() = '%s'" % (reg.get_short_name(),) )
        if( reg.name in self.register_names ):
            print(f"Duplicate register name {reg.name}")
        if( reg.bit_size is None and self.group_bit_size is not None ):
            reg.bit_size = self.group_bit_size
#            reg.type=vdb.arch.uint(reg.bit_size)
        reg.peripheral_name = peripheral_name
#        reg._dump()
        self.registers.append(reg)


    def _parse_cluster( self, node, base_base, peripheral_name,prefix,suffix ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
        dim = None
        dim_increment = None
        dim_index = None
        name = None
        description = None
        address_offset = None

        register_nodes = []
        for tag in node:
            match(tag.tag):
                case "dim":
                    dim = tag.text
                case "dimIncrement":
                    dim_increment = tag.text
                case "dimIndex":
                    dim_index = tag.text
                case "name":
                    name = tag.text
                case "description":
                    description = tag.text
                case "addressOffset":
                    address_offset = vdb.util.rxint(tag.text)
                case "register":
                    register_nodes.append(tag)
                case _:
                    # TODO alternateCluster to get the description from
                    if( tag.tag not in { "alternateCluster", "headerStructName"} ):
                        print(f"Never before seen cluster tag <{tag.tag}>{tag.text}</{tag.tag}>")
#        vdb.util.bark() # print("BARK")
        for rnode in register_nodes:
            itme = None
#            print("name = '%s'" % (name,) )
            if( dim is not None ):
                itme=range(0,int(dim))
            if( dim_index is not None ):
                itme=dim_index.split(",")
            base_address = base_base
            if( dim_increment is not None ):
                dim_increment = vdb.util.rxint(dim_increment)
            if( itme is None ):
                self._parse_cluster_register(rnode,base_address, peripheral_name, name,prefix,suffix)
            else:
                for it in itme:
                    reg_name = name % it
#                print("it = '%s'" % (it,) )
#                print("reg_name = '%s'" % (reg_name,) )
                    self._parse_cluster_register(rnode,base_address, peripheral_name, reg_name,prefix,suffix)
                    base_address += dim_increment
#        sys.exit(1)

    def _parse_register( self, node, base_address, peripheral_name,prefix,suffix ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
        reg = svd_device.register()
        reg.parse_xml(node,base_address,self.group_bit_size)
        reg.name = prefix + reg.name + suffix
        if( reg.name in self.register_names ):
            print(f"Duplicate register name {reg.name}")
        if( reg.bit_size is None and self.group_bit_size is not None ):
            reg.bit_size = self.group_bit_size
#            reg.type=vdb.arch.uint(reg.bit_size)
        reg.peripheral_name = peripheral_name
        self.registers.append(reg)

    def _parse_registers( self, node, base_address, peripheral_name,prefix,suffix ):
        if( len(node.attrib) > 0 ):
            print("node.attrib = '%s'" % (node.attrib,) )
        for tag in node:
            match(tag.tag):
                case "register":
                    self._parse_register(tag,base_address,peripheral_name,prefix,suffix)
                case "cluster":# TODO Wait, whats that? We need to support them for the stm32-svd tinygo files
                    self._parse_cluster(tag,base_address,peripheral_name,prefix,suffix)
                case _:
                    if( tag.tag not in { } ):
                        print(f"Never before seen group tag <{tag.tag}>{tag.text}</{tag.tag}>")
#                    pass

    def _parse_peripheral( self, node ):
        derived = node.attrib.get("derivedFrom",None)
        dnode = None
        if( derived is not None ):
#            print("derived = '%s'" % (derived,) )
            dnode = self.peripherals.get(derived,None)
#            print("dnode = '%s'" % (dnode,) )
        base_address = None
        deferred_list=[]
        peripheral_name = None
        prefix=""
        suffix=""
        dim = 1
        dim_increment = 0
        dim_index = None

        for tag in node:
            match(tag.tag):
                case "registers":
                    deferred_list.append( (self._parse_registers, tag) )
#                    self._parse_registers(tag,base_address)
                case "baseAddress":
                    base_address = vdb.util.rxint(tag.text)
                case "name":
                    peripheral_name = tag.text
                case "size":
                    self.group_bit_size = tag.text
                case "prependToName":
                    prefix = tag.text
                case "appendToName":
                    suffix = tag.text
                case "dimIndex":
                    dim_index = tag.text
                case "dim":
                    dim = tag.text
                case "dimIncrement":
                    dim_increment = tag.text
                case "groupName":
                    # should that be part of the register?
                    pass
                case _:
                    if( tag.tag not in {"disableCondition","version","addressBlock","description","interrupt","size","access" } ):
                        print(f"Never before seen peripheral tag <{tag.tag}>{tag.text}</{tag.tag}>")

#        print("deferred_list = '%s'" % (deferred_list,) )
        if( dim is not None ):
            itme=range(0,int(dim))
        if( dim_index is not None ):
            itme=dim_index.split(",")
        for d in itme:
            full_peripheral_name = peripheral_name
            try:
                full_peripheral_name = peripheral_name % dim
            except:
                pass
            if( len(deferred_list) == 0 and dnode is not None ):
                for nn in dnode:
                    if( nn.tag == "registers" ):
#                    print("nn.tag = '%s'" % (nn.tag,) )
                        self._parse_registers(nn,base_address,full_peripheral_name,prefix,suffix)

            for f,p in deferred_list:
                f(p,base_address,full_peripheral_name,prefix,suffix)
        self.peripherals[peripheral_name] = node

    def _parse_peripherals( self, node ):
        for p in node:
            match(p.tag):
                case "peripheral":
                    self._parse_peripheral(p)
                case _:
#                    print("p.tag = '%s'" % (p.tag,) )
                    pass

    def parse_from_xml( self, xml ):
        deferred_list=[]
        for node in xml:
            match(node.tag):
                case "name":
                    deferred_list.append( (self._parse_name,node) )
#                    self._parse_name(node)
                case "cpu":
                    deferred_list.append( (self._parse_cpu,node) )
#                    self._parse_cpu(node)
                case "peripherals":
                    deferred_list.append( (self._parse_peripherals,node) )
#                    self._parse_peripherals(node)
                case "size":
                    if( self.group_bit_size is None ):
                        self.group_bit_size = node.text
                case "description":
                    self.description=node.text
                case "access":
                    # TODO: save and give as default for lower layers
                    pass
                case "addressUnitBits":
                    if( node.text != "8" ):
                        print(f"Unsupported address unit bits {node.text}")
                case _:
                    if( node.tag not in { "version", "width", "resetValue", "resetMask", "vendor", "series", "licenseText", "vendorID" } ):
                        print(f"Never before seen device tag <{node.tag}>{node.text}</{node.tag}>")
        # Sometimes we need default values defined at this level to fill into the others, so parse breadth first
        for f,p in deferred_list:
            f(p)
        # Save some memory by removing the references to the xml tree
        self.peripherals = None

def parse_device(xml):
    membefore = vdb.util.memory_info()
    ndev = svd_device()
    ndev.parse_from_xml(xml)
    memafter = vdb.util.memory_info()
    if( membefore is not None and memafter is not None ):
        rssdif = memafter.rss - membefore.rss
        ndev.memory_estimation = rssdif
    if( ndev.name is None ):
        if( ndev.description is not None ):
            ndev.name = ndev.description
        else:
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
        ndev.origin = fname
        global devices
        key_name = ndev.name
        cnt = 0
#        while( key_name in devices ):
        while( ( odev := devices.get(key_name,None) ) is not None ):
            # already there, check if it is from the same file, in that case we can just overwrite it
            if( odev.origin == ndev.origin ):
                break
            cnt += 1
            key_name = ndev.name + "." + str(cnt)
        if( key_name != ndev.name ):
            print(f"Duplicate CPU {ndev.name}, renaming to {key_name}")
        devices[key_name] = ndev

def svd_list( flt = None):
    otbl = []

    header = ["Key","Name","CPU","Registers"]
    if( verbose ):
        header.append("Origin")
        header.append("Memory")

    otbl.append( header )
    if( flt is not None ):
        flt_re = re.compile(flt)
    for k,d in sorted(devices.items()):
        if( flt is not None ):
            m = flt_re.search(d.name)
            if( m is None ):
                m = flt_re.search(d.cpu.get_name())
                if( m is None ):
                    continue
        line = []
        line.append(k)
        line.append(d.name)
        line.append(d.cpu.get_name() )
        line.append(len(d.registers))
        if( verbose ):
            line.append(d.origin)
#            line.append(d.memory_estimation)
            line.append("%.3f %s" % vdb.util.bytestr(d.memory_estimation))

        otbl.append(line)
    vdb.util.print_table(otbl)

def do_svd_scan_one(dirname,at,filter_re):
    pathlist = []
    dirname = os.path.expanduser(dirname)
    for root, dirs, files in os.walk(dirname,followlinks=True):
        for f in files:
            if( f.endswith(".svd") ):
                fullpath = os.path.join(root,f)
                if( filter_re is not None and filter_re.search(fullpath) is None ):
                    continue
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
        except KeyboardInterrupt:
            return
        except:
            traceback.print_exc()
            print(f"Failed to load {p}")

def do_svd_scan(at,argv):
    filter_re = None
    if( len(argv) > 0 ):
        filter_re = re.compile(argv[0])
#    print("at = '%s'" % (at,) )
    if( at is not None ):
        at.set_progress("[svd #/#]")
    for d in scan_dirs.elements:
        try:
            do_svd_scan_one(d,at,filter_re)
        except:
            traceback.print_exc()
            print(f"Failed to scan directory '{d}'")

lazy_task = None
def svd_scan(argv):
    # later chose between background and foreground
    if( scan_background.value ):
        global lazy_task
        lazy_task = vdb.util.async_task( do_svd_scan, argv )
        lazy_task.start()
    else:
        do_svd_scan(None,argv)

# XXX mv to some "at first promp" logic
def start():
    if( not auto_scan.value ):
        print("svd not auto scanning due to vdb-svd-auto-scan False")
        return
    svd_scan([])

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
svd/v <cmd>   - Add more information to the command
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
                    svd_scan(argv[1:])
                case _:
                    self.usage()
        except Exception as e:
            traceback.print_exc()

cmd_svd()


# TODO:
# Rewrite hierarchial data to pass along some context object with a dict or members that tells for the lower levels what
# attributes are to be inherited. It shall not leak into siblings.
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
