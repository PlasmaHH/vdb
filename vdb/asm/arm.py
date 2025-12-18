#!/usr/bin/env python3

import re
import gdb
import vdb.asm
import rich
import typing
import sys

name = "arm"

return_mnemonics = set ([])
call_mnemonics = set(["bl", "blx"])
prefixes = set([ ])
base_pointer = "r11" # can be different
stack_pointer = "sp" # msp/psp should be handled by gdb itself

# ( use_or, list_of_flags )
flag_conditions = {
        "eq"  : ( False, [ ( "Z", 1, True ) ], "equal" ),
        "z"   : ( False, [ ( "Z", 1, True ) ], "zero" ),
        "ne"  : ( False, [ ( "Z", 0, True ) ], "not equal" ),
        "nz"  : ( False, [ ( "Z", 0, True ) ], "not zero" ),
        "cs"  : ( False, [ ( "C", 1, True ) ], "carry" ),
        "hs"  : ( False, [ ( "C", 1, True ) ], "unsigned higher or same" ),
        "cc"  : ( False, [ ( "C", 0, True ) ], "carry clear" ),
        "lo"  : ( False, [ ( "C", 0, True ) ], "unsinged lower" ),
        "mi"  : ( False, [ ( "N", 1, True ) ], "minus" ),
        "pl"  : ( False, [ ( "N", 0, True ) ], "plus" ),
        "vs"  : ( False, [ ( "V", 1, True ) ], "overflow" ),
        "vc"  : ( False, [ ( "V", 0, True ) ], "no overflow" ),
        "hi"  : ( False, [ ( "C", 1, True ), ( "Z", 0, True ) ], "unsigned higher" ),
        "ls"  : ( True,  [ ( "C", 0, True ), ( "Z", 1, True ) ], "unsigned lower or same" ),
        "ge"  : ( False, [ ( "N", "V", True ) ], "signed greater or equal" ),
        "lt"  : ( False, [ ( "N", "V", False ) ], "signed less" ),
        "gt"  : ( False, [ ( "Z", 0, True ), ( "N", "V", True ) ], "signed greater" ),
        "le"  : ( True,  [ ( "Z", 1, True ), ( "N", "V", False ) ], "signed less or equal" ),
        } # All others not supported yet due to no support for these flags yet


conditional_suffixes = { "eq","ne","cs","hs","cc","lo","mi","pl","vs","vc","hi","ls","ge","lt","gt","le","z","nz" }
encoding_suffixes = [ "n","w" ]
unconditional_jump_mnemonics = set([ "b", "bx", "cb" ] )
conditional_jump_mnemonics = set()
for uj in unconditional_jump_mnemonics:
    for csuf in conditional_suffixes:
        fmn = uj+csuf
        conditional_jump_mnemonics.add(fmn)
        for enc in encoding_suffixes:
            conditional_jump_mnemonics.add(fmn + "." + enc )

narm = set()
for unc in unconditional_jump_mnemonics:
    narm.add(unc)
    for enc in encoding_suffixes:
        narm.add(f"{unc}.{enc}")

unconditional_jump_mnemonics = narm



known_instructions = set()


def collect_instructions( name ):
    module = sys.modules[name]
    for funname in dir(module):
        if( funname.startswith("vt_flow_") ):
            funname = funname.removeprefix("vt_flow_")
            known_instructions.add( funname )
            # The following may not all exist but this is just for helping us parse suffixes better
            known_instructions.add( funname + "s" ) # a possible "set flags" version
            # byte, double and halfword versions?
            known_instructions.add( funname + "b" )
            known_instructions.add( funname + "d" )
            known_instructions.add( funname + "h" )
            # uhm, mov only?
            known_instructions.add( funname + "t" )
            known_instructions.add( funname + "w" )
            # These are just hacked together what we really want is a proper list ai guess. Any way to get one
            # automatically from gdb?

def extract_conditional( mnemonic ):
    if( len(known_instructions) == 0 ):
        collect_instructions(__name__)

    mnemonic = mnemonic.removesuffix(".n")
    mnemonic = mnemonic.removesuffix(".w")

    # For example for movs we have the problem do we interpret it as mo with suffix vs or no suffix at all? Generally we
    # would like to only have suffixes for known instructions as such when the remainder is not a known instruction we
    # do not accept it. Also first the longer ones as we have nz and z

    l2 = mnemonic[-2:]
    if( l2 in conditional_suffixes ):
        rm = mnemonic[:-2]
        if( rm in known_instructions ):
            return l2,rm

    l1 = mnemonic[-1:]
    if( l1 in conditional_suffixes ):
        rm = mnemonic[:-1]
        if( rm in known_instructions ):
            return l1,rm


    return (None, mnemonic)

