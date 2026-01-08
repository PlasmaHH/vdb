#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb
import vdb.color
import vdb.config
import vdb.subcommands
import vdb.util
import vdb.event


import re
import gdb
import traceback
import time
import sys

from collections.abc import Iterable


mod=sys.modules[__name__]
vdb.enabled_modules["shorten"] = mod

color_shorten = vdb.config.parameter("vdb-shorten-colors-templates", "#f60", gdb_type = vdb.config.PARAM_COLOUR)
fold_ellipsis = vdb.config.parameter("vdb-shorten-fold-ellipsis", "…" )
recursion_limit = vdb.config.parameter("vdb-shorten-recursion-limit",3)
verbosity = vdb.config.parameter("vdb-shorten-verbosity",1)

debug = vdb.config.parameter("vdb-shorten-debug",False)
cache = vdb.config.parameter("vdb-shorten-cache",True)
lazy  = vdb.config.parameter("vdb-shorten-lazy-load-typedefs",False)
space_diff = vdb.config.parameter("vdb-shorten-accept-space-diffs", True )


def log(fmt, *more ):
    try:
        print(fmt.format(*more))
    except:
        print(fmt)

def indent( i, fmt, *more ):
    log("  " * i + fmt, *more )

def prefix( i, msg, end = None ):
    print(" " * i + msg, end = end )


class namespace:

    def __init__(self,name,parent=None):
        self.name = name
        self.parent = parent

    def __str__(self):
        ret = self.name
        if( self.parent ):
            ret = self.parent.__str__() + "::" + ret
        return ret

class type_or_function:

    next_id = 0

    def __init__(self):
        self.namespace=None
#        self.name="{{placeholder for name}}"
        self.name=None
        self.template_parameters=None
        self.subobject=None
        self.parameters=None
        self.shortens = {}
        self.suppress_templates = False
        self.suppress_paramters = False
        self.id = type_or_function.next_id
        type_or_function.next_id += 1
        self.type = None
        self.tail = ""
        self.cached_string = None
        self.failed = False
        self.member_tail = None

    def replace_name( self, s, r ):
        if( self.name is not None ):
            self.name = self.name.replace(s,r)
        if( self.namespace is not None ):
            self.namespace.name = self.namespace.name.replace(s,r)
        if( self.subobject is not None ):
            self.subobject.replace_name(s,r)

    def to_dot( self, g ):
        n = g.node(f"{self.name}.{self.id}")
        n["id"] = self.id
        n["name"] = self.name
        n["type"] = self.type
        if( self.namespace is None ):
            n["ns"] = "None"
        else:
            n["ns"] = self.namespace
        if( self.subobject ):
            sn=self.subobject.to_dot(g)
            n.edge(sn.name)
        n["subobject"] = self.subobject
        if( self.template_parameters is not None ):
            n["tparam"] = len(self.template_parameters)
            for tp in self.template_parameters:
                tn = tp.to_dot(g)
                n["tparam"].tds[1]["port"] = "tparam"
                n.edge( tn.name, srcport = "tparam" )
        else:
            n["tparam"] = "None"

        if( self.parameters is not None ):
            n["param"] = len(self.parameters)
            for pp in self.parameters:
                pb = pp.to_dot(g)
                n["param"].tds[1]["port"] = "param"
                n.edge( pb.name, srcport = "param")
        else:
            n["param"] = None

        return n

    def set_type( self, nt ):
#        print(f"{self.type}[{self.id}] => {nt}")
        self.type = nt

#    def add_tail( self, subob ):
#        print("subob.id = '%s'" % (subob.id,) )
#        if( self.subobject ):
#            self.subobject.add_tail(subob)
#        else:
#            self.subobject = subob

    def shorten( self, name ):
        for old,new in self.shortens.items():
            name = name.replace(old,new)
        return name

    def add_ns( self, ns ):
        if( len(ns) > 0 ):
            ns=namespace(ns)
            ns.parent = self.namespace
            self.namespace = ns

    def add_param( self, par ):
        if( self.parameters is None ):
            self.parameters = []
        if( par is not None ):
#            par.dump()
            self.parameters.append(par)
