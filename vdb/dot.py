#!/usr/bin/env python
# -*- coding: utf-8 -*-

def dot_escape( txt ):
    txt = txt.replace(">","&gt;")
    txt = txt.replace("<","&lt;")
    return txt

def write_attributes( f, attributes ):
    for attr,val in attributes.items():
        val = dot_escape(val)
        attr = dot_escape(attr)
        f.write(f' {attr}="{val}" ')


class td:

    def __init__( self, content = None ):
        self.content = content
        self.attributes = {}

    def write(self,f):
        f.write("<td ")
        write_attributes(f,self.attributes)
        f.write(">")
        f.write(self.content)
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
        for td in self.tds:
            td.write(f)
        f.write("</tr>\n")

    def __setitem__( self, name, val ):
        self.attributes[name] = val

class table:
    def __init__( self ):
        self.attributes = {}
        self.trs = []

    def write(self,f):
        f.write("<table ")
        write_attributes(f,self.attributes)
        f.write(">")
        for tr in self.trs:
            tr.write(f)
        f.write("</table>")

    def add( self, tr ):
        self.trs.append(tr)

class edge:
    def __init__( self, to ):
        self.to = to
        self.attributes = {}

    def __setitem__( self, name, val ):
        self.attributes[name] = val

    def write( self, f, fr ):
        if( len(self.attributes) ):
            f.write(f'"{fr}" -> "{self.to}" [')
            for n,v in self.attributes.items():
                f.write(f' {n} = "{v}", ')
            f.write(" ]\n")
        else:
            f.write(f'"{fr}" -> "{self.to}";\n')

class node:
    def __init__( self, name ):
        self.name = name
        self.table = None
        self.rows = {}
        self.rownames = []
        self.edges = []

    def write(self,f):
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

    def edge( self, name ):
        e = edge(str(name))
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
        print("filename = '%s'" % filename )
        with open(filename,"w+") as f:
            f.write("digraph %s {\n" % self.name )
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
