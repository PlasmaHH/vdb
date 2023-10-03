#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb
import vdb.config
import vdb.dot
import vdb.command
import vdb.util
import vdb.layout
import vdb.cache

import gdb
import gdb.types
import intervaltree

import itertools
import colors
import traceback
import re
import os
import datetime




verbosity      = vdb.config.parameter("vdb-ftree-verbosity",4 )
dot_filebase   = vdb.config.parameter("vdb-ftree-filebase","ftree")
dot_command    = vdb.config.parameter("vdb-ftree-dot-command", "nohup dot -Txlib {filename} &>/dev/null &" )

array_elements = vdb.config.parameter("vdb-ftree-array-elements","0:3,-4:-1", gdb_type = vdb.config.PARAM_ARRAY )
color_invalid  = vdb.config.parameter("vdb-ftree-colors-invalid","#ff2222",gdb_type = vdb.config.PARAM_COLOUR)
color_union    = vdb.config.parameter("vdb-ftree-colors-union","#ffff66",gdb_type = vdb.config.PARAM_COLOUR)
color_vcast    = vdb.config.parameter("vdb-ftree-colors-virtual-cast","#ccaaff",gdb_type = vdb.config.PARAM_COLOUR)
color_dcast    = vdb.config.parameter("vdb-ftree-colors-down-cast","#aaffaa",gdb_type = vdb.config.PARAM_COLOUR)
color_ptrblack = vdb.config.parameter("vdb-ftree-colors-blacklist-pointer","#ff9900",gdb_type = vdb.config.PARAM_COLOUR)
color_mblack   = vdb.config.parameter("vdb-ftree-colors-blacklist-member","#334400",gdb_type = vdb.config.PARAM_COLOUR)
color_limit    = vdb.config.parameter("vdb-ftree-colors-limited","#88aaff",gdb_type = vdb.config.PARAM_COLOUR)
color_pp       = vdb.config.parameter("vdb-ftree-colors-pretty-print","#76d7c4",gdb_type = vdb.config.PARAM_COLOUR)
color_varname  = vdb.config.parameter("vdb-ftree-colors-variable-name",None,gdb_type = vdb.config.PARAM_COLOUR)


shorten_head   = vdb.config.parameter("vdb-ftree-shorten-head",15 )
shorten_tail   = vdb.config.parameter("vdb-ftree-shorten-tail",15 )
color_arrows   = vdb.config.parameter("vdb-ftree-color-arrows",True )

#resolve_typedefs = vdb.config.parameter("vdb-ftree-resolve-typedefs",True)
reparse_cast = vdb.config.parameter("vdb-ftree-reparse-cast",True)
vptr_cast = vdb.config.parameter("vdb-ftree-vptr-cast",True)

#vdb.config.set_array_elements(array_elements)

color_list = vdb.config.parameter("vdb-ftree-colors-arrows", "#ff0000;#00ff00;#0000ff;#ff8000;#ff00ff;#00ffff" , gdb_type = vdb.config.PARAM_COLOUR_LIST )

def indent( i, fmt, **more ):
    vdb.util.indent(i,fmt,**more)

def vindent( v, i, fmt, **more ):
    if( verbosity.get() >= v ):
        indent(i,fmt,**more)

def get( val, key, alternative ):
    ret = alternative
    try:
        ret = val[key]
    except:
        pass
    return ret

def verbose( lvl ):
    if( verbosity.get() >= lvl ):
        return True
    else:
        return False

def std_vector_size( m,ptr,value_cache):
#    print("m = '%s'" % m )
#    print("ptr = '%s'" % ptr )
#    for k,v in value_cache.items():
#        print("k = '%s'" % k )
#        print("v = '%s'" % v )

    end = "{0}_M_finish".format(*m)
    exval = value_cache.get(end,None)
#    print("ptr.val = '%s'" % ptr.val )
#    print("end = '%s'" % end )
#    print("exval = '%s'" % exval )
    dif = exval-ptr.val
#    print("dif = '%s'" % dif )
    return dif

def std_hashtable_node( m, val, path ):
#    print("m = '%s'" % m )
#    print("path = '%s'" % path )
    if( path.endswith("_M_buckets") ):
        return None
    xm = re.findall( "{(std::_Hashtable<[^}]*>)}", path )
#    print("xm = '%s'" % xm )
    if( verbosity.value > 4 ):
        print("xm = '%s'" % xm )
        print("path = '%s'" % path )
    if( len(xm) > 0 ):
        xtype = xm[-1] + "::__node_type"
        node_type = vdb.cache.lookup_type(xtype)
        if( verbosity.value > 4 ):
            print("xtype = '%s'" % xtype )
            print("node_type = '%s'" % node_type )

        if( node_type is not None ):
            node_type = node_type.strip_typedefs()
            return node_type.pointer()
    return None

def std_hashtable_member( m, val, path ):
#    print("m = '%s'" % m )
#    print("path = '%s'" % path )
#    xm = re.findall( "{(std::_Hashtable<[^}]*>)}", path )
#    print("xm = '%s'" % xm )
    node_type = vdb.cache.lookup_type(m[0])

    if( node_type is not None ):
        node_type = node_type.strip_typedefs()
        return node_type
    return None



def std_tree_node( m, val, path ):
#    print("m = '%s'" % m )
#    print("path = '%s'" % path )
    xm = re.findall( "{(std::_Rb_tree<[^}]*>)}::_M_t", path )
#    print("xm = '%s'" % xm )
    if( len(xm) > 0 ):

        node_type = vdb.cache.lookup_type(xm[-1] + "::_Link_type")

        if( node_type is not None ):
            node_type = node_type.strip_typedefs()
            return node_type

    return None