#        self.dump()

    def add_template( self, tpar ):
        if( self.template_parameters is None ):
            self.template_parameters = []
        if( tpar.name is None or len(tpar.name) > 0 ):
            self.template_parameters.append(tpar)
#        print("self.id = '%s'" % (self.id,) )
#        print("self.template_parameters = '%s'" % (self.template_parameters,) )
#        print("tpar = '%s'" % (tpar,) )


    def dump( self, level = 0 ):
        indent(level,"id : " + str(self.id))
        indent(level,"ns : " + str(self.namespace))
        indent(level,"name : " + str(self.name))
        indent(level,"type : " + str(self.type))
        indent(level,"tail : '" + str(self.tail) + "'" )
#        print("self.__dict__ = '%s'" % (self.__dict__,) )
        if( self.template_parameters is not None ):
            indent(level,f"template parameters[{len(self.template_parameters)}]")
            for t in self.template_parameters:
                t.dump(level+1)
        else:
            indent(level,"template parameters = None")
        if( self.parameters ):
            indent(level,f"parameters[{len(self.parameters)}]")
            cnt = 0
            for p in self.parameters:
                indent(level,f"param[{cnt}]")
                cnt += 1
                p.dump(level+1)
        else:
            indent(level,"parameters = None")
        if( self.subobject is not None ):
            indent(level,"Subobject")
            self.subobject.dump(level+1)


    def fold_templates( self, shortlist ):
        self.cached_string = None
        if( isinstance(shortlist,Iterable) and not isinstance(shortlist,str) ):
            for s in shortlist:
                self.fold_templates(s)
        else:
            if( self.subobject is not None ):
                self.subobject.fold_templates(shortlist)
            if( self.template_parameters is not None and len(self.template_parameters ) > 0):
                for tp in self.template_parameters:
                    tp.fold_templates(shortlist)
            if( self.parameters is not None and len(self.parameters) ):
                for p in self.parameters:
                    p.fold_templates(shortlist)
            if( self.name == shortlist ):
                self.suppress_templates = True
#                print(f"SET {self.id}:{self.name} => {self.suppress_templates}")

    def add_shorten( self, fro, to = None ):
        self.cached_string = None
        if( to is None ):
            for f,t in fro.items():
                self.add_shorten(f,t)
        else:
            if( self.subobject is not None ):
                self.subobject.add_shorten(fro,to)
            if( self.template_parameters is not None and len(self.template_parameters ) > 0 ):
                for tp in self.template_parameters:
                    tp.add_shorten(fro,to)
            if( self.parameters is not None and len(self.parameters) ):
                for p in self.parameters:
                    p.add_shorten(fro,to)
            self.shortens[fro] = to

    def __str__(self):
        return self.to_string()

    def parse_tail( self, tail ):
        self.member_tail = tail.split()

    def to_string( self, _ = 0 ):
#        if( self.cached_string is not None ):
#            return self.cached_string

        selfname = self.name
        if( selfname is None ):
            selfname = ""
#        elif( selfname == "__UNNAMED_OBJECT__" ):
#            print("self.parameters = '%s'" % (self.parameters,) )
#            selfname = ""
        elif( len(selfname) == 0 ):
            return ""

        ret = ""
#        print(f"A {ret=}")
        if( self.namespace is not None ):
            ret += str(self.namespace) + "::"
#        print(f"B {ret=}")
        ret += selfname
#        print(f"{self.name=}")
#        print(f"{selfname=}")
#        print(f"C {ret=}")
        ret = self.shorten(ret)
#        print(f"D {ret=}")

#        print(f"STR {self.id}:{self.name} => {self.suppress_templates}")
        if( self.template_parameters is not None ):
            if( self.suppress_templates ):
                ret += vdb.color.color("<" + fold_ellipsis.value +  ">",color_shorten.value)
            else:
                ret += "<"
                first=True
                for t in self.template_parameters:
                    if( first ):
                        first = False
                    else:
                        ret += ", "
                    ts = str(t)
#                    if( len(ts) == 0 ):
#                        print(f"Template parameter of length 0 {self.name}")
                    ret += ts
#                print("ret = '%s'" % (ret,) )
                if( ret[-1] == ">" ):
                    ret += " "
                ret += ">"
