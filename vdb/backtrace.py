#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.config
import vdb.shorten
import vdb.command

import re
import gdb
import os
import traceback



color_ns       = vdb.config.parameter("vdb-bt-colors-namespace",                "#ddf",    gdb_type = vdb.config.PARAM_COLOUR)
colors_addr     = vdb.config.parameter("vdb-bt-colors-address",                  None,      gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-bt-colors-function",                 "#99f",    gdb_type = vdb.config.PARAM_COLOUR)
color_frame    = vdb.config.parameter("vdb-bt-colors-selected-frame-marker",    "#0f0",    gdb_type = vdb.config.PARAM_COLOUR)
color_filename = vdb.config.parameter("vdb-bt-colors-filename",                 "#ffff99", gdb_type = vdb.config.PARAM_COLOUR)
color_objfile  = vdb.config.parameter("vdb-bt-colors-object-file",              "#ffbbbb", gdb_type = vdb.config.PARAM_COLOUR)
color_defobj   = vdb.config.parameter("vdb-bt-colors-default-object",           "#ffbbff", gdb_type = vdb.config.PARAM_COLOUR)
color_rtti     = vdb.config.parameter("vdb-bt-colors-rtti-warning",             "#c00",    gdb_type = vdb.config.PARAM_COLOUR)
#color_ = vdb.config.parameter( "vdb-bt-colors-","#")

color_addr     = vdb.config.parameter("vdb-bt-color-addresses", True )
addr_colorspec = vdb.config.parameter("vdb-bt-address-colorspec", "ma" )
showspec       = vdb.config.parameter("vdb-bt-showspec","naFPS")
#frame_marker = vdbnfo.config.parameter("vdb-bt-selected-frame-marker", "[*]" )
frame_marker = vdb.config.parameter("vdb-bt-selected-frame-marker","► ")

class ArgVal():

	def __init__( self, sym, val ):
		self.sym = sym
		self.val = val

	def symbol(self):
		return self.sym

	def value(self):
		return self.val

signals = {
1 : "SIGHUP",
2 : "SIGINT",
3 : "SIGQUIT",
4 : "SIGILL",
5 : "SIGTRAP",
6 : "SIGABRT",
7 : "SIGBUS",
8 : "SIGFPE",
9 : "SIGKILL",
10 : "SIGUSR1",
11 : "SIGSEGV",
12 : "SIGUSR2",
13 : "SIGPIPE",
14 : "SIGALRM",
15 : "SIGTERM",
16 : "SIGSTKFLT",
17 : "SIGCHLD",
18 : "SIGCONT",
19 : "SIGSTOP",
20 : "SIGTSTP",
21 : "SIGTTIN",
22 : "SIGTTOU",
23 : "SIGURG",
24 : "SIGXCPU",
25 : "SIGXFSZ",
26 : "SIGVTALRM",
27 : "SIGPROF",
28 : "SIGWINCH",
29 : "SIGIO",
30 : "SIGPWR",
31 : "SIGSYS",
32 : "SIGRTMIN",
		}

segv_codes = {
	1 : "SEGV_MAPERR",
	2 : "SEGV_ACCERR",
	3 : "SEGV_BNDERR",
	4 : "SEGV_PKUERR",
	5 : "SEGV_ACCADI",
	6 : "SEGV_ADIDERR",
	7 : "SEGV_ADIPERR",
}


bus_codes = {
1 : "BUS_ADRERR",
2 : "BUS_OBJERR",
3 : "BUS_MCEERR_AR",
4 : "BUS_MCEERR_AO"
}

no_codes = { 
		-60 :   "SI_ASYNCNL",
		-7 :   "SI_DETHREAD",
		-6 :  "SI_TKILL",
		-5 :  "SI_SIGIO",
		-4 : "SI_ASYNCIO",
		-3 : "SI_MESGQ",
		-2 :  "SI_TIMER",
		-1 :  "SI_QUEUE",
		0 :  "SI_USER",
		0x80 :  "SI_KERNEL"
		}

addr_signals = set( [ 7, 11 ] )

def get_siginfo( si, v = None ):
	ret = "Kernel Signal Handler: "
	signo=si["si_signo"]
	signo=int(signo)
	addr=False
	ret += "Signal {} ({})".format(signo, signals.get(signo,"??"))
	si_code=si["si_code"]
	si_code=int(si_code)

	codes = no_codes
	if( signo == 11 ):
		codes = segv_codes
	elif( signo == 7 ):
		codes = bus_codes

	ret += ", code {} ({})".format(si_code,codes.get(si_code,"??"))

	if( signo in addr_signals ):
		fault=si["_sifields"]["_sigfault"]["si_addr"]
		code=si["_sifields"]["_sigfault"]["si_addr"]
		mode="access"
		try:
			mv=gdb.parse_and_eval("((ucontext_t*){})->uc_mcontext.gregs[19] & 2".format(v))
			mv=int(mv)
			if( mv == 0 ):
				mode = "read"
			elif( mv == 1 ):
				mode = "write"
		except:
			pass
		ret += " trying to {} {}".format(mode,fault)
	return ret


class SignalFrame():

	def __init__(self,fobj):
		self.fobj = fobj
	
	def inferior_frame( self ):
#		print("BARK0")
		return self.fobj.inferior_frame()

	def function(self):
		frame = self.fobj.inferior_frame()
		sighandler = frame.newer()
		try:
			# signal handler first
			si=sighandler.read_var("si")
			v=sighandler.read_var("v")
		except:
			v=None
			si=gdb.parse_and_eval("$_siginfo")

		ret = get_siginfo(si,v)
		return ret

	def filename(self):
#		print("BARK2")
		return None

	def address(self):
		return None
#		print("BARK3")
#		return self.fobj.address()

	def frame_args(self):
#		print("BARK4")
		return None

	def line(self):
#		print("BARK5")
		return None


class BacktraceDecorator(gdb.FrameDecorator.FrameDecorator):

    def __init__(self, fobj,eli=[]):
        super(BacktraceDecorator, self).__init__(fobj)
        self.fobj = fobj
#		print("len(eli) = '%s'" % len(eli) )
        self.elis = eli

    def elided(self):
        frame = self.fobj.inferior_frame()
        signal_frame = False
        if( frame.type() == gdb.SIGTRAMP_FRAME ):
            signal_frame = True
        if( frame == gdb.newest_frame() ):
            signal_frame = True

#		print("len(self.elis) = '%s'" % len(self.elis) )
        ret = []
        for e in self.elis:
            ret.append(e)
        if( signal_frame ):
            ret.append( SignalFrame(self.fobj) )

        return ret

    def function(self):

        frame = self.fobj.inferior_frame()
        sal = frame.find_sal()
        addr = sal.pc
        address = ""
        if( int(addr) != 0 ):
            if( color_addr.value ):
                address = self.color_address(addr) + " in "
        if( not any((c in showspec.value) for c in "fF" ) ):
            if( "a" in showspec.value ):
                return address[:-4] 
            else:
                return None
        if( "a" not in showspec.value ):
            address = ""

        name = frame.name()
        if( name is None ):
            return address + "<unknown>"
        name = str(name)
        name = vdb.shorten.symbol(name)


        cpos = len(name)
        tparamstart=0

        if( name[-1] == ">" ):
            level=0

            for i in range(len(name)-1,-1,-1):
                if( name[i] == ">" ):
                    level += 1
                elif( name[i] == "<" ):
                    level -= 1
                if( level == 0):
                    tparamstart=i
                    cpos=i
                    break

        prefix=name
        fun=""
        suffix=""
#		print("cpos = '%s'" % cpos )
#		print("tparamstart = '%s'" % tparamstart )
        fns = name.rfind(":",0,cpos)
        if( fns != -1 ):
            fns += 1
            prefix=name[0:fns]
            if( tparamstart != 0 ):
                #				print("fns = '%s'" % fns )
#				print("tparamstart = '%s'" % tparamstart )
                fun=name[fns:tparamstart]
                suffix=name[tparamstart:]
            else:
                fun=name[fns:]
                suffix=""
        else:
            prefix=""
            fun=name
        tps=prefix.find("<")
        tparam = ""
        if( tps != -1 ):
            xp = prefix
            prefix = xp[0:tps]
            tparam = xp[tps:]
        if( "F" in showspec.value ):
            name= vdb.color.color(prefix,color_ns.value) + tparam + vdb.color.color(fun,color_function.value) + suffix
        else:
            name= vdb.color.color(fun,color_function.value)


        if( frame == gdb.selected_frame() ):
            name = vdb.color.color(frame_marker.value,color_frame.value) + name

        if( int(addr) != 0 ):
            if frame.type() == gdb.INLINE_FRAME:
                name = "[i] " + name
        else:
            if frame.type() == gdb.INLINE_FRAME:
                name = " [inlined]        " + name
            else:
                name = "                  " + name

        return address + name

    def basename( self, fname ):
        if( "s" in showspec.value ):
            return os.path.basename(fname)
        else:
            return fname

    def filename(self):
        if( not any((c in showspec.value) for c in "sS" ) ):
            return None
        frame = self.fobj.inferior_frame()
        sal = frame.find_sal()
        fname="<unknown>"
        try:
            fname = sal.symtab.filename
            fname = vdb.shorten.path(fname)
            fname = self.basename(fname)
            fname = vdb.color.color(fname,color_filename.value)
        except:
            try:
                fname = sal.symtab.objfile
                fname = vdb.shorten.path(fname)
                fname = self.basename(fname)
                fname = vdb.color.color(fname,color_objfile.value)
            except:
                try:
                    fname = super(BacktraceDecorator,self).filename()
                    if( fname is not None ):
                        fname = vdb.shorten.path(fname)
                        fname = self.basename(fname)
                        fname = vdb.color.color(fname,color_defobj.value)
                except:
                    pass
        return fname


    def frame_args(self):
        args = super(BacktraceDecorator,self).frame_args()
        if( args is None ):
            return args
        if( not any((c in showspec.value) for c in "pP" ) ):
            return None
#		print("args = '%s'" % args )
        ret = [ ]
#		gdb.execute("set logging file /dev/null")
#		gdb.execute("set logging redirect on")
#		gdb.execute("set logging on")
        for a in args:
            if( str(a.symbol()) == "__in_chrg" ):
                continue
#			print("a.symbol() = '%s'" % a.symbol() )
            if( "P" in showspec.value ):
                ret.append( ArgVal( a.symbol(), a.value() ) )
#                ret.append( ArgVal( a.symbol(), "A" ) )
#                ret.append( ArgVal( a.symbol(), "TEST") )
            else:
                ret.append( ArgVal( a.symbol(), "") )
#		gdb.execute("set logging redirect off")
#		gdb.execute("set logging off")
        return ret

    def color_address( self, ptr = None ):
        plen = 64//4 # get from global state
        if( ptr is None ):
            ptr = int(self.address(True))
        addr = f"0x{ptr:0{plen}x}"
#        return addr
#        print("type(colors_addr.value) = '%s'" % type(colors_addr.value) )
    
        if( len(colors_addr.value) > 0 ):
            return vdb.color.color(addr,colors_addr.value)
        else:
            s,_,_,_ = vdb.memory.mmap.color(ptr,addr,colorspec = addr_colorspec.value )
            return s

    def address(self,force = False):
        if( not force ):
            if( "a" not in showspec.value ):
                return None
            if( color_addr.value ):
                return None
        frame = self.fobj.inferior_frame()
        sal = frame.find_sal()
        addr = sal.pc
        if( int(addr) == 0 ):
            addr = None
#		print("addr = '%s'" % addr )
        return addr

    def line(self):
        if( not any((c in showspec.value) for c in "sS" ) ):
            return None
        l = super(BacktraceDecorator,self).line()
        return l



class BacktraceIterator:
    def __init__(self, ii):
        self.input_iterator = ii
        self.inlined_frames = []
        self.next_real = None

    def __iter__(self):
        return self

    def __next__(self):
#        print("__next__")
        try:
            frame = next(self.input_iterator)
#            print("frame = '%s'" % frame )
        except StopIteration:
            if( self.next_real is None ):
                if( len(self.inlined_frames) > 0 ):
                    inf = self.inlined_frames[0]
                    self.inlined_frames = self.inlined_frames[1:]
#                    print("Return inlined %s" % inf )
                    return inf
#                print("self.inlined_frames = '%s'" % self.inlined_frames )
                raise StopIteration
            sret = self.next_real
            self.next_real = None
#            print("Return next real %s" % self.next_real)
#            print("sret = '%s'" % sret )
            return sret
        sal = frame._base.find_sal()
        addr = sal.pc
#		print("Returning BD")
#		return BacktraceDecorator(frame)
        toret = None
        if( int(addr) != 0 ):
            if( self.next_real is not None ):
                toret = self.next_real
            self.next_real = BacktraceDecorator(frame)
            ifl = self.inlined_frames
            self.inlined_frames = []
        else:
            self.inlined_frames.append( BacktraceDecorator(frame) )

        if( toret ):
#            print("Return toret %s" % toret )
            return BacktraceDecorator( toret, ifl )

#        print("Saving frame for later (%s)" % (len(self.inlined_frames)) )
#        print("self.next_real = '%s'" % self.next_real )
        if( self.next_real is None and len(self.inlined_frames) > 0 ):
#            print("###########################################################################")
            inf = self.inlined_frames[0]
            self.inlined_frames = self.inlined_frames[1:]
            return inf
        try:
            ret = self.__next__()
#            print("Return self next %s" % ret )
#            print("self.inlined_frames = '%s'" % self.inlined_frames )
#            if( len(self.inlined_frames) > 0 ):
#                print("self.inlined_frames[0].fobj.inferior_frame() = '%s'" % self.inlined_frames[0].fobj.inferior_frame() )
            return ret
        except StopIteration:
#            print("Stop iteration at %s" % frame)
            return BacktraceIterator(frame)

class BacktraceFilter ( ):
    """Filter backtraces to make them look nicer"""

    def __init__ (self):
        self.name = "BacktraceFilter"
        self.priority = 100
        self.enabled = True
        gdb.frame_filters[self.name] = self

    def filter( self, frame_iter ):
        return BacktraceIterator( frame_iter )
#		frame_iter = map( BacktraceDecorator, frame_iter )
#		return frame_iter

# disable this line to completely disable the filter
bf=BacktraceFilter()

def do_backtrace( argv ):
    # We need to do that first because if we don't we change the currently selected frame midways and that isn't something gdb likes
    vdb.memory.mmap.lazy_parse()
    try:

        full=""
        if( len(argv) > 0 and argv[0] == "/r" ):
            bf.enabled = False
            argv = argv[1:]
        elif( len(argv) > 0 and argv[0] == "/f" ):
            full="full"
            argv = argv[1:]
        elif( color_addr.value ):
            vdb.memory.print_legend( addr_colorspec.value )
        if( len(argv) > 1 ):
            print("Too many arguments, expecting at most 1, ignoring all")
        if( len(argv) == 1 ):
            btoutput = gdb.execute("backtrace {} {}".format(full,argv[0]),False,True)
        else:
            btoutput = gdb.execute("backtrace {}".format(full),False,True)
        btoutput = re.sub( "warning: RTTI symbol not found for class '.*?'\n",vdb.color.color("RTTI",color_rtti.value),btoutput)
        if( "n" not in showspec.value ):
            btoutput = re.sub( "^(\s*)#[0-9]*", " ", btoutput, flags = re.MULTILINE )
        print(btoutput)
    except gdb.error as e:
        print(e)
        pass
    except:
        traceback.print_exc()
        pass
    finally:
        bf.enabled = True


class cmd_bt (vdb.command.command):
    """Run the backtrace without filters"""

    def __init__ (self):
        super (cmd_bt, self).__init__ ("bt", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
#        import cProfile
#        cProfile.runctx("do_backtrace(argv)",globals(),locals())
        do_backtrace( argv )


cmd_bt()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
