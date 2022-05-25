#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

import re
import traceback
import itertools
import time
import types
import functools

from enum import Enum,auto
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

def rxint( s ):
    try:
        r = int(s)
    except:
        try:
            r = int(s,16)
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

def bark( offset = 0 ):
    import traceback
    st = traceback.extract_stack()
    st = st[-2+offset]
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
    try:
        maybe_logprint(level,fmt.format(**more))
    except IndexError:
        maybe_logprint(level,fmt)

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
            cval = cell[0]
            clen = cell[1]
            if( len(cell) > 2 ):
                if( cell[2] == 0 ):  # truncate to max size
                    cval = cval[0:maxsz[cnt]]
            if( len(cell) > 1 ):
                if( isinstance(clen,str) ):
                    import vdb.color
                    v=cell[0]
                    c=cell[1]
                    cell = vdb.color.colorl(cval,clen) + cell[2:]
                    cval = cell[0]
                    clen = cell[1]
            if( clen == 0 ):
                clen = len(cval)
                xpad = maxsz[cnt] - clen
            else:
                xpad = maxsz[cnt] - clen
            if( cnt+1 == len(line) ):
                xpad = 0
            ret += f"{cval}{' ' * xpad}"
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
#        for cell in line:
        for cnt in range(0,len(line)):
            cell = line[cnt]
            if( cell is None ):
                cell=""
#            print("cnt = '%s'" % cnt )
            if isinstance(cell,tuple):
                if( len(cell) == 2 ):
                    clen = cell[1]
                    if( isinstance(clen,str) ):
                        clen = len(cell[0])
                    maxsz[cnt] = max(maxsz.get(cnt,0),clen)
                elif( len(cell) > 3):
                    maxsz[cnt] = max(maxsz.get(cnt,0),cell[3])
                else:
                    # Ignore the size at that point
                    maxsz[cnt] = max(maxsz.get(cnt,0),1)
            else:
                maxsz[cnt] = max(maxsz.get(cnt,0),len(str(cell)))
#            cnt += 1
#    for x,y in maxsz.items():
#        print("x = '%s'" % x )
#        print("y = '%s'" % y )
    for line in tbl:
        ret += format_line(line,maxsz,padbefore,padafter)
        ret += "\n"
    return ret

def print_table ( tbl, padbefore = " ", padafter = " " ):
    ret = format_table( tbl, padbefore, padafter )
    print(ret)
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


def gdb_numeric( val ):
    if( type(val) != gdb.Value ):
        return val
    if( val.type.code == gdb.TYPE_CODE_FLT ):
        return float(val)
    return int(val)

def braille( num ) :
    if( type(num) is int ):
        return chr(10240 + num )
    ret = ""
    for b in num:
        ret += braille(b)
    return ret

class Enum(Enum):

    @classmethod
    def get( cls, s , default = None ):
        try:
            return cls[s]
        except:
            traceback.print_exc()
            return default

class spinner_types(Enum):
    ascii    = auto()
    braille1 = auto()
    braille2 = auto()
    braille3 = auto()
    braille7 = auto()
    bar      = auto()
    bar_h    = auto()
    block    = auto()
    block_p  = auto()
    pie      = auto()
    circle   = auto()
    test     = auto()
    none     = auto()