#        print("self.id = '%s'" % (self.id,) )
#        print("self.parameters = '%s'" % (self.parameters,) )
#        print("self.subobject = '%s'" % (self.subobject,) )
        if( self.parameters is not None ):
            ret += "("
            first = True

            for par in self.parameters:
                if( first ):
                    first = False
                else:
                    ret += ", "
                ret += str(par)
            ret += ")"

        if( self.subobject is not None ):
#            print("self.subobject = '%s'" % (self.subobject,) )
#            print("self.subobject.parameters = '%s'" % (self.subobject.parameters,) )
            if( self.subobject.name is not None and len(self.subobject.name) != 0 ):
                ret += self.subobject.tail
#            print("ret = '%s'" % (ret,) )
#            print("self.subobject = '%s'" % (self.subobject,) )
#            print("ret = '%s'" % (ret,) )
            ret += str(self.subobject)

        if( self.member_tail is not None ):
            ret += " "
            ret += " ".join(self.member_tail)

        if( cache.value is True ):
            self.cached_string = ret
#        print("ret = '%s'" % (ret,) )
        return ret

def use_sofar( sofar ):
#    print("sofar = '%s'" % (sofar,) )
#    while( sofar.endswith(" ") ):
#        sofar = sofar[:-1]
    return sofar

def parse_fragment( frag, obj, level = 0 ):
#    indent(level,"Parsing fragment '{}'",frag[:250])
    sofar = ""

    ans = "(anonymous namespace)"
    une = "<unnamed enum>"

    tmpl_tailset = [ ":", "*", "&", " const" ]
#    func_tailset = [ "()" ]

    swallow_next = False
    in_tail = False

    i = -1
    while i < len(frag)-1:
        i += 1

        s=frag[i]
#        indent(level,f"@{level} frag[{i}]='{frag[i]}', {sofar=}, {in_tail=}, obj={obj}")
        if( s == " "):
#            indent(level,f"s is space, {swallow_next=}, {sofar=}")
            if( not swallow_next ):
                if( len(sofar) > 0 ):
#                    print(f"'{sofar}' => '{sofar+s}'")
                    sofar += s
#                sofar += str(level)
            swallow_next = False
            continue
        if( s == "(" ):
            if( frag[i:].startswith(ans) ):
                # sofar should be empty. assert maybe?
                sofar = ans
                i += len(ans)
                i -= 1
                continue
#            vdb.util.bark() # print("BARK")
            obj.add_param(None) # tell there are some, maybe 0
#            print(f"sofar use params '{sofar}'")
#            vdb.util.bark() # print("BARK")
            obj.name = use_sofar(sofar)
#            print(f"A1 {obj.name=}")
            sofar = ""
            obj.set_type("function")
#            print(f"S1 {obj.name=}")
            while True:
                ct = type_or_function()
                ct.set_type("function parameter")
                i += 1
#                indent(level,f"{frag[i:]=}")
                consumed = parse_fragment( frag[i:], ct, level+1 )
#                indent(level,f"{consumed=}")
#                ct.dump(level+1)
                i += consumed
                if( ct.name is None ):
                    print(f"{ct.subobject=}")
                    print(f"{frag=}")
                    print(f"{len(frag)=}")
                    print(f"{i=}")
                    print(f"{frag[i:]=}")
                    print(f"{frag[i+1:]=}")
                if( len( ct.name) > 0 ):
#                    vdb.util.bark() # print("BARK")
#                    print("ct.name = '%s'" % (ct.name,) )
                    obj.add_param(ct)
#                    print(f"S2 {obj.name=}")
#                print("obj.id = '%s'" % (obj.id,) )
                if( frag[i] == ")" ):
                    if( ct.subobject is not None ):
                        obj.subobject = ct.subobject
                        obj.subobject.name = None
#                        print(f"S3 {obj.name=}")
                        ct.subobject = None
                    break
            in_tail = True
#            print("obj.name = '%s'" % (obj.name,) )
#            print("frag[i:] = '%s'" % (frag[i:],) )
            continue
        if( s == ")" ):
#            vdb.util.bark() # print("BARK")
            obj.name = use_sofar(sofar)
