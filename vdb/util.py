#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

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

def gint( s ):
    val = gdb.parse_and_eval(s)
    r = int(val)
    return r

def xint( s ):
    try:
        r = int(s,16)
    except:
        try:
            r = int(s)
        except:
            raise Exception("%s can not be parsed as integer, neither base 10 or 16" % s )
    return r

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



code_dict = {
gdb.TYPE_CODE_PTR : ".TYPE_CODE_PTR",
gdb.TYPE_CODE_ARRAY : ".TYPE_CODE_ARRAY",
gdb.TYPE_CODE_STRUCT : ".TYPE_CODE_STRUCT",
gdb.TYPE_CODE_UNION : ".TYPE_CODE_UNION",
gdb.TYPE_CODE_ENUM : ".TYPE_CODE_ENUM",
gdb.TYPE_CODE_FLAGS : ".TYPE_CODE_FLAGS",
gdb.TYPE_CODE_FUNC : ".TYPE_CODE_FUNC",
gdb.TYPE_CODE_INT : ".TYPE_CODE_INT",
gdb.TYPE_CODE_FLT : ".TYPE_CODE_FLT",
gdb.TYPE_CODE_VOID : ".TYPE_CODE_VOID",
gdb.TYPE_CODE_SET : ".TYPE_CODE_SET",
gdb.TYPE_CODE_RANGE : ".TYPE_CODE_RANGE",
gdb.TYPE_CODE_STRING : ".TYPE_CODE_STRING",
gdb.TYPE_CODE_BITSTRING : ".TYPE_CODE_BITSTRING",
gdb.TYPE_CODE_ERROR : ".TYPE_CODE_ERROR",
gdb.TYPE_CODE_METHOD : ".TYPE_CODE_METHOD",
gdb.TYPE_CODE_METHODPTR : ".TYPE_CODE_METHODPTR",
gdb.TYPE_CODE_MEMBERPTR : ".TYPE_CODE_MEMBERPTR",
gdb.TYPE_CODE_REF : ".TYPE_CODE_REF",
gdb.TYPE_CODE_RVALUE_REF : ".TYPE_CODE_RVALUE_REF",
gdb.TYPE_CODE_CHAR : ".TYPE_CODE_CHAR",
gdb.TYPE_CODE_BOOL : ".TYPE_CODE_BOOL",
gdb.TYPE_CODE_COMPLEX : ".TYPE_CODE_COMPLEX",
gdb.TYPE_CODE_TYPEDEF : ".TYPE_CODE_TYPEDEF",
gdb.TYPE_CODE_NAMESPACE : ".TYPE_CODE_NAMESPACE",
gdb.TYPE_CODE_DECFLOAT : ".TYPE_CODE_DECFLOAT",
gdb.TYPE_CODE_INTERNAL_FUNCTION : ".TYPE_CODE_INTERNAL_FUNCTION",
}

def gdb_type_code( code ):
    return code_dict.get(code,code)


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
