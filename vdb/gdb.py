#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shlex
from enum import Enum


TYPE_CODE_PTR = None
TYPE_CODE_ARRAY = None
TYPE_CODE_PTR = None
TYPE_CODE_ARRAY = None
TYPE_CODE_STRUCT = None
TYPE_CODE_UNION = None
TYPE_CODE_ENUM = None
TYPE_CODE_FLAGS = None
TYPE_CODE_FUNC = None
TYPE_CODE_INT = None
TYPE_CODE_FLT = None
TYPE_CODE_VOID = None
TYPE_CODE_SET = None
TYPE_CODE_RANGE = None
TYPE_CODE_STRING = None
TYPE_CODE_BITSTRING = None
TYPE_CODE_ERROR = None
TYPE_CODE_METHOD = None
TYPE_CODE_METHODPTR = None
TYPE_CODE_MEMBERPTR = None
TYPE_CODE_REF = None
TYPE_CODE_RVALUE_REF = None
TYPE_CODE_CHAR = None
TYPE_CODE_BOOL = None
TYPE_CODE_COMPLEX = None
TYPE_CODE_TYPEDEF = None
TYPE_CODE_NAMESPACE = None
TYPE_CODE_DECFLOAT = None
TYPE_CODE_INTERNAL_FUNCTION = None



class Parameter:
    def __init__( self, *args, **kwargs ):
        self._value = ""

    @property
    def value( self ):
        return self._value

    @value.setter
    def value( self, val ):
        self._value = val
        if( self._value is None ):
            self._value = ""


class Command:
    def __init__( self, *args, **kwargs ):
        pass

    def dont_repeat( self ):
        pass

class error(Exception):
    pass

COMMAND_DATA = 0
COMPLETE_EXPRESSION = 0
PARAM_BOOLEAN = 0
COMMAND_SUPPORT = 0
PARAM_STRING = 0
PARAM_INTEGER = 0
BP_BREAKPOINT = 0
BP_HARDWARE_WATCHPOINT = 0
BP_READ_WATCHPOINT = 0
BP_ACCESS_WATCHPOINT = 0
BP_WATCHPOINT = 0

class mock_event:
    def connect( a ):
        pass

class events:
    new_objfile = mock_event
    new_thread = mock_event
    stop = mock_event
    before_prompt = mock_event
    memory_changed = mock_event
    inferior_call = mock_event

class mock_type:

    def __init__(self):
        self.sizeof = 0

    def pointer(self):
        return mock_type()

def lookup_type( a ):
    return mock_type()

def execute( *args, **kwargs ):
    args = args[0].split()
#    print("args = '%s'" % (args,) )
#    print("kwargs = '%s'" % kwargs )

    
#    print("args[0] = '%s'" % args[0] )
#    print("args[1] = '%s'" % args[1] )
    data = ""
    if( args[0].startswith("disassemble") ):
        with open(args[1], 'r') as myfile:
            data=myfile.read()
    return data

def selected_thread( ):
    return None

class Value:
    def __init__( self, x ):
        self.x = x

evaldict = {
        "*((void**)0xa37d60+0)" : 4
        }
def parse_and_eval( s ):
    print("s = '%s'" % s )
    return evaldict.get(s,0)

def string_to_argv( arg ):
    argv=shlex.split(arg)
    return argv

class FinishBreakpoint:
    pass

class Breakpoint:
    pass

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
