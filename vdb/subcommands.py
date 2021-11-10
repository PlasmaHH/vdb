#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

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
            sc = self.subcommands.setdefault(s,subcommands())
            sc.add_subcommand(rest,f)

    def run_subcommand( self, args ):
        s=args[0]
        rest=args[1:]
        sc = self.subcommands.get(s,None)
        if( sc is None ):
            print("Unknown vdb subcommand '%s'" % s )
            print("Known commands:")
            globals.show()
        else:
            if( isinstance(sc,subcommands) ):
                if( len(rest) == 0 ):
                    print(f"Subcommand {s} needs additional sub command parameter:")
                    sc.show()
                    return
                sc.run_subcommand(rest)
            else:
                sc(rest)

    def show( self, prefix = "" ):
        for k,s in self.subcommands.items():
            if( k[0] == "_" ):
                continue
            if( isinstance(s,subcommands) ):
                s.show(f"{prefix} {k}")
            else:
                print(f"{prefix} {k}")

globals = subcommands()

def run_subcommand( args ):
    globals.run_subcommand(args)

def add_subcommand( s, f ):
    globals.add_subcommand(s,f)

def show( argv ):
    globals.show()

add_subcommand( [ "show", "subcommands" ], show )

# a bit of a wrong place here but we need to avoid cyclic dependencies
add_subcommand( [ "show", "config" ], vdb.config.show_config )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