# XXX This is just copied from x86, we need to go through things and add them here
# The order is sometimes important
_arm_class_res = [
        ( "bic.*", "bit" ),
        ( "j.*|b.*|cb.*", "jump" ),
        ( "[vp]*mov.*|xchg.*|stos", "mem" ),
        ( "[vp]*cmp.*|test.*|cmov.*|[cp]*comisd", "cond" ),
        ( "call.*", "call" ),
        ( "ret.*", "ret" ),
        ( "nop.*|endbr.*" ,"nop" ),
        ( ".*mxcsr|vld.*|vst.*|vcom.*|ucom.*|pxor.*|punpckl.*", "vector" ),
        ( "[vp]*sub.*|[vp]*add.*|imul.*|[vp]*mul.*|[vp]*div.*|[vp]*dec.*|[vp]*inc.*|[vp]*neg.*", "math" ),
        ( "[vp]*fmadd.*|[vp]*fmsub.*", "math" ),
        ( "[vp]*fnmadd.*|[vp]*fnmsub.*", "math" ),
        ( "sbb", "math" ),
        ( "[vp]*xor.*|[vp]*shr.*|[vp]*and.*|[vp]*or.*|[vp]*shl.*|[vp]*sar.*|[vp]*ror.*|[vp]*not.*", "bit" ),
        ( "psrldq|pslldq", "bit" ),
        ( "push.*|pop.*|lea.*", "stack" ),
        ( "hlt.*|syscall.*|int.*", "sys" ),
        ( "ldm.*|stm.*", "stack" ),
        ( "ld.*|str.*", "mem" ),
        ( "eor.*|lsl.*|uxt.*|sxt.*|lsr.*", "bit" ),
        ( "it.*|tst.*", "cond" ),
        ]


argument_registers = [ "r0","r1","r2","r3","r4","r5","r6","r7","r8" ]
base_pointer = "sp"

class asm_arg(vdb.asm.asm_arg_base):

    shift_map = {
            "lsl #1" : 1,
            "lsl #2" : 2,
            "lsl #3" : 3
            }

    def __init__( self, target, arg ):
        self.writeback = False
        super().__init__( target, arg )

    @vdb.overrides
    def parse( self, arg ):
#        vdb.util.bark() # print("BARK")
#        print(f"parse( {arg=} )")
        arg = arg.strip()
        if( arg.startswith("{") ):
            self.list_start = True
            arg = arg[1:]

        if( arg.endswith("}") ):
            self.list_end = True
            arg = arg[:-1]
#        vdb.util.bark() # print("BARK")
        oarg = arg
        if( arg.startswith("0x") ):
            args = arg.split("<")
            if( len(args) > 1 ):
                arg = args[0].strip()
                # we throw away the symbolname here, do we want to keep it in case no other way shows it?
            self.jmp_target = vdb.util.rxint( arg )
        elif( arg.startswith("#") ):
            if( arg.startswith("#0x") ):
                self.immediate_hex = vdb.util.xint(arg[1:])
            else:
                self.immediate = int(arg[1:])
        elif( arg.startswith("[") and arg.endswith("]")):
            arg = arg[1:-1]
#            print(f"{arg=}")
            arg = list(map(str.strip,arg.split(",")))
#            print(f"{arg=}")
            self.dereference = True
            self.register = arg[0]
            offset_pos = None
            shift_pos = None
            if( len(arg) == 2 ):
                offset_pos = 1
            elif( len(arg) == 3 ):
                offset_pos = 1
                shift_pos = 2
#                print("arg[1] = '%s'" % (arg[1],) )
            if( offset_pos is not None ):
                self.offset = arg[offset_pos]
                if( self.offset.startswith("#") ):
                    self.offset = int(self.offset[1:])
            if( shift_pos is not None ):
                self.offset_shift = arg[shift_pos]
                self.offset_shift = self.shift_map.get(self.offset_shift)

#            if( len(arg) >= 3 ):
#                print(f"{len(arg)=}")
#                print(f"{arg=}")
#                print(f"{oarg=}")
#                print(f"{str(self)=}")
#                print(f"{self.register=}")
#                print(f"{self.add_register=}")
#                print(f"{self.offset=}")
#                print(f"{self.offset_shift=}")
#                print("########################################################################..........")
        else:
            if( arg.find("[") != -1 ):
                raise RuntimeError("No idea how to parse")
            if( arg.endswith("!") ):
                arg = arg.removesuffix("!")
                self.writeback = True
            self.register = arg

        self._check(oarg,False)

    def __str__( self ):
        ret = ""
        if( self.asterisk ):
            ret +=  "*"
        if( self.prefix is not None ):
            ret += f"%{self.prefix}:"
        if( self.dereference ):
            ret += "["
            ret += self.register
            if( self.add_register is not None ):
                ret += ", " + self.add_register
            if( self.offset is not None ):
                if( isinstance(self.offset,int) ):
                    ret += ", #" + str(self.offset)
                else:
                    ret += ", " + self.offset
            if( self.offset_shift is not None ):
                ret += ", lsl #" + str(self.offset_shift)
            ret += "]"
        elif( self.register is not None ):
            ret += self.register
        if( self.immediate is not None ):
            if( self.immediate_hex ):
                ret += f"${self.immediate:#0x}"
            else:
                ret += f"#{self.immediate}"
        if( self.jmp_target is not None ):
            ret += f"{self.jmp_target:#0x}"

        if( self.writeback ):
            ret += "!"

        return ret


class instruction( vdb.asm.instruction_base ):

    class_res = vdb.asm.instruction_base.compile_class_res( _arm_class_res )
    class_cache = {}
    last_cmp_immediate = 1

    def __init__( self, line, m, oldins, function_range ):
        super().__init__()
        self.parse(line,m,oldins, function_range)

    def executes( self, flags ):
