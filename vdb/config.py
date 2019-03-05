#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration value handling
"""

import vdb.util

import gdb

import sys
import types

PARAM_COLOUR = 0x800
PARAM_COLOR = PARAM_COLOUR


def guess_gdb_type( p ):
    if( isinstance(p,int) ):
        return gdb.PARAM_INTEGER
    if( isinstance(p,bool) ):
        return gdb.PARAM_BOOLEAN
    return gdb.PARAM_STRING

# In case the type is our artifical type colour, it will translate to gdb string and we check internally for a colour
# string
class parameter(gdb.Parameter):
    def __init__(self, name, default, docstring = "value of %s", gdb_type = None, on_set = None ):
        docstring = docstring % name
        self.docstring = docstring
        self.name = name
        self.default = default
        self.set_doc = 'Set ' + docstring
        self.show_doc = docstring + ':'
        self.is_colour = False
        if( gdb_type == PARAM_COLOR ):
            if( name.find("-colors-") == -1 ):
                raise Exception("Colour names must have -colors- in their name, '%s' does not" % name )
            self.is_colour = True
            gdb_type = gdb.PARAM_STRING
        if( gdb_type is None ):
            gdb_type = guess_gdb_type(default)
        super(parameter, self).__init__(name, gdb.COMMAND_SUPPORT, gdb_type )
        self.value = default
        self.previous_value = self.value
        self.on_set = on_set

    def check_colour( self ):
        x = vdb.color.color("",self.value)
#    @property
#    def native_value(self):
#        return value_to_gdb_native(self.value)
#
#    @property
#    def native_default(self):
#        return value_to_gdb_native(self.default)
#
#    @property
#    def is_changed(self):
#        return self.value != self.default

    def get_set_string(self):
        try:
            if isinstance(self.value, str):
                self.value = vdb.util.unquote(self.value)
            if( self.value == "default" ):
                self.value = self.default
            if( self.is_colour ):
                self.check_colour()
            if( self.on_set is not None ):
                self.on_set(self.value)
        except:
            self.value = self.previous_value
            raise
        self.previous_value = self.value
        return 'Set %s to %r' % (self.docstring, self.value)

    def get_show_string(self, svalue):
        return '%s (currently: %r)' % (self.docstring, self.value)

#    def __int__(self):
#        return int(self.value)
#
#    def __str__(self):
#        return str(self.value)
#
#    def __bool__(self):
#        return bool(self.value)
#
#    def __lt__(self, other):
#        return self.optname <= other.optname
#
#    def __div__(self, other):
#        return self.value / other
#
#    def __floordiv__(self, other):
#        return self.value // other
#
#    def __mul__(self, other):
#        return self.value * other
#
#    def __sub__(self, other):
#        return self.value - other
#
#    def __add__(self, other):
#        return self.value + other
#
#    def __pow__(self, other):
#        return self.value ** other
#
#    def __mod__(self, other):
#        return self.value % other
#

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
