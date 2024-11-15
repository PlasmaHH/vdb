#!/usr/bin/env python3

import re
import gdb
import vdb.asm

name = "arm"

return_mnemonics = set ([])
call_mnemonics = set(["bl", "blx"])
prefixes = set([ ])
base_pointer = "r11" # can be different
stack_pointer = "sp" # msp/psp should be handled by gdb itself

# ( use_or, list_of_flags )
flag_conditions = {
        "eq"  : ( False, [ ( "Z", 1, True ) ] ),
        "ne"  : ( False, [ ( "Z", 0, True ) ] ),
        "cs"  : ( False, [ ( "C", 1, True ) ] ),
        "hs"  : ( False, [ ( "C", 1, True ) ] ),
        "cc"  : ( False, [ ( "C", 0, True ) ] ),
        "lo"  : ( False, [ ( "C", 0, True ) ] ),
        "mi"  : ( False, [ ( "N", 1, True ) ] ),
        "pl"  : ( False, [ ( "N", 0, True ) ] ),
        "vs"  : ( False, [ ( "V", 1, True ) ] ),
        "vc"  : ( False, [ ( "V", 0, True ) ] ),
        "hi"  : ( False, [ ( "C", 1, True ), ( "Z", 0, True ) ] ),
        "ls"  : ( True,  [ ( "C", 0, True ), ( "Z", 1, True ) ] ),
        "ge"  : ( False, [ ( "N", "V", True ) ] ),
        "lt"  : ( False, [ ( "N", "V", False ) ] ),
        "gt"  : ( False, [ ( "Z", 0, True ), ( "N", "V", True ) ] ),
        "le"  : ( True,  [ ( "Z", 1, True ), ( "N", "V", False ) ] ),
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

def extract_conditional( mnemonic ):
    if( mnemonic.endswith(".n") or mnemonic.endswith(".w" ) ):
        mnemonic = mnemonic[:-2]
    l1 = mnemonic[-1:]
    if( l1 in conditional_suffixes ):
        return l1

    l2 = mnemonic[-2:]
    if( l2 in conditional_suffixes ):
        return l2

    return None

# XXX This is just copied from x86, we need to go through things and add them here
_arm_class_res = [
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
    @vdb.overrides
    def parse( self, arg ):
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

        return ret



class instruction( vdb.asm.instruction_base ):

    class_res = vdb.asm.instruction_base.compile_class_res( _arm_class_res )
    class_cache = {}
    last_cmp_immediate = 1

    def __init__( self, line, m, oldins ):
        super().__init__()
        self.parse(line,m,oldins)

    @vdb.overrides
    def parse( self, line, m, oldins ):
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
                if( arg[0] == "[" ):
                    arg = ",".join(args)
                    args = []
                else:
                    del args[0]
                aarg = asm_arg(target,arg)
#                print(f"{aarg=}")
                target = False
                self.args.append(arg)
                self.arguments.append(aarg)

        # reassemble to check the string for consistency
        reargs = []
        for a in self.arguments:
            astr = ""
            if( a.list_start ):
                astr = "{"
            astr += str(a)
            if( a.list_end ):
                astr += "}"
            reargs.append(astr)
        reargs = ", ".join(reargs)

        if( reargs != oargs.strip() ):
            print("CHECK OF WHOLE EXPRESION FAILED")
            print("oargs  = '%s'" % (oargs,) )
            print("reargs = '%s'" % (reargs,) )
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
        return self

# for the "according to the result" flags
def set_flags_result( flag_set, result, arg = None, val = None ):
    #  So far this is a copy of x86 and obviously wrong. Before we can do anything we need to figure out a good way to
    #  make vdb.register more architecture independent as things like the register size are not handled that way yet.
#    print(f"set_flags_result( {flag_set}, {result}, {arg} )")
#        vdb.util.bark() # print("BARK")
#    print(f"{arg.bitsize=}")
    if( result < 0 ):
        if( arg is not None and ( bs := arg.bitsize ) is not None ):
            result += (1 << bs)

    flag_set.set("Z", int(result == 0) )
    if( arg is not None and ( bs := arg.bitsize ) is not None ):
        sbit = ( 1 << (bs-1) )
        flag_set.set("N", int( (result & sbit) != 0  ))
        flag_set.set("V", int( (result & sbit) != (val & sbit) ) )

def vt_flow_ldr( ins, frame, possible_registers, possible_flags ):
    val,addr = ins.arguments[1].value( possible_registers )
    possible_registers.set( ins.arguments[0].register, val ,origin="flow_ldr" )
    return (possible_registers,possible_flags)

def vt_flow_str( ins, frame, possible_registers, possible_flags ):
    val,addr = ins.arguments[0].value( possible_registers )
    possible_registers.set( ins.arguments[1].register, val ,origin="flow_str" )
    return (possible_registers,possible_flags)

def vt_flow_add( ins, frame, possible_registers, possible_flags ):
    if( len(ins.arguments) == 2 ):
        sumlarg = ins.arguments[0]
        suml,_ = ins.arguments[0].value( possible_registers )
        sumr,_ = ins.arguments[1].value( possible_registers )
    else: # 3
        sumlarg = ins.arguments[1]
        suml,_ = ins.arguments[1].value( possible_registers )
        sumr,_ = ins.arguments[2].value( possible_registers )

    extext = f"Adding {suml} and {sumr}, storing it in {ins.arguments[0]}"

    if( ins.mnemonic == "adds" ):
        possible_flags.unset( [ "N", "Z", "C", "V" ] )
        extext += ", setting flags"

    if( suml is not None and sumr is not None ):
        sumv = suml + sumr
        possible_registers.set( ins.arguments[0].register, sumv,origin="flow_add" )
        if( ins.mnemonic == "adds" ):
            set_flags_result( possible_flags, sumv, sumlarg, suml )
            possible_flags.set( "C", int(sumv > sumr) )
            filtered = possible_flags.subset( { "Z","N","C","V" } )
            extext += f" to {filtered}"
    else:
        possible_registers.set( ins.arguments[0].register, None )
        ins.arguments[0].argspec = ""

    if( vdb.asm.asm_explain.value ):
        ins.add_explanation(extext)

    return (possible_registers,possible_flags)

def vt_flow_mov( ins, frame, possible_registers, possible_flags ):
    frm = ins.arguments[1]
    to  = ins.arguments[0]

    frmval,_ = frm.value( possible_registers )
    possible_registers.set( to.register, frmval )

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

def vt_flow_bl( ins, frame, possible_registers, possible_flags ):


    if( ins.next is not None ):
        possible_registers.set( "lr", ins.next.address, origin = "flow_bl" )
        if( vdb.asm.asm_explain.value ):
            ins.add_explanation(f"Branch to {ins.targets} and put return address {ins.next.address:#0x} in lr register (branch and link)")
    return (possible_registers,possible_flags)

def vt_flow_b( ins, frame, possible_registers, possible_flags ):
    if( vdb.asm.asm_explain.value ):
        if( ins.conditional_jump ):
            ins.add_explanation("Branch conditionally")
        else:
            ins.add_explanation("Branch unconditionally")

    if( vdb.asm.annotate_jumps.value ):
        if( ins.conditional_jump ):
            csuf = extract_conditional( ins.mnemonic )
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

#    taken,extrastring = vdb.asm.flag_check( mnemonic, possible_flags, jconditions )
#    ins.add_extra("MNE " + str(ins.mnemonic))
#    ins.add_extra("NEXT " + str(ins.next))
#    ins.add_extra("TARGETS " + str(ins.targets))
#    ins.add_extra("FLAGS " + str(possible_flags))

    return (possible_registers,possible_flags)

def vt_flow_push( ins, frame, possible_registers, possible_flags ):
    vl,rname,_ = possible_registers.get("sp")
    if( vl is not None ):
        nargs = len(ins.args)
        vl = int(vl) - nargs*( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_push")
    else:
        possible_registers.set(rname,None)

    for a in ins.arguments:
        a.target = False
        a.reset_argspec()
    ins.add_explanation(f"Push registers {{{', '.join(ins.args)}}} to the stack")

    # no flags affected
    return ( possible_registers, possible_flags )


def current_flags( frame ):
    return vdb.asm.current_flags(frame,"fpscr")



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