#        self.add_extra(f"SUFFIX {self.conditional_suffix}")
        if( self.conditional_suffix is not None ):
            taken,extrastring = vdb.asm.flag_check( self.conditional_suffix, flags, flag_conditions )
            _,_,ex = flag_conditions.get(self.conditional_suffix,"??")
#            self.add_extra(f"EX?? {ex}")
            return (True,taken)
        return (False,None)

    @vdb.overrides
    def parse( self, line, m, oldins, function_range ):
#        vdb.util.bark() # print("BARK")

        tokens = self.parse_common( line, m, oldins )

        ibytes = []
        while( self.bytere2.match(tokens[0]) ):
            ibytes.append(tokens[0])
            del tokens[0]
        self.bytes = ibytes

        while( tokens[0] in prefixes ):
            self.prefixes.append( tokens[0] )
            del tokens[0]

        self.mnemonic = tokens[0]
        if( self.mnemonic == ";" ):
            self.mnemonic = ""
        else:
            del tokens[0]

        # up until to the mnemonic x86 and arm are the same, so put everything into a function
        tokens = " ".join(tokens)
        tokens = tokens.split(";")
        if( len(tokens) == 1 ): ## aarch64 uses // instead of ;
            tokens = tokens[0].split("//")
        if( len(tokens) == 1 ): ## sometimes there is an @
            tokens = tokens[0].split("@")
        if( len(tokens) > 1 ):
            self.reference = "".join(tokens[1:])
            self.reference = [ ( self.reference, len(self.reference) ) ]
        args = tokens[0].strip()
#        print(f"{args=}")
        if( len(args) > 0 and args[-1] == ">" and ( ( lbi := args.find("<") ) > 0 ) ):
#            print(f"{lbi=}")
            args = args[:lbi]
#        print(f"{args=}")
        self.args_string = args

        oargs = args
#        print("start oargs = '%s'" % (args,) )

        if( len(args) > 0 ):
            self.args = []
#            print("args = '%s'" % (args,) )
            args = args.split(",")
#            print("args = '%s'" % (args,) )
            target = True
            while len(args) > 0:
                arg = args[0].strip()
                if( len(arg) == 0 ):
                    del args[0]
                    continue
                if( arg == "!" ):
                    self.arguments[-1].writeback = True
                    del args[0]
                    continue
                if( arg[0] == "[" ):
                    restarg = ",".join(args).strip()
                    # Re-parse that thing and then split again
#                    print(f"{restarg=}")
                    end = vdb.util.find_closing( restarg, 0, "[", "]" ) + 1
                    arg = restarg[0:end]
                    restarg = restarg[end:]
#                    print(f"{restarg=}")
                    if( len(restarg) > 0 ):
                        args = restarg.split(",")
                    else:
                        args = []
#                    print(f"{arg=}")
#                    print(f"{args=}")
                else:
                    del args[0]
                aarg = asm_arg(target,arg)
