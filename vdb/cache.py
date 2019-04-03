#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb

import gdb

import time

vdb.enabled_modules.append("cache")

cumulative_time = { }

class stopwatch:

    def __init__( self ):
        self.t_start = None
        self.t_stop = None
        self.accumulated = 0.0

    def print( self, msg ):
        dif = self.get()
        print(msg.format(dif))

    def start( self ):
        self.t_start = time.time()

    def stop( self ):
        self.t_stop = time.time()

    def pause( self ):
        self.stop()
        self.accumulated += self.lap()

    def cont( self ):
        self.start()

    def lap( self ):
        dif = self.t_stop - self.t_start
        return dif

    def get( self ):
        return self.lap() + self.accumulated

def add_time( t, n ):
    global cumulative_time
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
        except Exception as e:
            r.exception = e
        if( r.exception is not None ):
            raise r.exception
        return r.result


type_cache = cache_entry()

def lookup_type( name ):
    sw = stopwatch()
    sw.start()
    global type_cache
    t = type_cache.cache.get(name)
    if( t is None ):
        t = gdb.lookup_type(name)
        type_cache.cache[name] = t
        type_cache.misses += 1
    else:
        type_cache.hits += 1
    sw.stop()
    add_time(sw.get(),"gdb.lookup_type")
    sw.print("gdb.lookup_type(…) took {}s")
    return t

re_cache = cache_entry()

class re:

    class result:
        def __init__( self ):
            self.m = None

    def findall( rex, s ):
        global re_cache
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

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
