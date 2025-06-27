#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.cache
import vdb.color
import vdb.config
import vdb.util
import vdb.register
import vdb.hexdump

import gdb
import gdb.types

import os
import traceback
import re
import sys
import copy
import lzma
import time
import concurrent.futures
import json



auto_scan = vdb.config.parameter("vdb-svd-auto-scan",True,docstring="scan configured directories on start")
scan_dirs = vdb.config.parameter("vdb-svd-directories","~/svd/",gdb_type=vdb.config.PARAM_ARRAY )
scan_recur= vdb.config.parameter("vdb-svd-scan-recursive",True,docstring="Whether to scan directories recursively")
scan_background = vdb.config.parameter("vdb-svd-scan-background",True,docstring="Do the scan in the background")
scan_filter = vdb.config.parameter("vdb-svd-scan-filter","",docstring="Regexp to filter file names before loading")
scan_silent = vdb.config.parameter("vdb-svd-scan-silent",True,docstring="Don't ouput every file being scanned")
parse_delayed = vdb.config.parameter("vdb-svd-parse-delayed",False,docstring="When true, parse only fully when an svd load command is issued")
threads = vdb.config.parameter("vdb-svd-use-threads",True)


verbose = False
try:
#    test_xml_etree()
    import defusedxml.ElementTree as ET
#    from defusedxml.ElementTree import parse
except:
    import xml.etree.ElementTree as ET
#    from xml.etree.ElementTree import parse

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

    class parse_context:

        def __init__( self ):
            self.bit_size = None
            self.access = None
            self.base_address = None
            self.peripheral_name = ""
            self.prefix = ""
            self.suffix = ""
            self.reset_value = None
            self.group = None

        def clone( self ):
            return copy.copy(self)

    class register:

        class field:
            def __init__( self ):
                self.name = None
                self.description = None
                self.bit_pos = None
                self.bit_size = None
                self.access = None

            def register_description( self ):
                pass



        __slots__ = "name","display_name","mmap_address","bit_size","description","reset_value","access","peripheral_name","fields","group","altname"

        def __init__( self ):
            #svd xml fields
            self.name = None
            self.altname = None
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
            self.group = None

            # generated/cached fields
            self.fields = []

        def finish( self ):
            if( len(self.description) > 0 ):
                raise RuntimeError("Non empty register descriptions, something went wrong on loading")
            for s in self.__slots__:
                attr = getattr(self,s)
                if( attr is not None ):
                    if( isinstance(attr,str) ):
                        setattr( self, s, vdb.cache.pool_get(attr) )
            for f in self.fields:
                desc = None
                if( f.description is not None ):
                    desc = f.description.replace("\n"," ")
                    desc = vdb.cache.pool_get(desc)
                f.name = vdb.cache.pool_get(f.name)
                # see registery.py for the layout#
                # TODO In case we have "enums" add them here too instead of the None
                # TODO add to the register format there also something for the access specifier in order to support
                # write only fields (reading the register there would otherwise blacklist them)
                self.description[f.bit_pos] = ( f.bit_size, f.name, desc, None, self.access )

            # Save some memory
            self.fields = None

        def _dump( self ):
            addr=self.mmap_address
            if( addr is None ):
                addr = 0
            print(f"P={self.peripheral_name} D={self.display_name} N={self.name} G={self.group} @{addr:#0x}[{self.bit_size}] => {self.get_key_name()}")
            for pos,t5 in self.description.items():
                sz,name,desc,_,amap = t5
                print(f"    {name}[{sz}]\t{desc} {amap=}")


        def _parse_field( self, ctx, node ):
#            vdb.util.bark() # print("BARK")
            pos  = None
            sz   = None
            name = None
            desc = None
            access = None
            dim_inc = 0
            dim = None
            dim_index = None
            lsb = None
            msb = None

            for n in node:
