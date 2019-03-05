#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def unquote( s ):
    if( s.startswith('"')):
        s = s[1:]
    elif( s.startswith("'")):
        s = s[1:]
    if( s.endswith('"')):
        s = s[:-1]
    elif( s.endswith("'")):
        s = s[:-1]
    return s


def log(fmt, *more ):
    print(fmt.format(*more))

def indent( i, fmt, *more ):
    log("  " * i + fmt, *more )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
