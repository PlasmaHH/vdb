#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class subcommands:

    def __init__( self ):
        self.subcommands = { }

    def add_subcommand( self, s, f ):
        if( isinstance(s,str) ):
            self.subcommands[s] = f
        elif( len(s) == 1 ):
            self.subcommands[s[0]] = f
        else:
            rest=s[1:]
            s=s[0]
            sc=subcommands()
            self.subcommands[s] = sc
            sc.add_subcommand(rest,f)

    def run_subcommand( self, args ):
        s=args[0]
        rest=args[1:]
        sc = self.subcommands.get(s,None)
        if( sc is None ):
            print("Unknown vdb subcommand '%s'" % s )
            print("Known dict: %s" % subcommands )
        else:
            if( isinstance(sc,subcommands) ):
                sc.run_subcommand(rest)
            else:
                sc(rest)

globals = subcommands()

def run_subcommand( args ):
    globals.run_subcommand(args)

def add_subcommand( s, f ):
    globals.add_subcommand(s,f)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