def std_list_node( m, val, path ):
#    print("m = '%s'" % m )
#    print("path = '%s'" % path )
    xm = re.findall( "{(std::__cxx11::_List_base<[^}]*>)::_List_impl}::_M_impl", path )
#    print("xm = '%s'" % xm )
    if( len(xm) > 0 ):

        alloc_type = vdb.cache.lookup_type(xm[-1] + "::_Node_alloc_type")

        if( alloc_type is not None ):
#            print("alloc_type = '%s'" % alloc_type )
            alloc_type = alloc_type.strip_typedefs()
#            print("alloc_type = '%s'" % alloc_type )
            nm = re.match("^std::allocator<(.*)>$",alloc_type.name)
            if( nm is not None ):

#                print("nm = '%s'" % nm )
                node_type = vdb.cache.lookup_type(nm.group(1))
                return node_type.pointer()

    return None



def std_tree_member( m, val, path ):
#    print("m = '%s'" % m )
#    print("val = '%s'" % val )
#    print("path = '%s'" % path )
    xm = re.findall( "{(std::_Rb_tree<[^}]*>)}::_M_t", path )
#    print("xm = '%s'" % xm )
    if( len(xm) > 0 ):
        try:

            iterator_type = vdb.cache.lookup_type(xm[-1] + "::iterator")
            iterator_type = iterator_type.strip_typedefs()
            print("iterator_type = '%s'" % (iterator_type,) )
#            node_type = vdb.cache.lookup_type(xm[-1] + "::iterator")
            node_type = vdb.cache.lookup_type( iterator_type.name + "::pointer").target().target()
            print("node_type = '%s'" % (node_type,) )

            if( node_type is not None ):
                node_type = node_type.strip_typedefs()
                return node_type
        except gdb.error:
            traceback.print_exc()
            pass

    return None

def std_list_member( m, val, path ):
#    print("m = '%s'" % m )
#    print("val = '%s'" % val )
#    print("path = '%s'" % path )

    xm = re.findall( "{std::__cxx11::_List_base<([^}]*)>::_List_impl}::_M_impl", path )
#    print("xm = '%s'" % xm )
    if( len(xm) > 0 ):
        vt = xm[-1]
        ix = vt.find("<")
        if( ix != -1 ):
            ob = 1
            while ob > 0:
                ix += 1
                if( vt[ix] == "<" ):
                    ob += 1
                elif( vt[ix] == ">" ):
                    ob -= 1
            vt = vt[0:ix+1]
#            print("vt = '%s'" % vt )


        value_type = vdb.cache.lookup_type(vt)

        if( value_type is not None ):
            return value_type

    return None








class pointer:

    def __init__( self, val, src_port, obj, origin_td ):
        self.val = val
        self.src_port = src_port
        self.obj = obj
        self.origin_td = origin_td

    def __str__( self ):
        s=f"(@{int(self.val):#0x}:{self.src_port}, {self.obj})"
        return s

    def __repr__(self):
        return self.__str__()

def tuple_re_list( l ):
    ret = []
    for e0,e1 in l:
        r0 = re.compile(e0)
        ret.append( (r0,e1) )
    return ret

def re_list( l ):
    ret = []
    for e0 in l:
        r0 = re.compile(e0)
        ret.append( r0 )
    return ret



array_element_filter = [
    ( "^(.*::{std::_Hashtable<.*>}.*_M_h.*)::{[^}]*}::_M_buckets$",  "{0}::{{unsigned long}}::_M_bucket_count" ),
    ( "^(.*std::_Vector_base<.*>::.*)_M_start$", std_vector_size )
    ]
node_downcast_filter = [
    ( "std::__detail::_Hash_node_base", std_hashtable_node ),
    ( "std::_Rb_tree_node_base", std_tree_node ),
    ( "std::__detail::_List_node_base", std_list_node )
    ]
member_cast_filter = [
    ( "std::__detail::_Hash_node_value_base<([^}]*)>::{[^}]*}::_M_storage::.*__data" , std_hashtable_member ),
    ( "std::_Rb_tree.*_Rb_tree_node_base.*_M_storage" , std_tree_member ),
    ( "std::__cxx11::_List_base.*_List_node_base.*_M_storage" , std_list_member )
    ]
pointer_blacklist = [
    ".*std::_Vector_base.*_M_end_of_storage",
    ".*std::_Vector_base.*_M_finish"
    ]
member_blacklist = [
    ]
pretty_print_types = [
    "std::string$",
    "std::__cxx11::string$",
    "std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >$",
    ]

def add_array_element_filter( rex, act ):
    array_element_filter.append( (rex,act) )

def add_node_downcast_filter( rex, act ):
    node_downcast_filter.append( (rex,act) )

def add_member_cast_filter( rex, act ):
    member_cast_filter.append( (rex,act) )

def add_pointer_blacklist( rex ):
    pointer_blacklist.append( rex )

def add_member_blacklist( rex ):
    member_blacklist.append( rex )

def add_pretty_print_types( rex ):
    pretty_print_types.append( rex )

def set_array_element_filter( rel ):
    array_element_filter = rel

def set_node_downcast_filter( rel ):
    node_downcast_filter = rel

def set_member_cast_filter( rel ):
    member_cast_filter = rel

def set_pointer_blacklist( rel ):
    pointer_blacklist = rel

def set_member_blacklist( rel ):
    member_blacklist = rel

def set_pretty_print_types( rel ):
    pretty_print_types = rel

def pretty_print( val ):
    ret = ""
    try:
        ret += "[" + str(val["_M_string_length"]) + "]"
    except:
        pass
    ret += str(val)
    return ret