# braille( [ 0b1, 0b10, 0b100, 0b1000, 0b10000, 0b100000, 0b1000000,0b10000000] )
# '⠁⠂⠄⠈⠐⠠⡀⢀' 
available_spinners = {
        spinner_types.braille1 : braille( [ 0b1, 0b10, 0b100, 0b1000000, 0b10000000, 0b100000, 0b10000, 0b1000 ][::-1] ),
        spinner_types.braille2 : braille( [ 0b1000100, 0b110, 0b11, 0b1001, 0b11000, 0b110000, 0b10100000, 0b11000000 ]  ),
        spinner_types.braille3 : braille( [ 0b1000110, 0b111, 0b1011, 0b11001, 0b111000, 0b10110000, 0b11100000, 0b11000100 ]  ),
        spinner_types.braille7 : "⣾⣽⣻⢿⡿⣟⣯⣷"[::-1],
        spinner_types.bar      : "▂▃▄▅▆▇█",
        spinner_types.bar_h    : "█▉▊▋▌▍▎▏"[::-1],
        spinner_types.block    : "▘▝▗▖",
        spinner_types.block_p  : "▚▞",
        spinner_types.ascii    : "|/-\\",
        spinner_types.pie      : "◴◵◶◷"[::-1],
        spinner_types.circle   : "◜◝◞◟",
        spinner_types.test     : "⡀⡁⡂⡃⡄⡅⡆⡇⡈⡉⡊⡋⡌⡍⡎⡏⡐⡑⡒⡓⡔⡕⡖⡗⡘⡙⡚⡛⡜⡝⡞⡟⡠⡡⡢⡣⡤⡥⡦⡧⡨⡩⡪⡫⡬⡭⡮⡯⡰⡱⡲⡳⡴⡵⡶⡷⡸⡹⡺⡻⡼⡽⡾⡿⢀⢁⢂⢃⢄⢅⢆⢇⢈⢉⢊⢋⢌⢍⢎⢏⢐⢑⢒⢓⢔⢕⢖⢗⢘⢙⢚⢛⢜⢝⢞⢟⢠⢡⢢⢣⢤⢥⢦⢧⢨⢩⢪⢫⢬⢭⢮⢯⢰⢱⢲⢳⢴⢵⢶⢷⢸⢹⢺⢻⢼⢽⢾⢿⣀⣁⣂⣃⣄⣅⣆⣇⣈⣉⣊⣋⣌⣍⣎⣏⣐⣑⣒⣓⣔⣕⣖⣗⣘⣙⣚⣛⣜⣝⣞⣟⣠⣡⣢⣣⣤⣥⣦⣧⣨⣩⣪⣫⣬⣭⣮⣯⣰⣱⣲⣳⣴⣵⣶⣷⣸⣹⣺⣻⣼⣽⣾⣿",
#        spinner_types.none     : None,
        }

class spinner:

    def __init__( self, kind, inverse = False, chars = "?.", cps = 2 ):
        self.spinchars = available_spinners.get(kind,chars)
        if( inverse is True ):
            self.spinchars = self.spinchars[::-1]
        self.index = 0
        self.cps = cps

    def char( self, ts = None ):
        if( ts is None ):
            return self.spinchars[self.index]
        else:
            ts *= self.cps
            ix = int(ts) % len(self.spinchars)
            return self.spinchars[ix]

    def next( self ):
        self.index += 1
        self.index %= len(self.spinchars)
        return self.char()


class sliding_average:

    def __init__( self, steps ):
        self.sum = 0
        self.num = 0
        self.weightsum = 0
        self.numbers = []
        self.weights = []
        self.steps = steps

    def add( self, n, w = 1 ):
        self.numbers.append(n)
        self.weights.append(w)
        self.sum += n
        self.weightsum += w
        self.num += 1
        while( self.num > self.steps ):
            self.sum -= self.numbers[0]
            self.weightsum -= self.weights[0]
            self.num -= 1
            del self.numbers[0]
            del self.weights[0]

    def get( self ):
        if( self.weightsum != 0 ):
            return self.sum/self.weightsum
        else:
            return 0

    def _dump( self ):
        print("self.num = '%s'" % (self.num,) )
        print("self.numbers = '%s'" % (self.numbers,) )
        print("self.weightsum = '%s'" % (self.weightsum,) )
        print("self.weights = '%s'" % (self.weights,) )
        print("self.sum = '%s'" % (self.sum,) )

class eta:

    def __init__( self, total = 100, avg_steps = 50 ):
        self.start_ts = None
        self.last_pos = None
        self.total = total
        self.sa = sliding_average( avg_steps )

    def get( self, total = None ):
        if( total is None ):
            total = self.total

        remain = total - self.last_pos
        return self.sa.get() * remain

    def add( self, pos, now = None, total = None ):
        if( self.start_ts is None ):
            self.start_ts = time.time()
            self.last_pos = pos
            return None
        if( now is None):
            now = time.time()
        elapsed = now - self.start_ts
        num = pos - self.last_pos

        self.sa.add( elapsed, num )

        self.start_ts = now
        self.last_pos = pos

        return self.get(total)

