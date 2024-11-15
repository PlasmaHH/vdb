#!/usr/bin/env python3

import re
import sys

import gdb

import vdb.asm

name = "x86"

call_preserved_registers = [ "rbx", "rsp", "rbp", "r12", "r13", "r14", "r15" ]

jaliases = {
        "jae"  : "jnb",
        "jbe"  : "jna",
        "jc"   : "jb",
        "jnae" : "jb",
        "jnbe" : "ja",
        "jnc"  : "jnb",
        "jnge" : "jl",
        "jng"  : "jle",
        "jnle" : "jg",
        "jnl"  : "jge",
        "jpe"  : "jp",
        "jpo"  : "jnp",
        "jz"   : "je",
        }

# FLAG, FLAG, bool => (FLAG == FLAG) == bool

jconditions = {
        "e"  : ( False, [ ( "ZF", 1, True ) ] ),
        "ne" : ( False, [ ( "ZF", 0, True ) ] ),
        "b"  : ( False, [ ( "CF", 1, True ) ] ),
        "nb" : ( False, [ ( "CF", 0, True ) ] ),
        "a"  : ( False, [ ( "ZF", 0, True ), ( "CF", 0, True ) ] ),
        "na" : ( True,  [ ( "CF", 1, True ), ( "ZF", 1, True ) ] ),
        "l"  : ( False, [ ( "SF","OF", False ) ] ),
        "ge" : ( False, [ ( "SF","OF", True ) ] ),
        "le" : ( True,  [ ( "ZF", 1, True ), ( "SF","OF", False ) ] ),
        "g"  : ( False, [ ( "ZF", 0, True ), ( "SF","OF", True ) ] ),
        "p"  : ( False, [ ( "PF", 1, True ) ] ),
        "np" : ( False, [ ( "PF", 0, True ) ] ),

        } # All others not supported yet due to no support for these flags yet

prefixes = set([ "rep","repe","repz","repne","repnz", "lock", "bnd", "cs", "ss", "ds", "es", "fs", "gs", "notrack", "data16" ])
return_mnemonics = set (["ret","retq","iret"])
conditional_jump_mnemonics = set([ "jo", "jno", "js", "jns", "je", "jz", "jne", "jnz", "jb", "jnae", "jc", "jnb","jae","jnc","jbe","jna","ja","jnbe","jl","jng","jge","jnl","jle","jng","jg","jnle","jp","jnle","jp","jpe","jnp","jpo","jcxz","jecxz" ])
unconditional_jump_mnemonics = set([ "jmp", "jmpq" ] )
call_mnemonics = set(["call","callq","int"])

_x86_class_res = [
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
        ]

# Should arch setup change these? A module getting a "setup" call for the flavor?
base_pointer = "rbp" # XXX what for 32bit?
stack_pointer = "rsp"
argument_registers = [ "rdi", "rsi", "rdx", "rcx", "r8", "r9" ]

class asm_arg(vdb.asm.asm_arg_base):

    @vdb.overrides
    def parse( self, arg ):
#        vdb.util.bark() # print("BARK")
#        print("arg = '%s'" % (arg,) )
        oarg = arg
        if( arg.find(":") != -1 ):
            pf = arg.split(":")
            arg = pf[1]
            self.prefix = pf[0][1:]
#        print("self.prefix = '%s'" % (self.prefix,) )
#        print("arg = '%s'" % (arg,) )

        if( arg[0] == "*" ):
            self.asterisk = True
            arg = arg[1:]

        if( arg[-1] == ")" ):
            self.dereference = True
            if( arg[0] == "(" ):
                arg = arg[1:-1]
            else:
                argv = arg.split("(")
#                print("argv = '%s'" % (argv,) )
                po = argv[0]
#                print("po = '%s'" % (po,) )
                if( po[0] == "%" ):
                    if( po[-1] == ":" ):
                        self.prefix = po[1:-1]
                else:
                    self.offset = vdb.util.rxint(po)
#                    print("self.offset = '%s'" % (self.offset,) )
                arg = argv[1][:-1]
#                print("arg = '%s'" % (arg,) )
                marg = arg.split(",")
#                print("marg = '%s'" % (marg,) )
                if( len(marg) == 2 ):
                    self._check(oarg)
                elif( len(marg) == 3):
                    if( len(marg[0]) > 0 ):
                        self.add_register = marg[0][1:]
