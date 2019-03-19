#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