def eta_format( ts ):
    ts = int(ts)
    if( ts > 3600 ):
        h = ts // 3600
        m = ( ts // 60 ) % 60
        return f"{h}h{m}m"
    elif( ts > 60 ):
        m = ts // 60
        s = ts % 60
        return f"{m}m{s}s"
    else:
        return f"{ts}s"

class progress_indicator:

    def __init__( self, text = "", start = 0, total = 100, width = 80, avg_steps = 50, spintype = spinner_types.ascii, spinverse = False, spinchars = None, use_eta = False, cps = 2 ):
        self.spinner = spinner( spintype, spinverse, spinchars, cps )
        self.eta = None
        if( use_eta ):
            self.eta = eta(gdb_numeric(total),gdb_numeric(avg_steps))
        self.text = text
        self.start = gdb_numeric(start)
        self.total = gdb_numeric(total)
        self.current_pos = gdb_numeric(start)

    def set( self, pos, now = None ):
        if( self.eta is not None ):
            self.eta.add( pos, now )
        self.current_pos = pos

    def get( self, pos = None, now = None, text = None, format = None ):
        if( format is None ):
            format = "{text0} {percentage}{bar} {text1} {eta}"
        if( text is None ):
            text = self.text
        if( type(text) is list ):
            text0 = text[0]
            text1 = text[1]
        else:
            text0 = text
            text1 = ""
        if( pos is not None ):
            self.set(pos)
        else:
            pos = self.current_pos


        rnge = self.total - self.start
        pct = rnge / 100
        ppos = pos - self.start
        ppos /= pct

        percentage = ppos


        percentage = f"{percentage:4.1f}%"

        barchars = "[█ ]"
        bw = 120
        bfull = bw * ppos / 100
        br = bfull % 1
#        print("bfull = '%s'" % (bfull,) )
        bfull = int(bfull)

        be = bw - bfull
        be -= 1

#        print("bw = '%s'" % (bw,) )
#        print("bfull = '%s'" % (bfull,) )
#        print("br = '%s'" % (br,) )
#        print("be = '%s'" % (be,) )
        lastbar = "█▉▊▋▌▍▎▏"[::-1]
        xbar = len(lastbar) * br
        xbar = int(xbar)
#        print()
#        print("br = '%s'" % (br,) )
#        print("len(lastbar) = '%s'" % (len(lastbar),) )
#        print("xbar = '%s'" % (xbar,) )

        spinner = self.spinner.char( time.time() )
        bar = ""
        bar += barchars[0]
        bar += barchars[1] * bfull
        bar += lastbar[xbar]
        bar += spinner
        bar += barchars[2] * be
        bar += barchars[3]

        if( self.eta is not None ):
            eta = eta_format(self.eta.get())
        else:
            eta = ""

        out = format.format(**locals())
        return out


def memoize( reset_events = [] ):
    class memoize_cache:
        def __init__( self, func ):
#            bark() # print("BARK")
            self.func = func
            self.cache = {}
            functools.update_wrapper(self,func)
            from collections.abc import Iterable
            if( not isinstance(reset_events,Iterable)  ):
                rel = [ reset_events ]
            else:
                rel = reset_events

            for re in rel:
                re.connect( self.reset )

        def reset( self, xxx = None ):
#            bark() # print("BARK")
            self.cache = {}

        def __call__( self, *args, **kwargs ):
#            bark() # print("BARK")
            if( len(kwargs) > 0 ):
                return self.func(*args,**kwargs)

            val = self.cache.get(args, self )
            if( val is self ):
                val = self.func(*args)
                self.cache[args] = val
            return val
    return memoize_cache

pe_cache = {}

def parse_and_eval_cached( ex, override = False ):
    global pe_cache
    if( override ):
        cv = None
    else:
        cv = pe_cache.get( ex,None)
    if( cv is not None ):
        return cv

    res = gdb.parse_and_eval( ex )
    pe_cache[ex] = res
    return res




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