#                vdb.util.inspect(aarg)
#                print(f"{aarg=}")
                target = False
                self.args.append(arg)
                self.arguments.append(aarg)

        # reassemble to check the string for consistency
        reargs = ""
        for a in self.arguments:
            if( a.list_start ):
                reargs += "{"
            reargs += str(a)
            if( a.list_end ):
                reargs += "}"
            reargs += ", "

        reargs = reargs.removesuffix(", ")

        if( reargs != oargs.strip() ):
            print("ARM CHECK OF WHOLE EXPRESION FAILED")
            print(f"{oargs=}")
            print(f"{reargs=}")
            print(f"{self.arguments=}")
            self.add_extra(reargs,static=True)

        if( self.mnemonic in call_mnemonics ):
            self.call = True
            try:
                # Might be a register
                self.targets.add( vdb.util.xint(self.args[-1]) )
            except ValueError:
                pass
        elif( self.mnemonic in conditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
#            print("self.next = '%s'" % (self.next,) )
#            print("oargs = '%s'" % (oargs,) )
#            print("self.args = '%s'" % (self.args,) )
            self.targets.add( vdb.util.xint(self.args[-1]) )
            self.conditional_jump = True
        elif( self.mnemonic in unconditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
            try:
                self.targets.add( vdb.util.xint(oargs) )
            # Might not be a value, in that case we just ignore it
            except ValueError:
                pass
            self.unconditional_jump = True
        elif( self.mnemonic in ["tbb","tbh"] ): # arm jump table stuff
#            print("ARM TBB/TBH DETECTED")
            try:
                # TODO Check how to support other registers (would probably require rewriting targets)
                if( self.arguments[0].register == "pc" ):
                    if( self.mnemonic == "tbh" ):
                        ctyp = "unsigned short"
                        csz  = 2
                    else:
                        ctyp = "unsigned char"
                        csz  = 1
                    tbllen = int(instruction.last_cmp_immediate)
#                    print("tbllen = '%s'" % (tbllen,) )
#                    print("self.address = '%s'" % (self.address,) )
                    for i in range(0,tbllen):
                        gexp = f"{self.address} +4+ *({ctyp}*)({self.address}+4+{csz}*{i})*2"
#                        print("gexp = '%s'" % (gexp,) )
#                        gdb.execute(f"p *({ctyp}*)({self.address}+4+{csz}*{i})*2")
                        gexp = gdb.parse_and_eval( gexp )
#                        print("gexp = '%x'" % (gexp,) )
                        self.targets.add( int(gexp) )
#                        print("self = '%s'" % (self,) )

        # Try to find possible return equivalents

            except ValueError:
                pass
        elif( self.mnemonic.startswith("cmp") ):
            instruction.last_cmp_immediate = self.arguments[1].immediate
#            print("instruction.last_cmp_immediate = '%s'" % (instruction.last_cmp_immediate,) )
        elif( self.mnemonic.startswith("ldr") ):
            # Try to recover a jumptable
            # XXX Probably others than ldr do it too?
            if( self.args[0] == "pc" ):
                # This could also be a way to encode a return, assume so if it reads from the stackpointer without
                # offset
                if( self.arguments[1].register == "sp" ):
                    if( self.arguments[1].offset is None ):
                        self.return_ = True
#                print(f"{self.address=:#0x}")
#                print(f"{line=}")
#                print(f"{m=}")
#                print(f"{oldins=}")
#                print(f"{function_range[0]=:#0x}")
#                print(f"{function_range[1]=:#0x}")
#                startat = self.address
#                startat |= 0b111
#                startat += 1
#                for i in range( startat, function_range[1], 4):
#                    mem = int.from_bytes(vdb.memory.read( i, 4 ),"little")
#                    if( mem > function_range[0] and mem <= function_range[1] ):
#                        print(f"{mem=:#0x} @ {i:#0x}")

        if( self.mnemonic == "pop" ):
            if( "pc" in self.args ):
                self.return_ = True

        if( self.mnemonic == "b" or self.mnemonic == "bx" ):
            if( self.args[0] == "lr" ):
                self.return_ = True

        # "generic" pop like instructions
        if( self.mnemonic.startswith("ldm") or self.mnemonic.startswith("pop") ):
            for a in self.arguments:
                if( a.register == "pc" ):
                    self.return_ = True
                    break

        if( self.return_ ):
            self.add_extra("return",static=True)

        if( vdb.asm.debug_all(self) ):
            print("###########################################################")
            print("self.targets = '%s'" % (self.targets,) )

#            print("oldins = '%s'" % (oldins,) )
#            print("self = '%s'" % (self,) )
#            print("oldins.mnemonic = '%s'" % (oldins.mnemonic,) )
#            print("oldins.next = '%s'" % (oldins.next,) )
        if( oldins is not None and not oldins.return_ and not oldins.unconditional_jump ):
            oldins.next = self
            self.previous = oldins
#            print("oldins.next = '%s'" % (oldins.next,) )
#            print("2oldins = '%s'" % (oldins,) )
        self.iclass = self.mnemonic_class( self.mnemonic )

        self.conditional_suffix, self.base_mnemonic = extract_conditional( self.mnemonic )
        if( self.conditional_suffix is not None ):
            self.conditional = True
#            self.add_extra(f"COND: {self.conditional_suffix}",static=True)
        return self

# for the "according to the result" flags
def set_flags_result( flag_set, result, arg = None, val = None, flagset = "ZNVC" ):
    #  So far this is a copy of x86 and obviously wrong. Before we can do anything we need to figure out a good way to
    #  make vdb.register more architecture independent as things like the register size are not handled that way yet.
#    print(f"set_flags_result( {flag_set}, {result}, {arg} )")
#        vdb.util.bark() # print("BARK")
#    print(f"{arg.bitsize=}")
    if( result < 0 ):
        if( arg is not None and ( bs := arg.bitsize ) is not None ):
            result += (1 << bs)

    if( "Z" in flagset ):
        flag_set.set("Z", int(result == 0) )
    if( arg is not None and ( bs := arg.bitsize ) is not None ):
            if( "C" in flagset ):
                flag_set.set("C", int( (result >> arg.bitsize) & 1 ))
            sbit = ( 1 << (bs-1) )
            if( "N" in flagset ):
                flag_set.set("N", int( (result & sbit) != 0  ))
            if( "V" in flagset ):
                flag_set.set("V", int( (result & sbit) != (val & sbit) ) )
    return flag_set.subset( flagset )

# Gets the proper args from 2 and 3 arg versions of the opcode
def _extract_args_23( ins, possible_registers ):
    if( len(ins.arguments) == 2 ):
        dest    = ins.arguments[0]
        left,_  = ins.arguments[0].value( possible_registers )
        right,_ = ins.arguments[1].value( possible_registers )
    else: # assumed 3, might work for more too (those with that extra shift, doesnt matter for us here)
        dest    = ins.arguments[0]
        left,_  = ins.arguments[1].value( possible_registers )
        right,_ = ins.arguments[2].value( possible_registers )
    return (dest,left,right)

def _format_unknown( msg, *args ):
    uargs = []
    for a in args:
        u = vdb.asm.format_unknown( a[0], a[1] )
        uargs.append(u)
    ret = msg.format(*uargs)
#    print(f"{msg=}")
#    print(f"{ret=}")
#    print(f"{uargs=}")
    return ret

def vt_flow_orr( ins, frame, possible_registers, possible_flags , executes ):
    dest,left,right = _extract_args_23( ins, possible_registers )

    extext = _format_unknown( "Bitwise or of {0} and {1}, stored in register {2}", (left,"{:#0x}"),(right,"{:#0x}"),(ins.arguments[0].register,""))
    ftext = ""
    if( ins.mnemonic == "orrs" ):
        possible_flags.unset( [ "N", "Z", "C" ] )
        ftext += ", setting flags"

    if( left is not None and right is not None ):
        res = left | right
        possible_registers.set( ins.arguments[1].register, res, origin = "flow_orr")
        extext += f" => {res}{ftext}"
        if( ins.mnemonic == "orrs" ):
            filtered = set_flags_result( possible_flags, res, dest, left, "ZNC" )
            extext += f" to {filtered}"
    else:
        possible_registers.set( ins.arguments[1].register, None, origin = "flow_orr")
        extext += ftext

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)

def vt_flow_and( ins, frame, possible_registers, possible_flags , executes ):
    dest,left,right = _extract_args_23( ins, possible_registers )

    extext = _format_unknown( "Bitwise and of {0} and {1}, stored in register {2}", (left,"{:#0x}"),(right,"{:#0x}"),(ins.arguments[0].register,""))
    ftext = ""
    if( ins.mnemonic == "ands" ):
        possible_flags.unset( [ "N", "Z", "C" ] )
        ftext += ", setting flags"

    if( left is not None and right is not None ):
        res = left & right
        possible_registers.set( ins.arguments[1].register, res, origin = "flow_and")
        extext += f" => {res}{ftext}"
        if( ins.mnemonic == "ands" ):
            filtered = set_flags_result( possible_flags, res, dest, left, "ZNC" )
            extext += f" to {filtered}"
    else:
        possible_registers.set( ins.arguments[1].register, None, origin = "flow_and")
        extext += ftext

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)

