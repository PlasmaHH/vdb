#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb
import vdb.shorten

import gdb

import itertools
import re


vdb.enabled_modules.append("layout")

class byte_descriptor:
    def __init__(self,prefix,fname,ftype):
        self.prefix = prefix
        self.type = ftype
        self.member_name = fname
        self.code = None
        self.endcode = None

    def name( self ):
        return f"{self.prefix}::{self.member_name}"

class type_layout:
    def __init__ (self, atype ):
        self.bytes = []
        self.max_type_len = 0
        self.max_code_len = 0
        self.max_name_len = 0
        self.outer_type_name = ""
        self.atype = atype
        self.VTT = None
        self.parse(atype,0,"")

    def parse (self, atype, level, name, outername = "", offset = None):
        mprefix = outername

        # first/outer call, initialize a few things
        if( offset is None ):
            offset = 0
            self.bytes = list(itertools.repeat(byte_descriptor(None,None,None),atype.sizeof))
            self.max_type_len = 0
            mprefix = atype.name
            mprefix = vdb.shorten.symbol(mprefix)
            self.outer_type_name = atype.name

        if( offset < 0 ):
#            print(" ---- WARNING VIRTUAL INHERITANCE : GDB DOESN'T GIVE ENOUGH INFORMATION TO PROPERLY POSITION OBJECT ---- ")
            if( self.VTT is None ):
                af = atype.fields()[0]
                cmd = "p &'VTT for %s'" % (self.outer_type_name)
#                print("cmd = '%s'" % cmd )
                ofresult = gdb.execute(cmd,False,True)
#                print("ofresult = '%s'" % ofresult )
                g = re.search("(0x[a-fA-F0-9]*) <VTT for",ofresult)
#                print("g = '%s'" % g )
#                print("g.group(1) = '%s'" % g.group(1) )
                self.VTT=g.group(1)
            cmd="p ((uint64_t*)(%s%s))[0]" % (self.VTT,offset)
            ofresult = gdb.execute(cmd,False,True)
#            print("ofresult = '%s'" % ofresult )
            g = re.search("= ([0-9]*)",ofresult)
            newoffset=g.group(1)
            offset = int(newoffset)

        if name is None:
            name = ''
        tag = atype.tag
        if tag is None:
            tag = ''


        kind = 'struct' if atype.code == gdb.TYPE_CODE_STRUCT else 'union'
#        print ('/* %4d     */ %s%s %s {' % (atype.sizeof, ' ' * (2 * level), kind, tag))
        endpos = 0
#        print("atype.code = '%s'" % atype.code )
        for field in atype.fields():
            # Skip static fields
            if not hasattr (field, ('bitpos')):
                continue
            # find the type
            ftype = field.type.strip_typedefs()
            ftypename = ftype.name
            if( ftypename is None ):
                ftypename = str(ftype)
#            print("ftypename = '%s'" % ftypename )
#            print("field.__dict__ = '%s'" % field.__dict__ )
#            print("ftype = '%s'" % ftype )
#            print("ftype.name = '%s'" % ftype.name )
#            print("ftypename = '%s'" % ftypename )
#            print("field = '%s'" % field )
#            print("field.artificial = '%s'" % field.artificial )
#            print("field.name = '%s'" % field.name )

            bytepos = field.bitpos // 8
#            print("ftype = '%s'" % ftype )
            if ftype.code != gdb.TYPE_CODE_STRUCT:
#                print("offset = '%s'" % offset )
#                print("bytepos = '%s'" % bytepos )
#                print("ftype.sizeof = '%s'" % ftype.sizeof )
                for i in range(offset+bytepos,offset+bytepos+ftype.sizeof):
#                    print("i = '%s'" % i )
                    bd = byte_descriptor( mprefix,field.name, ftype )
                    self.bytes[i] = bd
                    self.max_name_len = max(self.max_name_len, len(bd.name()) )
                    self.max_type_len = max(self.max_type_len, len(str(ftype)) )

            # Detect hole
            if endpos < field.bitpos:
                hole = field.bitpos - endpos
#                print ('/* XXX %d bit hole, try to pack */' % hole)

            # Are we a bitfield?
            if field.bitsize > 0:
                fieldsize = field.bitsize
            else:
                if (ftype.code == gdb.TYPE_CODE_STRUCT or ftype.code == gdb.TYPE_CODE_UNION) and len(ftype.fields()) == 0:
                    fieldsize = 0 # empty struct
                else:
                    fieldsize = 8 * ftype.sizeof # will get packing wrong for structs

#            print("field.bitpos = '%s'" % field.bitpos )
#            print ('/* %3d %4d */' % (field.bitpos // 8, fieldsize // 8), end="")
            endpos = field.bitpos + fieldsize

            if ftype.code == gdb.TYPE_CODE_STRUCT:
                self.parse (ftype, level + 1, field.name, mprefix + "::" + field.name,offset+bytepos)
#            else:
#                print (' ' * (4 + 2 * level), end="")
#                print ('%s %s' % (str (ftype), field.name))

        code = "%s%s %s { // %4d" % ( ' ' * (2 * level), kind, tag,atype.sizeof)
        endcode = " " * (2*level) + "} // %s" % atype.name
        self.max_code_len = max(self.max_code_len,len(code))
        self.max_code_len = max(self.max_code_len,len(endcode))
        self.bytes[offset].code = code
        asof = atype.sizeof-1
        self.bytes[offset+asof].endcode = endcode
#        print (' ' * (14 + 2 * level), end="")
#        print ('} %s' % name)
        if( endpos//8 < atype.sizeof ):
            hole = (8*atype.sizeof) - endpos
#            print('/* XXX %d bit hole at the end, might be packed by the compiler */' % hole)







# vim: tabstop=4 shiftwidth=4 expandtab ft=python
