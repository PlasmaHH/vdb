#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

import re
import traceback
import itertools
import time
import types

import os
import sys

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
    try:
        val = gdb.parse_and_eval(s)
        r = int(val)
        return r
    except:
#        print("Errenous value %s" % (s,))
        raise

def xint( s ):
    try:
        r = int(s,16)
    except:
        try:
            r = int(s)
        except:
            raise Exception("%s can not be parsed as integer, neither base 10 or 16" % s )
    return r

class hexint(int):

    def __new__(cls,val):
        if( type(val) == int ):
            return val
        try:
            return int(val)
        except:
            return super().__new__(int,val,0)


def mint( s ):
    try:
        r = int(s,16)
    except:
        try:
            r = int(s)
        except:
            r = s
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

def bark( ):
    import traceback
    st = traceback.extract_stack()
    st = st[-2]
    print(f"{st.name}:{st.filename}:{st.lineno}")

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

logprint = print
loglevel = 3

def maybe_logprint( level, msg ):
    if( level <= loglevel ):
        logprint(msg)

def log(fmt, **more ):
    level = more.get("level",1)
    maybe_logprint(level,fmt.format(**more))

def indent( i, fmt, **more ):
    log("  " * i + fmt, **more )



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


def fixup_intparam( ip ):
    return ip.group(1)

fxre = re.compile("([0-9]+)ul")

def fixup_type( t ):
    return fxre.sub(fixup_intparam,t)



def guess_vptr_type( val ):
    """ Takes a pointer and tries to figure out if it points to an object that has a virtual table and then returns the
    "real" type according to that virtual table. This is to workaround some gdb bug where the dynamic type is
    inaccessible"""
    # otherwise gdb prints potentially some more text about it
    try:
        ptrval = int(val)
        vptr = gdb.parse_and_eval( f"*(void**)({ptrval})" )
        vpx = re.search("vtable for (.*?)\+[0-9]*>",str(vptr))
        if( vpx ):
            gdb_vptype=gdb.lookup_type(fixup_type(vpx.group(1)))
            val = val.cast(gdb_vptype.pointer())
        return val
    except:
        traceback.print_exc()
        return val

id_store = { }

def next_id( name ):
    global id_store
    nid = id_store.get(name,0)
    id_store[name] = nid+1
    return nid

def format_line( line, maxsz, padbefore, padafter ):
    ret = ""
    cnt = 0
    for cell in line:
        if( cell is None ):
            cell = ""
#        ret += str(maxsz[cnt])
        ret += padbefore
        if isinstance(cell,tuple):
            xpad = maxsz[cnt] - cell[1]
            if( cnt+1 == len(line) ):
                xpad = 0
#            ret += " %s " % xpad
#            ret += " %s " % cell[1]
            ret += f"{cell[0]}{' ' * xpad}"
        else:
            xmaxsz = maxsz[cnt]
            if( cnt+1 == len(line) ):
                xmaxsz = 0
            ret += "{cell:<{maxsz}}".format(cell = cell, maxsz = xmaxsz )
        ret += padafter
        cnt += 1
    return ret

def format_table( tbl, padbefore = " ", padafter = " " ):
    ret = ""
    if( len(tbl) == 0 ):
        return ret
#    maxsz = list(itertools.repeat(0,len(tbl[0])))
    maxsz = {}
#    print("len(maxsz) = '%s'" % len(maxsz) )
    for line in tbl:
#        print("line = '%s'" % line )
        cnt = 0
        for cell in line:
            if( cell is None ):
                cell=""
#            print("cnt = '%s'" % cnt )
            if isinstance(cell,tuple):
                if( len(cell) == 2 ):
                    maxsz[cnt] = max(maxsz.get(cnt,0),cell[1])
                else:
                    # Ignore the size at that point
                    maxsz[cnt] = max(maxsz.get(cnt,0),1)
            else:
                maxsz[cnt] = max(maxsz.get(cnt,0),len(str(cell)))
            cnt += 1
