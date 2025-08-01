#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb
import vdb.util

import gdb
import sys

from typing import Dict

mod=sys.modules[__name__]
vdb.enabled_modules["cache"] = mod

cumulative_time: Dict[float,float] = { }

def filename( cachename ):
    if( not cachename ):
        raise RuntimeError("Need cache name to generate cache filename")
    ret = f"{vdb.vdb_dir}/cache/{cachename}"
    return ret

# Loads the file as string data
def get_string( cachename ):
    with open(filename(cachename)) as f:
        return f.read()

def save_string( cachename, data ):
    with open(filename(cachename),"w") as f:
        f.write(data)

def add_time( t: float, n: float ):
    ct = cumulative_time.get(n,0.0)
    ct += t
    cumulative_time[n] = ct

class cache_entry:
    def __init__( self ):
        self.hits = 0
        self.misses = 0
        self.cache = { }

    def __str__( self ):
        ratio = self.hits/(self.hits+self.misses+0.000000001)
        r = f"{self.hits}h,{self.misses}m=>{ratio:.2f}@{len(self.cache)}"
        return r

class cache_result:
    def __init__(self):
        self.result = None

class execute_cache:
    class result:
        def __init__(self):
            self.result = None
            self.exception = None

    def __init__(self):
        self.cache = cache_entry()

    def execute( self, cmd, t0, t1 ):
        try:
            r = self.cache.cache.get((cmd,t0,t1),None)
            if( r is None ):
                r = execute_cache.result()
                self.cache.cache[(cmd,t0,t1)] = r
                r.result = gdb.execute(cmd,t0,t1)
        except Exception as e: # pylint: disable=broad-exception-caught
            r.exception = e
        if( r.exception is not None ):
            raise r.exception
        return r.result


type_cache = cache_entry()

def lookup_type( name ):
#    sw = vdb.util.stopwatch()
#    sw.start()
    t = type_cache.cache.get(name)
    if( t is None ):
        t = gdb.lookup_type(name)
        type_cache.cache[name] = t
        type_cache.misses += 1
    else:
        type_cache.hits += 1
#    sw.stop()
#    add_time(sw.get(),"gdb.lookup_type")
#    sw.print("gdb.lookup_type(…) took {}s")
    return t

re_cache = cache_entry()

class re:

    class result:
        def __init__( self ):
            self.m = None

    def findall( rex, s ):
        r = re_cache.cache.get( (rex,s), None )
        if( r is None ):
            re_cache.misses += 1
            r = re.result()
            r.m = rex.findall(s)
            re_cache.cache[(rex,s)] = r
        else:
            re_cache.hits += 1
        return r.m

def dump( ):
    print(f"type_cache : {type_cache}")
    print(f"re_cache   : {re_cache}")

    for k,v in cumulative_time.items():
        print(f"{k:<20} : {v}")

_identity_pool = {}
# In order to save memory for strings that exist often we try to redirect them to one that lives in the dict instead of
# duplicating it. This makes parsing slower but in the end we can save memory.
# TODO: test with guppy etc. how much we save
# XXX theoretically we can have different types as keys too, doesn't make sense for all though
def pool_get( k ):
    global _identity_pool
    r = _identity_pool.get(k,None)
    if( r is None ):
        _identity_pool[k] = k
        r = k
    return r


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
