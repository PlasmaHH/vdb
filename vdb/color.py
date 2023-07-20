#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import colors
import vdb.util

def color( s, cs ):
    s=str(s)
    if( cs is None ):
        return s
    if( not isinstance(cs,list) ):
        cs = cs.split(",")
    if( len(cs) == 1 ):
        return colors.color(s,cs[0])
    else:
        cs += ["","",""]
        return colors.color(s,fg=cs[0],bg=cs[1],style=cs[2])

@vdb.util.memoize()
def mcolor( s, cs ):
    return color(s,cs)

def colorl( s, cs ):
    return ( color(s,cs),len(s))

def concat_lst( lst ):
    ret = lst[0]
    if( isinstance(ret,str) ):
        ret = (ret,len(ret))
    for l in lst[1:] :
        ret = concat(ret,l)

    return ret

def concat( ltpl, rtpl = None ):
    """concatenate a string and its display lengths"""
    if( rtpl is None ):
        return concat_lst(ltpl)

    ls,ll = ltpl
    if( isinstance(rtpl,str) ):
        rs = rtpl
        rl = len(rs)
    else:
        rs,rl = rtpl
    return ( ls+rs,ll+rl )


# readline safe (?) colouring
def color_rl( s, cs ):
    # these special characters will make libreadline handle searches better
    # https://wiki.hackzine.org/development/misc/readline-color-prompt.html
    s = "\x02" + s + "\x01" # STX + s + SOH
    s = color(s,cs)
    s = "\x01" + s + "\x02" # SOH + s + STX
    # This way we should end up with \1<colorcode>\2<text>\1<colorcode>\2
    return s

def scolor( s, cs ):
    try:
        return color(s,cs)
    except:
        return colors.color(s,fg="red",style="underline")

def strip( s ):
    return colors.strip_color(s)

class color_str:

    def __init__( self, s, col = None ):
        self.s = s
        if( isinstance( s, str ) ):
            self.len = len(s)
        elif( isinstance( s, color_str ) ):
            if( col is not None ):
                self.s = strip(s.s)
                self.len = len(self.s)
            else:
                self.len = s.len
        else:
            raise RuntimeError(f"Expected str or color_str, got {type(s)}")
        self.color = col
#        print("repr(self) = '%s'" % (repr(self),) )

    def __repr__( self ):
        return f"color_str( s={self.s}, col={self.color}, len={self.len} )"


    def __len__( self ):
        return self.len

    def __str__( self ):
        if( self.color is not None ):
            ret = color(self.s,self.color)
        else:
            ret = self.s
        return ret

    def __add__( self, rhs ):
        if( self.color is not None ):
            self.s = color(self.s,self.color)
            self.color = None
        if( isinstance(rhs,str) ):
            self.s += rhs
        else:
            self.s += str(rhs)
        self.len += len(rhs)
#        print("repr(self) = '%s'" % (repr(self),) )
        return self

    def __radd__( self, lhs ):
        lhs=color_str(lhs)
        return lhs+self







# vim: tabstop=4 shiftwidth=4 expandtab ft=python
