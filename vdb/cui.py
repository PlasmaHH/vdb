#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util

import gdb
import gdb.types

import os
import traceback
import curses
import time
import re

# So, why not (n)curses? Well, mostly because of colours and lacking colour change support in a lot of terminals that
# otherwise support "true colour" ansi escape sequences. This together with a often not correctly set TERM variable will
# mess things up and we really don't want people to have to mess around with these things to experience the extended
# colours. Additionally it would limit us to a palette of 256 colours which one day might not be enough (as of writing
# this we could have up to 99 different at once active )

split_re=re.compile('(\x1b\\[(?:K|.*?m))')



class window:
    """
    An ascii window. We support optional borders and write functions that will not do anything outside the window. 
    Not redraw. No buffering. No writing over anything thats already there. No scrolling support.
    """

    def __init__( self ):
        self.origin_x = 0
        self.origin_y = 0
        self.width = 0
        self.height = 0
        self.wrap = False
        self.parent = None
        """
        Styling ideas:
        - background and foreground colour (for all standard text, normal will be translated to this but not other)
          - one for focus, one for not focus
        - line style for border ( - = and bg/fg)
          - one for focus, one not for focus
          - can be 0 too or just for one side ( for split windows? )
        """

    def _check_terminal( self ):
        """
        Internal function to check where possible if the terminal can do what we want and if not, throw an exception.
        Should we maybe do that generally for all colours too?
        """
        pass

    def at( self, x, y, s, col = None ):
        """
        Print entity s at position x,y, where s is either a plain uncoloured string or a pair of coloured string and
        length. Optional col is a colour string.
        String cut off/wrap is depending on the window setting.

        Use-case: mostly fzf search and similar. also internal implementation of scrolling possibly.
        """
        passA

    def append( self, s, col = None ):
        """
        Append a string to the "buffer". Will cause existing entries to scroll up? 
        """
        pass

    def resize( self, w, h ):
        """
        Resize to the new width and height
        """
        pass

    def move( self, x, y ):
        """
        Move origin to these new coordinates
        """
        pass

    def focus( self ):
        """
        Set focus on this window. Will remove focus from everywhere else
        """
        pass

    def close( self ):
        """
        might be necessary to inform the parent
        """
        pass

    def cursor( self, x, y ):
        """
        Set the cursor to that position
        """
        pass

class split_window:
    """
    "wraps" two windows that split some existing window or a "root window". Every resize of the border between them will
    resize the other too.
    """
    pass


# This is going to be terribly slow for strings that contain many colours but at least it should work
def ansi_output( scr, s ):
    s = split_re.split(s)
    out = None
    code = 0
    for c in s:
        if( c[0] == "\x1b" ):
            c=c[2:-1]
            if( out is not None ):
#                scr.addstr(f"{code=}")
                scr.addstr(out,code)
                out = None
            code = get_color_code(c)
        else:
            out = c
    if( out is not None ):
        scr.addstr(out,code)
#    scr.addstr(str(s))

def cui_loop( scr ):
    curses.cbreak()
    global dscr
    dscr=scr

    print("WITHIN LOOP")
    gdb.execute("start")
#    dis=gdb.execute("dis",False,True)
    dis=gdb.execute("reg foo",False,True)
    curses.cbreak() # gdb seems to disable it, alwways enable it again before getkey
    curses.use_default_colors()

    ansi_output( scr, dis )

    k=scr.getkey()


class cmd_cui(vdb.command.command):
    """Manage cui file loading and the interaction with the register display

cui list      - Lists known CPU definitions
cui load <ID> - Loads cui CPU definitions
cui scan      - Scan configured list of directories and (re)reads the found cui definitions
"""

    def __init__ (self):
        super (cmd_cui, self).__init__ ("cui", gdb.COMMAND_DATA)

    def do_invoke (self, argv ):
        self.dont_repeat()

        try:
            curses.wrapper( cui_loop )
        except Exception as e:
            vdb.print_exc()
        print("curses.COLORS = '%s'" % (curses.COLORS,) )
        print("curses.COLOR_PAIRS = '%s'" % (curses.COLOR_PAIRS,) )

cmd_cui()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