def vt_flow_tst( ins, frame, possible_registers, possible_flags , executes ):
    dest,left,right = _extract_args_23( ins, possible_registers )

    extext = _format_unknown( "test: Bitwise and of {0} and {1}, storing only flags", (left,"{:#0x}"),(right,"{:#0x}"))

    possible_flags.unset( [ "N", "Z", "C" ] )

    if( left is not None and right is not None ):
        res = left & right
        extext += f" => {res}"
        filtered = set_flags_result( possible_flags, res, dest, left, "ZNC" )
        extext += f" to {filtered}"
    else:
        pass

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)

def vt_flow_it( ins, frame, possible_registers, possible_flags , executes ):
    mle = len(ins.mnemonic) - 1
    cond = ins.args[0]
    extext = f"Conditional execution of the next {mle} instructions."
    for i,c in enumerate(ins.mnemonic[1:]):
        if( c == "t" ):
            extext += f"{i}) if {cond} "
        else:
            extext += f"{i}) if not {cond} "

    ins.add_explanation(extext)
    # We assume that the disassembler correctly synthesized these instructions suffixes
#    ins.unhandled = True
    return (possible_registers,possible_flags)

def vt_flow_uxth( ins, frame, possible_registers, possible_flags , executes ):

    right,_ = ins.arguments[1].value( possible_registers )

    extext = f"Unsigned Extend Halfword, sets the higher 16 bits to 0"
    # XXX Rotation is not yet implemented
    if( right is not None ):
        res = right & 0xffff
        possible_registers.set( ins.arguments[1].register, res, origin = "flow_uxth")
        extext += f", {right:#0x} & 0xffff => {res:#0x}"
    else:
        possible_registers.set( ins.arguments[1].register, None, origin = "flow_uxth")

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)


def vt_flow_bic( ins, frame, possible_registers, possible_flags , executes ):

    # bic r1,r2 is the same as bic r1,r1,r2
    if( len(ins.arguments) <= 2 ):
        valleft,_ = ins.arguments[0].value( possible_registers )
        valright,_ = ins.arguments[1].value( possible_registers )
    else:
        valleft,_ = ins.arguments[1].value( possible_registers )
        valright,_ = ins.arguments[2].value( possible_registers )

    if( len(ins.arguments) > 3 ):
        ins.add_extra("UNHANDLED SHIFT")

    extext = _format_unknown( f"Bitwise bit clear {0} & ~{1}", ( valleft, "" ), ( valright, "") )
    ftext = ""
    if( ins.mnemonic == "bics" ):
        possible_flags.unset( ["C", "N", "Z"] )
        ftext += ", setting flags CZN"

    if( valleft is not None and valright is not None ):
        res = valleft & ~valright
        possible_registers.set( ins.arguments[0].register, res, origin = "flow_bic" )
        extext += f" => {res}{ftext}"
        if( ins.mnemonic == "bics" ):
            filtered = set_flags_result( possible_flags, res, ins.arguments[1], flagset = "ZNC" )
            extext += f" to {filtered}"
    else:
        possible_registers.set( ins.arguments[0].register, None, origin = "flow_bic" )
        extext += ftext

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)

def vt_flow_ldr( ins, frame, possible_registers, possible_flags , executes ):
    val,addr = ins.arguments[1].value( possible_registers )
    possible_registers.set( ins.arguments[0].register, val ,origin="flow_ldr" )

    post_text = ""
    if( len(ins.arguments) == 3 ):
