#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb
import vdb.config
import vdb.dot
import vdb.command

import gdb
import gdb.types
import intervaltree

import itertools
import colors
import traceback
import re
import os
import datetime


def set_array_elements( cfg ):
    cfg.elements = []
    elem = cfg.value.split(",")
    for i in elem:
        cfg.elements.append(int(i))

dot_filebase   = vdb.config.parameter("vdb-ftree-filebase","ftree")
dot_command    = vdb.config.parameter("vdb-ftree-dot-command", "nohup dot -Txlib {filename} &>/dev/null &" )
array_elements = vdb.config.parameter("vdb-ftree-array-elements","0,1,2,3,-4,-3,-2,-1",on_set  = set_array_elements )
color_invalid  = vdb.config.parameter("vdb-ftree-colors-invalid","#ff2222",gdb_type = vdb.config.PARAM_COLOUR)

set_array_elements(array_elements)

code_dict = {
gdb.TYPE_CODE_PTR : ".TYPE_CODE_PTR",
gdb.TYPE_CODE_ARRAY : ".TYPE_CODE_ARRAY",
gdb.TYPE_CODE_STRUCT : ".TYPE_CODE_STRUCT",
gdb.TYPE_CODE_UNION : ".TYPE_CODE_UNION",
gdb.TYPE_CODE_ENUM : ".TYPE_CODE_ENUM",
gdb.TYPE_CODE_FLAGS : ".TYPE_CODE_FLAGS",
gdb.TYPE_CODE_FUNC : ".TYPE_CODE_FUNC",
gdb.TYPE_CODE_INT : ".TYPE_CODE_INT",
gdb.TYPE_CODE_FLT : ".TYPE_CODE_FLT",
gdb.TYPE_CODE_VOID : ".TYPE_CODE_VOID",
gdb.TYPE_CODE_SET : ".TYPE_CODE_SET",
gdb.TYPE_CODE_RANGE : ".TYPE_CODE_RANGE",
gdb.TYPE_CODE_STRING : ".TYPE_CODE_STRING",
gdb.TYPE_CODE_BITSTRING : ".TYPE_CODE_BITSTRING",
gdb.TYPE_CODE_ERROR : ".TYPE_CODE_ERROR",
gdb.TYPE_CODE_METHOD : ".TYPE_CODE_METHOD",
gdb.TYPE_CODE_METHODPTR : ".TYPE_CODE_METHODPTR",
gdb.TYPE_CODE_MEMBERPTR : ".TYPE_CODE_MEMBERPTR",
gdb.TYPE_CODE_REF : ".TYPE_CODE_REF",
gdb.TYPE_CODE_RVALUE_REF : ".TYPE_CODE_RVALUE_REF",
gdb.TYPE_CODE_CHAR : ".TYPE_CODE_CHAR",
gdb.TYPE_CODE_BOOL : ".TYPE_CODE_BOOL",
gdb.TYPE_CODE_COMPLEX : ".TYPE_CODE_COMPLEX",
gdb.TYPE_CODE_TYPEDEF : ".TYPE_CODE_TYPEDEF",
gdb.TYPE_CODE_NAMESPACE : ".TYPE_CODE_NAMESPACE",
gdb.TYPE_CODE_DECFLOAT : ".TYPE_CODE_DECFLOAT",
gdb.TYPE_CODE_INTERNAL_FUNCTION : ".TYPE_CODE_INTERNAL_FUNCTION",
}

def gdb_type_code( code ):
    return code_dict.get(code,code)

def fixup_intparam( ip ):
    return ip.group(1)

fxre = re.compile("([0-9]+)ul")

def fixup_type( t ):
#    print("type(t) = '%s'" % type(t) )
    return fxre.sub(fixup_intparam,t)



def indent( i, fmt, *more ):
    try:
        print(("  " * i + fmt).format(*more) )
    except:
        print(fmt)


def get( val, key, alternative ):
    ret = alternative
    try:
        ret = val[key]
    except:
        pass
    return ret

def get_type( vt, alternative = None ):
    try:
        ret = gdb.lookup_type(vt)
        return ret
    except:
        return None


def unprefix( arg, prefix ):
    string = str(arg)
    if( string.startswith(prefix) ):
        return string[len(prefix):]
    else:
        return string


