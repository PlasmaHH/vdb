#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.register

import gdb

syscalls = {
        "amd64" :
            {
                "exit"           : ([("int","error_code")],[]),
                "exit_group"     : ([("int","error_code")],[]),
                "futex"          : ( [( "uint32_t*","uaddr"),( "int", "futex_op"),("uint32_t","val") ], 
                                     [ [("timespec*","timeout"),("uint32_t","val2")],("uint32_t*","uaddr2"),("uint32_t","val3") ] ),
                "openat"         : ([("int","fd"),("char*","filename"),("int","flags"),("umode_t","mode")],[]),
                "read"           : ([("int","fd"),("char*","buf"),("size_t","count")],[]),
                "readv"          : ([("int","fd"),("iovec*","iov"),("int","iovcnt")],[]),
                "rt_sigprocmask" : ([("int","how"),("kernel_sigset_t*","set"),("kernel_sigset_t*","oldset"),("size_t","sigsetsize")],[]),
                "tgkill"         : ([ ("pid_t","tgid"),("pid_t","tid"),("int","sig")],[]),
                "write"          : ([("int","fd"),("char*","buf"),("size_t","count")],[]),
                "writev"         : ([("int","fd"),("iovec*","iov"),("int","iovcnt")],[]),

            }
        }

enum_maps = {
        "futex:futex_op" :
            {
                0   : "FUTEX_WAIT",                 1   : "FUTEX_WAKE",                 2   : "FUTEX_FD",               3   : "FUTEX_REQUEUE",
                128 : "FUTEX_WAIT_PRIVATE",         129 : "FUTEX_WAKE_PRIVATE",                                         131 : "FUTEX_REQUEUE_PRIVATE",

                4   : "FUTEX_CMP_REQUEUE",          5   : "FUTEX_WAKE_OP",              6   : "FUTEX_LOCK_PI",          7   : "FUTEX_UNLOCK_PI",
                132 : "FUTEX_CMP_REQUEUE_PRIVATE", 133 : "FUTEX_WAKE_OP_PRIVATE",       134 : "FUTEX_LOCK_PI_PRIVATE",  135 : "FUTEX_UNLOCK_PI_PRIVATE",

                8   : "FUTEX_TRYLOCK_PI",           9   : "FUTEX_WAIT_BITSET",          10  : "FUTEX_WAKE_BITSET",          11  : "FUTEX_WAIT_REQUEUE_PI",
                136 : "FUTEX_TRYLOCK_PI_PRIVATE",   137 : "FUTEX_WAIT_BITSET_PRIVATE",  138 : "FUTEX_WAKE_BITSET_PRIVATE",  139 : "FUTEX_WAIT_REQUEUE_PI_PRIVATE",

                12  : "FUTEX_CMP_REQUEUE_PI",
                140 : "FUTEX_CMP_REQUEUE_PI_PRIVATE",

                256 : "FUTEX_CLOCK_REALTIME"
            },
        "rt_sigprocmask:how" :
            {
                0   : "SIG_BLOCK", 1 : "SIG_UNBLOCK", 2 : "SIG_SETMASK"
            },
        "openat:fd" :
            {
                -100: "AT_FDCWD"
            }
        }


syscall_conventions = {
        "amd64" : {
            "number" : "rax",
            "ret0" : "rax",
            "ret1" : "rdx",
            "args" : [ "rdi", "rsi", "rdx", "r10", "r8", "r9" ],
            "clobber" : [ "rax", "rcx" ]
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
        try:
            ret = vdb.register.read(r)
        except:
            return (None,True)
        q = True
#    print(f"Register {r} not in {rd} ? {q}")
    return (str(ret),q)

def param_str( syscall, val, ptype, pname, register, questionable ):
    if( val is not None ):
        try:
            val = gdb.parse_and_eval(f"({ptype})({val})")
        except:
            # assume the type is not known, we fall back to void* then
            val = gdb.parse_and_eval(f"(void*)({val})")

        emap = enum_maps.get(f"{syscall}:{pname}",None)

        if( emap is not None ):
            ename = emap.get(vdb.util.mint(val),None)
            if( ename is not None ):
                val = f"{val}({ename})"
    else:
        val = "???"

    ret = f"{pname}[{register}] = {val}"
    if( questionable ):
        ret += "?"
    return ret

class syscall:

    def __init__(self, nr, name):
        self.nr = nr
        self.name = name
        self.parameters = []
        self.optional_paramters = []
        self.clobbers = []

    def to_str( self, registers ):

        ret = f"{self.name}[{self.nr}]( "
        for p in self.parameters:
            rval,q = reg(p.register,registers)
            ret += param_str(self.name,rval,p.types[0],p.names[0],p.register, q)
            ret += ","
        ret = ret[:-1]

        if( len(self.optional_paramters) > 0 ):
            if( len(self.parameters) > 0 ):
                ret += ","
            for o in self.optional_paramters:
                rval,q = reg(o.register,registers)
                ret += param_str(self.name,rval,o.types[0],o.names[0],o.register,q)
                ret += ","
            ret = ret[:-1]

        ret += ")"
        return ret

    def clobber( self, registers ):
        ret = registers
        for reg in self.clobbers:
            ret.pop(reg,None)
            alt = vdb.register.altname(reg)
            if( alt is not None ):
                ret.pop(alt,None)
        return ret

def get( nr ):
    return syscall_db.get(nr,None)

def gather_params( sarch, plist, cnt = 0 ):
    ret = []

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
            sc.optional_paramters = gather_params(sarch,optparamlist,len(sc.parameters))
        sc.clobbers = syscall_conventions[sarch]["clobber"]
#        print(f"{nr} => {sc.name}")
        syscall_db[int(nr)] = sc




parse_xml()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
