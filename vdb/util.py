#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def nstr( s ):
    if( s is None ):
        return ""
    return s

def maybe_utf8( ba ):
    try:
        return ba.decode("utf-8")
    except:
        return None

def ifset( s, p ):
    if( p is not None ):
        return s.format(p)
    return ""

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

suffixes_iso = [ "", "k","M","G","T","P","E","Z","Y" ]
suffixes_bin = [ "", "ki","Mi","Gi","Ti","Pi","Ei","Zi","Yi" ] 

def num_suffix( num, iso = False, factor = 1.5 ):
    if( iso ):
        p = 1000
        suffixes = suffixes_iso
    else:
        p = 1024
        suffixes = suffixes_bin

    snum = num
    n=0
    while( snum > (factor*p) ):
        snum /= p
        n += 1
    suffix = suffixes[n]
    return (snum,suffix)

def log(fmt, *more ):
    print(fmt.format(*more))

def indent( i, fmt, *more ):
    log("  " * i + fmt, *more )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