#            indent(level,f"A2 {obj.name=}")
#            indent(level,f"{i=}")

            if( i+1 < len(frag) and frag[i+1] == "(" ):
#                vdb.util.bark() # print("BARK")
                # a member funciton pointer special case thingie? parse parameters again I guess?
                sub = type_or_function()
                obj.subobject = sub
#                        print("frag[i+1:] = '%s'" % (frag[i+1:],) )
                consumed=parse_fragment( frag[i+1:],sub,level+1)
#                indent(level,f"{consumed=}")
                i += consumed
#            indent(level,f"s==) => {i}")
            return i
        if( s == ":" ):
            obj.add_ns( use_sofar(sofar) )
#            print(f"S4 {obj.name=}")
            sofar = ""
            continue
        if( s == "," ):
#            vdb.util.bark() # print("BARK")
#            print("obj.name = '%s'" % (obj.name,) )
            if( obj.name is not None and len(sofar) > 0 and obj.name != sofar ):
                obj.subobject = type_or_function()
                obj.subobject.name = use_sofar(sofar)
                obj.name="__UNNAMED_OBJECT__"
#                print(f"S5 {obj.name=}")
            else:
#            print("comma use_sofar '{sofar}'")
                obj.name = use_sofar(sofar)
#                print(f"A3 {obj.name=}")
            return i
        if( sofar in [ "operator", "operator<", "operator>" ] and s in "<>" ):
            pass
        elif( s == "<" ):
#            print("frag[i:] = '%s'" % (frag[i:],) )
#            print("sofar = '%s'" % (sofar,) )
            if( frag[i:].startswith(une) ):
                sofar = une
                i += len(une)
                i -= 1
                continue
            obj.name = use_sofar(sofar)
#            print(f"A4 {obj.name=}")
#            print(f"sofar before '{sofar}'")
#            print(f"obj.name before '{obj.name}'")
            while True:
                ct = type_or_function()
                i+=1 # consume the <
#                ct.name = ""
                i += parse_fragment( frag[i:], ct,level+1 )
                if( ct.name == "__UNNAMED_OBJECT__" ):
                    ct.name = None
#                vdb.util.bark() # print("BARK")
#                print("ct.name = '%s'" % (ct.name,) )
                ct.set_type("template parameter")
#                print(f"after template fragment @{level} frag[{i}]='{frag[i]}'")
#                print("ct.name = '%s'" % (ct.name,) )
                obj.add_template( ct )
#                print(f"S6 {obj.name=}")
#                print("i = '%s'" % i )
#                print("len(frag) = '%s'" % len(frag) )
#                print("frag = '%s'" % (frag,) )
#                if( i+1 == len(frag) ): # assume last closing >
#                    return i

                if( frag[i] == "," ):
                    continue
                if( frag[i] == ">" ):
#                    print(f"F1 {obj.name=}")
#                    obj.name = use_sofar(sofar)
#                    sofar = ""
#                    print(f"tail: '{frag[i+1:]}'")
                    if( (i+1) < len(frag) ):
                        for tail in tmpl_tailset:
                            off = 1
                            while i+off < len(frag):
                                if( frag[i+off] == " " ):
                                    off += 1
                                else:
                                    break
#                            print(f"{tail=}")
#                            print(f"{frag[i+off:]=}")
                            if( frag[i+off:].startswith(tail) ):
                                sub = type_or_function()
                                if( frag[i+off] == ":" ):
                                    sub.tail = "::"
                                if( frag[i+off] == " " ):
                                    sub.tail = " "
#                                print("replacing subobject")
                                obj.subobject = sub
                                obj = sub
#                                print(f"S7 {obj.name=}")
#                                obj.name = use_sofar(sofar)
                                sofar = ""
                                break
#                    print(f"F2 {obj.name=}")
#                    else:
#                        i+=1
#                    print("level = '%s'" % (level,) )
#                    print("i = '%s'" % (i,) )
#                    print("ct.name = '%s'" % (ct.name,) )
#                    if( level == 0 ):
#                        i += 1
                    break
            swallow_next = True
#            print(f"sofar after '{sofar}'")
#            print(f"obj.name after '{obj.name}'")
#            print("sofar = '%s'" % (sofar,) )
#            print(f"template continue on {frag} [{i}]")
            continue
        if( s == ">" ):
