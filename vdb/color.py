#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import colors
import vdb.util

def _strip( cs ):
    if( cs is not None ):
        cs = cs.strip()
    return cs

def color( s, cs ):
    s=str(s)
    if( cs is None ):
        return s
    if( not isinstance(cs,list) ):
        cs = cs.split(",")
    if( len(cs) == 1 ):
        return colors.color(s,cs[0].strip())
    else:
        cs += ["","",""]
        return colors.color(s,fg=_strip(cs[0]),bg=_strip(cs[1]),style=_strip(cs[2]))

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

def get_luminance( color):
    """
    Calculate the luminance of a CSS color (hex format).
    """
    # Remove the '#' character
    color = color[1:]
    # Parse RGB components
    r = int(color[0:2], 16) / 255.0
    g = int(color[2:4], 16) / 255.0
    b = int(color[4:6], 16) / 255.0

    # Convert to linear RGB
    def linearize(x):
        if x <= 0.03928:
            return x / 12.92
        else:
            return ((x + 0.055) / 1.055) ** 2.4

    r_linear = linearize(r)
    g_linear = linearize(g)
    b_linear = linearize(b)

    # Calculate luminance
    return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

@vdb.util.memoize()
def get_best_foreground_color( background_color):
    """
    Returns the best foreground color (black or white) for the given background.
    """
    luminance = get_luminance(background_color)
    if( luminance > 0.5 ):
        return "#000000"
    else:
        return "#ffffff"


class gradient:
    def __init__( self, colors ):
        self.colors = list(sorted( colors ))

    def get( self, val ):
#        print(f"get( {val=} )")
        oldcol = self.colors[0]
        for col in self.colors:
            if( val <= col[0] ):
                break
            oldcol = col

#        print(f"{oldcol=}")
#        print(f"{col=}")
        xrange = col[0] - oldcol[0]
#        print(f"{xrange=}")
        xnor = val - oldcol[0]
#        print(f"{xnor=}")
        if( xrange != 0 ):
            xnor /= xrange
        bg_col = self.calc_gradient( oldcol[1], col[1],xnor )
        fg_col = get_best_foreground_color( bg_col )

        return (bg_col, fg_col)


    def calc_gradient( self, colorl, colorr, x ):
        rl = int(colorl[1:3],16)
        gl = int(colorl[3:5],16)
        bl = int(colorl[5:7],16)

        rr = int(colorr[1:3],16)
        gr = int(colorr[3:5],16)
        br = int(colorr[5:7],16)

        r = round( rl + x*(rr-rl))
        g = round( gl + x*(gr-gl))
        b = round( bl + x*(br-bl))

        ret = f"#{r:02x}{g:02x}{b:02x}"
#    print(f"{ret=}")
        return ret










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