class ftree:
    def __init__( self ):
        self.visited = {}
        self.written_tables = set()
        self.current_port = 0
        self.color_index = 0
        self.value_cache = {}
        self.pp_cache = {}
        self.nodes = intervaltree.IntervalTree()
        self.edge_redirects = { }
        self.subobject_ports = { }
        self.array_element_filter = tuple_re_list( array_element_filter )
        self.node_downcast_filter = tuple_re_list( node_downcast_filter )
        self.member_cast_filter = tuple_re_list( member_cast_filter )
        self.pointer_blacklist = re_list( pointer_blacklist )
        self.member_blacklist = re_list( member_blacklist )
        self.pretty_print_types = re_list( pretty_print_types )

    def pointer_blacklisted( self, path, ptr ):
        sw = vdb.util.stopwatch()
        sw.start()
#        print("path = '%s'" % path )
#        print("ptr.obj.get_path() = '%s'" % ptr.obj.get_path() )
        ms = path + " -> " + ptr.obj.get_path()
        ret = False
        for pbl in self.pointer_blacklist:
            m = pbl.match(ms)
#            print(f"re.match({pbl},{ms}")
            if( m is not None ):
#                print("pbl = '%s'" % pbl )
                ret = True
                break
        sw.stop()
        vdb.cache.add_time(sw.get(),"pointer_blacklisted")
        return ret


    def next_port( self ):
        ret = self.current_port
        self.current_port += 1
        return ret

    def flat_subobjects( self, obj ):
        ret = []
        for so in obj.subobjects:
#            print("so = '%s'" % so )
            if( so.is_base_class ):
                ret += self.flat_subobjects( so )
            else:
                ret.append(so)
        return ret

    def needs_pretty_print( self, tname ):
        if( verbosity.value > 4 ):
            print(f"needs_pretty_print( {tname=} ) => ", end = "")
        cr = self.pp_cache.get(tname,None)
        if( cr is None ):
            cr = vdb.cache.cache_result()
            cr.result = False
            self.pp_cache[tname] = cr
            for ppt in self.pretty_print_types:
                if( ppt.match(tname) is not None ):
                    cr.result = True
                    break
        if( verbosity.value > 4 ):
            print(cr.result)
        return cr.result

    def is_blacklisted( self, obj ):
        for mb in self.member_blacklist:
            if( mb.match(obj.get_path()) is not None ):
                return True
        return False

    def xtable( self, obj, val, path ):
        ret = []
        ptrlist = []
        rows = 0
        maxcols = 0

        if( self.is_blacklisted( obj ) ):
            tr = vdb.dot.tr()
            tr.td(obj.name)["bgcolor"] = color_mblack.value
            tr.td_raw("&nbsp;")
            ret += [ tr ]
            rows += 1
            return ( ret, rows, ptrlist )


#        print("obj.get_path() = '%s'" % obj.get_path() )

        if( obj.type.name is not None ):
            if( self.needs_pretty_print(obj.type.name) ):
#                print("obj = '%s'" % obj )
                tr = vdb.dot.tr()
                if( obj.index is None and obj.parent is not None ):
                    tr.td(obj.name)["bgcolor"] = color_pp.value
                td,ptrlist,istd = self.table_entry( obj, val, path, force_pp = True )
#                td["bgcolor"] = "#426343"
                tr.tds.append(td)
                ret += [ tr ]
                rows += 1
                return ( ret, rows, ptrlist )

        so = None
#        nval = self.try_member_cast( val, obj.get_path() )
        nval = self.try_member_cast( val, path + obj.get_path() )
#        print("obj.final = '%s'" % (obj.final,) )
        if( nval is not None ):
            xval = nval
            nlayout = vdb.layout.object_layout( value = nval )
            xobj = nlayout.object
#            if( self.needs_pretty_print(xobj.type.name) ):
#                xobj.parent = obj.parent
            l,r,p = self.xtable(xobj,xval,path)
            ret += l
            rows += r
            ptrlist += p
            so = xobj
            val=xval
#            return ( ret, rows, ptrlist )
        if( obj.final ):
            xval = val
            tr = vdb.dot.tr()
            so = obj

#            td = tr.td(xval)
#            print("path = '%s'" % path )
            td,ptrlist,istd = self.table_entry( obj, val, path )
            if( istd ):
                tr.tds.append(td)
                ret += [ tr ]
                rows += 1
            else:
                # really is a list of tr
                ret += td
                rows += len(td)
        else:
#            print("len(obj.subobjects) = '%s'" % len(obj.subobjects) )
#            for so in obj.subobjects:
#            print("Subobjects of %s" % obj )
#            print("val = '%s'" % val )
#            print("val.type = '%s'" % val.type )
            for so in self.flat_subobjects( obj ):
                if( so.type.strip_typedefs().code == gdb.TYPE_CODE_UNION ):
                    print("NO FULL UNION SUPPORT YET, EXPECT FUNNY RESULTS")
#                    if( so.name is None ):
#                        print("UNION IS ANONYMOUS, HAVE NO IDEA HOW TO GET THE VALUE THERE YET")
#                        rbk=val[so.field]
#                        print("rbk = '%s'" % rbk )
#                        continue
#                print("")
#                print("val.type = '%s'" % val.type )
#                print("so = '%s'" % so )
#                print("so.field = '%s'" % so.field )
#                print("so.field.name = '%s'" % so.field.name )
#                print("so.field.type = '%s'" % so.field.type )
#                print("so.name = '%s'" % so.name )
#                print("so.parent = '%s'" % so.parent )
#                print("so.parent.type = '%s'" % so.parent.type )
#                print("so.type = '%s'" % so.type )
                # Check if the member is in one of the base classes, if it is, we need to cast before we can use the
                # field to access it
                if( so.parent is not None and so.parent.type != val.type ):
                    # To just access the field we can even use a pointer