#            print("sofar = '%s'" % (sofar,) )
#            vdb.util.bark() # print("BARK")
#            print("obj.name = '%s'" % (obj.name,) )
#            print("sofar = '%s'" % (sofar,) )
            if( obj.name is not None and len(sofar) > 0 and obj.name != sofar ):
#                print(f"S8 {obj.name=}")
#                print("Going subobject")
                obj.subobject = type_or_function()
                obj.subobject.name = use_sofar(sofar)
#                print(f"B1 {obj.subobject.name=}")
            elif( obj.name is not None and len(sofar) == 0 ):
#                print("Leaving name")
                pass # leave the old name
            else:
#                print("Old overwrite")
#            if( len(sofar) > 0 ):
                obj.name = use_sofar(sofar)
#                print(f"A5 {obj.name=}")
            if( len(obj.name) == 0 ):
                obj.name = None
            return i
#        print(f"{sofar=} += {s=}")
        sofar += s

#    indent(level,f"{len(frag)=}")
#    indent(level,f"at end {i=}")
#    indent(level,f"{sofar=}")
#    indent(level,f"obj={obj}")
    i += 1
    if( len(sofar) > 0 ):
#        print(f"{sofar=}")
        if( in_tail ):
            obj.parse_tail( sofar )
        else:
            obj.name = use_sofar(sofar)
#        print(f"S9 {obj.name=}")
#        print(f"exit obj.name '{obj.name}'")
    return i




def parse_function( fun, silent = False ):
#    print(f"parse_function( {fun=}, {silent=} )")
    func = type_or_function()
    rest = fun
    sub = func
    func.set_type("type_or_function")

#    print(f"X0 {sub.name=}")
    rest = rest.replace("operator()","operator__CALL__")
    rest = rest.replace("<union>","__UNION__")
    i = parse_fragment( rest , sub )
#    print(f"{rest=}")
#    print(f"{len(rest)=}")
#    print(f"{i=}")
    sub.replace_name("operator__CALL__","operator()")
    sub.replace_name("__UNION__","<union>")

#    print(f"X1 {sub.name=}")




    if( i != len(rest) and not silent ):
        print(f"Consumed {i} out of {len(rest)} bytes, parser doesn't know about the rest")

    sf = str(func)
    s0 = sf.replace(" ","")
    s1 = fun.replace(" ","")
    s0 = sf
    s1 = fun

    if( space_diff.value ):
        s0s = s0.replace(" ","")
        s1s = s1.replace(" ","")
    else:
        s0s = s0
        s1s = s1


    if( debug.value and s0s != s1s ):
        print(f"Recreating the function signature leads a difference ({len(s0)},{len(s1)})")
        print(f"{fun=}")
        print(f"{sf=}")
#        cnt = 0
        d0 = ""
        d1 = ""
        for i in range(0,len(s0)):
            if( s0[i] != s1[i] ):
                d0 = s0[i-10:i+40]
                d1 = s1[i-10:i+40]
                break
        print("Found   :" + d0)
        print("Expected:" + d1)
        func.dump()
        func.failed = True
    elif( s0s != s1s ):
        if( not silent ):
            vdb.log( f"Failed to properly parse '{fun}', shortening not possible, recommend writing a testcase", level = 2)
            vdb.log( f"{s0=}", level = 2 )
            vdb.log( f"{s1=}", level = 2 )
        func.failed = True

#	func.dump()
    return func







def template_fold(fname,template):
    start = fname.find(template)
    if( start == -1 ):
        return fname
    start += len(template)
    t_prefix=fname[0:start]
#	print("start = '%s'" % start )
#	print("fname = '%s'" % fname )
#	print("prefix = '%s'" % prefix )
    level = 0
    for i in range(start,len(fname)):
        if( fname[i] == "<" ):
            level+=1
        elif( fname[i] == ">" ):
            level-=1
        if( level == 0 ):
            suffix=fname[i+1:]
            suffix=template_fold(suffix,template)
            fname = t_prefix + vdb.color.color("<…>",color_shorten.value) + suffix
            break
    return fname