#                        print("self.add_register = '%s'" % (self.add_register,) )
                    self.register = marg[1][1:]
                    self.multiplier = vdb.util.rxint(marg[2])
                    self._check(oarg)
                    return

        if( arg[0] == "%" ):
            self.register = arg[1:]
#            print("self.register = '%s'" % (self.register,) )

        if( arg[0] == "$" ):
            if( arg.startswith("$0x") ):
                self.immediate_hex = True
            self.immediate = vdb.util.rxint( arg[1:] )

        if( arg.startswith("0x") ):
            self.jmp_target = vdb.util.rxint( arg )
#        print("self.jmp_target = '%s'" % (self.jmp_target,) )
        self._check(oarg)

    def __str__( self ):
        ret = ""
        if( self.asterisk ):
            ret +=  "*"
        if( self.prefix is not None ):
            ret += f"%{self.prefix}:"
        if( self.offset is not None ):
            ret += f"{self.offset:#0x}"
        if( self.dereference ):
            ret += "("
            if( self.multiplier is not None ):
                if( self.add_register is not None ):
                    ret += "%" + self.add_register
                ret += ","
            ret += "%" + self.register
            if( self.multiplier is not None ):
                ret += f",{self.multiplier}"
            ret += ")"
        elif( self.register is not None ):
            ret += "%" + self.register
        if( self.immediate is not None ):
            if( self.immediate_hex ):
                ret += f"${self.immediate:#0x}"
            else:
                ret += f"${self.immediate}"
        if( self.jmp_target is not None ):
            ret += f"{self.jmp_target:#0x}"
        return ret

class instruction( vdb.asm.instruction_base ):

    class_res = vdb.asm.instruction_base.compile_class_res( _x86_class_res )
    class_cache = {}


    # line: the assembler text line
    # m: the match of the linere regular expression
    def __init__( self, line, m, oldins ):
        super().__init__()
        self.parse(line,m,oldins)

    jmpre = re.compile("^\*(0x[0-9a-fA-F]*)\(.*")
    last_cmp_immediate = 1

    @vdb.overrides
    def parse( self, line, m, oldins ) -> "instruction":
#        print(f"parse( {line=}, {m=}, {oldins=} )")
        tokens = self.parse_common( line, m, oldins )

#        print("tokens = '%s'" % tokens )
        # the dissamble version without <line+>

        xtokens = []
#            print("tokens = '%s'" % tokens )
        # This pastes the next token to the previous one when it ends with a , as this always means they belong together
        while len(tokens) > 0:
            tok = tokens[0]
            if( len(xtokens) > 0 and xtokens[-1].endswith(",") ):
                xtokens[-1] += tok
            else:
                xtokens.append(tok)
            tokens = tokens[1:]
#        print("xtokens = '%s'" % xtokens )
        tokens = xtokens

        tpos = 0
        ibytes = []
#            print("tpos = '%s'" % (tpos,) )
#            print("tokens = '%s'" % (tokens,) )
        # Different asm dialects have different ways to show the bytes, x86 shows them in as single bytes with spaces
        # XXX When doing arm check if we can have a function and just pass the regex
        while( tpos < len(tokens) ):
            tok = tokens[tpos]
            if( self.bytere.match(tok) ):
#                print(f"bytes: {tok}")
                ibytes.append( tok )
                tpos += 1
            else:
                break
#        print("ibytes= '%s'" % (ibytes,) )
#        print(f"{tpos=}")
        self.bytes = ibytes

        tokens = tokens[tpos:]
#        print(f"{tokens=}")
        # Now there should be the instruction

        tpos = 0
        # instruction is menmonic or prefix + mnemonic, easiest way is to know about all prefixes and check if its one
        while( tokens[tpos] in prefixes ):
            self.prefixes.append( tokens[tpos] )
            tpos += 1
        # Next the mnemonic
        self.mnemonic = tokens[tpos]
        tpos += 1
        # After the mnemonic there is possibly some arguments (there are mnemonics without arguments)
        if( len(tokens) > tpos ):
            self.args = vdb.asm.split_args(tokens[tpos])
            self.args_string = tokens[tpos]
            tpos += 1
