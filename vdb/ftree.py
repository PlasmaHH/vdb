#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb
import vdb.config
import vdb.dot
import vdb.command
import vdb.util
import vdb.layout

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

verbosity      = vdb.config.parameter("vdb-ftree-verbosity",3 )
dot_filebase   = vdb.config.parameter("vdb-ftree-filebase","ftree")
dot_command    = vdb.config.parameter("vdb-ftree-dot-command", "nohup dot -Txlib {filename} &>/dev/null &" )
array_elements = vdb.config.parameter("vdb-ftree-array-elements","0,1,2,3,-4,-3,-2,-1",on_set  = set_array_elements )
color_invalid  = vdb.config.parameter("vdb-ftree-colors-invalid","#ff2222",gdb_type = vdb.config.PARAM_COLOUR)
color_union    = vdb.config.parameter("vdb-ftree-colors-union","#ffff66",gdb_type = vdb.config.PARAM_COLOUR)
color_vcast    = vdb.config.parameter("vdb-ftree-colors-virtual-cast","#ccaaff",gdb_type = vdb.config.PARAM_COLOUR)
color_dcast    = vdb.config.parameter("vdb-ftree-colors-down-cast","#aaffaa",gdb_type = vdb.config.PARAM_COLOUR)
shorten_head   = vdb.config.parameter("vdb-ftree-shorten-head",15 )
shorten_tail   = vdb.config.parameter("vdb-ftree-shorten-tail",15 )

set_array_elements(array_elements)


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




def std_vector_size( m,ptr,value_cache):
#    print("m = '%s'" % m )
#    print("ptr = '%s'" % ptr )
#    for k,v in value_cache.items():
#        print("k = '%s'" % k )
#        print("v = '%s'" % v )

    end = "{0}_M_finish".format(*m)
    exval = value_cache.get(end,None)
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
        node_type = gdb.lookup_type(xtype)
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
    node_type = gdb.lookup_type(m[0])

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

        node_type = gdb.lookup_type(xm[-1] + "::_Link_type")

        if( node_type is not None ):
            node_type = node_type.strip_typedefs()
            return node_type

    return None

def std_tree_member( m, val, path ):
#    print("m = '%s'" % m )
#    print("val = '%s'" % val )
#    print("path = '%s'" % path )
    xm = re.findall( "{(std::_Rb_tree<[^}]*>)}::_M_t", path )
#    print("xm = '%s'" % xm )
    if( len(xm) > 0 ):

        node_type = gdb.lookup_type(xm[-1] + "::value_type")

        if( node_type is not None ):
            node_type = node_type.strip_typedefs()
            return node_type

    return None






class pointer:

    def __init__( self, val, src_port, path ):
        self.val = val
        self.src_port = src_port
        self.path = path

    def __str__( self ):
        s=f"(@0x{int(self.val):x}:{self.src_port}, {self.path})"
        return s

class ftree:
    def __init__( self ):
        self.visited = set()
        self.written_tables = set()
        self.current_port = 0
        self.value_cache = {}
        self.nodes = intervaltree.IntervalTree()
        self.edge_redirects = { }
        self.subobject_ports = { }
        self.array_element_filter = [
                ( "(.*::{std::_Hashtable<.*>}.*_M_h.*)::{[^}]*}::_M_buckets$",  "{0}::{{unsigned long}}::_M_bucket_count" ),
#                ( "(.*std::unordered_.*<.*>.*::{std::_Hashtable<.*>}_M_h)::{.*}_M_buckets$", "{0}::{{unsigned long}}_M_bucket_count" ),
                ( "(.*std::_Vector_base<.*>::.*)_M_start$", std_vector_size )
                ]
        self.node_downcast_filter = [
                ( "std::__detail::_Hash_node_base", std_hashtable_node ),
                ( "std::_Rb_tree_node_base", std_tree_node )
                ]
        self.member_cast_filter = [
                ( "std::__detail::_Hash_node_value_base<([^}]*)>::{[^}]*}::_M_storage::.*__data" , std_hashtable_member ),
                ( "std::_Rb_tree.*_Rb_tree_node_base.*_M_storage" , std_tree_member )
                ]

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

    def xtable( self, obj, val, path ):

        ret = []
        ptrlist = []
        rows = 0
        maxcols = 0