shortens = {
        "std::basic_string<char, std::char_traits<char>, std::allocator<char> >": "std::string",
        "std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >": "std::string",
        "std::__cxx11::basic_string<wchar_t, std::char_traits<wchar_t>, std::allocator<wchar_t> >": "std::wstring",
        "std::basic_ostream<char, std::char_traits<char> >": "std::ostream",
        "std::basic_ostream<wchar_t, std::char_traits<wchar_t> >": "std::wostream",
        "(anonymous namespace)": "(anon)",
        "<unnamed enum>": "<enum>",
        "std::__detail::": "std::_d::",
        "unsigned char": "uint8_t",
        "signed char": "int8_t"
        }

cstdint_candidates = [
        "int", "long", "long long", "short", ""
        ]

cstdint_prefixes = [
        ( "unsigned", "u" ),
        ( "signed", "" ),
        ( "", "" )
        ]

re_shortens = [
        (r"std::_Vector_base<(.*), std::allocator<\1 *> >",
           r"std::vector<\1>"),
        (r"std::vector<(.*), std::allocator<\1 *> >",
           r"std::vector<\1>"),
        (r"std::_Hashtable<(.*), (.*), std::allocator<\2 >, std::__detail::_Select1st, std::equal_to<int>, std::hash<int>, std::__detail::_Mod_range_hashing, std::__detail::_Default_ranged_hash, std::__detail::_Prime_rehash_policy, std::__detail::_Hashtable_traits<false, false, true> >",
            r"std::_Hashtable<\1, \2>"),
        (r"std::__detail::_Map_base<(.*), (.*), std::allocator<\2 >, std::__detail::_Select1st, std::equal_to<.*>, std::hash<\1>, std::__detail::_Mod_range_hashing, std::__detail::_Default_ranged_hash, std::__detail::_Prime_rehash_policy, std::__detail::_Hashtable_traits<false, false, true>, true>",
            r"std::__detail::_Map_base<\1, \2>"),
        (r"std::_Hashtable<(.*),(.*),std::allocator<\2 >,std::__detail::_Select1st,std::equal_to<int>,std::hash<int>,std::__detail::_Mod_range_hashing,std::__detail::_Default_ranged_hash,std::__detail::_Prime_rehash_policy,std::__detail::_Hashtable_traits<false,false,true> >",
            r"std::_Hashtable<\1, \2>"),
        (r"std::_Rb_tree<(.*),(.*),\s*std::_Select1st<.*>,\s*std::less<.*>,\s*std::allocator<.*> >",
            r"std::_Rb_tree<\1, \2>"),
        (r"std::map<(.*),(.*),.*std::allocator<std::pair<.*> > >",
            r"std::map<\1,\2>"),
        ]

cre_shortens = [ ]

for rre,subs in re_shortens:
    cre_shortens.append( (re.compile(rre), subs ) )


@vdb.event.new_objfile()
def redo_cstdint( _ev ):
#    print("Reparsing cstdint shortens")
    for pref,uint in cstdint_prefixes:
        for cand in cstdint_candidates:
            tcand = f"{pref} {cand}".strip()
            try:
                gdbt = gdb.lookup_type(tcand)
            except gdb.error:
                continue
            if( gdbt.sizeof == 0 ):
                continue
            sz = gdbt.sizeof * 8
            sname = f"{uint}int{sz}_t"
            if( len(sname) <= len(tcand) ):
                cre_shortens.append( (re.compile(rf"\b{tcand}\b" ), sname) )



def add_shorten( st ):
    lst=[]
    if( isinstance(st,tuple) ):
        f,t = st
        shortens[f] = t
    elif( isinstance(st,str) ):
        # Format is A => B
        vst = st.splitlines()
        for l in vst:
            shrt = l.split("=>")
            if( len(shrt) != 2 ):
#                print(f"Ignoring line '{l}'")
                continue
            lst.append( (shrt[0].strip(),shrt[1].strip()) )
    else:
        lst=st

    for lt in lst:
        shortens[lt[0]] = lt[1]


def add_shorten_v( argv ):
    if( len(argv) != 2 ):
        print(f"add_shorten expects exactly 2 arguments, {len(argv)} given")
    else:
        f=argv[0]
        t=argv[1]
        add_shorten( (f,t) )
        print(f'Added shorten from "{f}" to "{t}"')
    global symbol_cache
    symbol_cache = {}

