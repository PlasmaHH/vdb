#!/usr/bin/env python3

import re
import gdb
import vdb.asm

name = "arm"

return_mnemonics = set ([])
call_mnemonics = set(["bl", "blx"])
prefixes = set([ ])
base_pointer = "r11" # can be different

conditional_suffixes = [ "eq","ne","cs","hs","cc","lo","mi","pl","vs","vc","hi","ls","ge","lt","gt","le","z","nz" ]
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
        ( "ld.*|str.*", "mem" ),
        ( "lsl.*|uxt.*|sxt.*", "bit" ),
        ( "it.*", "cond" ),
        ]



argument_registers = [ "r0","r1","r2","r3","r4","r5","r6","r7","r8" ]
base_pointer = "sp"

class asm_arg(vdb.asm.asm_arg_base):

    @vdb.overrides
    def parse( self, arg ):
        arg = arg.strip()
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
            arg = list(map(str.strip,arg.split(",")))
            self.dereference = True
            self.register = arg[0]
            if( len(arg) > 1 ):
#                print("arg[1] = '%s'" % (arg[1],) )
                if( arg[1][0] == "#" ):
                    self.offset = int(arg[1][1:])
                else:
                    self.add_register = arg[1]
        else:
            self.register = arg
#        print("arg = '%s'" % (arg,) )
#        print("str(self) = '%s'" % (str(self),) )
        self._check(oarg,False)

    def __str__( self ):
        ret = ""
        if( self.asterisk ):
            ret +=  "*"
        if( self.prefix is not None ):
            ret += f"%{self.prefix}:"
        if( self.dereference ):
            ret += "["
            if( self.multiplier is not None ):
                if( self.add_register is not None ):
                    ret += "%" + self.add_register
                ret += ","
            ret += self.register
            if( self.offset is not None ):
                ret += ", #" + str(self.offset)
            if( self.multiplier is not None ):
                ret += f",{self.multiplier}"
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
        self.arg_is_list = False
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

        if( tokens[0] in prefixes ):
            self.prefix = tokens[0]
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
#        print("oargs = '%s'" % (args,) )

        if( len(args) > 0 ):
            self.args = []
            if( args[0] == "{" and args[-1] == "}" ):
                self.arg_is_list = True
                args = args[1:-1]
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
                target = False
                self.args.append(arg)
                self.arguments.append(aarg)
        reargs = ", ".join(map(str,self.arguments))
        if( self.arg_is_list ):
            reargs = "{" + reargs + "}"
        if( reargs != oargs.strip() ):
            print("CHECK OF WHOLE EXPRESION FAILED")
            print("oargs  = '%s'" % (oargs,) )
            print("reargs = '%s'" % (reargs,) )
            self.add_extra(reargs)

        
        if( self.mnemonic in call_mnemonics ):
            self.call = True
            self.targets.add( vdb.util.xint(self.args[-1]) )
        elif( self.mnemonic in conditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
#            print("self.next = '%s'" % (self.next,) )
#            print("oargs = '%s'" % (oargs,) )
#            print("self.args = '%s'" % (self.args,) )
            self.targets.add( vdb.util.xint(self.args[-1]) )
            self.conditional_jump = True
        elif( self.mnemonic in unconditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
            self.targets.add( vdb.util.xint(oargs) )
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


            except ValueError:
                pass
        elif( self.mnemonic.startswith("cmp") ):
            instruction.last_cmp_immediate = self.arguments[1].immediate
#            print("instruction.last_cmp_immediate = '%s'" % (instruction.last_cmp_immediate,) )

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

# XXX There are some, we just need to extract them
def current_flags( frame ):
    fs = vdb.asm.flag_set()
    return fs


def vt_flow_mov( ins, frame, possible_registers, possible_flags ):
    if( vdb.asm.asm_explain.value ):
        frm = ins.arguments[1]
        to  = ins.arguments[0]
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

    possible_registers.set( "lr", ins.next.address, origin = "flow_bl" )
    if( not vdb.asm.annotate_jumps.value ):
        return (possible_registers,possible_flags)

    if( ins.next is not None ):
        ins.add_explanation(f"Branch to {ins.targets} and put return address {ins.next.address} in lr register (branch and link)")
    return (possible_registers,possible_flags)

def vt_flow_b( ins, frame, possible_registers, possible_flags ):
    if( not vdb.asm.annotate_jumps.value ):
        return (possible_registers,possible_flags)
    ins.add_extra(f"JUMP TO BE HANDLED")
    if( ins.conditional_jump ):
        ins.add_explanation("Branch conditionally")
    else:
        ins.add_explanation("Branch unconditionally")
        ins.next = None
    return (possible_registers,possible_flags)

def vt_flow_push( ins, frame, possible_registers, possible_flags ):
    vl,rname,_ = possible_registers.get("sp")
    if( vl is not None ):
        nargs = len(ins.args)
        vl = int(vl) - nargs*( vdb.arch.pointer_size // 8 )
        possible_registers.set(rname,vl,origin="flow_push")

    for a in ins.arguments:
        a.target = False
        a.reset_argspec()
    ins.add_explanation(f"Push registers {{{', '.join(ins.args)}}} to the stack")

    # no flags affected
    return ( possible_registers, possible_flags )





# vim: tabstop=4 shiftwidth=4 expandtab ft=python