#        nval = self.try_member_cast( val, obj.get_path() )
        nval = self.try_member_cast( val, path + obj.get_path() )
        if( nval is not None ):
            xval = nval
            nlayout = vdb.layout.object_layout( value = nval )
            xobj = nlayout.object
            l,r,p = self.xtable(xobj,xval,path)
            ret += l
            rows += r
            ptrlist += p
        elif( obj.final ):
            xval = val
            tr = vdb.dot.tr()

#            td = tr.td(xval)
            td,ptrlist,istd = self.table_entry( obj, val, path, None )
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
            for so in self.flat_subobjects( obj ):
                if( so.type.strip_typedefs().code == gdb.TYPE_CODE_UNION ):
                    print("NO FULL UNION SUPPORT YET, EXPECT FUNNY RESULTS")
#                    if( so.name is None ):
#                        print("UNION IS ANONYMOUS, HAVE NO IDEA HOW TO GET THE VALUE THERE YET")
#                        rbk=val[so.field]
#                        print("rbk = '%s'" % rbk )
#                        continue
#                print("so = '%s'" % so )
#                print("val = '%s'" % val )
#                print("val.type = '%s'" % val.type )
#                print("so.field = '%s'" % so.field )
                if( so.name is None ):
                    soval = val[so.field]
#                    print("soval = '%s'" % soval )
                else:
                    print("val = '%s'" % val )
                    print("val.type = '%s'" % val.type )
                    print("obj = '%s'" % obj )
                    soval = val[so.name]
#                    print("val[so.name] = '%s'" % val[so.name] )
                l,r,p = self.xtable(so,soval,path)
                ret += l
                rows += r
                ptrlist += p
        if( obj.parent is not None and len(ret) > 0 ):
            td = vdb.dot.td(obj.name)
            td["rowspan"] = rows

            if( obj.offset != 0 ):
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
                    td.content = vdb.dot.dot_escape("<union>")
#            ret[0] = f'<td rowspan="{rows}" >{obj.name}</td>' + ret[0]
            xtr = ret[0]
            xtr.tds = [ td ] + xtr.tds


#        print("ret = '%s'" % ret )
#        print("rows = '%s'" % rows )
        return ( ret, rows, ptrlist )

    def array_entry( self, fval, elements, path ):
#        print("array_entry")
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
                if( entry_object.type.strip_typedefs().code == gdb.TYPE_CODE_STRUCT ):
                    etbl,rows,moreptr = self.xtable( entry_object, eptr.dereference() ,path)
#                    print("moreptr = '%s'" % moreptr )
#                    print("etbl = '%s'" % etbl )
#                    print("xtr = '%s'" % xtr )
                    xtd = xtr.td(i)
                    xtd["rowspan"] = rows
                    xtr.tds += etbl[0].tds
                    rettr.append(xtr)
                    rettr += etbl[1:]
                else:
                    etbl,moreptr,istd = self.table_entry( entry_object, eptr.dereference(), path, index = i )
                    if( istd ):
                        xtr.td(i)
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

#        print("ptrlist = '%s'" % ptrlist )
#                        print("rettr = '%s'" % rettr )
        return ( rettr, ptrlist )

    # the right side of the table, that is for plain types just the value representation. Additionally it returns a list
    # of pointers (with some ports maybe?)
    def table_entry( self, obj, fval, path, index = None ):
#        print(f"table_entry( {obj}, {fval}, {elements}")
#        moreptr = []
        rettd = vdb.dot.td()
#        print("table_entry")
        self.print_gdbval(fval)
        ptrlist = []
#        print("vdb.util.gdb_type_code(fval.type.code) = '%s'" % vdb.util.gdb_type_code(fval.type.code) )
        real_type = fval.type.strip_typedefs()
        self.print_gdbval(fval,real_type)
        try:
#            print("obj.get_path() = '%s'" % obj.get_path() )
#            print("fval = '%s'" % fval )
            if( index is not None ):
                self.value_cache[obj.get_path() + f"[{index}]"] = fval
            else:
                self.value_cache[obj.get_path()] = fval
            if( real_type.code == gdb.TYPE_CODE_PTR ):
#                print(vdb.color.color("real_type.code = '%s'" % vdb.util.gdb_type_code(real_type.code),"#ff9900" ) )
#                print("PTR is %s" % fval )
#                print("obj = '%s'" % obj )
#                print("fval.dereference().type.code = '%s'" % vdb.util.gdb_type_code(fval.dereference().type.code) )
                try:
                    # This causes an attempt to read the value. If it is unreachable memory or so, it will throw
                    rm=gdb.selected_inferior().read_memory(fval,1)
                    port = self.next_port()
#                    moreptr.append( ( fval, obj.get_path(), port, rettd, f ) )
                    rettd["port"] = port
                    # Don't follow function pointers (or pointers to pointers, like in a VTT)
                    if( fval.dereference().type.code == gdb.TYPE_CODE_FUNC ):
                        pass
                    elif( fval.dereference().type.code == gdb.TYPE_CODE_PTR and fval.dereference().type.code == gdb.TYPE_CODE_PTR ):
                        pass
                    else:
                        ptrlist.append( pointer( fval, port, obj.get_path() ) )
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
#                    moreptr.append( ( fval.referenced_value().address, obj.get_path(), port, rettd, f ) )
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
                except:
                    traceback.print_exc()
                    pass
#                rettd.content = "@" + str(fval)
                rettd.content = "*" + "0x{:x}".format(int(fval.referenced_value().address))
            elif( real_type.code == gdb.TYPE_CODE_STRUCT ):
                try:
#                    rettd.content = "STRUCT MARKED AS FINAL"
                    rettd.content = vdb.dot.dot_escape(str(fval))
                    port = self.next_port()
                    rettd["port"] = port
                    self.subobject_ports[int(fval.address)] = port
#                    rt,ptrlist = self.table(fval,obj.get_path(),False,f)
#                    rettd.content = rt
#                    if( rt is None ):
#                        rettd.content = "NONE real code %s" % vdb.util.gdb_type_code(real_type.code)
                    return ( rettd, ptrlist, True )
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
                    rettd.content = str(fval)
                else:
                    s,e = real_type.range()
                    trs,moreptr = self.array_entry(fval.dereference(),e+1,path)
#                    rettd.content = "ARRAY OF " + real_type.target().name
                    return ( trs, moreptr, False )
            else:
                if( verbosity.value > 4 ):
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
                    rettd.content = str(fval)
            return ( rettd, ptrlist, True )
        except gdb.MemoryError:
            traceback.print_exc()
            pass
        except:
#            print("BARK")
            traceback.print_exc()
            pass
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
        for are,action in self.array_element_filter:
#            print("are = '%s'" % are )
            m = re.findall(are,ptr.path)
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
                return elements
    
    def apply_cast_action( self, val, m, path, action ):
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
            print(f"try_member_cast( @0x{int(val.address):x}, {path})")
#        print("path = '%s'" % path )
        for df,action in self.member_cast_filter:
            m = re.findall( df, path )
            ret = self.apply_cast_action(val,m,path,action)
            if( ret is not None ):
                return ret
        return None

    def try_node_downcast( self, val, path ):
        xtype = val.type.target().strip_typedefs()
        if( xtype.code == gdb.TYPE_CODE_PTR ):
            xtype = xtype.target().strip_typedefs()
        if( verbosity.value > 3 ):
            print("val.type = '%s'" % val.type )
            print("val.type.target() = '%s'" % val.type.target() )
            print(f"try_node_downcast(0x{int(val):x}, {xtype})")
#        print("path = '%s'" % path )
#        print("val = '%s'" % val )
        for df,action in self.node_downcast_filter:
#            print("df = '%s'" % df )
            m = re.findall( df, str(xtype) )
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
#                tr.td("")["colspan"] = cs
            mntd = max(mntd,ntd)
        return mntd


    # expects a pointer to the object in val. Add code to support non-pointers too for cases where we pass a stack local
    def ftree (self, val, level, limit, graph, path = "", elements = None ):

        # When someone passes a non-pointer try to make it one
        if( level == 0 and val.type.code != gdb.TYPE_CODE_PTR ):
            return self.ftree( val.address, level, limit, graph, path, elements )

        if( int(val) in self.visited ):
            return ([],0,[])
        self.visited.add(int(val))



#        print("########### ftree %s" % val )

        oval = val
        val = self.try_node_downcast(val,path)
        dcval = val

        ptrval = int(val)
        xs = self.nodes[ptrval]
        if( len(xs) > 0 ):
            for x in xs:
                self.edge_redirects[ptrval] = x[2].name
#                print("x[2].name = '%s'" % x[2].name )
            return None


        dval = val.dereference()
        xl = vdb.layout.object_layout( value = dval )

#        print("val = '%s'" % val )
#        print("val.type = '%s'" % val.type )
#        print("xl.type = '%s'" % xl.type )
#        print("xl.vtype = '%s'" % xl.vtype )
#        print("xl.vtt = '%s'" % xl.vtt )
        val = val.cast(xl.type.pointer())
        dval = val.dereference()
#        print("val = '%s'" % val )
#        print("?? val.type = '%s'" % val.type )

#        print("path = '%s'" % path )
#        print("xl.object.get_path() = '%s'" % xl.object.get_path() )

#        print("xl.object = '%s'" % xl.object )

        rl,_,ptrlist = self.xtable(xl.object,dval,path)
#        print("rl = '%s'" % rl )

        n = graph.node(int(val))
        n.table = vdb.dot.table()

        if( elements is None ):
            self.nodes[ptrval:ptrval+int(val.type.target().sizeof)] = n
        # prepare header tr
        htr = vdb.dot.tr()
        htd = htr.td("0x{:x}".format(int(val)))

        ttr = vdb.dot.tr()
        ttd = ttr.td(self.shorten(xl.object.type.name))
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

        # No subobjects etc. so the best we can do is probably to get a table entry for it
        if( elements is not None ):
            print("elements = '%s'" % elements )
            trs,moreptr = self.array_entry(dval,elements,path)
            n.table.trs += trs
            ptrlist += moreptr
            self.nodes[ptrval:ptrval+int(dval.type.sizeof)*elements] = n
        elif( len(n.table.trs) == 0 ):
            td,moreptr,istd = self.table_entry(xl.object,val.dereference(),path)
            if( istd ):
                n.table.tr().tds.append(td)
                ptrlist += moreptr
            else:
                pass

        # try fixing table layout to have all tr equal td
        tdmax = self.fillup_trs(n.table.trs,0)
        self.fillup_trs(n.table.trs,tdmax)

        # maxe the header span over that amount
        htd["colspan"] = tdmax
        ttd["colspan"] = tdmax

        n.table.trs = [ htr, ttr ] + n.table.trs


        for p in ptrlist:

            pelements = self.check_for_array(p)
#            print("pelements = '%s'" % pelements )

            self.ftree( p.val, level+1, limit, graph, path = path + " -> " + p.path, elements = pelements )
#            print("p.val = '%s'" % int(p.val) )
#            print("self.subobject_ports = '%s'" % self.subobject_ports )
            n.edge(self.edge_redirects.get(int(p.val),int(p.val)), srcport = p.src_port, tgtport = self.subobject_ports.get(int(p.val),None))


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
#            f.ftree (val, 0,limit,g )
            f.ftree( val, 0, limit, g )

#            xl = vdb.layout.object_layout(val.type,val)
#            return
            self.print_result()
            print("limit = '%s'" % limit )
            g.write(filebase)

            filename = filebase + ".dot"
            cmd=dot_command.value.format(filename=filename, filebase=filebase)
            print(f"Created '{filename}', starting {cmd}")
            os.system(cmd)
        except Exception as e:
            traceback.print_exc()

cmd_ftree()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