#                    print(f"{val.type=}")
#                    print(f"{so.parent.type=}")
                    try: # Quick hack to make diamond inheritance problems working
                        bval = val.address.cast( so.parent.type.pointer() )
                    except gdb.error:
                        continue
#                    print("bval = '%s'" % bval )
#                    print("bval.type = '%s'" % bval.type )
                    soval = bval[so.field]
                else:
#                if( so.name is None ):
                    soval = val[so.field]
#                    print("soval = '%s'" % soval )
#                else:
#                    print("val = '%s'" % val )
#                    print("val.type = '%s'" % val.type )
#                    print("obj = '%s'" % obj )
#                    soval = val[so.name]
#                    print("val[so.name] = '%s'" % val[so.name] )
#                print("1path = '%s'" % path )
#                print("so.get_path() = '%s'" % so.get_path() )
                l,r,p = self.xtable(so,soval,path)
                ret += l
                rows += r
                ptrlist += p
        if( obj.parent is not None and len(ret) > 0 ):
            td = vdb.dot.td(obj.name)
            td["rowspan"] = rows
            if( obj.type.name is not None and self.needs_pretty_print( obj.type.name ) ):
                td["bgcolor"] = color_pp.value
            else:
                if( len(ret) == 1 and so is not None and so.type.name is not None and self.needs_pretty_print(so.type.name) ):
                    td["bgcolor"] = color_pp.value
                if( len(color_varname.value) > 0 ):
                    td["bgcolor"] = color_varname.value

            if( obj.byte_offset != 0 ):
#                print("obj = '%s'" % obj )
#                print("obj.offset = '%s'" % obj.offset )
                port = self.next_port()
                td["port"] = port
#                print("val = '%s'" % val )
                self.subobject_ports[int(val.address)] = port
#                print("port = '%s'" % port )
            if( obj.type.code == gdb.TYPE_CODE_UNION ):
                td["bgcolor"] = color_union.value
                if( obj.name is None ):
                    td.set("<union>")
#            ret[0] = f'<td rowspan="{rows}" >{obj.name}</td>' + ret[0]
            xtr = ret[0]
            xtr.tds = [ td ] + xtr.tds


#        print("ret = '%s'" % ret )
#        print("rows = '%s'" % rows )
        return ( ret, rows, ptrlist )

    def array_entry( self, fval, elements, path ):
        sw = vdb.util.stopwatch()
        sw.start()
#        print(f"array_entry(fval,{elements},{path})")
        try:
            rettr = []
            ptrlist = []
#        htr = vdb.dot.tr()
#        htr.td("length")
#        htr.td(elements)
#        rettr.append(htr)
            over = array_elements.elements

            if( len(over) == 0 ):
                over = range(0,elements)

            printed_elements = set()
            cnt = 0
            elements = int(elements)

            ptr = fval.address
#            print("over = '%s'" % over )

#            htr = vdb.dot.tr()
#            htr.td("over")
#            htr.td(over)
#            rettr.append(htr)

            first_value = ptr.dereference()
            entry_layout = vdb.layout.object_layout( value = first_value )
            entry_object = entry_layout.object

            for i in over:
                if( i < 0 ):
                    i = elements + i
                if( i < 0 ):
                    continue
                if( i >= elements ):
                    continue
                if( i in printed_elements ):
                    continue
                printed_elements.add(i)

                if( cnt != i ):
                    xtr = vdb.dot.tr()
                    xtd = xtr.td("…")
#                    xtd["colspan"] = 2
                    rettr.append(xtr)
                    cnt = i
                cnt+=1

                eptr = ptr + i
                # This will be probably a bit messy. We have "pointers" (array indices) to some objects and we want to
                # lay them out as elements of a table, but the normal process is to make one table per object
                xtr = vdb.dot.tr()
                print("entry_object.type.strip_typedefs() = '%s'" % entry_object.type.strip_typedefs() )
                if( entry_object.type.strip_typedefs().code == gdb.TYPE_CODE_STRUCT or entry_object.type.strip_typedefs().code == gdb.TYPE_CODE_UNION ):
#                    print("path = '%s'" % path )
#                    traceback.print_stack()
                    eo = entry_object.clone()
                    eo.index = i
#                    print("eo = '%s'" % eo )
                    sw.pause()
                    etbl,rows,moreptr = self.xtable( eo, eptr.dereference() ,path )
                    sw.cont()
#                    print("moreptr = '%s'" % moreptr )
#                    print("etbl = '%s'" % etbl )
#                    print("xtr = '%s'" % xtr )
                    xtd = xtr.td(i)
                    xtd["rowspan"] = rows
                    if( entry_object.type.strip_typedefs().code == gdb.TYPE_CODE_UNION ):
                        xtd["bgcolor"] = color_union.value
                    elif( self.needs_pretty_print(eo.name) ):
                        xtd["bgcolor"] = color_pp.value
                    port = self.next_port()
                    xtd["port"] = port
                    self.subobject_ports[int(eptr)] = port
                    xtr.tds += etbl[0].tds
                    rettr.append(xtr)
                    rettr += etbl[1:]
                else:
                    eo = entry_object.clone()
                    eo.index = i
                    sw.pause()
                    etbl,moreptr,istd = self.table_entry( eo, eptr.dereference(), path )
                    sw.cont()
                    if( istd ):
                        xtd=xtr.td(i)
                        port = self.next_port()
                        xtd["port"] = port
                        self.subobject_ports[int(eptr)] = port
                        xtr.tds.append(etbl)
                        rettr.append(xtr)
                    else:
                        pass
                ptrlist += moreptr

            if( cnt < elements ):
                xtr = vdb.dot.tr()
                xtd = xtr.td("…")
#                xtd["colspan"] = 2
                rettr.append(xtr)
        except:
#            print("EXCEPTION")
            traceback.print_exc()