def guess_vptr_type( val ):
    """ Takes a pointer and tries to figure out if it points to an object that has a virtual table and then returns the
    "real" type according to that virtual table. This is to workaround some gdb bug where the dynamic type is
    inaccessible"""
    # otherwise gdb prints potentially some more text about it
    try:
#        print("val = '%s'" % val )
        ptrval = int(val)
        vptr = gdb.parse_and_eval( f"*(void**)({ptrval})" )
#        print("vptr = '%s'" % vptr )
        vpx = re.search("vtable for (.*?)\+[0-9]*>",str(vptr))
        if( vpx ):
#            print("vpx = '%s'" % vpx )
            gdb_vptype=gdb.lookup_type(fixup_type(vpx.group(1)))
            val = val.cast(gdb_vptype.pointer())
#            print("val = '%s'" % val )
        return val
    except:
        traceback.print_exc()
        return val

def std_vector_size( name,m,ptr,value_cache):
#    print("name = '%s'" % name )
#    print("m = '%s'" % m )
#    print("ptr = '%s'" % ptr )
#    for k,v in value_cache.items():
#        print("k = '%s'" % k )
#        print("v = '%s'" % v )

    end = "{0}_M_finish".format(*m)
    exval = value_cache.get(end,None)
#    print("end = '%s'" % end )
#    print("exval = '%s'" % exval )
    dif = exval-ptr
#    print("dif = '%s'" % dif )
    return dif

def std_hashtable_node( m, val, f, pval, fullname ):
    print("m = '%s'" % m )
    print("fullname = '%s'" % fullname )
    xm = re.findall( "{(std::_Hashtable<[^}]*>)}", fullname )
    print("xm = '%s'" % xm )
    node_type = gdb.lookup_type(xm[-1] + "::__node_type")
    print("node_type = '%s'" % node_type )
    if( node_type is not None ):
        return node_type.pointer()
    return None

class ftree:
    def __init__( self ):
        self.visited = set()
        self.written_tables = set()
        self.current_port = 0
        self.value_cache = {}
        self.array_element_filter = []
        self.nodes = intervaltree.IntervalTree()
        self.edge_redirects = { }
        self.subobject_ports = { }
        self.array_element_filter = [ 
                ( "(.*std::unordered_.*<.*>.*::{std::_Hashtable<.*>}_M_h)::{.*}_M_buckets$", "{0}::{{unsigned long}}_M_bucket_count" ),
                ( "(.*std::vector<.*>::.*)_M_start$", std_vector_size )
                ]
        self.downcast_filter = [ 
                ( "std::__detail::_Hash_node_base", std_hashtable_node )
                ]

    def next_port( self ):
        ret = self.current_port
        self.current_port += 1
        return ret

    # the right side of the table, that is for plain types just the value representation. Additionally it returns a list
    # of pointers (with some ports maybe?)
    def table_entry( self, name, fval, f ):
        moreptr = []
        rettd = vdb.dot.td()
#        print("table_entry")
        self.print_gdbval(fval)
        real_type = fval.type.strip_typedefs()
        self.print_gdbval(fval,real_type)
        try:
            self.value_cache[name] = fval
            if( real_type.code == gdb.TYPE_CODE_PTR ):
#                print("PTR is %s" % fval )
                try:
                    # This causes an attempt to read the value. If it is unreachable memory or so, it will throw
                    rm=gdb.selected_inferior().read_memory(fval,1)
                    port = self.next_port()
                    moreptr.append( ( fval, name, port, rettd, f ) )
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
                except gdb.MemoryError:
                    rettd["bgcolor"] = color_invalid.value
                except:
                    traceback.print_exc()
                    rettd["bgcolor"] = color_invalid.value
                rettd.content = "*" + "0x{:x}".format(int(fval))
            elif( real_type.code == gdb.TYPE_CODE_REF ):
                try:
                    # This causes an attempt to read the value. If it is unreachable memory or so, it will throw
                    rm=gdb.selected_inferior().read_memory(fval.reference_value().address,1)
                    port = self.next_port()
                    moreptr.append( ( fval.referenced_value().address, name, port, rettd, f ) )
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
                except:
                    traceback.print_exc()
                    pass
