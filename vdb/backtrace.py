#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.config
import vdb.shorten

import re
import gdb
import os



color_ns       = vdb.config.parameter("vdb-bt-colors-namespace",                "#ddf",    gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-bt-colors-function",                 "#99f",    gdb_type = vdb.config.PARAM_COLOUR)
color_frame    = vdb.config.parameter("vdb-bt-colors-selected-frame-marker",    "#0f0",    gdb_type = vdb.config.PARAM_COLOUR)
color_filename = vdb.config.parameter("vdb-bt-colors-filename",                 "#ffff99", gdb_type = vdb.config.PARAM_COLOUR)
color_objfile  = vdb.config.parameter("vdb-bt-colors-object-file",              "#ffbbbb", gdb_type = vdb.config.PARAM_COLOUR)
color_defobj   = vdb.config.parameter("vdb-bt-colors-default-object",           "#ffbbff", gdb_type = vdb.config.PARAM_COLOUR)
color_rtti     = vdb.config.parameter("vdb-bt-colors-rtti-warning",             "#c00",    gdb_type = vdb.config.PARAM_COLOUR)
#color_ = vdb.config.parameter( "vdb-bt-colors-","#")

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
			# vwd signal handler first
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

		name = frame.name()
		if( name is None ):
			return "<unknown>"
		name = str(name)
		name = vdb.shorten.function(name)


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
		name= vdb.color.color(prefix,color_ns.value) + tparam + vdb.color.color(fun,color_function.value) + suffix


		if( frame == gdb.selected_frame() ):
			name = vdb.color.color("[*]",color_frame.value) + name

		sal = frame.find_sal()
		addr = sal.pc
		if( int(addr) != 0 ):
			if frame.type() == gdb.INLINE_FRAME:
				name = "[i] " + name
		else:
			if frame.type() == gdb.INLINE_FRAME:
				name = " [inlined]        " + name
			else:
				name = "                  " + name
		
		return name

	def filename(self):
		frame = self.fobj.inferior_frame()
		sal = frame.find_sal()
		fname="<unknown>"
		try:
			fname = sal.symtab.filename
			fname = vdb.shorten.path(fname)
			fname = vdb.color.color(fname,color_filename.value)
		except:
			try:
				fname = sal.symtab.objfile
				fname = vdb.color.color(fname,color_objfile.value)
			except:
				try:
					fname = super(BacktraceDecorator,self).filename()
					if( fname is not None ):
						fname = vdb.color.color(fname,color_defobj.value)
				except:
					pass
		return fname


	def frame_args(self):
		args = super(BacktraceDecorator,self).frame_args()
		if( args is None ):
			return args
#		print("args = '%s'" % args )
		ret = [ ]
#		gdb.execute("set logging file /dev/null")
#		gdb.execute("set logging redirect on")
#		gdb.execute("set logging on")
		for a in args:
			if( str(a.symbol()) == "__in_chrg" ):
				continue
#			print("a.symbol() = '%s'" % a.symbol() )
			ret.append( ArgVal( a.symbol(), a.value() ) )
#		gdb.execute("set logging redirect off")
#		gdb.execute("set logging off")
		return ret

	def address(self):
		frame = self.fobj.inferior_frame()
		sal = frame.find_sal()
		addr = sal.pc
		if( int(addr) == 0 ):
			addr = None
#		print("addr = '%s'" % addr )
		return addr



class BacktraceIterator:
	def __init__(self, ii):
		self.input_iterator = ii
		self.inlined_frames = []
		self.next_real = None

	def __iter__(self):
		return self

	def __next__(self):
		try:
			frame = next(self.input_iterator)
		except StopIteration:
			if( self.next_real is None ):
				raise StopIteration
			sret = self.next_real
			self.next_real = None
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
			return BacktraceDecorator( toret, ifl )

#		print("Saving frame for later (%s)" % (len(self.inlined_frames)) )
		try:
			return self.__next__()
		except StopIteration:
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



class cmd_Bto (gdb.Command):
	"""Run the backtrace without filters"""

	def __init__ (self):
		super (cmd_Bto, self).__init__ ("bto", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

	def invoke (self, arg, from_tty):
		argv = gdb.string_to_argv(arg)
		try:
			bf.enabled = False
			if( len(argv) == 1 ):
				gdb.execute("bt {}".format(argv[0]))
			else:
				gdb.execute("bt")
		except:
			pass
		finally:
			bf.enabled = True

cmd_Bto()

class cmd_bt (gdb.Command):
	"""Run the backtrace without filters"""

	def __init__ (self):
		super (cmd_bt, self).__init__ ("bt", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
		self.dont_repeat()

	def invoke (self, arg, from_tty):
		argv = gdb.string_to_argv(arg)
		try:
			if( len(argv) == 1 ):
				btoutput = gdb.execute("backtrace {}".format(argv[0]),False,True)
			else:
				btoutput = gdb.execute("backtrace",False,True)
			btoutput = re.sub( "warning: RTTI symbol not found for class '.*?'\n",vdb.color.color("RTTI",color_rtti.value),btoutput)
			print(btoutput)
		except:
			pass

cmd_bt()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