#        finally:
#            print("FINALLY")

        sw.stop()
        vdb.cache.add_time(sw.get(),"array_entry")
#        print("ptrlist = '%s'" % ptrlist )
#                        print("rettr = '%s'" % rettr )
        return ( rettr, ptrlist )
#        return ( [], [] )

    # the right side of the table, that is for plain types just the value representation. Additionally it returns a list
    # of pointers (with some ports maybe?)
    def table_entry( self, obj, fval, path, force_pp = False ):
        sw = vdb.util.stopwatch()
        sw.start()
#        print(f"table_entry( {obj}, {fval}, {elements}")
#        moreptr = []
        rettd = vdb.dot.td()
#        print("table_entry")
#        self.print_gdbval(fval)
        ptrlist = []
#        print("vdb.util.gdb_type_code(fval.type.code) = '%s'" % vdb.util.gdb_type_code(fval.type.code) )
        real_type = fval.type.strip_typedefs()
#        self.print_gdbval(fval,real_type)
        try:
#            print("obj = '%s'" % obj )
#            print("obj.get_base() = '%s'" % obj.get_base() )
#            print("obj.get_path() = '%s'" % obj.get_path() )
#            print("fval = '%s'" % fval )
            if( obj.get_base().index is not None ):
#                print("INDX")
#                print("obj = '%s'" % obj )
                self.value_cache[ f"[{obj.get_base().index}]" + obj.get_path() ] = fval
            else:
                self.value_cache[obj.get_path()] = fval
            if( force_pp ):
                rettd.set(pretty_print(fval))
            elif( real_type.code == gdb.TYPE_CODE_PTR ):
#                print(vdb.color.color("real_type.code = '%s'" % vdb.util.gdb_type_code(real_type.code),"#ff9900" ) )
#                print("PTR is %s" % fval )
#                print("obj = '%s'" % obj )
#                print("fval.dereference().type.code = '%s'" % vdb.util.gdb_type_code(fval.dereference().type.code) )
                try:
                    # This causes an attempt to read the value. If it is unreachable memory or so, it will throw
                    port = self.next_port()
#                    moreptr.append( ( fval, obj.get_path(), port, rettd, f ) )
                    rettd["port"] = port
                    # Don't follow function pointers (or pointers to pointers, like in a VTT)
#                    fcode = fval.dereference().type.code
                    self.subobject_ports[int(fval.address)] = port
                    ftarget = fval.type.target()
                    fcode = ftarget.code
                    if( fcode == gdb.TYPE_CODE_FUNC ):
                        pass
                    elif( fcode == gdb.TYPE_CODE_PTR and ftarget.target().code == gdb.TYPE_CODE_FUNC ):
                        pass
                    else:
                        rm=gdb.selected_inferior().read_memory(fval,1)
#                        print("ptrlist append fval = '%s'" % fval )
                        ptrlist.append( pointer( fval, port, obj, rettd) )
                except gdb.MemoryError:
                    rettd["bgcolor"] = color_invalid.value
                except:
                    traceback.print_exc()
                    rettd["bgcolor"] = color_invalid.value
                rettd.content = "*" + "{:#0x}".format(int(fval))
            elif( real_type.code == gdb.TYPE_CODE_REF ):
                try:
                    # This causes an attempt to read the value. If it is unreachable memory or so, it will throw
                    port = self.next_port()
#                    moreptr.append( ( fval.referenced_value().address, obj.get_path(), port, rettd, f ) )
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
                    target = fval.referenced_value()
                    ptrlist.append( pointer( target.address, port, obj, rettd) )
                    rettd.content = "@" + "{:#0x}".format(int(target.address))
                    rm=gdb.selected_inferior().read_memory(target.address,1)
                except gdb.MemoryError:
                    rettd["bgcolor"] = color_invalid.value
                except:
                    rettd["bgcolor"] = color_invalid.value
                    traceback.print_exc()
                    pass
#                rettd.content = "@" + str(fval)
            elif( real_type.code == gdb.TYPE_CODE_STRUCT ):
                try:
#                    rettd.content = "STRUCT MARKED AS FINAL"
                    rettd.set(str(fval))
                    port = self.next_port()
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
#                    rt,ptrlist = self.table(fval,obj.get_path(),False,f)
#                    rettd.content = rt
#                    if( rt is None ):
#                        rettd.content = "NONE real code %s" % vdb.util.gdb_type_code(real_type.code)
#                    return ( rettd, ptrlist, True )
                except:
                    traceback.print_exc()
                    pass
            elif( real_type.code == gdb.TYPE_CODE_ARRAY ):
#                print("real_type.range() = '%s,%s'" % real_type.range() )
#                print("real_type.fields() = '%s'" % real_type.fields() )
#                print("real_type.name = '%s'" % real_type.name )
#                print("real_type.target() = '%s'" % real_type.target() )
#                print("real_type.target().name = '%s'" % real_type.target().name )
                if( real_type.target().name in [ "char", "unsigned char" ] ):
                    # print them as strings
                    rettd.set(str(fval))
                else:
                    s,e = real_type.range()
                    sw.stop()
                    trs,moreptr = self.array_entry(fval.dereference(),e+1,path)
#                    rettd.content = "ARRAY OF " + real_type.target().name
                    vdb.cache.add_time(sw.get(),"table_entry")
                    return ( trs, moreptr, False )
            else:
                if( verbosity.value > 4 ):
                    print("obj.final = '%s'" % obj.final )
                    print(vdb.color.color("real_type.code = '%s'" % vdb.util.gdb_type_code(real_type.code),"#ff9900" ) )
#                print("real_type.name = '%s'" % real_type.name )
                if( fval is None ):
                    rettd.content = "none real code %s" % vdb.util.gdb_type_code(real_type.code)
                elif( real_type.name == "char" ):
                    # The caller dereferenced a char pointer, thus we try to interpret it as a string
                    # TODO let the caller tell us if we should really do it, probably we pass the pointer then and a
                    # size 
