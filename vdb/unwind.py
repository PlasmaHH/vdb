#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.arch
import vdb.event
import vdb.memory
import vdb.asm
import vdb.hook

import gdb
import gdb.unwinder

import re
import traceback
import colors

enable_unwinder = vdb.config.parameter("vdb-unwind-enable",False)

hint_marker = vdb.config.parameter("vdb-unwind-hint-marker", "-----v")
hint_context = vdb.config.parameter("vdb-unwind-hint-context","1,0")
hint_default_range = vdb.config.parameter("vdb-unwind-hint-default-range", "-8,64", gdb_type = vdb.config.PARAM_ARRAY )

hint_color = vdb.config.parameter("vdb-unwind-colors-hint",   "#f55", gdb_type = vdb.config.PARAM_COLOUR)
hint_start_color = vdb.config.parameter("vdb-unwind-colors-hint-start",   "#ff8", gdb_type = vdb.config.PARAM_COLOUR)


class FrameId(object):
    def __init__(self, sp, pc):
        self.sp = sp
        self.pc = pc

def read_register( pf, reg ):
    try:
        return pf.read_register(reg)
    except ValueError:
        return None

class frame_info:

    def __init__(self,pf):
        self.thread_id = gdb.selected_thread().num
        self.sp = read_register(pf,"sp")
        self.pc = read_register(pf,"pc")
        self.rbp = read_register(pf,"rbp")
#        print("self.sp.is_optimized_out = '%s'" % (self.sp.is_optimized_out,) )
#        print("self.pc.is_optimized_out = '%s'" % (self.pc.is_optimized_out,) )
#        print("self.rbp.is_optimized_out = '%s'" % (self.rbp.is_optimized_out,) )
        self.level = pf.level()
        self.registers = {}
        for r in [ "rdi", "rsi", "rdx", "rcx", "rax" ]:
            rr = read_register(pf,r)
#            print("type(rr) = '%s'" % (type(rr),) )
#            print("rr = '%s'" % (rr,) )
#            print("rr.is_lazy = '%s'" % (rr.is_lazy,) )
#            print("rr.type = '%s'" % (rr.type,) )
#            print("rr.is_optimized_out = '%s'" % (rr.is_optimized_out,) )
            if( rr is not None and not rr.is_optimized_out ):
                self.registers[r] = rr
#        print(self)

    def __str__(self):
        ret = f"tid={self.thread_id}, level={self.level}, sp={self.sp}, pc={self.pc}, rbp={self.rbp}, registers={self.registers}"
        return ret

    def id( self ):
        return FrameId( self.sp, self.pc )

class unwind_filter(gdb.unwinder.Unwinder):

    class ArgVal():

        def __init__( self, sym, val ):
            self.sym = sym
            self.val = val

        def symbol(self):
            return self.sym

        def value(self):
            return self.val

    def __init__( self ):
        super(unwind_filter, self).__init__("vdb unwinder")
        self._enabled = True
        self.skip_next = False
        self.cache = {}
        self.replacements = {}
        self.annotations = {}
        self.clear()

    def do_annotate_frames( self, frame ):
        fi = self.cache.get(frame.level(),None)
        if( fi is None ):
            an = "No Unwind Info"
        else:
            an = f"level = {fi.level}, pc = {fi.pc}, sp = {fi.sp}, rbp = {fi.rbp}"
            for r,v in fi.registers.items():
                an += f", {r} = {v}"

        return [ self.ArgVal(str(frame.level()),an) ]

    def clear( self ):
        self.vptype = gdb.lookup_type("void").pointer()
        self.ptype = vdb.arch.gdb_uintptr_t
        self.cache = {}
        self.replacements = {}

    def __call__(self,pending_frame):
        try:
            if( self._enabled ):
                return self.do_call(pending_frame)
            else:
                return None
        except:
            print("unwind __call__")
            traceback.print_exc()

    def record( self, frameno, pf ):
        self.cache[frameno] = frame_info(pf)

    def fix( self, frameno, register, value ):
        f = self.cache.get( frameno-1, None )
        r = self.cache.get( frameno, None )
        if( f is None ):
            print(f"Cannot fix frame {frameno}, frame before it must be cached too")
            return
        if( r is None ):
            print(f"Cannot fix frame {frameno}, frame is not cached")

        cvalue = gdb.Value(value).cast(self.ptype).cast(self.vptype)
        if( register == "sp" ):
            r.sp = cvalue
        elif( register == "pc" ):
            r.pc = cvalue
        elif( register == "rbp" ):
            r.rbp = cvalue
        else:
            r.registers[register] = cvalue
        self.replacements[int(f.sp),int(f.pc)] = r

    def hide( self, frameno ):
        print(f"hide({frameno})")
        f = self.cache.get(frameno-1,None)
        r = self.cache.get(frameno+1,None)

        if( f is None or r is None ):
            print(f"Cannot hide frame {frameno}, both adjacent frames must be cached")
            return None

        self.replacements[(int(f.sp),int(f.pc))] = r
        print(f"Trying to hide frame {frameno}")
