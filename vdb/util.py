#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gdb

import re
import traceback
import itertools
import time
import types
import functools
import logging
import logging.handlers
import rich.console
import rich.progress

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
            raise ValueError("%s can not be parsed as integer, neither base 10 or 16" % s )
    return r

def rxint( s ):
    try:
        r = int(s)
    except:
        try:
            r = int(s,16)
        except:
            if( s.startswith("#") ):
                xs=s.replace("#","0b")
            try:
                r = int(xs,2)
            except:
                raise ValueError("%s can not be parsed as integer, neither base 10 or 16 or 2" % s )
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

logfilename = "vdb.log"
logger = None

logprint = print
console_logprint = print

loglevel = 4
console_loglevel = 3

def logger_logprint( msg, level ):
    ll = 60 - level * 10
    logger.log(ll,msg)

def init_logger( ):
    global logger
    logging.basicConfig( style="{", format = "{asctime} {message}" )
    logger = logging.getLogger("vdb")
    logger.propagate = False
#    print("logger.hasHandlers() = '%s'" % (logger.hasHandlers(),) )
#    print("logger.handlers = '%s'" % (logger.handlers,) )
    while( len(logger.handlers) > 0 ):
        logger.removeHandler( logger.handlers[0] )

    rfh = logging.handlers.RotatingFileHandler(logfilename, maxBytes = 1, backupCount = 320 )
    logger.addHandler(rfh)

    logger.warning("Opened Logfile")
    logger.removeHandler(rfh)
    rfh = logging.FileHandler(logfilename)
    logger.addHandler(rfh)
    logger.setLevel(1)
    global logprint
    formatter = logging.Formatter( style="{", fmt = "{asctime} {message}" )
    rfh.setFormatter(formatter)
    logprint = logger_logprint

Loglevel = Enum("Level", [ "error", "warn", "info", "notice", "debug", "trace" ] )

levelprefixes = {
        0 : "[FAT] ", # Should probably only use when we have to exit gdb (i.e. hopefully never)
        1 : "[ERR] ", # when something doesn't work
        2 : "[WRN] ", # when something doesn't fully work but can continue
        3 : "[INF] ", # Inform the user about something hapenning, default max level should be here
        4 : "[NOT] ", # Some extra information, not always necessary, per default don't print
        5 : "[DBG] ", # Only when debugging stuff ( some modules might have their own )
        6 : "[TRC] "  # really details trace of all kinds of things that are going on
        }

def maybe_logprint( level, msg, queue = False ):
    if( logger is None ):
        init_logger()
    st = traceback.extract_stack()
    st = st[-3]
    fn = os.path.split(st.filename)
    fn = fn[-1]
    fn = fn.removesuffix(".py")
    loc = f"{fn}.{st.name} "

    logprefix = levelprefixes.get(level,f"[{level}] ")

    global loglevel
    # never print anything to console but not to logfile
    if( loglevel < console_loglevel ):
        loglevel = console_loglevel

    if( level <= loglevel ):
        if( logprint is not None ):
            logprint(logprefix+loc+msg,level)
    if( level <= console_loglevel ):
        if( console_logprint != logprint ):
#            print(f"console_logprint({msg=})")
            if( console_logprint is not None ):
                if( queue ):
                    import vdb.prompt
                    vdb.prompt.queue_msg(msg)
                else:
                    console_logprint(msg)

def qlog( fmt, *posargs, **kwargs):
    level = kwargs.get("level",1)
    if( isinstance(level,Loglevel) ):
        level = level.value
    xpfmt=fmt.format(*posargs,**kwargs)
    maybe_logprint(level,xpfmt,queue=True)


class kw_dict(dict):

    def __missing__(self,key):
        return f"{{{key}}}"

# Use via from vdb.util import log as vlog
# to save in typing
def log( fmt, *posargs, **kwargs):
    level = kwargs.get("level",1)
    if( isinstance(level,Loglevel) ):
        level = level.value
    try:
        xpfmt=fmt.format(*posargs,**kwargs)
    except:
        xpfmt=fmt.format_map(kw_dict(**kwargs))
    maybe_logprint(level,xpfmt)

def indent( i, fmt, *posargs, **more ):
    log("  " * i + fmt, *posargs, **more )

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
    t = t.replace(">>","> >")
    t = t.replace(">>","> >")
    return fxre.sub(fixup_intparam,t)


process = None

try:
    import psutil
    import os
    process = psutil.Process(os.getpid())
except:
    pass

def memory_info( ):
    if( process is None ):
        return None
    return process.memory_info()


byte_factors = {
        "TiB" : 1024*1024*1024*1024,
        "GiB" : 1024*1024*1024,
        "MiB" : 1024*1024,
        "kiB" : 1024,
        }

def bytestr( b, cf = 1.1 ):
    fb = b / cf
    for suf,fac in byte_factors.items():
        if( fb >= fac ):
            return ( b / fac, suf )
    return ( b, "B" )


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
        vdb.print_exc()
        return val

id_store = { }