#                rettd.content = "@" + str(fval)
                rettd.content = "*" + "0x{:x}".format(int(fval.referenced_value().address))
            elif( real_type.code == gdb.TYPE_CODE_STRUCT ):
                try:
                    rt,ptrlist = self.table(fval,name,False,f)
                    rettd.content = rt
                    if( rt is None ):
                        rettd.content = "NONE real code %s" % gdb_type_code(real_type.code)
                    return ( rettd, ptrlist )
                except:
                    traceback.print_exc()
                    pass
            else:
#                print(vdb.color.color("real_type.code = '%s'" % gdb_type_code(real_type.code),"#ff9900" ) )
                if( fval is None ):
                    rettd.content = "none real code %s" % gdb_type_code(real_type.code)
                else:
                    rettd.content = str(fval)
            return ( rettd , moreptr )
        except gdb.MemoryError:
            return ( td, moreptr )


    # Expects the value object
    def table( self, fval, name, header, f ):
#        print("Table of %s" % fval )
        if( fval.address in self.written_tables ):
#            print("Table already generated once")
            return
        self.written_tables.add(fval.address)
        self.print_gdbval(fval)
        ptrlist = []
        rt = vdb.dot.table()
        if( header ):
            tr = rt.tr()
#            td = tr.td(str(fval.type))
#            td["colspan"] = "2"
            td = tr.td("0x{:x}".format(int(fval.address)))
            td["colspan"] = "2"
#        print("fval.type = '%s'" % fval.type )

        rtype = fval.type.strip_typedefs()
        if( f is not None ):
            if( rtype.name == "char" ):
                # It is a string, try to gdb print it 
                xtr = rt.tr()
                xtr.td(" ".join(str(fval.address).split()[1:]))
                return ( rt, ptrlist )
#        if( rtype.name == "char *" ):
        if( rtype.code != gdb.TYPE_CODE_STRUCT ):
            xrtype = f.type.strip_typedefs().unqualified()
            xtr = rt.tr()
            xtr.td("UNSUPPORTED %s" % gdb_type_code(rtype.code))
            xtr.td(str(xrtype))
            xtr.td(str(gdb_type_code(xrtype.code)) )
            xtr.td(str(rtype))
#            print("SKIPPING UNSUPPORTE TYPE CODE %s" % gdb_type_code(rtype.code) )
            return ( rt, ptrlist )
        for f in fval.type.fields():
            rtype = f.type.strip_typedefs()
#            print("Tf.name = '%s'" % f.name )
            tr=vdb.dot.tr()
            if( f.is_base_class ):
                tdval = fval.cast(f.type)
                td,moreptr = self.table(tdval,name + "::" + str(f.type),False,f)
                if( len(td.trs) != 0 ):
                    td = tr.td_raw(td)
                    td["colspan"] = 2
                else:
                    tr = None
                ptrlist += moreptr
                traceback.print_exc()
            elif( not hasattr(f,"bitpos") ):
                # static field
                continue
            elif( f.type.code == gdb.TYPE_CODE_UNION ):
                print("SKIPPING UNION, CURRENTLY NOT SUPPORTED")
                continue
            else:
#                if( f.name is None ):
#                    self.print_gdbfield(f)
#                print("f.name = '%s'" % f.name )
                tdval = fval[f.name]
                tr.td(f.name)
#                td,moreptr = self.table_entry(name + "::" + str(f.name),tdval, f)
                td,moreptr = self.table_entry(name + "::{" + str(rtype) + "}" + str(f.name),tdval, f)
                ptrlist += moreptr
                tr.tds.append(td)
            if( tr is not None ):
                rt.add(tr)
        return ( rt, ptrlist )


    def print_gdbfield( self, f ):
        if( hasattr(f,"bitpos") ):
            print("f.bitpos = '%s'" % f.bitpos )
        if( hasattr(f,"enumval") ):
            print("f.enumval = '%s'" % f.enumval )
        print("f.name = '%s'" % f.name )
        print("f.artificial = '%s'" % f.artificial )
        print("f.is_base_class = '%s'" % f.is_base_class )
        print("f.bitsize = '%s'" % f.bitsize )
        print("f.type = '%s'" % f.type )
        print("f.type.code = '%s'" % gdb_type_code(f.type.code) )
        if( hasattr(f,"parent_type" )):
            print("f.parent_type = '%s'" % f.parent_type )
            if( hasattr(f.parent_type,"parent_type" )):
                print("f.parent_type.parent_type = '%s'" % f.parent_type.parent_type )



    def print_gdbval( self, val, rtype = None ):
        try:
            if( rtype is None ):
                rtype = val.type.strip_typedefs()