#                    print("str(fval.address) = '%s'" % str(fval.address) )
                    strv = str(fval.address).split()
                    while( len(strv) > 0 and strv[0][0] != '"' ):
                        strv = strv[1:]
                    rettd.content = " ".join(strv)
                else:
#                    print("real_type = '%s'" % real_type )
#                    print("elements = '%s'" % elements )
                    rettd.set(str(fval))
        except gdb.MemoryError:
            traceback.print_exc()
            pass
        except:
#            print("BARK")
            traceback.print_exc()
            pass
        sw.stop()
        vdb.cache.add_time(sw.get(),"table_entry")
        return ( rettd, ptrlist, True )




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
        print("f.type.code = '%s'" % vdb.util.gdb_type_code(f.type.code) )
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
#            print("val.type.code = '%s'" % vdb.util.gdb_type_code(rtype.code) )
#            print("val.dynamic_type = '%s'" % val.dynamic_type )
#            print("val.is_lazy = '%s'" % val.is_lazy )
#            print("val = '%s'" % val )
        except:
            traceback.print_exc()
            pass

    def check_for_array( self, ptr ):
        if( verbosity.value > 3 ):
            print(f"check_for_array( {ptr} )")
        sw = vdb.util.stopwatch()
        sw.start()
        ret = None
#        resw = vdb.util.stopwatch()
        for are,action in self.array_element_filter:
#            print("are = '%s'" % are )
            idx = ptr.obj.get_base().index
            if( idx is not None ):
                sstr = f"[{idx}]" + ptr.obj.get_path()
            else:
#                m = re.findall(are,ptr.obj.get_path())
                sstr = ptr.obj.get_path()
#            resw.start()
            m = are.findall(sstr)
#            m = vdb.cache.re.findall(are,sstr)
#            resw.stop()
#            resw.print("re.findall {:.9f}")
#            if( resw.get() > 0.02 ):
#                print("sstr = '%s'" % sstr )
#                print("are = '%s'" % are )
#            vdb.cache.add_time(resw.get(),"check_for_array.findall")
#            print("m = '%s'" % m )
            if( m ):
#                print(vdb.color.color("#########################################","#ff0"))
                if( callable(action) ):
                    elements = action(m,ptr,self.value_cache)
                else:
#                    print("m = '%s'" % m )
#                    print("action = '%s'" % action )
                    action = action.format(*m)
#                    print("action = '%s'" % action )
#                    print("action = '%s'" % action )
#                    print("self.value_cache = '%s'" % self.value_cache )
#                    for cand,val in self.value_cache.items():
#                        print("cand   = '%s'" % cand   )
                    elements = self.value_cache.get(action,None)
#                    print("elements = '%s'" % elements )
                ret = elements
                break
        sw.stop()
        vdb.cache.add_time(sw.get(),"check_for_array")
        return ret
    
    def apply_cast_action( self, val, m, path, action ):
        if( verbosity.value > 4 ):
            print(f"apply_cast_action( {self=}, {str(val)=}, {m=}, {path=}, {action=} )")
        if( m ):
            newtype = action(m,val,path)
            if( newtype is not None ):
                newtype = newtype.strip_typedefs()
                if( newtype.code == gdb.TYPE_CODE_PTR ):
                    print("Downcasting 0x%x to %s" % (int(val),str(newtype)) )
                    val = val.cast(newtype)
                else:
                    print("Downcasting @0x%x to %s" % (int(val.address),str(newtype)) )
                    # Not a pointer, lets see if casting works better if we do it through a pointer
                    valptr = val.address
                    nvalptr = valptr.cast(newtype.pointer())
                    val = nvalptr.dereference()
#                    val = val.cast(newtype)
                return val
        return None

    def try_member_cast(  self, val, path ):
        if( verbosity.value > 4 ):
            print(f"try_member_cast( @{int(val.address):#0x}, {vdb.color.color(path,'#fe6')})")
        sw = vdb.util.stopwatch()
        sw.start()
#        print("path = '%s'" % path )
        for df,action in self.member_cast_filter:
            m = df.findall( path )
            ret = self.apply_cast_action(val,m,path,action)
            if( ret is not None ):
                return ret
        sw.stop()
        vdb.cache.add_time(sw.get(),"try_member_cast")
        return None

    # Check if we have a downcast action available, matching one of the configured regexes. These will then downcast to
    # the "real" type of the object ( handy for std:: container nodes )
    def try_node_downcast( self, val, path, level ):
        if( verbose(4) ):
            indent(level,f"try_node_downcast({int(val):#0x}({val.type=}), path, {level=})")

        xtype = val.type.target().strip_typedefs()

        if( xtype.code == gdb.TYPE_CODE_PTR ):
            xtype = xtype.target().strip_typedefs()
        if( verbose(4) ):
            indent(level,f"{val.type=} => {xtype=}")

        for df,action in self.node_downcast_filter:
            m = df.findall( str(xtype) )
            ret = self.apply_cast_action(val,m,path,action)
            if( ret is not None ):
                return ret
        return val

    def shorten( self, s ):
        if( s is None ):
            return s
        s = vdb.shorten.symbol(s)
        s = vdb.color.colors.strip_color(s)
        if( len(s) > (shorten_head.value + shorten_tail.value)+1 ):
            s0 = s[:shorten_head.value]
            s1 = s[-shorten_tail.value:]
            s = s0 + "…" + s1
        return s

    # returns the tdmax, so call once to get it, then call it with tdmax to actually fill with tds
    def fillup_trs( self, trs, tdmax ):
        tbl = {}

        retmax = 0
        mntd = 0
        for tr in trs:
            ntd = 0
            for k,v in tbl.items():
                v-=1
                tbl[k] = v
            o=0
            for i in range(0,len(tr.tds)):
                td = tr.tds[i]
                while( tbl.get(i+o,0) > 0 ):
                    ntd += 1
                    o += 1
                tbl[i+o] = td.attributes.get("rowspan",1)
                ntd += td.attributes.get("colspan",1)
            if( ntd < tdmax ):
                cs = tdmax - ntd
                td["colspan"] = cs+1