#                print("n.tag = '%s'" % (n.tag,) )
#                print("n.text = '%s'" % (n.text,) )
                match(n.tag):
                    case "name":
                        name = n.text
                    case "description":
                        desc = n.text
                        if( desc is not None ):
                            desc = re.sub(r"\s+", " ", desc )
                    case "bitOffset":
                        pos = vdb.util.rxint(n.text)
                    case "bitWidth":
                        sz = vdb.util.rxint(n.text)
                    case "access":
                        access=access_map(n.text)
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
#                        print("pos = '%s'" % (pos,) )
                    # TODO here we have to take the name and generate multiple register fields out of it ( same for
                    # registers ). See e.g. https://siliconlabs.github.io/Gecko_SDK_Doc/CMSIS/SVD/html/group__dim_element_group__gr.html
                    case "dimIncrement":
                        dim_inc = vdb.util.rxint(n.text)
                    case "dimIndex":
                        dim_index = n.text
                    case "dim":
                        dim = vdb.util.rxint(n.text)
                    case "lsb":
                        lsb = vdb.util.rxint(n.text)
                    case "msb":
                        msb = vdb.util.rxint(n.text)
                    case "writeConstraint": # TODO need to figure out what this is
                        pass
                    case "readAction": # afaik we can ignore this for our needs
                        pass
                    case "resetValue":
                        pass
                    case _:
                        if( n.tag not in { "modifiedWriteValues" } ):
                            print(f"Never before seen register field tag <{n.tag}>{n.text}</{n.tag}>")

            if( lsb is not None and msb is not None ):
                pos = lsb
                sz = (msb - lsb) + 1
            if( dim_index is not None ):
                dim_index = dim_index.split(",")

            if( dim_index is not None ):
                items = ( name % i for i in dim_index )
            elif( dim is not None ):
                items = ( name % i for i in range(0,dim) )
            else:
                items = [ name ]
            
            if( pos is None ):
                return
            for it in items:
#                self.description[pos] = svd_device.register.field( sz, it, desc, None, access_map(access) )
                f = svd_device.register.field( )

                f.name = it
                f.description = desc
                f.bit_pos = pos
                f.bit_size = sz
                f.access = access_map(access)
                self.fields.append(f)
                pos += dim_inc


        def _parse_fields( self, ctx, node ):
            for f in node:
                match(f.tag):
                    case "field":
                        self._parse_field(ctx,f)
#            print("self.name = '%s'" % (self.name,) )
#            print("self.description = '%s'" % (self.description,) )

        def get_key_name( self ):
            sname = self.get_short_name()
#            print("self.peripheral_name = '%s'" % (self.peripheral_name,) )
            if( self.peripheral_name is not None ):
                sname = self.peripheral_name + "." + sname
            return sname

        def get_short_name( self ):
#            vdb.util.bark() # print("BARK")
#            print("self.name = '%s'" % (self.name,) )
#            print("self.display_name = '%s'" % (self.display_name,) )
            if( self.display_name is None ):
                return self.name
            if( len(self.display_name) < len(self.name) ):
                return self.display_name
            return self.name

        def __str__( self ):
            ret = f"{self.name}@{self.mmap_address:#0x}[{self.bit_size}])"
            return ret
     
    def __init__( self ):
        self.name = None
        self.description = None
        self.registers = []
        self.register_names = set()
        self.cpu = svd_device.cpu_description()
        self.origin = None # file name, set externally after parsing completed
        self.peripherals = {}
        self.memory_estimation = None
        self.derive_registers = {}
        self.version = None
        self.file_size = None
        self.hash = None

    def load( self, unload = True ):
        print(f"Loading {len(self.registers)} register descriptions")
        vdb.register.mmapped_blacklist = {}
        if( unload ):
            vdb.register.mmapped_descriptions = {}
            vdb.register.mmapped_positions = {}
            print("Removed all previous register descriptions (use svd/k load to keep them)")
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
                    print(f"{r.display_name} ({r.name} has no bit_size")
                # TODO configureable? intresting at all?
#                if( bitsize is None ):
#                    bitsize = 32
#                    rtype=vdb.arch.uint(bitsize)

                vdb.register.mmapped_descriptions[name] = (name, bitsize, r.description, None )