def show_shorten( _ ):
    print("Configured shortens are:")
    mlen=0
    for s,t in shortens.items():
        mlen = max(mlen,len(s))

    mlen += 2
    for s,t in shortens.items():
        xs="'"+s+"'"
        print(f"{xs:<{mlen}} => '{t}'")


vdb.subcommands.add_subcommand( [ "add", "shorten" ], add_shorten_v )
vdb.subcommands.add_subcommand( [ "show", "shorten" ], show_shorten )




foldables = [ ]
conditional_foldables: dict[str,list] = {
        ".*" : []
        }

def add_foldable( fld ):
    if( isinstance(fld,str) ):
        add_foldable(fld.splitlines())
    else:
        for f in fld:
            f = f.strip()
            if( len(f) > 0 ):
                foldables.append(f)

def add_conditional( cond, fld = None ):
    if( isinstance(fld,str) ):
        add_conditional( cond, fld.splitlines() )
    else:
        cfoldables = conditional_foldables.get(cond,[])
        for f in fld:
            f = f.strip()
            if( len(f) > 0 ):
                cfoldables.append( f )

def add_foldable_v( argv ):
    if( len(argv) not in [1,2] ):
        print(f"add_foldable expects 1 or 2 arguments, {len(argv)} given" % len(argv) )
    elif( len(argv) == 1 ):
        add_foldable( argv[0] )
    elif( len(argv) == 2 ):
        add_conditional( argv[0], argv[1] )
    global symbol_cache
    symbol_cache = {}

def show_foldable( _ ):
    print("Foldables are:")
    for f in foldables:
        print(f"'{f}'")

    print("Conditional foldables:")
    for c,fl in conditional_foldables.items():
        print(c)
        for f in fl:
            print(f"    {f}")

vdb.subcommands.add_subcommand( [ "add","foldable" ], add_foldable_v )
vdb.subcommands.add_subcommand( [ "show","foldable"] , show_foldable )

lazy_task = None

loaded_typedefs = False
def lazy_load_typedefs( _ = None):
    if( loaded_typedefs ):
        return

    global lazy_task
    # Already one task running?
    if( lazy_task is not None ):
        return

    lazy_task = vdb.util.async_task( async_load_typedefs )
    async_load_typedefs( lazy_task )
    return
    lazy_task.start()

def async_load_typedefs( at ):
    try:
        print("Loading typelist in background...")
        print("WARNING! Due to gdb/python instabilities doing anything during that phase may lead to crashes. For the time being we don't do this in the background")
        at.set_progress("[ types #/# ]")
        load_typedefs( at )
        print("Finished loading typelist")
    except:
        vdb.print_exc()
    finally:
        at.set_progress(None)
    global lazy_task
    lazy_task = None

def load_typedefs( at ):
    t0 = time.time()
    global loaded_typedefs
    loaded_typedefs = True
    typelist = gdb.execute("info types",False,True)

    candidates: dict[str,str] = {}
    targets = set()
    multitarget = set()
    cnt = 0

    typelines = typelist.splitlines()
    print(f"{len(typelines)=}")
    for line in typelines:
        cnt += 1
        # Want only typedefs of templates
        if( line.find("typedef") != -1 and line.find("<") != -1 ):
            line = line.replace("(anonymous namespace)","__VDB_ANONYMOUS_NAMESPACE_PLACEHOLDER__")
            sl = line.split()
            # Rules out typdef members of templates
            if( sl[-1].find(">") != -1 ):
                continue
            if( sl[0] == "File" ):
                continue
            if( sl[1] != "typedef" ):
                print(f"Not sure what this is: {line}")
                continue
            sl = sl[2:]
            to = sl[-1]
            if( to.endswith(";") ):
                to = to[:-1]
            fr = " ".join(sl[:-1])
            fr = fr.replace("__VDB_ANONYMOUS_NAMESPACE_PLACEHOLDER__","(anonymous namespace)")
            to = to.replace("__VDB_ANONYMOUS_NAMESPACE_PLACEHOLDER__","(anonymous namespace)")