#            print("gdb value:")
#            print("val.address = '%s'" % val.address )
#            print("val.type = '%s'" % rtype )
#            print("val.type.code = '%s'" % gdb_type_code(rtype.code) )
#            print("val.dynamic_type = '%s'" % val.dynamic_type )
#            print("val.is_lazy = '%s'" % val.is_lazy )
#            print("val = '%s'" % val )
        except:
            traceback.print_exc()
            pass

    def check_for_array( self, name, ptr ):
        for are,action in self.array_element_filter:
#            print("name = '%s'" % name )
#            print("are  = '%s'" % are )
#            m = are.match(name)
            m = re.findall(are,name)
            if( m ):
#                print(vdb.color.color("#########################################","#ff0"))
                if( callable(action) ):
                    elements = action(name,m,ptr,self.value_cache)
                else:
#                    print("m = '%s'" % m )
#                    print("action = '%s'" % action )
                    action = action.format(*m)
#                    print("action = '%s'" % action )
#                    print("self.value_cache = '%s'" % self.value_cache )
#                    for cand,val in self.value_cache.items():
#                        print("cand   = '%s'" % cand   )
                    elements = self.value_cache.get(action,None)
#                    print("elements = '%s'" % elements )
                return elements

    def try_downcast( self, val, f, pval, fullname ):
#        print("fullname = '%s'" % fullname )
#        print("val.type = '%s'" % val.type )
#        print("val = '%s'" % val )
#        if( pval is not None ):
#            print("pval.type = '%s'" % pval.type )
#            print("pval = '%s'" % pval )
        if( f is None ):
            return val
#        self.print_gdbfield(f)
        for df,action in self.downcast_filter:
            print("df = '%s'" % df )
            print("str(val.type) = '%s'" % str(val.type) )
            m = re.findall( df, str(val.type) )
            if( m ):
                newtype = action(m,val,f,pval,fullname)
                if( newtype is not None ):
                    val = val.cast(newtype)
                    break

        return val

    # expects a pointer to the object in val. Add code to support non-pointers too for cases where we pass a stack local
    def ftree (self, val, level, limit, graph, f = None, pval = None, fullname = "" ):
        try:
#            self.value_cache.clear()
#            self.print_gdbval(val)

            if( level >= limit or val is None ):
                return None
            val = guess_vptr_type(val)
#            self.print_gdbval(val)
            if( int(val) in self.visited ):
                return None
            self.visited.add(int(val))
            ptrval = int(val)
            if( ptrval ):
                xs = self.nodes[int(ptrval)]
                if( len(xs) > 0 ):
                    for x in xs:
#                        n = graph.node(ptrval)
#                        n.edge(x[2].name)
#                        n.plainlabel = "subobject"
                        self.edge_redirects[ptrval] = x[2].name

#                        print("ptrval = '%s'" % ptrval )
#                        for _,_,n in self.nodes:
#                            print("n.name = '%s'" % n.name )
#                            for e in n.edges:
#                                print("e.to = '%s'" % e.to )
#                                if( e.to == ptrval ):
#                                    e.to = x[2].name
                        return None
#                print("xs = '%s'" % xs )

            val = self.try_downcast(val,f,pval,fullname)
            tbl,ptrlist = self.table( val.dereference(),str(val.type), True,f)
            n = graph.node(ptrval)
            n.table = tbl

            if( ptrval ):
#                print("val = '%s'" % val )
#                print("ptrval = '%s'" % int(ptrval) )
                self.nodes[int(ptrval):int(ptrval)+int(val.type.target().sizeof)] = n
#            print("self.nodes = '%s'" % self.nodes )
#            print("self.value_cache = '%s'" % self.value_cache )

            while( len(ptrlist) > 0 ):
