#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io

def dot_escape( txt ):
    txt = txt.replace("&","&amp;")
    txt = txt.replace(">","&gt;")
    txt = txt.replace("<","&lt;")
    return txt

def write_attributes( f, attributes ):
    for attr,val in attributes.items():
        val = str(val)
        val = dot_escape(val)
        attr = dot_escape(attr)
        f.write(f' {attr}="{val}" ')


class td:

    def __init__( self, content = None ):
        self.content = content
        self.attributes = {}

    def set( self, nc ):
        self.content = dot_escape(nc)

    def write(self,f):
        f.write("<td ")
        write_attributes(f,self.attributes)
        f.write(">")
        if( isinstance(self.content,table) ):
            self.content.write(f)
        else:
            f.write(str(self.content))
        f.write("</td>\n")

    def __setitem__( self, name, val ):
        self.attributes[name] = val

class tr:

    def __init__( self ):
        self.tds = []
        self.attributes = {}

    def td( self, val ):
        t = td(dot_escape(str(val)))
        self.tds.append(t)
        return t

    def td_raw( self, val ):
        t = td(val)
        self.tds.append(t)
        return t

    def write(self,f):
        f.write("<tr ")
        write_attributes(f,self.attributes)
        f.write(">")
        for itd in self.tds:
            itd.write(f)
        f.write("</tr>\n")

    def __str__( self ):
        f = io.StringIO()
        self.write(f)
        return f.getvalue()

    def __setitem__( self, name, val ):
        self.attributes[name] = val

class table:
    def __init__( self ):
        self.attributes = {}
        self.trs = []
        self.attributes["border"] = "0"
        self.attributes["cellspacing"] = "0"
        self.attributes["cellborder"] = "1"
        self.attributes["cellpadding"] = "0"

    def write(self,f):
        if( len(self.trs) == 0 ):
            return
        f.write("<table ")
        write_attributes(f,self.attributes)
        f.write(">")
        for itr in self.trs:
            itr.write(f)
        f.write("</table>")

    def add( self, atr ):
        self.trs.append(atr)

    def tr( self ):
        t = tr()
        self.add(t)
        return t

class edge:
    def __init__( self, to, port = None, srcport = None, tgtport = None ):
        self.to = to
        self.port = port
        self.srcport = srcport
        self.tgtport = tgtport
        self.attributes = {}

    def __setitem__( self, name, val ):
        self.attributes[name] = val

    def write( self, f, fr ):
        tpstr = ""
        spstr = ""
        if( self.port is not None ):
            tpstr = f':"{self.port}"'
        elif( self.tgtport is not None ):
            tpstr = f':"{self.tgtport}"'
        if( self.srcport is not None ):
            spstr = f':"{self.srcport}"'

        if( len(self.attributes) ):
            f.write(f'"{fr}"{spstr} -> "{self.to}"{tpstr} [')

            for n,v in self.attributes.items():
                f.write(f' {n} = "{v}", ')
            f.write(" ];\n")
        else:
            f.write(f'"{fr}"{spstr} -> "{self.to}"{tpstr};\n')

class node:
    def __init__( self, name ):
        self.name = name
        self.table = None
        self.rows = {}
        self.rownames = []
        self.edges = []
        self.plainlabel = None

    def write(self,f):
        if( self.plainlabel is not None ):
            f.write(f'"{self.name}" [ label="{self.plainlabel}" ];\n')
        else:
            f.write(f'"{self.name}" [ shape=plaintext label=<\n')
            if( self.table ):
                self.table.write(f)
            if( len(self.rows) ):
                st = table()
                st.attributes["border"] = "0"
                st.attributes["cellspacing"] = "0"
                st.attributes["cellborder"] = "1"
                for rn in self.rownames:
                    st.trs.append(self.rows[rn])
                st.write(f)
            f.write("\n>];\n")

    def edge( self, name, port = None, srcport = None, tgtport = None ):
        e = edge(str(name), port, srcport, tgtport)
        self.edges.append(e)
        return e

    def write_edges( self, f ):
        for e in self.edges:
            e.write(f,self.name)

    def __getitem__( self, name ):
        return self.rows.get(name,None)

    def __setitem__( self, name, val ):
        rtr = self.rows.get(name,None)
        if( rtr is None ):
            self.rownames.append(name)
            rtr = tr()
            self.rows[name] = rtr
            rtr.td(name)
            rtr.td(None)
        rtr.tds[1].content = str(val)
        return rtr.tds[1]


class graph:

    def __init__( self, name ):
        self.name = name
        self.nodes = []
        self.node_attributes = {"shape":"box"}
        self.attributes = {}

    def write( self, filename ):
        if( not filename.endswith( ".dot" )):
            filename += ".dot"
#        print("filename = '%s'" % filename )
        with open(filename,"w+") as f:
            f.write(f"digraph {self.name} {{\n")
            f.write("node [ ")
            for nn,nv in self.node_attributes.items():
                f.write(f'{nn}="{nv}"')
            f.write(" ];\n")
            for n in self.nodes:
                n.write(f)
            for n in self.nodes:
                n.write_edges(f)
            f.write("}\n")

    def node( self, name ):
        n = node(name)
        self.nodes.append(n)
        return n



def color_raw( s, col ):
    return f'<font color="{col}">{s}</font>'

def color( s, col ):
    s = dot_escape(s)
    return color_raw(s,col)
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