#        print(f"{self.args_string=}")
#        print(f"{self.args=}")

        # Parse the arguments into argument objects
        if( self.args is not None and len(self.arguments) == 0 ):
            # mov $0x18,%edi means load 0x18 into %edi, thus the second is the target. For more the last one is always
            # marked.
            for a in self.args:
                self.arguments.append( asm_arg(False,a) )
            if( len(self.arguments) > 0 ):
                self.arguments[-1].target = True

        if( self.mnemonic in return_mnemonics ):
            self.return_ = True

        # For comparison mnemonics
        if( self.mnemonic.startswith("cmp") ):
            m = re.search(self.cmpre,self.args_string)
#                print("m = '%s'" % m )
            if( m is not None ):
                cmparg = m.group(1)
                instruction.last_cmp_immediate = vdb.util.xint(cmparg)

        # Any jump or call?
        if( self.mnemonic in conditional_jump_mnemonics ):
            self.conditional_jump = True
            self.jump = True
        elif( self.mnemonic in call_mnemonics ):
            self.call = True
            self.jump = True
        elif( self.mnemonic in unconditional_jump_mnemonics ):
            self.unconditional_jump = True
            self.jump = True



        # After the argument there is still something. It grew over the years how we handle that, but from now on lets
        # try to unify things.
        # for x86 gdb seems to output:
        # - "# 0xdeadbeef" or "# 0xdeadbeef <symbol>" (or <symbol+offset> for functions) for arguments that use # %rip/%eip
        # - <symbol> or <symbol+offset> for jump/call instructions
        if( len(tokens) > tpos ):
#                print("tokens = '%s'" % (tokens,) )
#                print("tokens[tpos] = '%s'" % tokens[tpos] )
            if( tokens[tpos] == "#" ):
                self.reference.append( " ".join(tokens[tpos+1:]) )
                self.raw_reference = " ".join(tokens[tpos+1:])
#                    print("self.reference = '%s'" % self.reference )
            elif( tokens[tpos].startswith("<") ):
                if( not self.jump ):
                    print(f"{line=} has jump target annotation but was not detected any jumping/calling instruction previously")
#                    self.conditional_jump = True
#                    print("TARGET ADD '%s'" % tokens[tpos-1])
                self.target_name = " ".join(tokens[tpos:])
                self.raw_target = " ".join(tokens[tpos:]) # And never change it anymore
            else:
                print(f"{line=} has unknown annotation")
#            elif( self.mnemonic in conditional_jump_mnemonics ):

        # What kind of target do we jump to?
        if( self.jump ):
            # Check if this is maybe just an address
            try:
                self.targets.add(vdb.util.xint(self.args[0]))
            except ValueError:
                pass
#            print(f"{self.jmpre}.search({self.args[0]})")
            # Check if it some kind of dereference (starts with *)
            m = self.jmpre.search(self.args[0])
#            print(f"{m=}")

            if( m is not None ):
                a = self.arguments[0]
#                print(f"{a=}")
                # Pretend these are the only registers known is the various versions of ip/pc
                next_ip = self.address + len(self.bytes) # on x86 the current rip value is already pointing to the next instruction

                pc_registers = vdb.asm.register_set()
                pc_registers.set( "rip" , next_ip)
                pc_registers.set( "eip" , next_ip)
                pc_registers.set( "ip" , next_ip)
                pc_registers.set( "pc" , next_ip)
                # If this is of the usual type of "jmp *0xdeadbeef(%rip)" then this gets the address to jump to
                ival,iaddr = a.value(pc_registers)

                # Since its dereferenced, its the value we are after
                if( ival is not None ):
                    self.targets.add( vdb.util.xint(ival) )
#                print(f"ival = {int(ival):#0x}" if ival is not None else "ival = None")
#                print(f"iaddr = {int(iaddr):#0x}" if iaddr is not None else "iaddr = None")
                table = m.group(1)
                cnt = 0
#                print(f"{table=}")
                # If its not pc based, it likely is based on another register. It usually some index into a table.
                # XXX Find a testcase for this
                # If its just of the form "jmp *rax" we can't do much about it here
                # XXX In the vt_flow part, when the register value is known, add the target
                while True:
                    try:
                        jmpval = gdb.parse_and_eval(f"*((void**){table}+{cnt})")
#                        print("jmpval = '%s'" % jmpval )
                        if( jmpval == 0 ):
                            break
                    except gdb.MemoryError:
                        break
                    # This is a little hack, usually the last cmp governs the default case of a switch/case computed
                    # jump
                    if( cnt > instruction.last_cmp_immediate ):
                        break