#        print("self.replacements = '%s'" % (self.replacements,) )

    def search_replacements( self, pc, sp ):
#        print("sp = '%s'" % (sp,) )
#        print("pc = '%s'" % (pc,) )
#        for k,v in self.replacements.items():
#            fsp,fpc = k
#            print("fsp = '%s'" % (fsp,) )
#            print("fpc = '%s'" % (fpc,) )
#            print("sp == fsp = '%s'" % (sp == fsp,) )
#            print("pc == fpc = '%s'" % (pc == fpc,) )
        r = self.replacements.get( ( int(sp), int(pc) ), None )
#        print("rs = '%s'" % (rs,) )
#        print("ri = '%s'" % (ri,) )
        return r

    def do_call(self,pending_frame):
        import vdb.asm
        sp = pending_frame.read_register("sp")
        pc = pending_frame.read_register("pc")
        lr = pending_frame.read_register("lr")
        print(f"{int(lr)=}")

        arch=pending_frame.architecture()
        try:
            listing = vdb.asm.parse_from_gdb(str(int(pc)),arch=arch,fakeframe=pending_frame,cached=False)
        except:
            listing = None
        last = None
        possible_registers = {}
        if( listing is not None ):
            for ins in listing.instructions:
                if( ins.address == int(pc) ):
#                print("ins.address = '%s'" % (ins.address,) )
#                print("int(pc) = '%s'" % (int(pc),) )
#                print("ins = '%s'" % (ins,) )
#                print("last = '%s'" % (last,) )
                    if( last is not None ):
#                    print("last.address = '%s'" % (last.address,) )
#                    print("last.possible_register_sets = '%s'" % (last.possible_register_sets,) )
                        if( len(last.possible_register_sets) > 0 ):
                            possible_registers = last.possible_register_sets[-1]
                last = ins

        lvl = pending_frame.level() # by default this is the frame numbers as in the backtrace shown
#        print(f"{lvl} : 0x{vdb.util.xint(pc):16x} : 0x{vdb.util.xint(sp):16x}")
        self.record(lvl,pending_frame)

        if( self.skip_next ):
            self.skip_next = False
            return None
#        try:
#            print("%s : pending_frame = '%s' : %s" % (pending_frame.level(),pending_frame,pc) )
#        except:
#            print("%s : pending_frame = '%s' : %s" % ("??",pending_frame,pc) )
#        rs,ri = self.replacements.get( ( sp, pc ), (None,None) )
        r = self.search_replacements( pc, sp )
        if( r is not None ):
#            rs = gdb.Value(rs).cast(self.ptype).cast(self.vptype)
#            ri = gdb.Value(ri).cast(self.ptype).cast(self.vptype)
            print(f"Trying to replace stackframe {pc},{sp} by {r.pc},{r.sp}")
            fid = r.id()
#            fid = FrameId(sp,pc)
#            print("fid = '%s'" % (fid,) )
#            print("fid.sp = '%s'" % (fid.sp,) )
#            print("fid.pc = '%s'" % (fid.pc,) )
#            print("fid.sp.type = '%s'" % (fid.sp.type,) )
#            print("fid.pc.type = '%s'" % (fid.pc.type,) )
#            print("fid.sp.type.sizeof = '%s'" % (fid.sp.type.sizeof,) )
#            print("fid.pc.type.sizeof = '%s'" % (fid.pc.type.sizeof,) )
            unwind_info = pending_frame.create_unwind_info(fid)

            all_registers = pending_frame.architecture().registers()
            for rnum in all_registers:
                try:
                    rval = pending_frame.read_register(rnum)
                    unwind_info.add_saved_register(rnum,rval)
                except:
                    print("rnum = '%s'" % (rnum,) )
                    traceback.print_exc()
            unwind_info.add_saved_register("pc",fid.pc)
            unwind_info.add_saved_register("sp",fid.sp)
            unwind_info.add_saved_register("rbp",r.rbp)
            for reg in [ "rax", "rdi", "rsi", "rdx", "rcx", "r8", "r9" ]:
                rval = possible_registers.get(reg,None)
                if( rval is not None ):
                    cvalue = gdb.Value(rval).cast(self.ptype).cast(self.vptype)
#                    print("reg = '%s'" % (reg,) )
#                    print("rval = '%s'" % (rval,) )
                    unwind_info.add_saved_register(reg,cvalue)