#    for x,y in maxsz.items():
#        print("x = '%s'" % x )
#        print("y = '%s'" % y )
    for line in tbl:
        ret += format_line(line,maxsz,padbefore,padafter)
        ret += "\n"
    return ret

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

# todo: create special requirement exception
def requires( check, msg ):
    if( not check ):
        raise Exception("Requirement not met: %s" % msg )

class async_task:
    def __init__( self, task ):
        self.task = task
        self.progress = None
        self.thread = None

    def get_progress( self ):
        return self.progress

    def set_progress( self, msg ):
        if( self.progress is None ):
            import vdb.prompt
            vdb.prompt.add_progress( self.get_progress )
        self.progress = msg

    def run( self ):
        try:
            while( self.thread is None ):
                time.sleep(0) # necessary so the start function below can exit
            self.task(self)
        except:
            traceback.print_exc()
        finally:
            self.progress = None

    def start( self ):
        import vdb
        self.thread = vdb.texe.submit(self.run)


class xdict(dict):

    def getas( self, typ, name, default = None ):
        try:
            var = self.get(name,default)
            var = typ(var)
        except:
#            print(f"{var} is not of {typ}")
            var = default
        return var

def parse_vars( argv ):
#    print("argv = '%s'" % (argv,) )
    retargv = []
    retvars = xdict()
#    retvars.getas = types.MethodType( getas, retvars )
#    retvars.getas = getas.__get__(retvars)

    oldarg = None

    store_next = False
    for arg in argv:
        if( store_next ):
            store_next = False
            retvars[oldarg] = arg
            oldarg = None
            continue
        if( arg == "=" ):
            store_next = True
            continue
        if( arg[-1] == "=" ):
            if( oldarg is not None ):
                retargv.append(oldarg)
            oldarg = arg[:-1]
            store_next = True
            continue
        if( arg[0] == "=" ):
            retvars[oldarg] = arg[1:]
            oldarg = None
            continue
        if( oldarg is not None ):
            retargv.append(oldarg)
        xp = arg.split("=")
        if( len(xp) == 2 ):
            retvars[xp[0]] = xp[1]
            continue
        oldarg = arg
    if( oldarg is not None ):
        retargv.append(oldarg)

    return ( retargv, retvars )



    print("retargv = '%s'" % (retargv,) )
    print("retvars = '%s'" % (retvars,) )

class silence:

    def __init__( self ):
        self.redirect = None
        self.file = None
        self.logging = None

    def __enter__( self ):
        if( gdb.parameter("logging redirect") ):
            self.redirect = "on"
        else:
            self.redirect = "off"
        self.file = gdb.parameter("logging file")
        self.logging = "off"

#        print("ABOUT TO DISABLE OUTPUT")
#        print("sys.stdout.fileno() = '%s'" % (sys.stdout.fileno(),) )
#        gdb.execute("set logging redirect on")
#        gdb.execute("set logging file si.txt")
#        gdb.execute("set logging enabled on")

        sys.stdout.flush()
#        self.stdout_fd = os.dup( sys.stdout.fileno() )
        self.stdout_fd = os.dup( 1 )
        self.dev_null = open("/dev/null","w")
##        os.dup2( self.dev_null.fileno(), self.stdout.fileno() )
        os.dup2( self.dev_null.fileno(), 1 )
#        print("DISABLED OUTPUT")
        sys.stdout.flush()


    def __exit__( self, type, value, traceback ):
#        gdb.execute(f"set logging off")#,False,True)
        sys.stdout.flush()
##        os.dup2( self.stdout_fd, self.stdout.fileno() )
        os.dup2( self.stdout_fd, 1 )
#        gdb.execute(f"set logging off",False,False)
#        gdb.execute(f"set logging redirect {self.redirect}",False,True)
#        gdb.execute(f"set logging file {self.file}",False,True)
#        print("ENABLED OUTPUT")
        sys.stdout.flush()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
