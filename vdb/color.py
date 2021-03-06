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

def colorl( s, cs ):
    return ( color(s,cs),len(s))

# readline safe (?) colouring
def color_rl( s, cs ):
    # these special characters will make libreadline handle searches better
    s = "\x02" + s + "\x01" # STX + s + SOH
    s = color(s,cs)
    s = "\x01" + s + "\x02" # SOH + s + STX
    return s

def scolor( s, cs ):
    try:
        return color(s,cs)
    except:
        return colors.color(s,fg="red",style="underline")




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
