#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shlex

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
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
