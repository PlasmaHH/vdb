#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import colors

def color( s, cs ):
    s=str(s)
    if( cs is None ):
        return s
    cs = cs.split(",")
    if( len(cs) == 1 ):
        return colors.color(s,cs[0])
    else:
        cs += ["","",""]
        return colors.color(s,fg=cs[0],bg=cs[1],style=cs[2])

def scolor( s, cs ):
    try:
        return color(s,cs)
    except:
        return colors.color(s,fg="red",style="underline")




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