#        print(f"{ins}")
#        vdb.util.inspect( possible_registers )
#        vdb.util.inspect( ins.arguments[0] )
#        vdb.util.inspect( ins.arguments[1] )
#        vdb.util.inspect( ins.arguments[2] )
#        print(f"{len(ins.arguments)=}")
#        print(f"{val=}")
#        print(f"{addr=}")
        # XXX Verify these calculations
        val,addr = ins.arguments[1].value( possible_registers )
        addval,_ = ins.arguments[2].value( possible_registers )
        # Since its dereferencing, the addr is the one we are looking for as the value of the register
        if( addr is None ):
            possible_registers.set( ins.arguments[1].register, addr )
        elif( addval is not None ):
            possible_registers.set( ins.arguments[1].register, addr + addval )
        else:
            possible_registers.set( ins.arguments[1].register, None )
#        vdb.util.inspect( possible_registers )
        post_text = f", advancing register {ins.arguments[1].register} by {ins.arguments[2].immediate}"

    if( addr is not None ):
        ins.loads_from.add( int(addr) )

    if( ins.arguments[0].register == "pc" ):
        print("HEY HERE LOOK WE LDR into PC THIS MUST BE A COMPUTED JUMP WE SHOULD DO SOMTHING ABOUT IT")

    ins.add_explanation(f"Load value {vdb.asm.format_unknown(val)} from memory address {vdb.asm.format_unknown(addr,'{:#0x}')} into register {ins.arguments[0].register}{post_text}")
    return (possible_registers,possible_flags)

def vt_flow_str( ins, frame, possible_registers, possible_flags , executes ):
    rval,_ = ins.arguments[0].value( possible_registers )
    val,addr = ins.arguments[1].value( possible_registers )

    if( len(ins.arguments) == 3 ):
        # XXX Verify these calculations
#        print(f"{ins.arguments[1]=}")
#        print(f"{ins.arguments[2]=}")
        val,addr = ins.arguments[1].value( possible_registers )
        addval,_ = ins.arguments[2].value( possible_registers )
        # XXX Cannot handle yet str  r3, [r2, #16]!
        # yes the one with the bang
        if( addr is None  or addval is None):
            possible_registers.set( ins.arguments[1].register, addr )
        else:
            possible_registers.set( ins.arguments[1].register, addr + addval )

    ins.add_explanation(f"Store value {vdb.asm.format_unknown(rval)} into memory at {vdb.asm.format_unknown(addr,'{:#0x}')}")
    return (possible_registers,possible_flags)

def vt_flow_stmdb( ins, frame, possible_registers, possible_flags , executes ):
    target,_ = ins.arguments[0].value( possible_registers )
    # ! version writes back the value
    extext = _format_unknown( "Store Multiple Decrement Before stores the registers {0} in memory starting at {1} and decremented each step. Same as push.", ( str(ins.arguments[1:]),"" ), ( target, "{:#0x}") )

    if( target is not None ):
        target -= 4 * (len(ins.arguments)-1)

    if( ins.arguments[0].writeback ):
        extext += " Writes back decremented register"
        possible_registers.set( ins.arguments[0].register, target )

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)

def vt_flow_lsl( ins, frame, possible_registers, possible_flags , executes ):
    # XXX Many of these are almost the same, just the actual calculation differs. Unify them.
    # lsl r0,r1 is the same as lsl r0,r0,r1
    dest, lsl, lsr = _extract_args_23( ins, possible_registers )

    extext = _format_unknown( "Logical shift left {0} by {1} bits", ( lsl, "" ), ( lsr, "" ))

    ftext = ""
    if( ins.mnemonic == "lsls" ):
        possible_flags.unset( [ "N", "Z", "C" ] )
        ftext += ", setting flags"

    if( lsl is not None and lsr is not None ):
        res = lsl << lsr
        possible_registers.set( dest.register, res ,origin="flow_lsl" )
        if( ins.mnemonic == "lsls" ):
            filtered = set_flags_result( possible_flags, res, dest, lsl, "ZNC" )
            extext += f"{ftext} to {filtered}"
        extext += f" => {res}"
    else:
        possible_registers.set( dest.register, None )
        extext += ftext

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)


def vt_flow_lsr( ins, frame, possible_registers, possible_flags , executes ):
    # XXX Many of these are almost the same, just the actual calculation differs. Unify them.
    # lsr r0,r1 is the same as lsr r0,r0,r1
    dest, lsr, lsr = _extract_args_23( ins, possible_registers )

    extext = _format_unknown( "Logical shift left {0} by {1} bits", ( lsr, "" ), ( lsr, "" ))

    ftext = ""
    if( ins.mnemonic == "lsrs" ):
        possible_flags.unset( [ "N", "Z", "C" ] )
        ftext += ", setting flags"

    if( lsr is not None and lsr is not None ):
        res = lsr >> lsr
        possible_registers.set( dest.register, res ,origin="flow_lsr" )
        if( ins.mnemonic == "lsrs" ):
            filtered = set_flags_result( possible_flags, res, dest, lsr, "ZNC" )
            extext += f"{ftext} to {filtered}"
        extext += f" => {res}"
    else:
        possible_registers.set( dest.register, None )
        extext += ftext

    ins.add_explanation(extext)
    return (possible_registers,possible_flags)


