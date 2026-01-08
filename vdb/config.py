#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration value handling
"""

import vdb.util

import gdb

import traceback
import re

PARAM_COLOUR = 0x800
PARAM_COLOR  = PARAM_COLOUR
PARAM_FLOAT  = 0x801
PARAM_COLOUR_LIST = 0x802
PARAM_COLOR_LIST = PARAM_COLOUR_LIST
PARAM_ARRAY = 0x803

execute_origin = None

def guess_gdb_type( p ):
#    print("Guess type of %s is %s" % (p,type(p)))
    if( isinstance(p,bool) ): # a python bool is a python int too
        return gdb.PARAM_BOOLEAN
    if( isinstance(p,int) ):
        return gdb.PARAM_INTEGER
    if( isinstance(p,float) ):
        return PARAM_FLOAT
    return gdb.PARAM_STRING

def split_colors( cfg ):
    ne = cfg.value.split(";")
    for e in ne:
        _ = vdb.color.color("",e)
    cfg.elements = ne

registry = {}
# In case the type is our artifical type colour, it will translate to gdb string and we check internally for a colour
# string
class parameter(gdb.Parameter):
    def __init__(self, name, default, showstring = "value of %s", docstring = "Documentation of %s", gdb_type = None, on_set = None ):
        try:
            self.docstring = docstring % name
        except:
            self.docstring = docstring
        try:
            self.showstring = showstring % name
        except:
            self.showstring = showstring
        self.name = name
        self.default = default
        self.theme_default = None
        self.origin = None
        self.set_doc = 'Set ' + showstring
#        self.show_doc = docstring + ': %s'
        self.show_doc = self.docstring
        if( self.__doc__ is None ):
            self.__doc__ = "" # to suppress undocumented warning of gdb. Is this a bug? or an undocumented feature?
        self.is_colour = False
        self.is_float = False
        self.gdb_type = gdb_type
        self.original_type = gdb_type
        self.elements = []
        self.internal_on_set = None
        self.on_set = on_set
        if( gdb_type == PARAM_COLOR ):
            if( name.find("-colors-") == -1 ):
                raise RuntimeError(f"Colour names must have -colors- in their name, '{name}' does not" % name )
            self.is_colour = True
            gdb_type = gdb.PARAM_STRING
            self.theme_default = default
            self.internal_on_set = self.check_colour
        elif( gdb_type == PARAM_COLOUR_LIST ):
            self.is_colour = True
            gdb_type = gdb.PARAM_STRING
            self.internal_on_set = split_colors
            self.theme_default = default
        elif( gdb_type == PARAM_ARRAY ):
            self.internal_on_set = set_array_elements
            gdb_type = guess_gdb_type(default)
        elif( gdb_type is None ):
            gdb_type = guess_gdb_type(default)
            self.gdb_type = gdb_type
            self.original_type = gdb_type
        if( gdb_type is  PARAM_FLOAT ):
            self.is_float = True
            self.fvalue = float(default)
            default = str(float(default))
            gdb_type = gdb.PARAM_STRING
        super().__init__(name, gdb.COMMAND_SUPPORT, gdb_type )
        self.value = default
        self.previous_value = self.value

        try:
            self._safe_on_set()
        except:
#            vdb.util.console.print_exception( show_locals = True )
            pass

        registry[self.name] = self

    # This isn't quite right, we ideally would like to pass None while value is something else and have it check if None
    # is the default
    def is_default( self, val = registry ): # pylint: disable=dangerous-default-value
        if( val is registry ):
            val = self.value
        if( val == self.default ):
            return True
        if( val == str(self.default) ):
            return True
        if( self.default is None and val == "" ):
            return True
        return False

    def _safe_on_set( self ):
        if( self.internal_on_set ):
            self.internal_on_set(self)
        if( self.on_set ):
            self.on_set(self)

    def append( self, val ):
        try:
            if( self.original_type == gdb.PARAM_STRING ):
                self.value += val
                self._safe_on_set()
            elif( self.original_type == PARAM_COLOUR_LIST ):
#                print("len(self.elements) = '%s'" % (len(self.elements),) )
                self.value += ";"
                self.value += val
                self._safe_on_set()
#                print("len(self.elements) = '%s'" % (len(self.elements),) )
            elif( self.original_type == PARAM_ARRAY ):
                self.value += ","
                self.value += val
                self._safe_on_set()
            else:
                print(f"Sorry, we do not support appending for {vdb.util.gdb_type_code( self.original_type )}" )
        except:
            vdb.print_exc()
            self.value = self.previous_value
        self.previous_value = self.value

    def get( self ):
        if( self.gdb_type == gdb.PARAM_INTEGER ):
            if( self.value is None ):
                return 0
        if( self.gdb_type == PARAM_COLOUR_LIST ):
            return self.elements
        if( self.gdb_type == PARAM_ARRAY ):
            return self.elements
        if( self.is_float ):
            return self.fvalue
        # XXX What about lists? arrays? those should be handled here too
        return self.value

    def check_colour( self, _ ):
        _ = vdb.color.color("",self.value)

    def record_origin( self ):
        st = traceback.extract_stack()
        wait_for_themes = False

        if( execute_origin is not None ):
            self.origin = execute_origin
            return

        if( st[0].name == "get_set_string" ):
            self.origin = "command-line"
            return

        for s in st:
            if( s.name == "load_themes" ):
                wait_for_themes = True
                continue
            if( wait_for_themes and s.filename.find("importlib") == -1 ):
                self.origin = s.filename
                break
#            print("st[%s] = '%s'" % (i,st[i],) )

    def set_default( self ):
        newdef = self.default
        if( newdef is None ):
            newdef = "None"
        self.set(newdef)

    def set( self, new_value ):
        ret = self.get_set_string(new_value)
        # emulate gdb behaviour as good as we can
        if( ret is not None and len(ret) > 0 ):
            print(ret)

    def get_set_string(self, new_value = None):
        self.record_origin()

        # gdb sets self.value before calling us, but sometimes we want to call this function from within our code too
        if( new_value is not None ):
            self.value = new_value

        try:
            if isinstance(self.value, str):
                self.value = vdb.util.unquote(self.value)
            if( self.value == "None" ):
                self.value = None
            elif( self.value == "default" ):
                self.value = self.default
#            if( self.is_colour ):
#                self._safe_on_set()
#                self.check_colour(self)
            if( self.is_float ):
                self.fvalue = float(self.value)
            self._safe_on_set()
        except:
            vdb.print_exc()
            self.value = self.previous_value
            raise
        self.previous_value = self.value
        pval = self.value
        if isinstance(self.value, str):
            if( len(pval) == 0 ):
                pval = "None"

        if( verbosity.value is None or verbosity.value < 2 ):
            return ""
        if( self.is_colour ):
            vshow = self.get_vdb_show_string()[0][0]
            return f'Set {self.showstring} to {vshow}'
        else:
            return f'Set {self.showstring} to {repr(pval)}'

    def get_show_string(self, _ ):
        return f'{self.showstring} (currently: {repr(self.value)})'

    def get_vdb_show_string(self ):
        xval = []
        if( self.gdb_type == PARAM_COLOR ):
            val = vdb.color.colorl( self.value, self.value )
            xval.append(val)
        elif( self.gdb_type == PARAM_COLOUR_LIST ):
            cval = ("",0)
            for _,e in enumerate(self.elements):
                cv = vdb.color.colorl(e,e)
                cval=vdb.color.concat( cval, cv )
                cval=vdb.color.concat( cval, ";" )
            xval.append(cval)
        else:
            if( self.value is None ):
                xval.append( ("",0) )
            else:
                xtpl = (str(self.value),len(str(self.value)))
                # , separated lists can be wrapped
                if( xtpl[1] > 42 ):
                    for sc in (",","}{"):
                        xv = xtpl[0].split(sc)
                        if( len(xv) > 1 ):
                            xs = ""
                            for v in xv:
                                if( len(xs) > 42 ):
                                    xval.append( (xs,len(xs)) )
                                    xs = ""
                                xs += v
                                xs += sc
                            # last one got a , where it should not
                            xs = xs[:-1]
                            xval.append( (xs,len(xs)) )
                            return xval

                xval.append( xtpl )

        return xval


verbosity = parameter("vdb-config-verbosity",3)


def set_string( s ):
    s = s.strip()
    if(len(s) == 0):
        return
    if( s[0] == "#" ):
        return
    try:
#        print("s = '%s'" % s )
        gdb.execute(f"set {s}")
    except:
        print(f"Failed to set {s}")
#        vdb.print_exc()

def set_iterable( l ):
    for i in l:
        set_string(i)

def set( s ):
    if( isinstance(s,str) ):
        xs = s.splitlines()
        set_iterable(xs)
    else:
        set_iterable(s)

def execute_string( s ):
    s = s.strip()
    if(len(s) == 0):
        return
    if( s[0] == "#" ):
        return
    try:
#        print("s = '%s'" % s )
        gdb.execute(f"{s}")
    except:
        print(f"Failed to execute {s}")
#        vdb.print_exc()

def execute_iterable( l ):
    for i in l:
        execute_string(i)

def execute( s, origin = None ):
    global execute_origin
    execute_origin = origin
    if( isinstance(s,str) ):
        xs = s.splitlines()
        execute_iterable(xs)
    else:
        execute_iterable(s)
    execute_origin = None


def set_array_elements( cfg, d0 = ",", d1 = ":" ):
#    print("cfg.value = '%s'" % (cfg.value,) )
    cfg.elements = []
    elem = cfg.value.split(d0)
    for i in elem:
        i=i.split(d1)
        if( len(i) == 1 ):
            try:
                cfg.elements.append(int(i[0]))
            except:
                cfg.elements.append(i[0])
        elif( len(i) == 2):
            try:
                s=int(i[0])
                e=int(i[1])
                if( s > e ):
                    cfg.elements += list( range(s,e-1,-1) )
                else:
                    cfg.elements += list( range(s,e+1) )
            except:
                cfg.elements.append(i)
        else:
            try:
                s=int(i[0])
                e=int(i[1])
                r=int(i[2])
                if( s > e ):
                    cfg.elements += list( range(s,e-1,-r) )
                else:
                    cfg.elements += list( range(s,e+1,r) )
            except:
                cfg.elements.append(i)
#    print("cfg.elements = '%s'" % cfg.elements )

def show_config( argv ):
    cre = None
    verbose = False
    short = False
    if( len(argv) > 0 ):
        if( argv[0] == "/v" ):
            argv = argv[1:]
            verbose = True
        if( len(argv) > 0 and argv[0] == "/s" ):
            argv = argv[1:]
            short = True

    if( len(argv) > 0 ):
        cre = re.compile(argv[0])

    if( short ):
        for n,c in registry.items():
            if( cre is not None and cre.search(n) is None ):
                continue
            if( not c.is_default() ):
#                print("c.value = '%s'" % (c.value,) )
#                print("c.default = '%s'" % (c.default,) )
#                print("type(c.value) = '%s'" % (type(c.value),) )
#                print("type(c.default) = '%s'" % (type(c.default),) )
                print(f'set {n} = "{c.value}"')
        return

    otbl = []
    hl = ["Name","Type",("Hooked",6,-4),"Value" ]
    if( verbose ):
        hl.append("Origin")
        hl.append("Documentation")
    otbl.append( hl )
    type_map = {
            PARAM_COLOR : "color",
            gdb.PARAM_STRING : "string",
            gdb.PARAM_BOOLEAN : "bool",
            gdb.PARAM_INTEGER : "int",
            PARAM_FLOAT : "float",
            PARAM_COLOUR_LIST : "colors",
            PARAM_ARRAY : "array"
            }
    for n,c in registry.items():
        if( cre is not None and cre.search(n) is None ):
            continue
        val = c.get_vdb_show_string()

        hooked = None
        if( c.on_set is not None ):
            hooked = "X"

        first = True
        line = []
#        print("n = '%s'" % (n,) )
#        print("val = '%s'" % (val,) )
        for v in val:
            if( first ):
                line = [ n, type_map.get(c.gdb_type,c.gdb_type), hooked, v]
                if( verbose ):
                    line.append(c.origin)
                    # Hopefully nobody ever starts their documentation with this one
                    if( not c.docstring.startswith("Documentation of ")):
                        line.append(c.docstring)
                first = False
            else:
                line = [ None, None, None, v ]
            otbl.append( line )

    print( vdb.util.format_table(otbl) )

def get( cname ):
    return registry.get(cname)

def append( argv ):
#    vdb.util.bark() # print("BARK")
    if( len(argv) == 0 ):
        print("Set/a <vdb-config-parameter> [<value>]")
        return
    name = argv[0]
    if( not name.startswith("vdb-") ):
        print("We only support vdb config parameters that start with 'vdb-'")
        return
    val = None
    if( len(argv) >= 1 ):
        val = argv[1]
    c=registry.get( name, None)
    if( c is None ):
        print(f"No vdb config value named {name}, check for spelling mistakes")
        return
    c.append( val )



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