#                        print("last_cmp_immediate = '%s'" % last_cmp_immediate )
                    self.targets.add(int(jmpval))
                    cnt += 1
                self.reference.append( f"{len(self.targets)} computed jump targets " ) # + str(self.targets)
#                    print("jmpval = '%s'" % jmpval )
#                    print("m = '%s'" % m )
#                    print("m.group(1) = '%s'" % m.group(1) )
#                    print("self = '%s'" % self )
            else:
                try:
                    self.targets.add(vdb.util.xint(tokens[tpos-1]))
                except:
                    pass

        if( self.jump and len(self.targets) == 0 ):
            print(f"WARNING {line=} has no targets")

        self.iclass = self.mnemonic_class( self.mnemonic )

#            print("tokens = '%s'" % tokens[tpos:] )

        # Previous insstruction "falls through" to this one, except:
        # - its a ret(urn)
        # - its an unconditional jump
        if( oldins is not None and not oldins.return_ and not oldins.unconditional_jump ):
            oldins.next = self
            self.previous = oldins
        oldins = self
        return self

bit_counts = bytes(bin(x).count("1") for x in range(256))  
# for the "according to the result" flags
def set_flags_result( flag_set, result, arg = None ):
#        vdb.util.bark() # print("BARK")
    if( result < 0 ):
        if( arg is not None and ( bs := arg.bitsize ) is not None ):
            result += (1 << bs)

#        print("result = '%s'" % (result,) )
    lsb = result & 0xFF
    bcnt = bit_counts[lsb]
    flag_set.set("PF", int( bcnt & 1 == 0 ) )
    flag_set.set("ZF", int(result == 0) )
    if( arg is not None and ( bs := arg.bitsize ) is not None ):
        sbit = ( 1 << (bs-1) )
        flag_set.set("SF", int( (result & sbit) != 0  ))
        mask = ( 1 << bs ) - 1
#            print(f"mask = {int(mask):#0x}")
#            print("bs = '%s'" % (bs,) )
        r = result & mask
        # XXX really not sure about this one in case of signs and all
        flag_set.set("OF", int(r != result) )
        flag_set.set("CF", int(r != result) )

def vt_flow_j( ins, frame, possible_registers, possible_flags ):
    if( not vdb.asm.annotate_jumps.value ):
        return (possible_registers,possible_flags)

    mnemonic = jaliases.get( ins.mnemonic, ins.mnemonic )
    mnemonic = mnemonic[1:] # cut of the "j"

    taken,extrastring = vdb.asm.flag_check( mnemonic, possible_flags, jconditions )
    if( taken is not None ):
        if( taken ):
            ins.add_extra(f"Jump taken" + extrastring)
        else:
            ins.add_extra(f"Jump NOT taken" + extrastring)
    else:
        ins.add_extra(f"Unhandled conditional jump: {extrastring}")
#        print("extrastring = '%s'" % (extrastring,) )
#        print("possible_flags = '%s'" % (possible_flags,) )

    return ( possible_registers, possible_flags )

