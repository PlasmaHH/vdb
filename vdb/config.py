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
PARAM_COLOR = PARAM_COLOUR


def guess_gdb_type( p ):
#    print("Guess type of %s is %s" % (p,type(p)))
    if( isinstance(p,bool) ): # a python bool is a python int too
        return gdb.PARAM_BOOLEAN
    if( isinstance(p,int) ):
        return gdb.PARAM_INTEGER
    return gdb.PARAM_STRING

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
        if( gdb_type == PARAM_COLOR ):
            if( name.find("-colors-") == -1 ):
                raise Exception("Colour names must have -colors- in their name, '%s' does not" % name )
            self.is_colour = True
            gdb_type = gdb.PARAM_STRING
            self.theme_default = default
        if( gdb_type is None ):
            gdb_type = guess_gdb_type(default)
        super(parameter, self).__init__(name, gdb.COMMAND_SUPPORT, gdb_type )
        self.value = default
        self.previous_value = self.value
        self.on_set = on_set

    def check_colour( self ):
        x = vdb.color.color("",self.value)

    def get_set_string(self):
        try:
            if isinstance(self.value, str):
                self.value = vdb.util.unquote(self.value)
            if( self.value == "None" ):
                self.value = None
            elif( self.value == "default" ):
                self.value = self.default
            if( self.is_colour ):
                self.check_colour()
            if( self.on_set is not None ):
                self.on_set(self.value)
        except:
            traceback.print_exc()
            self.value = self.previous_value
            raise
        self.previous_value = self.value
        pval = self.value
        if isinstance(self.value, str):
            if( len(pval) == 0 ):
                pval = "None"
        if( self.is_colour ):
            return 'Set %s to %s' % (self.docstring, vdb.color.color(pval,self.value))
        else:
            return 'Set %s to %r' % (self.docstring, pval )

    def get_show_string(self, svalue):
        return '%s (currently: %r)' % (self.docstring, self.value)


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

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
