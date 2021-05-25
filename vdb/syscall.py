#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.register

import gdb

syscalls = {
        "amd64" :
            {
                "futex" : ( [( "uint32_t*","uaddr"),( "int", "futex_op"),("uint32_t","val") ], [ [("timespec*","timeout"),("uint32_t","val2")],("uint32_t*","uaddr2"),("uint32_t","val3") ] ),
                "rt_sigprocmask" : ([("int","how"),("kernel_sigset_t*","set")],[]),
                "tgkill" : ([ ("pid_t","tgid"),("pid_t","tid"),("int","sig")],[])
            }
        }

syscall_conventions = {
        "amd64" : {
            "number" : "rax",
            "ret0" : "rax",
            "ret1" : "rdx",
            "args" : [ "rdi", "rsi", "rdx", "r10", "r8", "r9" ]
            }
        }

syscall_db = {}

class syscall_parameter:
    def __init__( self ):
        self.names = []
        self.types = []
        self.register = None

def reg( r, rd ):
    ret = rd.get(r,None)
    q = False
    if( ret is None ):
        ret = vdb.register.read(r)
        q = True
    return (str(ret),q)

def param_str( val, ptype, pname, questionable ):
    val = gdb.parse_and_eval(f"({ptype})({val})")
    ret = f"{pname} = {val}"
    if( questionable ):
        ret += "?"
    return ret

class syscall:

    def __init__(self, nr, name):
        self.nr = nr
        self.name = name
        self.parameters = []
        self.optional_paramters = []

    def to_str( self, registers ):

        ret = f"{self.name}[{self.nr}]( "
        for p in self.parameters:
            rval,q = reg(p.register,registers)
            ret += param_str(rval,p.types[0],p.names[0], q)
            ret += ","
        ret = ret[:-1]

        if( len(self.optional_paramters) > 0 ):
            if( len(self.parameters) > 0 ):
                ret += ","
            for o in self.optional_paramters:
                ret += param_str(reg(o.register,registers),o.types[0],o.names[0])
                ret += ","
            ret = ret[:-1]

        ret += ")"
        return ret

def get( nr ):
    return syscall_db.get(nr,None)

def gather_params( sarch, plist ):
    ret = []
    cnt = 0

    args = syscall_conventions[sarch]["args"]
    for polyparam in plist:
        sp = syscall_parameter()
        ret.append(sp)
        if( len(args) > cnt ):
            sp.register = args[cnt]

#        print("cnt = '%s'" % (cnt,) )
#        print("sp.register = '%s'" % (sp.register,) )

        cnt += 1
        if( type(polyparam) == list ):
            for ptype,pname in polyparam:
                sp.names.append(pname)
                sp.types.append(ptype)
        else:
            ptype,pname = polyparam
            sp.names.append(pname)
            sp.types.append(ptype)
#            print("ptype = '%s'" % (ptype,) )
#            print("pname = '%s'" % (pname,) )
    return ret

def parse_xml( fn = None ):
    # XXX depending on the architecture change the path and relead the information
    sarch = "amd64"
    if( fn is None ):
        fn = f"/usr/share/gdb/syscalls/{sarch}-linux.xml"
    calldict = syscalls[sarch]

    from defusedxml.ElementTree import parse
    et = parse(fn)

    global syscall_db
    for s in et.iter("syscall"):
        name = s.attrib["name"]
        nr = s.attrib["number"]

        paramlist,optparamlist = calldict.get(name,(None,None) )
        sc = syscall(nr,name)
        if( paramlist is not None ):
            sc.parameters = gather_params(sarch,paramlist)
            sc.optional_paramters = gather_params(sarch,optparamlist)
#        print(f"{nr} => {sc.name}")
        syscall_db[int(nr)] = sc




parse_xml()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