#            self.skip_next = True
#            print("unwind_info = '%s'" % (unwind_info,) )
            return unwind_info
        else:
            nx = self.cache.get( pending_frame.level()+1, None )
#            print("nx = '%s'" % (nx,) )
#            print("possible_registers = '%s'" % (possible_registers,) )
            if( nx is None ):
                return None
#            sp = pending_frame.read_register("sp")
#            pc = pending_frame.read_register("pc")
#            rbp = pending_frame.read_register("rbp")
#            print("rbp = '%s'" % (rbp,) )
#            f = self.cache.get(pending_frame.level())
#            print("f.rbp = '%s'" % (f.rbp,) )

            fid = nx.id()
            unwind_info = pending_frame.create_unwind_info(fid)
            all_registers = pending_frame.architecture().registers()
#            for rnum in range(0,196):
            for rnum in all_registers:
#                print("rnum = '%s'" % (rnum,) )
                try:
                    rval = pending_frame.read_register(rnum)
                    unwind_info.add_saved_register(rnum,rval)
                except:
                    print("rnum = '%s'" % (rnum,) )
                    traceback.print_exc()


            unwind_info.add_saved_register("pc",fid.pc)
            unwind_info.add_saved_register("sp",fid.sp)
            if( nx.rbp is not None ):
                unwind_info.add_saved_register("rbp",nx.rbp)
            for reg in [ "rax", "rdi", "rsi", "rdx", "rcx", "r8", "r9" ]:
                rval = possible_registers.get(reg,None)
                if( rval is not None ):
                    cvalue = gdb.Value(rval).cast(self.ptype).cast(self.vptype)
#                    print("reg = '%s'" % (reg,) )
#                    print("rval = '%s'" % (rval,) )
                    unwind_info.add_saved_register(reg,cvalue)
            return unwind_info
#        print("Not intresting")
        return None
        # Create UnwindInfo.  Usually the frame is identified by the stack
        # pointer and the program counter.
#        sp = pending_frame.read_register(<SP number>)
#        pc = pending_frame.read_register(<PC number>)
#        unwind_info = pending_frame.create_unwind_info(FrameId(sp, pc))

        # Find the values of the registers in the caller's frame and
        # save them in the result:
#        unwind_info.add_saved_register(<register>, <value>)

        # Return the result:
#        return unwind_info

class unwind_dispatch(gdb.unwinder.Unwinder):

    def __init__( self ):
        super(unwind_dispatch, self).__init__("vdb unwinder")
        self._enabled = enable_unwinder.value
        self.unwinders = {}
        self.annotate_frames = True

    def do_annotate_frames( self, frame, tid = None ):
        return self.current_unwinder(tid).do_annotate_frames(frame)

    def __call__(self,pending_frame):
        try:
            if( self._enabled ):
                return self.do_call(pending_frame)
            else:
                return None
        except:
            print("unwind __call__")
            traceback.print_exc()

    def current_unwinder( self, tid = None ):
        if( tid  is None ):
            tid = gdb.selected_thread().num

        unwinder = self.unwinders.get(tid,None)
        if( unwinder is None ):
            unwinder = unwind_filter()
            self.unwinders[tid] = unwinder
        return unwinder


    def do_call(self,pending_frame):
        
        return self.current_unwinder()(pending_frame)

    def clear( self ):
        for t,u in self.unwinders.items():
            u.clear()

    def enable( self, en ):
        self._enabled = en
        for t,u in self.unwinders.items():
            u._enabled = en

    def hide( self, frameno ):
        return self.current_unwinder().hide(frameno)

    def fix( self, frameno, reg, val ):
        return self.current_unwinder().fix(frameno,reg,val)


#unwinder = unwind_filter()
unwinder = unwind_dispatch()
flush_count=0

def hint( argv ):
    range_start = hint_default_range.elements[0]
    range_stop = hint_default_range.elements[1]

    stack_base="$sp"
    if( len(argv) > 0 ):
        if( argv[0].startswith("+") ):
            range_stop = int(argv[0])
        else:
            stack_base = argv[0]

    vptype = gdb.lookup_type("void").pointer()
    isym = gdb.execute("info symbol $pc",False,True)
    m=re.search(".*(\+ [0-9]*) in section.*",isym)
    funcstart = None
    if( m is not None ):
#        print("m = '%s'" % (m,) )
#        print("m.group(0) = '%s'" % (m.group(0),) )
#        print("m.group(1) = '%s'" % (m.group(1),) )
        offset = m.group(1)
        funcstart = gdb.parse_and_eval(f"$pc-{offset}")
        print(f"Searching for call to {funcstart}")