def next_id( name ):
    global id_store
    nid = id_store.get(name,0)
    id_store[name] = nid+1
    return nid

Align = Enum("Align", [ "LEFT", "RIGHT" ] )
class table_cell:

    def __init__( self, s, color, dpy_len, max_size, truncate ):
        self.s = str(s)
        self.color = color
        if( dpy_len is None ): # Default len is just the strlen
            dpy_len = len(s)
        self.dpy_len = dpy_len   # The length in really printed chars, can be smaller than len due to colours
        self.max_size = max_size # truncate string to that if necessary. Can't work together with preset dpy_len
        if( truncate is None ): # default behaviour
            truncate = True
        self.truncate = truncate
        self.rendered = False
        self.align = Align.LEFT
#        print(f"cell: .s={self.s}[{len(self.s)}], .color={self.color}, .dpy_len={self.dpy_len}, .max_size={self.max_size}, .truncate={self.truncate}")


    def render( self, width, skip_padding = False):
        if( not self.rendered ):
#            print("self.s = '%s'" % (self.s,) )
#            print("type(self.s) = '%s'" % (type(self.s),) )
#            print("self.dpy_len = '%s'" % (self.dpy_len,) )

#            print(f"render(width={width},.s={self.s}[{len(self.s)}],.dpy_len={self.dpy_len},.truncate={self.truncate}")
            if( len(self.s) <= self.dpy_len ): # No special chars that could interfere with truncating
                if( self.dpy_len > width and self.truncate ): # need to truncate
                    self.s = self.s[:width]

            if( self.color is not None ): # Will change the len(self.s) but not the amount of displayed characters
                import vdb.color
                self.s = vdb.color.color(self.s,self.color)
        self.rendered = True

        # Now all we need is the padding
        xpad = width - self.dpy_len
        if( skip_padding or xpad < 0 ):
            xpad = 0
#        print(f"render(width={width}, skip_padding={skip_padding} cell: .s={self.s}[{len(self.s)}], .color={self.color}, .dpy_len={self.dpy_len}, .max_size={self.max_size}, .truncate={self.truncate} => xpad={xpad}")
        if( self.align == Align.LEFT ):
            ret = f"{self.s}{' ' * xpad}"
        else:
            ret = f"{' ' * xpad}{self.s}"
        return ret

def format_hbar(maxsz, padbefore, padafter ):
    ret=""
    for c,m in maxsz.items():
        l = m + len(padbefore) + len(padafter) - 1
        ret += "+"
        ret += "-" * l
    return ret


def format_line( line, maxsz, padbefore, padafter ):
    if( line is None ):
        return format_hbar(maxsz,padbefore,padafter)
    ret = ""
    for column,cell in enumerate(line):
        ret += padbefore
        ret += cell.render(maxsz[column], column+1 >= len(line) )
        ret += padafter
    return ret

def format_table( tbl, padbefore = " ", padafter = " ", as_list = False ):
    """
    Formats a table made out of a list of lines. Each line is a list too. Each cell in that line is either
    - None, denotes an empty string
    - a string
    - a 2-tuple made of a string and its display length (Must match the actual display len, otherwise table is messed up)
    - a 2-tuple made of a string and a colour string (causing the whole cell to have that colour)
    - a 3-tuple made of a string, either a colour string or a display len, and then some size thing. If that size is 0, display len
      is ignored and the string is truncated to the maximum size of other fields. If its > 0 then the size of this field
      will cause the column to be at most that size, but the string can be bigger. If the value is < 0 then it will be
      truncated to the column width, and the positive version is taken as the maximum width
    - a 4-tuple made of a string, a colour string, display len, and the max size

    The table will be layed out so that the width is the width of the biggest element
    """

    if( len(tbl) == 0 ):
        if( as_list ):
            return []
        else:
            return ""

#    maxsz = list(itertools.repeat(0,len(tbl[0])))
    maxsz = {}
    normal_table = []
#    print("len(maxsz) = '%s'" % len(maxsz) )
    from vdb.color import color_str
    for line in tbl:
#        print("maxsz = '%s'" % (maxsz,) )
#        print("line = '%s'" % line )
        column = 0
        nline = []
        if( line is None ):
            normal_table.append(line)
            continue
#        for cell in line:
        for column in range(0,len(line)):
            cell = line[column]
            if( cell is None ):
                cell=""
            align = Align.LEFT
#            print("column = '%s'" % column )
            if isinstance(cell,color_str):