def vt_flow_push( ins, frame, possible_registers, possible_flags ):
    vl,rname,_ = possible_registers.get("rsp")
    oldvl=vl
    if( vl is not None ):
        vl = int(vl) - ( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_push")

    if( vdb.asm.vdb.asm.asm_explain.value ):
        pval,_ = ins.arguments[0].value(possible_registers)
        if( pval is not None ):
            vls=f"({pval:#0x})"
        else:
            vls=""

        ex=f"Pushes value of {ins.args[0]}{vls} to the stack"
        if( oldvl is not None ):
            ex += f" @{oldvl:#0x}"
        ins.add_explanation(ex)
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_pop( ins, frame, possible_registers, possible_flags ):
    vl,rname,_ = possible_registers.get("rsp")
    if( vl is not None ):
        vl = int(vl) + ( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_pop")

    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_mov( ins, frame, possible_registers, possible_flags ):
    if( vdb.asm.debug_all(ins) ):
        print()
        vdb.util.bark() # print("BARK")


    if( vdb.asm.debug_all(ins) ):
        print("ins = '%s'" % (ins,) )
        print("ins.mnemonic = '%s'" % (ins.mnemonic,) )
        print("ins.args_string = '%s'" % (ins.args_string,) )
        print("ins.args = '%s'" % (ins.args,) )
        print("ins.arguments = '%s'" % (ins.arguments,) )

        print("possible_registers = '%s'" % (possible_registers,) )
        print("ins.possible_in_register_sets = '%s'" % (ins.possible_in_register_sets,) )
        print("ins.possible_out_register_sets = '%s'" % (ins.possible_out_register_sets,) )

    frm = ins.arguments[0]
    to  = ins.arguments[1]

    frmval,_ = frm.value( possible_registers )
    toval,toloc = to.value( possible_registers )
    # the new register value will be...
    if( not to.dereference ):
        # We ignore any (initial frame setup) move of rsp to rbp to keep the value intact
        # XXX if we do it that way we can also from here on (backwards?) assume rsp=rbp. (likely just after it we
        # sub something from rsp, we should support basic calculations too)
        if( frm.register != "rsp" or to.register != "rbp" ):
            possible_registers.set( to.register, frmval,origin="flow_mov" )
        # TODO We need to do this anyways when we are at a position before that move
        # TODO this all seems fishy, we need a testcase for when this matters. maybe only in backpropagation?
        possible_registers.set( to.register, frmval,origin="flow_mov" )
#        if( frm.register == "rsp" and to.register == "rbp" ):
#            if( toval is not None ):
#                possible_registers.set( "rsp", toval )
    to.specfilter("=")
    to.specfilter("%")

    if( vdb.asm.debug_all(ins) ):
        print("possible_registers = '%s'" % (possible_registers,) )
        print("ins.possible_in_register_sets = '%s'" % (ins.possible_in_register_sets,) )
        print("ins.possible_out_register_sets = '%s'" % (ins.possible_out_register_sets,) )


    if( vdb.asm.asm_explain.value ):
        frmstr=""
        if( frmval is not None ):
            frmstr=f"({frmval:#0x})"
        ex = ""
        if( frm.immediate is not None ):
            ex += f"Store immediate value {frm} "
        elif( frm.dereference ):
            ex += f"Store memory value at {frm}{frmstr} "
        else:
            ex += f"Store register value of {frm}{frmstr} "

        if( to.dereference ):
            memtgt=""
            if( toloc is not None ):
                memtgt=f"({toloc:#0x})"
            ex += f"in memory location {to}{memtgt}"
        else:
            ex += f"in register {to}"

        ins.add_explanation(ex)

    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_jmp( ins, frame, possible_registers, possible_flags ):
    # XXX If target of the jmp is dynamic we might want to (re)calculate it here
    # no flags affected
    tgtv,_ = ins.arguments[0].value( possible_registers )
    if( tgtv is not None ):
        ins.targets.add(tgtv)
    return ( possible_registers, possible_flags )

def vt_flow_shl( ins, frame, possible_registers, possible_flags ):
    shifts,_ = ins.arguments[0].value( possible_registers )
    tgtv,_ = ins.arguments[1].value( possible_registers )

    if( tgtv is not None ):
        nv = tgtv << shifts
        # XXX CF setting is not handled (as it depends on the size of the used register)
        possible_registers.set( ins.arguments[1].register, nv, origin="flow_shl" )
    return ( possible_registers, possible_flags )

def vt_flow_shr( ins, frame, possible_registers, possible_flags ):
    shifts,_ = ins.arguments[0].value( possible_registers )
    tgtv,_ = ins.arguments[1].value( possible_registers )

    if( tgtv is not None and shifts is not None ):
        nv = tgtv >> shifts
        # XXX Sign extend?
        # XXX CF setting is not handled (as it depends on the size of the used register)
        possible_registers.set( ins.arguments[1].register, nv, origin="flow_shr" )
    return ( possible_registers, possible_flags )


def vt_flow_sub( ins, frame, possible_registers, possible_flags ):
    sub,_ = ins.arguments[0].value( possible_registers )
    tgtv,_ = ins.arguments[1].value( possible_registers )
    possible_flags.unset( [ "CF","OF","SF","ZF","AF","PF"] )
    nv = None
    if( tgtv is not None and sub is not None):
        nv = tgtv - sub
        possible_registers.set( ins.arguments[1].register, nv, origin="flow_sub" )
        set_flags_result( possible_flags, nv, ins.arguments[1] )
        possible_flags.set( "CF", int(tgtv > sub) )
    else:
        ins.arguments[0].argspec = ""

    if( vdb.asm.asm_explain.value ):
        nvs=""
        tvs=""
        if( nv is not None ):
            nvs=f"({nv:#0x})"
        if( tgtv is not None ):
            tvs=f"({tgtv:#0x})"
        ins.add_explanation( f"Subtracts {ins.args[0]} from {ins.args[1]}{tvs} and stores it in {ins.args[1]}{nvs}" )

    return ( possible_registers, possible_flags )


def vt_flow_add( ins, frame, possible_registers, possible_flags ):
    add,_ = ins.arguments[0].value( possible_registers )
    tgtv,_ = ins.arguments[1].value( possible_registers )
    possible_flags.unset( [ "CF","OF","SF","ZF","AF","PF"] )
    if( tgtv is not None and add is not None):
        nv = tgtv + add
        possible_registers.set( ins.arguments[1].register, nv,origin="flow_add" )
        set_flags_result( possible_flags, nv, ins.arguments[1] )
        possible_flags.set( "CF", int(tgtv > add) )
    else:
        possible_registers.set( ins.arguments[1].register, None )
        ins.arguments[0].argspec = ""

    return ( possible_registers, possible_flags )

def vt_flow_test( ins, frame, possible_registers, possible_flags ):
#    print("ins = '%s'" % (ins,) )
    a0,_ = ins.arguments[0].value( possible_registers )
    a1,_ = ins.arguments[1].value( possible_registers )
    if( ins.arguments[0].arg_string != ins.arguments[1].arg_string ):
        ins.arguments[1].argspec += "%"
#    print("a0 = '%s'" % (a0,) )
#    print("a1 = '%s'" % (a1,) )
    possible_flags.unset( [ "SF","ZF","AF","PF"] )
    if( a0 is not None and a1 is not None ):
        t = a0 & a1
        set_flags_result( possible_flags,t,ins.arguments[1])
        # XXX add SF and PF support as soon as some other place needs it
#        ins.possible_flag_sets.append( possible_flags )
    possible_flags.set("OF",0)
    possible_flags.set("CF",0)
    # No changes in registers, so just
    return ( possible_registers, possible_flags )

def explain_xor( ins, v0, v1, t, args ):
    if( len(args) == 2 and args[0].register == args[1].register ):
        ins.add_explanation( f"Performs xor on register {args[0]} with itself, setting it to 0")
    else:
        v0s=""
        v1s=""
        ts =""
        if( v0 is not None ):
            v0s=f"({v0:#0x})"
        if( v1 is not None ):
            v1s=f"({v0:#0x})"
        if( t is not None ):
            ts=f"({t:#0x})"
        if( args[0].dereference ):
            a0loc = "memory location"
        else:
            a0loc = "register"
        if( args[1].dereference ):
            a1loc = "memory location"
        else:
            a1loc = "register"
        ins.add_explanation(f"Performs xor on {a0loc} {args[0]}{v0s} with {a1loc} {args[1]}{v1s} and storing the result in {a1loc} {args[1]}{ts}")


def vt_flow_pxor( ins, frame, possible_registers, possible_flags ):
    args = ins.arguments
    v0=None
    v1=None
    t = None
    if( not args[1].dereference ):
        v0,_ = args[0].value( possible_registers )
        v1,_ = args[1].value( possible_registers )
        if( v0 is not None and v1 is not None ):
            t = v0 ^ v1
            possible_registers.set( args[1].register, t,origin="flow_pxor" )
        else: # no idea about the outcome, don't set it
            possible_registers.set( args[1].register, None )
        if( len(args) == 2 ):
            # xor zeroeing out a register
            if( args[0].register == args[1].register ):
                possible_registers.set( args[1].register ,0, origin="flow_pxor")
                args[0].specfilter("%")

    if( vdb.asm.asm_explain.value ):
        explain_xor(ins,v0,v1,t,args)

    return ( possible_registers, possible_flags )


def vt_flow_xor( ins, frame, possible_registers, possible_flags ):
    args = ins.arguments

    v0=None
    v1=None
    t = None
    # We only do it when not writing to memory
    possible_flags.unset( [ "SF","ZF","AF","PF"] )
    if( not args[1].dereference ):
        v0,_ = args[0].value( possible_registers )
        v1,_ = args[1].value( possible_registers )
        if( v0 is not None and v1 is not None ):
            t = v0 ^ v1
            possible_registers.set( args[1].register, t,origin="flow_xor" )
            set_flags_result( possible_flags,t)
        else: # no idea about the outcome, don't set it
            possible_registers.set( args[1].register, None )
        if( len(args) == 2 ):
            # xor zeroeing out a register
            if( args[0].register == args[1].register ):
                possible_registers.set( args[1].register ,0,origin="flow_xor")
                set_flags_result( possible_flags,0)
                args[0].specfilter(None)

    possible_flags.set("OF",0)
    possible_flags.set("CF",0)

    if( vdb.asm.asm_explain.value ):
        explain_xor(ins,v0,v1,t,args)

    return ( possible_registers, possible_flags )

def vt_flow_and( ins, frame, possible_registers, possible_flags ):
    args = ins.arguments

    # We only do it when not writing to memory
    possible_flags.unset( [ "SF","ZF","AF","PF"] )
    if( not args[1].dereference ):
        v0,_ = args[0].value( possible_registers )
        v1,_ = args[1].value( possible_registers )
        if( v0 is not None and v1 is not None ):
            t = v0 & v1
            possible_registers.set( args[1].register, t ,origin="flow_and")
            set_flags_result( possible_flags,t)
        else: # no idea about the outcome, don't set it
            possible_registers.set( args[1].register, None )

    possible_flags.set("OF",0)
    possible_flags.set("CF",0)
    return ( possible_registers, possible_flags )

def _vt_flow_cmovcc( flags, ins, frame, possible_registers, possible_flags ):
    tgt = ins.arguments[1]
    src = ins.arguments[1]
    src_val,_,_ = possible_registers.get( src.register )
    extrastring = ""
    msgstring = ""
    for flag,val in flags.items():
        flag_value = possible_flags.get(flag)
        # XXX Refactor this to use the same thing as the  jumps as the suffixes are the same
        # No value known? Can't tell if we execute
        if( flag_value is None ):
            msgstring = f"{flag} is unknown"
            possible_registers.set( tgt.register, None )
            break
        # Not the expected one, don't copy
        if( flag_value != val ):
            msgstring = "not moved"
            extrastring += f",{flag}[{flag_value}] != {val}"
            break
        extrastring += f",{flag}[{flag_value}] == {val}"
    else: # went through all, they seem to match
        if( src_val is None ):
            # src not known so tgt is unknown now to
            possible_registers.set( tgt.register, None )
            msgstring = "would move, srcval unknown"
        else:
            possible_registers.set( tgt.register,  src_val, "flow_cmov" )
            msgstring = "moved"


    if( vdb.asm.annotate_cmove.value ):
        ins.add_extra( msgstring + extrastring )

    return ( possible_registers, possible_flags )

def vt_flow_cmove( ins, frame, possible_registers, possible_flags ):
    # no flags affected
    return _vt_flow_cmovcc( { "ZF" : 1 }, ins, frame, possible_registers, possible_flags )

def vt_flow_endbr64( ins, frame, possible_registers, possible_flags ):
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_nop( ins, frame, possible_registers, possible_flags ):
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_hlt( ins, frame, possible_registers, possible_flags ):
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_movz( ins, frame, possible_registers, possible_flags ):
    # XXX Not implemented
    ins.unhandled = True
    return ( possible_registers, possible_flags )

def vt_flow_movs( ins, frame, possible_registers, possible_flags ):
    # XXX Not implemented
    ins.unhandled = True
    return ( possible_registers, possible_flags )

def vt_flow_neg( ins, frame, possible_registers, possible_flags ):
    ins.arguments[0].target = True
    val,_ = ins.arguments[0].value(  possible_registers )
    possible_flags.clear() # until we properly support them its better to not leave wrongs in
    possible_flags.unset( [ "CF","OF","SF","ZF","AF","PF"] )
    if( val is not None ):
        val = 0 - val
        possible_registers.set( ins.arguments[0].register, val ,origin="flow_neg")
        if( val == 0 ):
            possible_flags.set("CF",0)
        else:
            possible_flags.set("CF",1)
    else:
        possible_flags.unset("CF")
    return ( possible_registers, possible_flags )

def vt_flow_lea( ins, frame, possible_registers, possible_flags ):
#    print("ins.line = '%s'" % (ins.line,) )
    a0 = ins.arguments[0]
    a1 = ins.arguments[1]

    # the value is unintresting, lea only computes the address
    a0.specfilter("=")

    fv,fa = a0.value(possible_registers)
    possible_registers.set( a1.register, None )
    if( fa is not None ):
        if( not a1.dereference and a1.register is not None):
            possible_registers.set( a1.register, fa ,origin="flow_lea")

    # no flags affected
    return ( possible_registers, possible_flags )

# XXX sub does exactly the same with the flags, maybe combine into a common function
def vt_flow_cmp( ins, frame, possible_registers, possible_flags ):
    a0 = ins.arguments[0]
    a1 = ins.arguments[1]

    a1.argspec += "=" # we compare values and want to see the involved ones

    v0 = a0.value(possible_registers)[0]
    v1 = a1.value(possible_registers)[0]
#    print("v0 = '%s'" % (v0,) )
#    print("v1 = '%s'" % (v1,) )
    possible_flags.unset( [ "CF","OF","SF","ZF","AF","PF"] )
    if( v0 is not None and v1 is not None ):
        t = v1-v0
        possible_flags.set( "ZF", int( v0 == v1 ) )
        possible_flags.set( "CF", int( v0 > v1 ) ) # XXX revisit for accurate signed/unsigned 32/64 bit stuff (and the other flags)
        set_flags_result( possible_flags, t,a1 )

    return ( possible_registers, possible_flags )

def vt_flow_syscall( ins, frame, possible_registers, possible_flags ):
#            print("possible_registers = '%s'" % (possible_registers,) )
#            ins._gen_extra()
    rax,_,_ = possible_registers.get("rax",None)
    if( rax is not None ):
        sc = vdb.asm.get_syscall( rax )
#                    print("rax = '%s'" % (rax,) )
#                    print("sc = '%s'" % (sc,) )
        if( sc is not None ):
            qm = "?"
            if( ins.marked or (ins.next and ins.next.marked) ):
                qm="!"
            ins.add_extra( sc.to_str(possible_registers,qm,frame) )
            possible_registers = sc.clobber(possible_registers)
        else:
            ins.add_extra(f"syscall[{rax}]()")
    possible_flags.clear() # syscall can return whatever
#                    ins.add_extra(f"{possible_registers}")
    return ( possible_registers, possible_flags )

def vt_flow_leave( ins, frame, possible_registers, possible_flags ):
    rbp,_,_ = possible_registers.get("rbp",None)
    if( rbp is not None ):
        possible_registers.set("rsp",rbp,origin="flow_leave")
    # XXX do the "pop rbp" too
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_call( ins, frame, possible_registers, possible_flags ):
    npr = vdb.asm.register_set()
    npr.copy( possible_registers, call_preserved_registers )
    possible_registers = npr

    # For calculated calls/jumps we usually don't have the register available when we are past that point, however when
    # the next one is the marked one, that means we are still within the call, meaning the register should still be the
    # valid one. This is often the case in stacktraces, thus it makes sense to handle it here
    # Nothing else could calculate the target yet, use this as a last resort
#    if( len(ins.targets) == 0 ):
#        ins.add_extra("LAST RESORT CALCULATION FOR TARGET DONE")
    # XXX Turns out this mostly doesn't work since gdb doesn't provide us with the register if its later overwritten,
    # dang
    # Here is the next idea: rsp should be available. Make a backwards flow mechanism too that will recover these
    # values. Be conservative there and break if we are target of something else than the previous instruction?
#        if( ins.next is not None and ins.next.marked ):
#            ins.add_extra("NEXT IS MARKED")
#            arg = ins.arguments[0]
#            ins.add_extra(str(arg))
#            ins.add_extra(str(arg.register))
#            rval = frame.read_register(arg.register)
#            rval = int(rval)
#            ins.add_extra(f"{arg.register} set to {rval}")
#            ins.override_register_set = vdb.asm.register_set()
#            ins.override_register_set.set( arg.register, rval )
##            val = arg.value(frame)
#            ins.add_extra(str(val))
    # no flags affected
    return ( possible_registers, possible_flags )

def vt_flow_ret( ins, frame, possible_registers, possible_flags ):
    npr = vdb.asm.register_set()
    possible_registers = npr
    # no flags affected
    return ( possible_registers, possible_flags )



def current_flags( frame ):
    return vdb.asm.current_flags(frame,"eflags")

# Enhancements:
# To the flow we could add some "speculative memory" that we read stuff from first, that way we can in later parts of
# the listing "see" things set in the speculative execution of further ones.
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
