#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration value handling
"""

import vdb.util

import gdb

import sys
import types
import traceback

PARAM_COLOUR = 0x800
PARAM_COLOR  = PARAM_COLOUR
PARAM_FLOAT  = 0x801


def guess_gdb_type( p ):
#    print("Guess type of %s is %s" % (p,type(p)))
    if( isinstance(p,bool) ): # a python bool is a python int too
        return gdb.PARAM_BOOLEAN
    if( isinstance(p,int) ):
        return gdb.PARAM_INTEGER
    if( isinstance(p,float) ):
        return PARAM_FLOAT
    return gdb.PARAM_STRING

def split_colors( cfg ):
    cfg.elements = cfg.value.split(";")

# In case the type is our artifical type colour, it will translate to gdb string and we check internally for a colour
# string
class parameter(gdb.Parameter):
    def __init__(self, name, default, docstring = "value of %s", gdb_type = None, on_set = None ):
        docstring = docstring % name
        self.docstring = docstring
        self.name = name
        self.default = default
        self.theme_default = None
        self.set_doc = 'Set ' + docstring
        self.show_doc = docstring + ':'
        self.is_colour = False
        self.is_float = False
        if( gdb_type == PARAM_COLOR ):
            if( name.find("-colors-") == -1 ):
                raise Exception("Colour names must have -colors- in their name, '%s' does not" % name )
            self.is_colour = True
            gdb_type = gdb.PARAM_STRING
            self.theme_default = default
        if( gdb_type is None ):
            gdb_type = guess_gdb_type(default)
        if( gdb_type is  PARAM_FLOAT ):
            self.is_float = True
            self.fvalue = float(default)
            default = str(float(default))
            gdb_type = gdb.PARAM_STRING
        super(parameter, self).__init__(name, gdb.COMMAND_SUPPORT, gdb_type )
        self.value = default
        self.previous_value = self.value
        self.on_set = on_set
        try:
            if( self.on_set is not None ):
                self.on_set(self)
        except:
            pass

    def check_colour( self ):
        x = vdb.color.color("",self.value)

    def get_set_string(self):
#        print("self.name = '%s'" % self.name )
#        print("self.value = '%s'" % self.value )
        try:
            if isinstance(self.value, str):
                self.value = vdb.util.unquote(self.value)
            if( self.value == "None" ):
                self.value = None
            elif( self.value == "default" ):
                self.value = self.default
            if( self.is_colour ):
                self.check_colour()
            if( self.is_float ):
                self.fvalue = float(self.value)
            if( self.on_set is not None ):
                self.on_set(self)
        except:
            traceback.print_exc()
            self.value = self.previous_value
            raise
        self.previous_value = self.value
        pval = self.value
        if isinstance(self.value, str):
            if( len(pval) == 0 ):
                pval = "None"

        if( verbosity.value is None or verbosity.value < 2 ):
            return ""
        if( self.is_colour ):
            return 'Set %s to %s' % (self.docstring, vdb.color.color(pval,self.value))
        else:
            return 'Set %s to %r' % (self.docstring, pval )

    def get_show_string(self, svalue):
        return '%s (currently: %r)' % (self.docstring, self.value)


verbosity = parameter("vdb-config-verbosity",3)


def set_string( s ):
    s = s.strip()
    if(len(s) == 0):
        return
    if( s[0] == "#" ):
        return
    try:
#        print("s = '%s'" % s )
        gdb.execute(f"set {s}")
    except:
        print(f"Failed to set {s}")
#        traceback.print_exc()

def set_iterable( l ):
    for i in l:
        set_string(i)

def set( s ):
    if( isinstance(s,str) ):
        xs = s.splitlines()
        set_iterable(xs)
    else:
        set_iterable(s)

def execute_string( s ):
    s = s.strip()
    if(len(s) == 0):
        return
    if( s[0] == "#" ):
        return
    try:
#        print("s = '%s'" % s )
        gdb.execute(f"{s}")
    except:
        print(f"Failed to execute {s}")
#        traceback.print_exc()

def execute_iterable( l ):
    for i in l:
        execute_string(i)

def execute( s ):
    if( isinstance(s,str) ):
        xs = s.splitlines()
        execute_iterable(xs)
    else:
        execute_iterable(s)


def set_array_elements( cfg ):
    cfg.elements = []
    elem = cfg.value.split(",")
    for i in elem:
        i=i.split(":")
        if( len(i) == 1 ):
            cfg.elements.append(int(i[0]))
        elif( len(i) == 2):
            s=int(i[0])
            e=int(i[1])
            if( s > e ):
                cfg.elements += list( range(s,e-1,-1) )
            else:
                cfg.elements += list( range(s,e+1) )
        else:
            s=int(i[0])
            e=int(i[1])
            r=int(i[2])
            if( s > e ):
                cfg.elements += list( range(s,e-1,-r) )
            else:
                cfg.elements += list( range(s,e+1,r) )
#    print("cfg.elements = '%s'" % cfg.elements )


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