#                print("cell = '%s'" % (cell,) )
                ncell = table_cell(cell.s,cell.color,cell.len,None,None)
                maxsz[column] = max(maxsz.get(column,0),ncell.dpy_len)
                pass
            elif isinstance(cell,tuple):
                if( len(cell) > 0 and isinstance(cell[0],Align) ):
                    align = cell[0]
                    cell = cell[1:]
                match len(cell):
                    case 0: # empty
                        ncell = table_cell("",None,1,None,None)
                    case 1: # just a string
                        ncell = table_cell(cell[0],None,len(cell[0]),None,None)
                        maxsz[column] = max(maxsz.get(column,0),ncell.dpy_len)
                    case 2: # string and col or len
                        if( isinstance(cell[1],str) ): # is a colour, not a len
                            colour = cell[1]
                            clen = len(cell[0])
                        else:
                            colour = None
                            clen = cell[1]
                        ncell = table_cell(cell[0],colour,clen,None,None)
                        maxsz[column] = max(maxsz.get(column,0),ncell.dpy_len)
                    case _: # string, then col or len
                        cval = cell[0]
                        if( isinstance(cell[1],str) ): # a colour
                            colour = cell[1]
                            clen = cell[2]
                            if( clen == 0 ):
                                clen = len(cell[0])
                                maxs = 0
                            else:
                                maxs = None
                        else:
                            colour = None
                            clen = cell[1]
                            maxs = cell[2]
                        if( len(cell) > 3 ):# then the 4th is definetly a maxs
                            maxs = cell[3]
                        if( maxs is not None ):
                            # The maximum size that a column is automatically expanded to
                            truncate = False
                            # negative means to actually tuncate the value, positive can overflow the cell
                            if( maxs <= 0 ):
                                truncate = True
                                maxs = -maxs
                            ncell = table_cell(cval,colour,clen,maxs,truncate)
                            dm = min(maxs,ncell.dpy_len)
                            maxsz[column] = max(maxsz.get(column,0),dm)
                        else:
                            ncell = table_cell(cval,colour,clen,maxs,None)
                            maxsz[column] = max(maxsz.get(column,0),ncell.dpy_len)
            else: # just some printable thing
                ncell = table_cell(str(cell),None,None,None,None)
                maxsz[column] = max(maxsz.get(column,0),ncell.dpy_len)
            ncell.align = align
            nline.append(ncell)
        normal_table.append(nline)
#    print("maxsz = '%s'" % (maxsz,) )

    if( as_list ):
        ret = []
        for line in normal_table:
            ret.append(format_line(line,maxsz,padbefore,padafter))
        return ret
    else:
        ret = ""
        for line in normal_table:
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
    def __init__( self, task, *args ):
        self.task = task
        self.args = args
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
            self.task(self,*self.args)
        except:
            vdb.print_exc()
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
            vdb.print_exc()
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
        self.width=width

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
            self.set(pos,now)
        else:
            pos = self.current_pos


        rnge = self.total - self.start
        if( rnge != 0 ):
            pct = rnge / 100
            ppos = pos - self.start
            ppos /= pct
        else:
            ppos = 100

        percentage = ppos


        percentage = f"{percentage:4.1f}%"

        barchars = "[█ ]"
        bw = self.width
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

callvl = 0
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
            log(f"Resetting memoize cache for {self.func}",level=4)
#            print(f"reset({self},{xxx}")
#            bark() # print("BARK")
            self.cache = {}

        # todo: profile and speedup
        def __call__( self, *args, **kwargs ):
#            global callvl
#            callvl += 1
#            bark() # print("BARK")
#            indent(callvl,str(self))
#            indent(callvl,"args = '%s'" % (args,) )
#            print("kwargs = '%s'" % (kwargs,) )
#            if( len(kwargs) > 0 ):
#                return self.func(*args,**kwargs)

            key = (args,tuple(zip(kwargs.keys(),kwargs.values())))
#            print("key = '%s'" % (key,) )
#            val = self.cache.get(args, self )
            val = self.cache.get( key, self )
#            indent(callvl,"val = '%s'" % (val,) )
            if( val is self ):
                val = self.func(*args,**kwargs)
                self.cache[key] = val
                val = self.cache.get( key, self )
#                indent(callvl,"val = '%s'" % (val,) )
#                indent(callvl,"len(self.cache) = '%s'" % (len(self.cache),) )
#            callvl -= 1
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


def is_started( ):
    try:
        gdb.selected_frame()
        return True
    except:
        return False

# Since we are wrapped rich won't detect the console capabilities directly
console = rich.console.Console( force_terminal = True, color_system = "truecolor" )

def progress_bar( bar_width = 120, complete_style = "bar.complete", style = "bar.back", spinner = None, num_completed = False, download = False, speed = False ):
    dcol = list(rich.progress.Progress.get_default_columns())
    dcol[1] = rich.progress.BarColumn( bar_width = bar_width, complete_style = complete_style, style = style )
    if( num_completed ):
        dcol.insert(2, rich.progress.MofNCompleteColumn() )
    if( spinner is not None ):
        if( isinstance(spinner,str) ):
            dcol.insert( 2, rich.progress.SpinnerColumn(spinner_name=spinner ) )
        else:
            dcol.insert( 2, rich.progress.SpinnerColumn( ) )
    if( speed ):
        dcol.insert( 2, rich.progress.TransferSpeedColumn( ) )
    if( download ):
        dcol.insert( 2, rich.progress.DownloadColumn( ) )
    ret = rich.progress.Progress( *dcol,console = console )
    return ret

def stripped_lines( string ):
    for line in string.split("\n"):
        line = line.strip()
        if( len(line) == 0 ):
            continue
        yield line



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