#                print(f"{name} => @{r.mmap_address}[{bitsize}] = {rtype}")
                vdb.register.mmapped_positions[name] = ( name, r.mmap_address, bitsize, rtype )
                vdb.hexdump.annotate_range(r.mmap_address, bitsize//8, name )
        if( skip > 0 ):
            print(f"Skipped {skip} registers due to unkonwn mapping position.")

    def _parse_name( self, ctx, node ):
        self.name = node.text

    def _parse_group( self, ctx, node ):
        if( len(node.attrib) > 0 ):
            vdb.util.bark() # print("BARK")
            print("node.attrib = '%s'" % (node.attrib,) )
        access = ctx.access
        group = ctx.group
        bit_size = ctx.bit_size
        deferred_list=[]
        for tag in node:
            match(tag.tag):
                # TODO check file formats, we are missing base address and peripheral name here. Whats our parent data?
                case "registers":
                    deferred_list.append( (self._parse_registers,tag) )
#                    self._parse_registers(tag,0)
                case "peripherals":
                    deferred_list.append( (self._parse_peripherals,tag) )
#                    self._parse_peripherals(tag)
                case "size":
                    bit_size = vdb.util.rxint(tag.text)
                case "access":
                    access = access_map(tag.text)
                case "name":
                    group = tag.text
                case "groups":
                    self._parse_groups(ctx,tag)
                case _:
                    if( tag.tag not in {"type","description","type","IsCPUModeItem" } ):
                        print(f"Never before seen group tag <{tag.tag}>{tag.text}</{tag.tag}>")

        ctx = ctx.clone()
        ctx.access = access
        ctx.group = group
        ctx.bit_size = bit_size
        for f,p in deferred_list:
            f(ctx,p)

    def _parse_groups( self,ctx, node ):
        for tag in node:
            match(tag.tag):
                case "group":
                    self._parse_group(ctx,tag)
                case _:
                    if( tag.tag not in { } ):
                        print(f"Never before seen groups tag <{tag.tag}>{tag.text}</{tag.tag}>")


    def _parse_cpu( self, ctx, node ):
        if( len(node.attrib) > 0 ):
            vdb.util.bark() # print("BARK")
            print("node.attrib = '%s'" % (node.attrib,) )
        dp_name=None
        for tag in node:
            match(tag.tag):
                case "groups":
                    self._parse_groups(ctx,tag)
                case "name":
                    self.cpu.name = tag.text
                case "displayName":
                    dp_name = tag.text
                case "revision":
                    self.cpu.revision = tag.text
                case "endian":
                    self.endian = tag.text
                case _:
                    if( tag.tag not in { "fpuPresent","mpuPresent","nvicPrioBits","vendorSystickConfig","vtorPresent", "fpuDP", "sauNumRegions", "sauRegionsConfig", "dspPresent","icachePresent", "pmuPresent","dcachePresent", "pmuNumEventCnt", "itcmPresent","dtcmPresent", "deviceNumInterrupts" } ):
                        print(f"Never before seen cpu tag <{tag.tag}>{tag.text}</{tag.tag}>")

        if( dp_name is not None and self.cpu.name is not None ):
            self.cpu_description.cpu_map[self.cpu.name] = dp_name
#        if( dp_name is not None and self.cpu.name is None ):
#            print("Display name cpu only {dp_name}")

    def _parse_cluster_register( self, ctx, node ):
        return self._parse_register(ctx,node)

    def _parse_cluster( self, ctx, node ):
#        vdb.util.bark() # print("BARK")
#        print("node = '%s'" % (node,) )
#        print("node.tag = '%s'" % (node.tag,) )
        if( len(node.attrib) > 0 ):
            vdb.util.bark() # print("BARK")
            print("node.attrib = '%s'" % (node.attrib,) )
        dim = None
        dim_increment = None
        dim_index = None
        name = None
        description = None
        address_offset = None
        base_address = ctx.base_address
        bit_size = ctx.bit_size
        access = ctx.access

        register_nodes = []
        for tag in node:
#            print("tag.tag = '%s'" % (tag.tag,) )
#            if( tag.text is not None ):
#                print("tag.text = '%s'" % (tag.text.strip(),) )
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
                case "size":
                    bit_size = vdb.util.rxint(tag.text)
                case "access":
                    access = tag.text
                case "cluster":
                    # I don't think this is as per spec but there are files doing it
                    self._parse_cluster( ctx, tag )
                case _:
                    # TODO alternateCluster to get the description from
                    if( tag.tag not in { "alternateCluster", "headerStructName"} ):
                        print(f"Never before seen cluster tag <{tag.tag}>{tag.text.strip()}</{tag.tag}>")
#                        vdb.util.bark(-2) # print("BARK")
#                        vdb.util.bark(-1) # print("BARK")
#                        vdb.util.bark() # print("BARK")
#        vdb.util.bark() # print("BARK")
        ctx = ctx.clone()
        ctx.bit_size = bit_size
        ctx.base_address = base_address
        ctx.access = access
        for rnode in register_nodes:
            itme = None
#            print("name = '%s'" % (name,) )
            if( dim is not None ):
                itme=range(0,int(dim))
            if( dim_index is not None ):
                itme=dim_index.split(",")
            base_address = ctx.base_address
            if( dim_increment is not None ):
                dim_increment = vdb.util.rxint(dim_increment)
            if( itme is None ):
                self._parse_cluster_register(ctx,rnode)
            else:
                for it in itme:
                    reg_name = name % it
#                print("it = '%s'" % (it,) )
#                print("reg_name = '%s'" % (reg_name,) )
#                    self._parse_cluster_register(rnode,base_address, peripheral_name, reg_name,prefix,suffix)
                    self._parse_cluster_register(ctx,rnode)
                    base_address += dim_increment
#        sys.exit(1)

    def _parse_register( self, ctx, node ):
#        if( len(node.attrib) > 0 ):
#            vdb.util.bark() # print("BARK")
#            print("node.attrib = '%s'" % (node.attrib,) )

        bit_size = ctx.bit_size
        name = None
        base_address = ctx.base_address
        mmap_address = None
        display_name = None
        name = None
        prefix = ctx.prefix
        suffix = ctx.suffix
        access = ctx.access
        description = None
        reset_value = ctx.reset_value
        altname = None
        group = ctx.group

        dim = None
        dim_index = None
        dim_increment = 0
        peripheral_name = ctx.peripheral_name


        fields_nodes = []

        for n in node:
            match(n.tag):
                case "name":
                    name = n.text
                case "displayName":
                    display_name = n.text
                case "addressOffset":
                    mmap_address = int(base_address + vdb.util.rxint(n.text))
                case "resetValue":
                    reset_value = vdb.util.rxint(n.text)
                case "size":
                    bit_size = vdb.util.rxint(n.text)
                case "width":
                    bit_size = vdb.util.rxint(n.text)
                case "access":
                    access = access_map(n.text)
                case "description":
                    description = n.text
                case "fields":
                    fields_nodes.append(n)
                case "dim":
                    dim = vdb.util.rxint(n.text)
                case "dimIncrement":
                    dim_increment = vdb.util.rxint(n.text)
                case "dimIndex":
                    dim_index = n.text
                case "alternateRegister":
                    altname = n.text
                case "groupName":
                    group = n.text
                case "type":
                    pass
                case "dataType":
                    # TODO this might be useful for the register descriptions stuff
                    pass
                case "field":
                    # TODO some files are broken and have this here
                    pass
                case _:
                    # TODO write Constraint is very intresting for preventing crashes, but we would need extensive
                    # register support for that
                    if( n.tag not in { "resetMask", "modifiedWriteValue", "modifiedWriteValues", "writeConstraint", "alternateGroup", "readAction", "range", "enumeratedValues", "Index","AliasName","reset","Index","ID","Index1","Index2" } ):
#                        print("name = '%s'" % (name,) )
                        print(f"Never before seen register tag <{n.tag}>{n.text}</{n.tag}>")
#                        print("n.tag = '%s'" % (n.tag,) )
                    pass

        ctx= ctx.clone()
        ctx.bit_size = bit_size
        ctx.access = access
        ctx.reset_value = reset_value
        ctx.base_address = base_address
        ctx.group = group
        derived = node.attrib.get("derivedFrom",None)

        num_items = 0
        # BUG !!
        # dim_index is a string and we act like its a list of something
        if( dim_index is not None ):
            num_items = len(dim_index)
            items = list( name % i for i in dim_index )
#            print(f"{items=}")
            try:
                if( altname is not None ):
                    altitems = list( altname % i for i in dim_index )
            except:
                altitems = list( altname + i for i in dim_index )

            try:
                if( derived is not None ):
                    ditems = list( derived % i for i in dim_index )
            except:
                ditems = items
            dpyitems = []
            try:
                if( display_name is not None ):
                    dpyitems = list( display_name % i for i in dim_index )
            except:
                if( name is not None ):
                    dpyitems = list( name % i for i in dim_index )

        elif( dim is not None ):
            num_items = dim
#            print("self.name = '%s'" % (self.name,) )
#            print("name = '%s'" % (name,) )
            try:
                items = list( name % i for i in range(0,dim) )
            except:
                items = [ name ] * num_items
            if( altname is not None ):
                try:
                    altitems = list( altname % i for i in range(0,dim) )
                except TypeError:
                    altitems = [ altname ] * num_items
            if( derived is not None ):
                ditems = ( derived % i for i in range(0,dim) )
            if( display_name is not None ):
                dpyitems = ( display_name % i for i in range(0,dim) )
        else:
            num_items = 1
            items = [ name ]
            if( altname is not None ):
                altitems = [ altname ]
            if( derived is not None ):
                ditems = [ derived ]
            if( display_name is not None ):
                dpyitems = [display_name]

        if( altname is None ):
            altitems = [ None ] * num_items
        if( derived is None ):
            ditems = [ None ] * num_items
        if(display_name is None ):
            dpyitems = [ None ] * num_items

        if( mmap_address is None ):
            return

        for it,alt,der,dpname in zip(items,altitems,ditems,dpyitems):
            rctx = ctx.clone()
            rctx.base_address = mmap_address
            reg = svd_device.register()

            fields = []
            
            # XXX Should we delay parsing of them until we have all normal registers to allow for different order? Possibly
            # need to loop through them when one derived depends on another derived....
            if( der is not None ):
                rdict = self.derive_registers.get(der,None)
                if( rdict is None ):
                    print(f"derivedFrom {der} but register not found")
                else:
                    fields = rdict.fields
                    for attr in [ "bit_size", "access", "peripheral_name", "reset_value" ]:
                        rav = getattr(rdict,attr)
                        if( rav is not None ):
                            setattr(rctx,attr,rav)

            if( alt is not None ):
                reg.altname = prefix + alt + suffix
            reg.name = prefix + it + suffix
            if( reg.name in self.register_names ):
                print(f"Duplicate register name {reg.name}")
            if( dpname is not None ):
                reg.display_name = prefix + dpname + suffix

            reg.bit_size = bit_size
            reg.peripheral_name = peripheral_name
            reg.mmap_address = mmap_address
            reg.group = rctx.group
            reg.fields = fields
            for f in fields_nodes:
                reg._parse_fields(rctx,f)
            self.registers.append(reg)
            self.derive_registers[it] = reg
#            reg._dump()
            mmap_address += dim_increment



    def _parse_registers( self, ctx, node ):
#        vdb.util.bark() # print("BARK")
#        print("node = '%s'" % (node,) )
#        print("node.tag = '%s'" % (node.tag,) )
        if( len(node.attrib) > 0 ):
            vdb.util.bark() # print("BARK")
            print("node.attrib = '%s'" % (node.attrib,) )

        access = ctx.access
        deferred_list = []
        for tag in node:
            match(tag.tag):
                case "register":
                    deferred_list.append( (self._parse_register,tag) )
#                    self._parse_register(ctx,tag)
                case "cluster":
                    deferred_list.append( (self._parse_cluster,tag) )
#                    self._parse_cluster(ctx,tag)
                case "access":
                    access = access_map(tag.text)
                case _:
                    if( tag.tag not in { } ):
                        print(f"Never before seen registers tag <{tag.tag}>{tag.text}</{tag.tag}>")
#                    pass
        ctx = ctx.clone()
        ctx.access = access

        for f,n in deferred_list:
            f(ctx,n)

    def _parse_peripheral( self, ctx, node ):
        derived = node.attrib.get("derivedFrom",None)
        dnode = None
        if( derived is not None ):
#            print("derived = '%s'" % (derived,) )
            dnode = self.peripherals.get(derived,None)
#            print("dnode = '%s'" % (dnode,) )

        base_address = None
        deferred_list=[]
        peripheral_name = None
        prefix=ctx.prefix
        suffix=ctx.suffix
        dim = 1
        dim_increment = 0
        dim_index = None
        group = ctx.group
        reset_value = ctx.reset_value
        bit_size = ctx.bit_size

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
                    bit_size = vdb.util.rxint(tag.text)
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
                    group = tag.text
                case "resetValue":
                    reset_value = vdb.util.rxint(tag.text)
                case _:
                    if( tag.tag not in {"disableCondition","version","addressBlock","description","interrupt","size","access","headerStructName","resetMask","alternatePeripheral" } ):
                        print(f"Never before seen peripheral tag <{tag.tag}>{tag.text}</{tag.tag}>")

        ctx = ctx.clone()

        ctx.base_address = base_address
        ctx.prefix = prefix
        ctx.suffix = suffix
        ctx.group = group
        ctx.bit_size = bit_size

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
            pctx = ctx.clone()
            pctx.peripheral_name = full_peripheral_name
            if( len(deferred_list) == 0 and dnode is not None ):
                for nn in dnode:
                    if( nn.tag == "registers" ):
#                    print("nn.tag = '%s'" % (nn.tag,) )
                        self._parse_registers(pctx,nn)

            for f,p in deferred_list:
                f(pctx,p)
        self.peripherals[peripheral_name] = node

    def _parse_peripherals( self, ctx, node ):
        for p in node:
            match(p.tag):
                case "peripheral":
                    self._parse_peripheral(ctx,p)
                case _:
#                    print("p.tag = '%s'" % (p.tag,) )
                    pass

    def finish( self ):
        """
        Parsing is done, we can drop all caches and intermediate structures to save memory now and build the final description structures
        """
        for r in self.registers:
            r.finish()
        self.derive_registers = None
        self.peripherals = None

    def parse_from_xml( self, xml ):
        ctx = svd_device.parse_context()
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
                    ctx.bit_size = vdb.util.rxint(node.text)
                case "description":
                    self.description=node.text
                case "access":
                    ctx.access = access_map(node.text)
                case "vendorExtensions":
                    # Some svd files tell us about the flash and (s)ram layout here, we could put that into the vmmap
                    # stuff
                    pass
                case "version":
                    self.version = node.text
                case "addressUnitBits":
                    if( node.text != "8" ):
                        print(f"Unsupported address unit bits {node.text}")
                case _:
                    if( node.tag not in { "width", "resetValue", "resetMask", "vendor", "series", "licenseText", "vendorID", "headerSystemFilename", "deviceNumInterrupts", "headerDefinitionsPrefix" } ):
                        print(f"Never before seen device tag <{node.tag}>{node.text}</{node.tag}>")
        # Sometimes we need default values defined at this level to fill into the others, so parse breadth first
        for f,p in deferred_list:
            f(ctx,p)
        # Save some memory by removing the references to the xml tree
        self.peripherals = None

    def to_json( self ):
        ret = {
                "name" : self.name,
                "cpu"  : self.cpu.get_name(),
                "num_registers" : len(self.registers),
                "origin" : self.origin,
                "size" : self.file_size,
                "hash" : self.hash,
                }
        return ret

class device_stub:
    def __init__( self ):
        pass

    def load( self, unload = True ):
        pass
        # parse the svd file mentioned here

def svd_load(idname,keep):
    d = devices.get(idname,None)
    if( d is None ):
        d = dev_queue.get(idname,None)
        if( d is None ):
            print(f"Uncrecognized µC name '{idname}', list of known ones:")
            svd_list()
            return
        svd_load_file(d,None)
        d = devices.get(idname,None)
    d.load(not keep)

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
    ndev.finish()
    return ndev


dev_queue = {}

# move to util?
def any_open( fn ):
    if( fn.endswith(".xz") ):
        return lzma.open(fn,"r")
    else:
        return open(fn,"r")

def svd_queue_file(fname,at):
#    if( at is None ):
#        print(f"\r{fname}",flush=True,end="")

    device_re = re.compile("<device")
#    name_re = re.compile("<name>")
    device_name_re = re.compile("name>(.*?)</name")

    within_device = False
    version = "_"

    # XXX Handle differently versioned files here too
    with any_open(fname) as f:
        for line in f.readlines():
            if( not isinstance(line,str) ):
                line = line.decode()
            if( device_re.search(line) is not None ):
#                print("line = '%s'" % (line,) )
                within_device = True
            if( within_device ):
                m = device_name_re.search(line)
                if( m is not None ):
                    name = m.group(1)
#                    print(f" => {name}",end="")
#                    print(" "*16,flush=True,end="")
                    dev_queue[name] = fname
#                    print("m.group(1) = '%s'" % (m.group(1),) )
#                    print("line = '%s'" % (line,) )
                    break


def svd_load_file(fname,at):
    if( at is None ):
        if( not scan_silent.value ):
            print(f"Loading {fname}… ",end="")

    with any_open(fname) as f:
        data = f.read()
        if( not isinstance(data,str) ):
            data = data.decode()
        data = data.replace(" & "," &amp; ")
    if( len(data) < 16 ):
        print("File too small, does it contain anything?")
        return None

    xml = ET.fromstring(data)
    root = xml
    ndev=parse_device(root)
    if( ndev.name is None ):
        print(" contains no named CPU, discarding")
    else:
        if( not scan_silent.value ):
            print(f"=> {ndev.name}")
        ndev.origin = fname
        global devices
        key_name = ndev.name
        cnt = 0
        # Check if its knonwn already, in that case we try to rename *both* with their version number
        otherdev = devices.get(key_name,None)
        # key_name does not include version number yet
        if( otherdev is not None ):
            othernewname = otherdev.name
            if( otherdev.version is not None ):
                del devices[key_name]
                othernewname = f"{key_name}_{otherdev.version}"
                devices[othernewname] = otherdev
            if( ndev.version is not None ):
                key_name = f"{key_name}_{ndev.version}"

        oldkey = key_name
        # If we still have the same name
        while( ( odev := devices.get(key_name,None) ) is not None ):
            # already there, check if it is from the same file, in that case we can just overwrite it
            if( odev.origin == ndev.origin ):
                break
            otherdev = odev
            cnt += 1
            key_name = oldkey + "." + str(cnt)
        # ouotput message if the keyname had to change

        if( key_name != ndev.name ):
            print(f"Duplicate CPU {ndev.name}, renaming new to {key_name}, old to {othernewname}")
        ndev.hash = vdb.util.hash( fname )
        ndev.file_size = os.path.getsize( fname )
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

    for k,f in sorted(dev_queue.items()):
        if( flt is not None ):
            m = flt_re.search(k)
            if( m is None ):
                continue
        line = []
        line.append(k)
        line.append(k)
        line.append(None)
        line.append("?")
        if( verbose ):
            line.append(f)
            line.append("?")
        otbl.append(line)

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
            if( d.memory_estimation is not None ):
                line.append("%.3f %s" % vdb.util.bytestr(d.memory_estimation))
            else:
                line.append(None)

        otbl.append(line)
    vdb.util.print_table(otbl)

# do we want a global version of this? or fine grained for every plugin? or both?

keep_parsing = True

@vdb.event.gdb_exiting()
def stop_parsing( ):
    global keep_parsing
    keep_parsing = False

class task_pool:
    def __init__( self ):
        self.threads = []
        self.completed = []

    def submit( self, *args ):
        t = vdb.texe.submit( *args )
        self.threads.append(t)

    def wait( self ):
        for f in concurrent.futures.as_completed( self.threads ):
            self.completed.append(f)
            yield f

    def clear( self ):
        self.threads = []
        self.completed = []

    def cancel( self ):
        for t in self.threads:
            t.cancel()


def do_svd_scan_one(dirname,at,filter_re):
    global keep_parsing
    keep_parsing = True
    pathlist = []
    dirname = os.path.expanduser(dirname)

    for root, dirs, files in os.walk(dirname,followlinks=True):
        for f in files:
            if( f.endswith(".svd") or f.endswith(".svd.xz") ):
                fullpath = os.path.join(root,f)
                if( filter_re is not None and filter_re.search(fullpath) is None ):
                    continue
                pathlist.append(fullpath)
    filter_re = None
    if( scan_filter.value is not None and len(scan_filter.value) > 0 ):
        filter_re = re.compile(scan_filter.value)
    pt = None

    prog = vdb.util.progress_bar(num_completed = True, spinner = True)
    xtra=""
    if( filter_re is not None ):
        xtra="up to "
    if( parse_delayed.value and at is None ):
        pt = prog.add_task( f"Queueing {xtra}{len(pathlist)} SVD Files ", total = len(pathlist) )
    if( not parse_delayed.value and at is None and scan_silent.value ):
        pt = prog.add_task(f"Parsing {xtra}{len(pathlist)} SVD Files ", total = len(pathlist)  )

    if( pt is not None ):
        prog.start()

    tp = None
    if( threads.value ):
        tp = task_pool()

    for i,p in enumerate(pathlist):
        if( not keep_parsing ):
            print("Abort svd parsing")
            break
        if( filter_re is not None and filter_re.search(p) is None ):
            continue
        if( at is not None ):
            at.set_progress(f"[svd {i}/{len(pathlist)}]")
        try:
            if( parse_delayed.value ):
                if( threads.value ):
                    tp.submit( svd_queue_file,p,at)
                else:
                    svd_queue_file(p,at)
                    if( pt is not None ):
                        prog.update( pt, completed = i )
            else:
                if( threads.value ):
                    tp.submit( svd_load_file,p,at)
                else:
                    svd_load_file(p,at)
                    if( pt is not None ):
                        prog.update( pt, completed = i )
        except KeyboardInterrupt:
            prog.stop()
            if( threads.value ):
                tp.cancel()
            return
        except:
            vdb.print_exc()
            print(f"Failed to load {p}")

    if( threads.value ):
        try:
            for f in tp.wait():
                r = f.result()
                prog.update( pt, completed = len(tp.completed) )
        except KeyboardInterrupt:
            prog.stop()
            tp.cancel()
            return
        except:
            vdb.print_exc()

    prog.stop()

#    if( parse_delayed.value and at is None ):
#        print("Done")

def save_cache( ):
    x = json.dumps(devices, default = lambda x: x.to_json() )
    d = json.loads(x)
    vdb.util.pprint(d)
    vdb.cache.save_string("svd",x)

# Loads from the cache file and creates stub objects
def load_cache( ):
    x = vdb.cache.get_string("svd")
    data = json.loads(x)
    vdb.util.pprint(data)

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
            vdb.print_exc()
            print(f"Failed to scan directory '{d}'")
    save_cache( )

lazy_task = None
def svd_scan(argv, background):
    # later chose between background and foreground
    if( background ):
        global lazy_task
        lazy_task = vdb.util.async_task( do_svd_scan, argv )
        lazy_task.start()
        print("Started svd background scan")
    else:
        do_svd_scan(None,argv)

@vdb.event.before_first_prompt()
def startup():
    if( not auto_scan.value ):
        print("svd not auto scanning due to vdb-svd-auto-scan False")
        return
    svd_scan([],scan_background.value)

def get( ar, ix, alt ):
    try:
        return ar[ix]
    except:
        return alt

class cmd_svd(vdb.command.command):
    """Manage SVD file loading and the interaction with the register display

svd list      - Lists known CPU definitions
svd load <ID> - Loads svd CPU definitions, replacing everything
svd/k load    - Loads but merges with existing ones ("keep")
svd scan      - Scan configured list of directories and (re)reads the found svd definitions
svd/f scan    - Do the scan in the foreground (default is set per config)
svd/v <cmd>   - Add more information to the command
"""

    def __init__ (self):
        super (cmd_svd, self).__init__ ("svd", gdb.COMMAND_DATA)

    def complete( self, text, word ):
        if( text.startswith("/v ") or text.startswith("/k ")):
            text = text[3:]
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
            argv,flags = self.flags(argv)
            global verbose
            verbose = False
            keep = False

            background = scan_background.value
            if( "v" in flags ):
                verbose = True
            if( "k" in flags ):
                keep = True
            if( "f" in flags ):
                background = False

            subcmd = argv[0]
            match(subcmd):
                case "load":
                    if( len(argv) < 2 ):
                        raise RuntimeError("load needs CPU parameter")
                    svd_load(argv[1],keep)
                case "list":
                    svd_list(get(argv,1,None))
                case "scan":
                    svd_scan(argv[1:],background)
                case _:
                    self.usage()
        except Exception as e:
            vdb.print_exc()

cmd_svd()
# Reset: Halt core after reset via DEMCR.VC_CORERESET.
# Reset: Reset device via AIRCR.SYSRESETREQ.

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