#        print("offset = '%s'" % (offset,) )
    archname = gdb.selected_frame().architecture().name()
    if( archname.startswith("arm") ):
        callre = re.compile("bl (0x[0-9a-f]*)")
        ccallre = re.compile("bl \*%") # computed calls
    else:
        callre = re.compile("call (0x[0-9a-f]*)")
        ccallre = re.compile("call \*%") # computed calls
    # $rsp-16 is kinda the default position
    # for other archs we might search differently?
#    for i in range(-8,64):
    for i in range(-8,range_stop):
        pos = f"{stack_base}+({vptype.sizeof}*{i})"
        mem=vdb.memory.read(pos,vptype.sizeof)
        val=gdb.Value(mem,vptype)

        at = vdb.memory.mmap.get_atype(val)
        if( at == vdb.memory.access_type.ACCESS_EX ):
            cmd=f"dis/{hint_context.value} {int(val)}"
            try:
                dis=gdb.execute(cmd,False,True)
            except:
                print("Failed: cmd = '%s'" % (cmd,) )
                traceback.print_exc()
                dis=None
            dis = dis.splitlines()
#            rng = dis[0]
            dis = dis[1:]
            pose = gdb.parse_and_eval(pos)
            print(vdb.color.color(f"At {pose} ({pos}) in ",hint_start_color.value), end = "")
            print(f"{val}:")
            if( funcstart is not None ):
                for d in dis:
                    pd = colors.strip_color(d)
                    m = callre.search(pd)
                    if( m is None ):
                        m = ccallre.search(pd)
                        if( m is not None ):
                            print(vdb.color.color(hint_marker.value,hint_color.value), end = "")
                            print(" (computed call, check actual registers if possible)")
                    else:
#                        print("m = '%s'" % (m,) )
#                        print("m.group(0) = '%s'" % (m.group(0),) )
#                        print("m.group(1) = '%s'" % (m.group(1),) )
                        target = m.group(1)
                        target = vdb.util.xint(target)
#                        print("target = '%s'" % (target,) )
#                        print("funcstart = '%s'" % (funcstart,) )
                        if( target == int(funcstart) ):
                            print(vdb.color.color(hint_marker.value,hint_color.value))
            for d in dis:
                if( len(d) > 0 ):
                    print(d)
#            print("dis = '%s'" % (dis,) )

#            asm=vdb.asm.get_single(val)
#            da=gdb.selected_frame().architecture().disassemble(int(val),count=1)


@vdb.event.new_objfile()
def flush():
    global flush_count
    flush_count += 1
    frameno = None
    try:
        frameno = gdb.selected_frame().level()
    except:
        pass
    gdb.execute("maintenance flush register-cache") # clear cache, cause to call again
    if( frameno is not None ):
        gdb.execute(f"frame {frameno}",False,True)

@vdb.event.stop()
@vdb.event.new_objfile()
def clear():
    global flush_count
    flush_count=0
    global unwinder
    unwinder.clear()

def register():
    gdb.unwinder.register_unwinder( None, unwinder, replace = True )

def enable():
    global unwinder
    unwinder.enable(True)
    register()

def disable():
    global unwinder
    unwinder.enable(False)
    register()

def hide( argv ):
    global unwinder
    unwinder.hide( int(argv[0]) )
    flush()

def fix( argv ):
    global unwinder
    unwinder.fix( int(argv[0]), argv[1], vdb.util.xint(argv[2]) )
    flush()



@vdb.event.before_prompt()
def auto_flush():
#    if( flush_count < 1 and unwinder.enabled ):
    if( flush_count < 1 ):
        flush()


register()

class cmd_unwind (vdb.command.command):
    """Module holding information about memory mappings

    """

    def __init__ (self):
        super (cmd_unwind, self).__init__ ("unwind", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            if( len(argv) > 0 ):
#                print("argv = '%s'" % (argv,) )
                if( argv[0] == "enable" ):
                    enable()
                elif( argv[0] == "disable" ):
                    disable()
                elif( argv[0] == "hide" ):
                    hide(argv[1:])
                elif( argv[0] == "fix" ):
                    fix(argv[1:])
                elif( argv[0] == "clear" ):
                    clear()
                elif( argv[0] == "hint" ):
                    hint(argv[1:])
                else:
                    raise Exception("No idea what you mean by %s" % argv)
            else:
                raise Exception("unwind got %s arguments, expecting 0 or 1" % len(argv) )
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_unwind()

# not sure if this is the right place, but its a "fix" from some odd unwind related behaviour, so just put it here
#def frame_changed( frcmd ):
#    print("Detected frame change, flushing registers")
#    gdb.execute("maintenance flush register-cache")

#vdb.hook.any_after( "^fr.*\s+[0-9]+", frame_changed )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