#                if( cs == -1 ):
#                    print("tdmax = '%s'" % tdmax )
#                    print("ntd = '%s'" % ntd )
            mntd = max(mntd,ntd)
        return mntd

    def next_color( self ):
        col = color_list.elements[self.color_index]
        self.color_index += 1
        self.color_index %= len(color_list.elements)
        return col

    # expects a pointer to the object in val. Add code to support non-pointers too for cases where we pass a stack local
    def ftree (self, val, level, limit, graph, path = "", elements = None ):
        # When someone passes a non-pointer try to make it one
        if( level == 0 and val.type.code != gdb.TYPE_CODE_PTR ):
            return self.ftree( val.address, level, limit, graph, path, elements )

        if( verbose(3) ):
            indent(level,"= "*15)
            indent(level,f"ftree({val.type=},{level=},{limit=},graph,path,{elements=})")

        # Depth limit reached
        if( level > limit ):
            vindent(4,level,f"Reached depth limit of {limit}")
            return

        # Address has already been visited
        if( int(val) in self.visited ):
            ast = self.visited[int(val)]
            vindent(4,level,f"Address {int(val):#0x} already visited as {ast}")
            return ([],0,[])
        self.visited[(int(val))] = repr(val.type)

        oval = val

        val = self.try_node_downcast(val,path,level)
        if( verbose(4) ):
            indent(level,f"After node downcast: {val.type=}")
        dcval = val

        ptrval = int(val)
        xs = self.nodes[ptrval]
        if( len(xs) > 0 ):
            vindent(4,level,f"{len(xs)} entries overlapping with current object found")
            for x in xs:
                self.edge_redirects[ptrval] = x[2].name
            return None

        try:
            vindent(4,level,f"VPTR Test")
            vindent(4,level,f"{val.type=}")
            vindent(4,level,f"{val=}")
            vindent(4,level,f"{str(val)=}")
            vindent(4,level,f"{val.address=}")
            vptr = val["__vptr"] # XXX Check how different compilers do it
            vindent(4,level,"vptr = '%s'" % (vptr,) )
        except:
            traceback.print_exc()
            pass

        dval = val.dereference()
        vindent(4,level,f"{dval.type=}")

        xl = vdb.layout.object_layout( value = dval )
#        if( verbose(4) ):
#            indent(level,f"Object has {len(xl.descriptors)} descriptors")
#            for d in xl.descriptors:
#                indent(level,str(d))
#            print("dval.type.fields() = '%s'" % (dval.type.fields(),) )
        # If it has no subobjects, we try and resolve the typedef. There seems to be a problem with IAR generated
        # binaries that it won't show it for these typedefs
        if( len(xl.object.subobjects) == 0 and dval.type.code == gdb.TYPE_CODE_TYPEDEF ):
            if( reparse_cast.value ):
                tr_dval = gdb.parse_and_eval(f"*({dval.type.strip_typedefs()}*){int(dval.address)}")
            else:
                tr_dval = dval.cast( dval.type.strip_typedefs() )
            vindent(4,level,f"Resolved {tr_dval.type=}")
            tr_xl = vdb.layout.object_layout( value = tr_dval )
            vindent(4,level,f"After resolving typedef, object has {len(tr_xl.object.subobjects)} subobjects")
            print("tr_dval.type.fields() = '%s'" % (tr_dval.type.fields(),) )

            if( len(tr_xl.object.subobjects) > 0 ):
                xl = tr_xl
                dval = tr_dval

#        print("val = '%s'" % val )
#        print("val.type = '%s'" % val.type )
#        print("xl.type = '%s'" % xl.type )
#        print("xl.vtype = '%s'" % xl.vtype )
#        print("xl.vtt = '%s'" % xl.vtt )
        if( val.type != xl.type.pointer() ):
            val = val.cast(xl.type.pointer())
            dval = val.dereference()
#        print("val = '%s'" % val )
#        print("?? val.type = '%s'" % val.type )

#        print("path = '%s'" % path )
#        print("xl.object.get_path() = '%s'" % xl.object.get_path() )

#        print("xl.object = '%s'" % xl.object )

        rl = []
        ptrlist = []
        if( elements is None ):
#            print("0path = '%s'" % path )
            rl,_,ptrlist = self.xtable(xl.object,dval,path)
#        print("rl = '%s'" % rl )

        n = graph.node(int(val))
        n.table = vdb.dot.table()

        if( elements is None ):
            print("val.type = '%s'" % val.type )
            print("val.type.target() = '%s'" % val.type.target() )
            print("vdb.util.gdb_type_code(val.type.target().code) = '%s'" % (vdb.util.gdb_type_code(val.type.target().code),) )
            print("val.type.target().sizeof = '%s'" % val.type.target().sizeof )
            print("ENode 0x%x from 0x%x to 0x%x" % (n.name,ptrval,ptrval+int(val.type.target().sizeof)) )
            target_type = val.type.target().strip_typedefs()
            print("target_type = '%s'" % (target_type,) )
            print("target_type.sizeof = '%s'" % (target_type.sizeof,) )
            tsizeof = target_type.sizeof
            if( tsizeof == 0 ): # XXX Workaround for a bug??
                ttstr = vdb.util.fixup_type(str(target_type))
                tsizeof = gdb.parse_and_eval(f"sizeof({ttstr})")
                print("tsizeof = '%s'" % (tsizeof,) )
            # sometimes with IAR the size is just not there
            if( tsizeof == 0 ):
                tsizeof = 1
            self.nodes[ptrval:ptrval+int(tsizeof)] = n
        # prepare header tr
        htr = vdb.dot.tr()
        htd = htr.td("{:#0x}".format(int(val)))

        ttr = vdb.dot.tr()

        try:
            on0 = val.type.target().name
            if( on0 is None ):
                on0 = str(val.type.target())
        except:
            on0 = val.type.name
            if( on0 is None ):
                on0 = str(val.type)

        on1 = xl.object.type.name
        if( on1 is None ):
            on1 = str(xl.object.type)