#            if( to.find("::__") != -1 ):
                # ignore possibly reserved names
#                continue
            if( len(fr) > len(to) ):
                xto = candidates.get(fr,None)
                if( xto is None or len(xto) > len(to) ):
                    candidates[fr] = to
                    if( to in targets ):
                        multitarget.add(to)
                    targets.add( to )
        if( cnt % 100 == 0 ):
            at.set_progress( f"[ types {cnt}/{len(typelines)}({len(candidates)}) ]" )


    print(f"{len(candidates)=}")
#    print("multitarget = '%s'" % (multitarget,) )
    for fr,to in candidates.items():
        if( to in multitarget ):
            continue
        if( verbosity.value > 2 ):
            print(f"Shortening '{fr}'[{len(fr)}]' => '{to}'[{len(to)}]" )
        add_shorten((fr,to))
        # XXX Try to fully replicate the gdb provided type string, including all spaces
#        pfr = parse_function(fr)
#        add_shorten(str(pfr),to)
    t1 = time.time()
    td = t1-t0
    print(f"Loaded {cnt} type items in {td}s, found {len(candidates)} for automatic typedef shortening")


symbol_cache: dict[str,str] = {}

lazy_hint = True

def symbol(fname,silent = False):

    global lazy_hint

    if( lazy.value ):
        lazy_load_typedefs()
    elif( lazy_hint ):
        lazy_hint = False
        vdb.util.qlog("Lazy typedef loading is disabled. To manually load typedefs for shortening, do vdb load shorten")

    if( fname is None ):
        return fname

    infname = fname

    global symbol_cache
    if( cache.value ):
        fret = symbol_cache.get(fname,None)
        if( fret is not None ):
            return fret
    else:
        symbol_cache = {}

    fun = parse_function(fname,silent)

    if( debug.value ):
        import vdb.dot as vdot
        g = vdot.graph("function")
        fun.to_dot(g)
        g.write("shorten.dot")

#    print("debug.value = '%s'" % (debug.value,) )
#    print( f"'{fun}' =?= '{fname}'")
    if( not fun.failed ):
#    if( str(fun) == infname ):
#    print("bef = '%s'" % (fun,) )
        fun.add_shorten(shortens)
        fun.fold_templates(foldables)
        for con,folds in conditional_foldables.items():
            if( re.search( con, infname ) is not None ):
                fun.fold_templates(folds)
        fname=str(fun)
    else:
        fname = infname


    # Do the shortens on the complete string type too

    cnt = 0
    while True:
        cnt += 1
        ofname = fname
        for old,new in shortens.items():
            fname = fname.replace(old,new)
        for cre,sub in cre_shortens:
#            print(f"{fname} => ('{cre}') => ",end="")
#            m = cre.match(fname)
#            print(f"{m=}... ",end="")
            fname = cre.sub( sub, fname )
#            print(f"{fname}")
        if( ofname == fname ):
            break
        if( cnt >= recursion_limit.value ):
            break

    symbol_cache[infname] = fname
#    print(f"[{len(symbol_cache)}]{infname} => {fname}")
    return fname

def symbol_cmd(args):
    sym = " ".join(args)
    print(symbol(sym))

vdb.subcommands.add_subcommand( [ "shorten"] , symbol_cmd )
vdb.subcommands.add_subcommand( [ "load", "shorten"] , lazy_load_typedefs )

# This does some of the work of load_typedefs, maybe share it
def test_all(_):
    typelist = gdb.execute("info types",False,True)

    prere = re.compile("^[0-9]*:(.*)")
    cnt = 0
    for line in typelist.splitlines():
        line=line.strip()
        if( len(line) == 0 ):
            continue
        if( line[-1] == ":" ):
            continue

        m = prere.match(line)
        if( m is not None ):
            line = m.group(1).strip()
        if( line[-1] == ";" ):
            line = line[:-1]
        # They should be in the list as types elsewhere anyways
        if( line.startswith("typedef") ):
            continue

        fun = parse_function(line)
        cnt += 1
    print(f"Tested {cnt} type strings...")

def path( fname ):
    return fname

vdb.subcommands.add_subcommand( [ "_test_all_shorten"] , test_all )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