# Basically sub without store, always sets flags only
def vt_flow_cmp( ins, frame, possible_registers, possible_flags , executes ):
    dr,cmpl, cmpr = _extract_args_23( ins, possible_registers )

    extext = f"compare: subtracting {vdb.asm.format_unknown(cmpl)} and {vdb.asm.format_unknown(cmpr,'{}')}, storing only the flags"

    possible_flags.unset( [ "N", "Z", "C", "V" ] )

    if( cmpl is not None and cmpr is not None ):
        sumv = cmpl - cmpr
        extext += f" => {sumv}"
        set_flags_result( possible_flags, sumv, dr, cmpl, "ZNC" )
            # Carry flag: 1 if result exceeds 32 bits
#            possible_flags.set("C", int( (sumv >> 32) & 1 ))
            # Overflow flag: 1 if signed overflow
        possible_flags.set("V", int( ( (cmpl ^ cmpr) & (cmpl ^ sumv) ) & 0x80000000 ))
        filtered = possible_flags.subset( { "Z","N","C","V" } )
        extext += f" to {filtered}"
    else:
        pass

    ins.add_explanation(extext)

    return (possible_registers,possible_flags)


def vt_flow_add( ins, frame, possible_registers, possible_flags , executes ):
    sumlarg, suml, sumr = _extract_args_23( ins, possible_registers )

    extext = f"Adding {vdb.asm.format_unknown(suml)} and {vdb.asm.format_unknown(sumr,'{}')}, storing it in {ins.arguments[0]}"

    ftext = ""
    if( ins.mnemonic == "adds" ):
        possible_flags.unset( [ "N", "Z", "C", "V" ] )
        ftext += ", setting flags"

    if( suml is not None and sumr is not None ):
        sumv = suml + sumr
        possible_registers.set( ins.arguments[0].register, sumv,origin="flow_add" )
        extext += f" => {sumv}"
        if( ins.mnemonic == "adds" ):
            set_flags_result( possible_flags, sumv, sumlarg, suml, "ZNC" )
            # Carry flag: 1 if result exceeds 32 bits
#            possible_flags.set("C", int( (sumv >> 32) & 1 ))
            # Overflow flag: 1 if signed overflow
            possible_flags.set("V", int( ( (suml ^ sumr) & (suml ^ sumv) ) & 0x80000000 ))
            filtered = possible_flags.subset( { "Z","N","C","V" } )
            extext += f"{ftext} to {filtered}"
    else:
        extext += ftext
        possible_registers.set( ins.arguments[0].register, None )
        ins.arguments[0].argspec = ""

    ins.add_explanation(extext)

    return (possible_registers,possible_flags)

def vt_flow_sub( ins, frame, possible_registers, possible_flags , executes ):
    sublarg, subl, subr = _extract_args_23( ins, possible_registers )

    extext = f"Subtracting {vdb.asm.format_unknown(subl)} and {vdb.asm.format_unknown(subr,'{}')}, storing it in {ins.arguments[0]}"

    ftext = ""
    if( ins.mnemonic == "subs" ):
        possible_flags.unset( [ "N", "Z", "C", "V" ] )
        ftext = ", setting flags"

    if( subl is not None and subr is not None ):
        sumv = subl - subr
        possible_registers.set( ins.arguments[0].register, sumv,origin="flow_sub" )
        extext += f" => {sumv}"
        if( ins.mnemonic == "subs" ):
            set_flags_result( possible_flags, sumv, sublarg, subl, "ZNC" )
            # Carry flag: 1 if result exceeds 32 bits
#            possible_flags.set("C", int( (sumv >> 32) & 1 ))
            # Overflow flag: 1 if signed overflow
            possible_flags.set("V", int( ( (subl ^ subr) & (subl ^ sumv) ) & 0x80000000 ))
            filtered = possible_flags.subset( { "Z","N","C","V" } )
            extext += f"{ftext} to {filtered}"
    else:
        if( ins.mnemonic == "subs" ):
            extext += ftext
        possible_registers.set( ins.arguments[0].register, None )
        ins.arguments[0].argspec = ""

    ins.add_explanation(extext)

    return (possible_registers,possible_flags)

def vt_flow_mov( ins, frame, possible_registers, possible_flags , executes ):
    frm = ins.arguments[1]
    to  = ins.arguments[0]

    frmval,_ = frm.value( possible_registers )
#    possible_registers.dump()
    possible_registers.set( to.register, frmval, origin = "flow_mov" )

    if( vdb.asm.asm_explain.value ):
        if( frm.immediate is not None ):
            frmstr=f"{frm}"
            frmval,_ = frm.value( possible_registers )
            if( frmval is not None ):
                frmstr=f"{frmval:#0x}"
            ins.add_explanation(f"Move immediate value {frmstr} to register {to}")
        else:
            ins.add_explanation(f"Move contents from register {frm} to register {to}")

    return (possible_registers,possible_flags)

def vt_flow_bl( ins, frame, possible_registers, possible_flags , executes ):
    if( ins.next is not None ):
        # LR is not saved by the caller as such even when we correctly return, LR might be different