#                print("len(ptrlist) = '%s'" % len(ptrlist) )
                head = ptrlist[0]
                ptrlist = ptrlist[1:]
                ptr,name,port,ptd,pf = head

                try:
                    elements = self.check_for_array(name,ptr)
                    if( elements is not None ):
                        xtable = vdb.dot.table()
                        ptd.content = xtable

                        over = array_elements.elements
                        if( len(over) == 0 ):
                            over = range(0,elements)

                        printed_elements = set()
                        cnt = 0
                        elements = int(elements)
                        for i in over:
                            if( i < 0 ):
                                i = elements + i
                            if( i >= elements ):
                                continue
                            if( i in printed_elements ):
                                continue
                            printed_elements.add(i)

                            if( cnt != i ):
                                xtr = xtable.tr()
                                xtd = xtr.td("…")
                                xtd["colspan"] = 2
                                cnt = i
                            cnt+=1

                            eptr = ptr + i
                            etbl,moreptr = self.table_entry( f"{name}[{i}]" , eptr.dereference(),pf )
                            xtr = xtable.tr()
                            xtr.td(i)
                            xtd = xtr.tds.append(etbl)

                            ptrlist += moreptr
                        if( cnt < elements ):
                            xtr = xtable.tr()
                            xtd = xtr.td("…")
                            xtd["colspan"] = 2

#                        print("THIS IS AN ARRAY")
#                        print("elements = '%s'" % elements )
#                        print("type(ptr) = '%s'" % type(ptr) )
#                        print("ptr = '%s'" % ptr )
#                        print("ptr = '%s'" % ptr )
                    else:
                        self.ftree(ptr,level+1,limit,graph,pf,val,fullname + " " + name)
#                        print("ptr = '%s'" % ptr )
#                        print("type(ptr) = '%s'" % type(ptr) )
                        
                        n.edge(self.edge_redirects.get(int(ptr),int(ptr)),srcport = "%s:e" % port, tgtport = self.subobject_ports.get(int(ptr),None))
                except:
                    traceback.print_exc()
                    pass

        except:
            traceback.print_exc()
            pass

#        if( f is None ):
#            for n,v in self.value_cache.items():
#                print("n = '%s'" % n )

        return None


class cmd_ftree (vdb.command.command):
    """Show a tree representation of an object an the things it points to.
    It takes a pointer to some object"""
    # 

    def __init__ (self):
        super (cmd_ftree, self).__init__ ("ftree", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.bytes = []
        self.max_type_len = 0
        self.max_code_len = 0
        self.max_name_len = 0
        self.outer_size = 0
        self.outer_type_name = ""
        self.result = ""
        self.dont_repeat()


    def print( self, msg,*more ):
        self.result += str(msg).format(*more) + "\n"

    def log(self, fmt, *more ):
        self.print(fmt.format(*more))

    def print_result( self ):
        print(self.result)
        self.result=""
        return None

    def invoke (self, arg, from_tty):
        argv = gdb.string_to_argv(arg)
        self.print("argv = '%s'" % argv )
        if len(argv) > 2:
            raise gdb.GdbError('ftree takes 1-2 arguments.')

        a0 = gdb.parse_and_eval(argv[0])
        px = a0
        limit = 70
        if( len(argv) == 2 ):
            a1 = gdb.parse_and_eval(argv[1])
            try:
                limit = int(argv[1])
            except:
                try:
                    px = a1.cast(px.type)
                except:
                    traceback.print_exc()
                    px = None
                    pass

        val = px
        try:
            self.print("")
            filebase = dot_filebase.value
            now=datetime.datetime.now()
            filebase=now.strftime(filebase)
            g = vdb.dot.graph("ftree")
            f = ftree()
#            print("rf = '%s'" % rf )
#            print("val['refcount'] = '%s'" % val['refcount'] )
#            return
            f.ftree (val, 0,limit,g )

            self.print_result()
            print("limit = '%s'" % limit )
            g.write(filebase)

            filename = filebase + ".dot"
            cmd=dot_command.value.format(filename=filename, filebase=filebase)
            print(f"Created '{filename}', starting {cmd}")
            os.system(cmd)
#            os.system("nohup dot -Txlib ftree.dot &")
        except Exception as e:
            traceback.print_exc()

cmd_ftree()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