#        print("on0 = '%s'" % (on0,) )
#        print("on1 = '%s'" % (on1,) )

        # One could be a typedef, take the shortest one
        if( len(on1) < len(on0) ):
            on = on1
        else:
            on = on0

        ttd = ttr.td(self.shorten(on))
#        print("xl.type = '%s'" % xl.type )
#        print("xl.vtype = '%s'" % xl.vtype )

#        print("dval.type = '%s'" % dval.type )
#        print("dval.dynamic_type = '%s'" % dval.dynamic_type )

#        print("oval.type = '%s'" % oval.type )
#        print("oval.dynamic_type = '%s'" % oval.dynamic_type )
        # downcast returned something else
        if( oval.type != dcval.type ):
            ttd["bgcolor"] = color_dcast.value
        
        # The vcast mechanism had to fix something
        elif( oval.type != val.type ):
            ttd["bgcolor"] = color_vcast.value

        if( elements is not None ):
            ttd.content += f"[{elements}]"

        n.table.trs += rl

        # It is an "external array" throw away the previous generated 
        if( elements is not None ):
#            print("elements = '%s'" % elements )
            trs,moreptr = self.array_entry(dval,elements,path)
#            trs,moreptr = ( [], [] )
            n.table.trs += trs
#            n.table.trs = trs
            ptrlist += moreptr
            if( elements > 0 ):
#                print("Node 0x%x from 0x%x to 0x%x (%s)" % (n.name,ptrval,ptrval+int(dval.type.sizeof)*elements,elements) )
                self.nodes[ptrval:ptrval+int(dval.type.sizeof)*elements] = n
        # No subobjects etc. so the best we can do is probably to get a table entry for it
        elif( len(n.table.trs) == 0 ):
            td,moreptr,istd = self.table_entry(xl.object,val.dereference(),path)
            if( istd ):
                n.table.tr().tds.append(td)
                ptrlist += moreptr
            else:
                pass

        # try fixing table layout to have all tr equal td
        tdmax = self.fillup_trs(n.table.trs,0)
        tdmax = max(tdmax,1)
        self.fillup_trs(n.table.trs,tdmax)

        # maxe the header span over that amount
        htd["colspan"] = tdmax
        ttd["colspan"] = tdmax

        n.table.trs = [ htr, ttr ] + n.table.trs


        for p in ptrlist:
            if( self.pointer_blacklisted(path,p) ):
                p.origin_td["bgcolor"] = color_ptrblack.value
                continue

            pelements = self.check_for_array(p)
#            print("pelements = '%s'" % pelements )
            if( p.val.type.target().strip_typedefs().code != gdb.TYPE_CODE_VOID ):
                if( level < limit ):
                    self.ftree( p.val, level+1, limit, graph, path = path + " -> " + p.obj.get_path(), elements = pelements )
            if( level >= limit and int(p.val) not in self.visited ):
                p.origin_td["bgcolor"] = color_limit.value
                continue
#            print("p.val = '%s'" % int(p.val) )
#            print("self.subobject_ports = '%s'" % self.subobject_ports )
            e=n.edge(self.edge_redirects.get(int(p.val),int(p.val)), srcport = p.src_port, tgtport = self.subobject_ports.get(int(p.val),None))
            if( color_arrows.value ):
                e["color"] = self.next_color()


class cmd_ftree (vdb.command.command):
    """Show a graphviz tree representation of an object an the things it points to.

ftree <pointer>|<variable> [<limit>]  - It takes a pointer to some object or a variable up to <limit> levels deep (default 70)
"""
    # 

    def __init__ (self):
        super (cmd_ftree, self).__init__ ("ftree", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.result = ""


    def print( self, msg,*more ):
        self.result += str(msg).format(*more) + "\n"

    def log(self, fmt, *more ):
        self.print(fmt.format(*more))

    def print_result( self ):
        print(self.result)
        self.result=""
        return None

    def do_invoke (self, argv ):
#        argv = gdb.string_to_argv(arg)
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
#            f.ftree (val, 0,limit,g )
            sw = vdb.util.stopwatch()
            sw.start()
            try:
                f.ftree( val, 0, limit, g )
            except:
                traceback.print_exc()
#            import cProfile
#            cProfile.runctx("f.ftree( val, 0, limit, g )",globals(),locals())
#            print("f.edge_redirects = '%s'" % f.edge_redirects )
            sw.stop()
            sw.print("Creating ftree took {}")
            sw.start()

#            xl = vdb.layout.object_layout(val.type,val)
#            return
            self.print_result()
            print("limit = '%s'" % limit )
            g.write(filebase)
            sw.stop()
            sw.print("Writing ftree took {}")

            filename = filebase + ".dot"
            cmd=dot_command.value.format(filename=filename, filebase=filebase)
            print(f"Created '{filename}', starting {cmd}")
            os.system(cmd)
            vdb.cache.dump()
        except Exception as e:
            traceback.print_exc()
        self.dont_repeat()

cmd_ftree()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