#        possible_registers.set( "lr", ins.next.address, origin = "flow_bl" )
        ins.add_explanation(f"Branch to {vdb.asm.format_unknown(ins.targets,'{:#0x}')} and put return address {ins.next.address:#0x} in lr register (branch and link)")

    possible_registers.set("r0",None, origin = "flow_bl")
    possible_registers.set("r1",None, origin = "flow_bl")
    possible_registers.set("r2",None, origin = "flow_bl")
    possible_registers.set("r3",None, origin = "flow_bl")
    possible_registers.set("r12",None, origin = "flow_bl")
    possible_registers.set("lr",None, origin = "flow_bl")
    return (possible_registers,possible_flags)

def vt_flow_cb( ins, frame, possible_registers, possible_flags , executes ):
    if( vdb.asm.asm_explain.value ):
        if( ins.conditional_jump ):
            _,_,ex = flag_conditions.get(ins.conditional_suffix,(0,0,ins.conditional_suffix))
            ins.add_explanation(f"Compare and branch on {ex}")
        else:
            ins.add_explanation("Compare and branch unconditionally? that exists?")

    # For ARM Cortex-M, cb is a compare and branch instruction
    # Flags are set based on the compare
    # This is a placeholder for actual flag setting logic
    possible_flags.unset( [ "N", "Z", "C", "V" ] )
    return (possible_registers,possible_flags)

def vt_flow_b( ins, frame, possible_registers, possible_flags , executes ):
    if( vdb.asm.asm_explain.value ):
        if( ins.conditional_jump ):
            _,_,ex = flag_conditions.get(ins.conditional_suffix,"??")
            ins.add_explanation(f"Branch conditionally if {ex}")
        else:
            if( ins.address in ins.targets ):
                ins.add_explanation("Branch unconditionally (infinte loop)")
            else:
                ins.add_explanation("Branch unconditionally")

    if( vdb.asm.annotate_jumps.value ):
        if( ins.conditional_jump ):
            csuf = ins.conditional_suffix
            if( csuf is None ):
                ins.add_extra("Could not extract conditional suffix")

            taken,extrastring = vdb.asm.flag_check( csuf , possible_flags, flag_conditions )
            if( taken is not None ):
                if( taken ):
                    ins.add_extra(f"branch taken" + extrastring)
                else:
                    ins.add_extra(f"branch NOT taken" + extrastring)
            else:
                ins.add_extra(f"Unhandled conditional branch: {extrastring}")

    return (possible_registers,possible_flags)

def vt_flow_push( ins, frame, possible_registers, possible_flags , executes ):
    vl,rname,_ = possible_registers.get("sp")
    if( vl is not None ):
        nargs = len(ins.args)
        vl = int(vl) - nargs*( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_push")
    else:
        possible_registers.set(rname,None,origin = "flow_push")

    for a in ins.arguments:
        a.target = False
        a.reset_argspec()
    ins.add_explanation(f"Push registers {', '.join(ins.args)} to the stack")

    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_pop( ins, frame, possible_registers, possible_flags , executes ):
    vl,rname,_ = possible_registers.get("sp")
    if( vl is not None ):
        nargs = len(ins.args)
        vl = int(vl) + nargs*( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_pop")
    else:
        possible_registers.set(rname,None,origin = "flow_pop")

    for a in ins.arguments:
        a.target = False
        a.reset_argspec()
        possible_registers.set( a.register, None )
    ins.add_explanation(f"Pops registers {', '.join(ins.args)} from the stack")

    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_cpsid( ins, frame, possible_registers, possible_flags , executes ):
    arg = str(ins.arguments[0])
    match arg:
        case "i":
            ins.add_explanation("Disables interrupts by setting PRIMASK")
        case "f":
            ins.add_explanation("Sets FAULTMASK")
        case _:
            ins.add_explanation(f"Unknown mask flag {arg}")
    # XXX Change the mask registers? Guess the exact bits depend on the arch?
    return ( possible_registers, possible_flags )

def vt_flow_cpsie( ins, frame, possible_registers, possible_flags , executes ):
    arg = str(ins.arguments[0])
    match arg:
        case "i":
            ins.add_explanation("Enables interrupts by clearing PRIMASK")
        case "f":
            ins.add_explanation("Clears FAULTMASK")
        case _:
            ins.add_explanation(f"Unknown mask flag {arg}")
    # XXX Change the mask registers? Guess the exact bits depend on the arch?
    return ( possible_registers, possible_flags )

def vt_flow_ldm( ins, frame, possible_registers, possible_flags , executes ):
    mnem = ins.mnemonic.removesuffix(".w")
    variant = mnem[3:]

    src = ins.arguments[0].register
    regs = []
    for r in ins.arguments[1:]:
        regs.append(r.register)
        possible_registers.set(r.register,None)
    regs = ",".join(regs)

    ins.add_explanation(f"Loads registers {regs} from {src}")
    if "pc" in regs:
        ins.add_explanation("pc is in registers, this acts like a branch")
    # XXX Do the actual functional implementation of loading
    # handle IA/FD versions properly
    return ( possible_registers, possible_flags )

def current_flags( frame ):
    for cand in [ "fpscr", "xpsr", "xPSR", "apsr" ]:
        try:
            return vdb.asm.current_flags(frame,cand)
        except:
            return vdb.asm.current_flags(frame,"apsr")

# Computes a string for comparison with assembler load arguments to determine a possible load of a local variable
# without knowing the register value
def var_expression( offset, register ):
    ret = f"[{register}, #{offset}]"
#    print(f"var expression {ret=}")
    return ret
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
