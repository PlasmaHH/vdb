#!/usr/bin/env python3

import re

import vdb.asm

name = "arm"

class instruction( vdb.asm.instruction_base ):

    last_cmp_immediate = 1

    def __init__( self, line, m, oldins ):
        super().__init__()
        self.parse(line,m,oldins)
        self.arg_is_list = False


    @vdb.overrides
    def parse( self, line, m, oldins ):
#        vdb.util.bark() # print("BARK")

        tokens = self.parse_common( line, m, oldins )

        addr = tokens[0].strip()
        if( addr[-1] == ":" ):
            addr = addr[:-1]
            self.offset = ""
            del tokens[0] # address
        else:
            self.offset = tokens[1].strip()[1:-1]
            if( self.offset[0] == "+" ):
                self.offset = self.offset[1:]
            del tokens[0] # address
            del tokens[0] # offset



        self.address = vdb.util.xint(addr)
#        if( self.marked ):
#            print(f" marked address {self.address:#0x}")

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
                aarg = arm_asm_arg(target,arg)
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

        
        if( self.mnemonic in arm_conditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
#            print("self.next = '%s'" % (self.next,) )
#            print("oargs = '%s'" % (oargs,) )
#            print("self.args = '%s'" % (self.args,) )
            self.targets.add( vdb.util.xint(self.args[-1]) )
            self.conditional_jump = True
        elif( self.mnemonic in arm_unconditional_jump_mnemonics ):
#            print("self = '%s'" % (self,) )
            self.targets.add( vdb.util.xint(oargs) )
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
                    tbllen = int(arm_instruction.last_cmp_immediate)
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
            arm_instruction.last_cmp_immediate = self.arguments[1].immediate
#            print("arm_instruction.last_cmp_immediate = '%s'" % (arm_instruction.last_cmp_immediate,) )

        if( debug_all(self) ):
            print("###########################################################")
            print("self.targets = '%s'" % (self.targets,) )

        if( oldins is not None ):
#            print("oldins = '%s'" % (oldins,) )
#            print("self = '%s'" % (self,) )
#            print("oldins.mnemonic = '%s'" % (oldins.mnemonic,) )
#            print("oldins.next = '%s'" % (oldins.next,) )
            if oldins.mnemonic not in arm_unconditional_jump_mnemonics :
                oldins.next = self
#            print("oldins.next = '%s'" % (oldins.next,) )
#            print("2oldins = '%s'" % (oldins,) )
        return self

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
