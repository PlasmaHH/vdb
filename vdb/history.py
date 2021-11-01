#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.command
import vdb.util

import gdb

import traceback
import time
import datetime
import os
import pathlib
import sys
import string



color_marker  = vdb.config.parameter("vdb-history-colors-marker",       "#d1005c", gdb_type = vdb.config.PARAM_COLOUR)
color_bg      = vdb.config.parameter("vdb-history-colors-background",   "#303030", gdb_type = vdb.config.PARAM_COLOUR)
color_stat    = vdb.config.parameter("vdb-history-colors-statistics",   "#afaf87", gdb_type = vdb.config.PARAM_COLOUR)
color_prompt  = vdb.config.parameter("vdb-history-colors-prompt",       "#87afd7", gdb_type = vdb.config.PARAM_COLOUR)
color_match   = vdb.config.parameter("vdb-history-colors-match",        "#87af87", gdb_type = vdb.config.PARAM_COLOUR)

match_maxlen  = vdb.config.parameter("vdb-history-match-maxlen",120)
case_sensitive = vdb.config.parameter("vdb-history-match-case-sensitive",True)


class raw_input:

    def __init__( self ):
        pass

    def loop( self ):
        import termios
        import tty
        old = None
        valid = True
        try:
            old = termios.tcgetattr(sys.stdin)
#            old[3] = old[3] | termios.ECHO
            tty.setraw(sys.stdin)
            while(True):
                c = sys.stdin.read(1)
                if c == '\x03':
                    raise KeyboardInterrupt
                elif c == '\x04':
                    raise EOFError
                if( self.nextchar(c) is True ):
                    break
        except KeyboardInterrupt:
            valid = False
            pass
        except EOFError:
            valid = False
            pass
        finally:
            termios.tcsetattr( sys.stdin, termios.TCSADRAIN, old)
        return self.after_loop(valid)


class ansi:

    def __init__( self, out ):
        self.out = out

    def escape( self ):
        self.out.write("\x1b[")

    def up( self, num = 1):
        self.escape()
        self.out.write(f"{num}A")

    def down( self, num = 1):
        self.escape()
        self.out.write(f"{num}B")

    def right( self, num = 1):
        self.escape()
        self.out.write(f"{num}C")

    def left( self, num = 1):
        self.escape()
        self.out.write(f"{num}D")

    def column( self, n ):
        self.escape()
        self.out.write(f"{n}G")

    def move( self, x, y ):
        self.escape()
        self.out.write(f"{x};{y}H")

    def clear_line( self, n = 2 ):
        self.escape()
        self.out.write(f"{n}K")

    def clear_screen( self, n = 2 ):
        self.escape()
        self.out.write(f"{n}K")

    def save( self ):
        self.escape()
        self.out.write("s")

    def restore( self ):
        self.escape()
        self.out.write("u")

class fuzzy_history(raw_input):
#    def default( self, c ):
#        print("INPUT WAS %s" % c )

    def __init__( self, history, maxmatches ):
        self.maxmatches = maxmatches
        self.history = []
        for h in history:
            if( h.startswith("#") or len(h) == 0 ):
                continue
            self.history.append(h)
        self.current = ""
        self.result_display = self.maxmatches*[("","")]
        self.matches = len(self.history)
        self.marker = maxmatches
        self.escape = False
        self.escape_sequence = ""

        self.results()
        self.prompt()
        self.match()
        self.full_format()
        sys.stdout.flush()

    def prompt( self ):
        a = ansi(sys.stdout)
        a.column(0)
        a.clear_line(0)
        sys.stdout.write( vdb.color.color(">", color_prompt.value ) )
        sys.stdout.write( f" {self.current}  " )
        sys.stdout.write( vdb.color.color("<", color_prompt.value ) )
        sys.stdout.write( vdb.color.color(f" {self.matches}/{len(self.history)}", color_stat.value) )
    
    def results( self ):
        cnt=0
        for r,h in self.result_display:
            cnt += 1
            a = ansi(sys.stdout)
            a.column(0)
            a.clear_line(0)

            if( self.marker == cnt ):
                sys.stdout.write(vdb.color.color("> ",f"{color_marker.value},{color_bg.value}"))
                sys.stdout.write(vdb.color.color(r,",#333"))
            else:
                sys.stdout.write(vdb.color.color(" ",",#333"))
                sys.stdout.write(" ")
                sys.stdout.write(r)
            sys.stdout.write("\n")

    def full_format( self ):
        a = ansi(sys.stdout)
        a.save()
        a.up(len(self.result_display))
        a.column(0)
        a.clear_screen(0)
        self.results()
        self.prompt()
        a.restore() # mainly for the row only
        a.column(3 + len(self.current))

    def entry_matches( self, search, string ):
        if( len(search) == 0 ):
            return string
        idx = 0
        hlstring = ""
        nfstring =  ""
        for sidx in range(0,len(string)):
#            print("sidx = '%s'" % (sidx,) )
#            print("nfstring = '%s'" % (nfstring,) )
#            print("hlstring = '%s'" % (hlstring,) )
            s = string[sidx]
#            if( s == search[idx] ):
            a = s
            b = search[idx]
            if( not case_sensitive.value ):
                a = a.casefold()
                b = b.casefold()
            if( a == b ):
                if( len(nfstring) < match_maxlen.value ):
                    hlstring += vdb.color.color(s,color_match.value)
#                    hlstring += "*"
                idx += 1
                if( idx >= len(search) ):
#                    print()
#                    print("search = '%s'" % (search,) )
#                    print("string = '%s'" % (string,) )
#                    print("nfstring = '%s'" % (nfstring,) )
#                    print("len(nfstring) = '%s'" % (len(nfstring),) )
                    tail = string[sidx+1:]
#                    print("tail = '%s'" % (tail,) )
                    if( len(nfstring) < match_maxlen.value ):
                        if( len(string) < match_maxlen.value ):
                            hlstring += tail
                        else:
                            tailtail = tail[: match_maxlen.value - len(nfstring) ]
#                            print("tailtail = '%s'" % (tailtail,) )
                            hlstring += tailtail
#                    print("hlstring = '%s'" % (hlstring,) )
#                    print()
                    return hlstring
            else:
                if( len(nfstring) < match_maxlen.value ):
                    hlstring += s
            if( len(nfstring) < match_maxlen.value ):
                nfstring += s
        return None

    def match( self ):
#        rstr = ""
#        for c in self.current:
#            rstr += re.escape(c) + ".*"
#        sre=re.compile(rstr)

        self.result_display = self.maxmatches*[("","")]
        ridx = self.maxmatches
        self.matches = 0
        for h in reversed(self.history):
            a = ansi(sys.stdout)
            a.column(0)
            a.clear_line(0)
#            sys.stdout.write(f"Testing item {h} against {rstr}")
#            if( sre.search(h) is not None ):
            m = self.entry_matches( self.current, h )
            if( m is not None ):
                self.matches += 1
                ridx -= 1
                if( ridx >= 0 ):
                    if( m is None ):
                        m = ""
                    self.result_display[ridx] = (m,h)

        self.full_format()

    def nextchar( self, c ):
        if( self.escape ):
            self.escape_sequence += c
            if( self.escape_sequence == "[" ): # wait for more
                return False
            elif( self.escape_sequence == "[A" ): # arrow up
                self.marker = max(self.marker-1,1)
            elif( self.escape_sequence == "[B" ): # arrow down
                self.marker = min(self.marker+1,self.maxmatches)
            self.escape = False
            self.full_format()
            sys.stdout.flush()
            return False

        if( ord(c) == 13 ):
            return True

        if( ord(c) == 127 ):
            self.current = self.current[:-1]
        elif( ord(c) == 27 ): # escape char
            self.escape = True
            self.escape_sequence = ""
            return False
        elif( c in string.printable and not ( c in "\t\n\r\v\f") ):
            self.current += c
            sys.stdout.write(c)
        else: # ignore non printables for now
            return False
        self.match()

#        sys.stdout.write("\r")
#        sys.stdout.write(self.current)
        sys.stdout.flush()
        self.escape = False
        return False

    def after_loop( self, valid ):
        a = ansi(sys.stdout)
        a.column(0)
        a.clear_line(0)
        sys.stdout.flush()
        return valid

    def get( self ):
        return self.result_display[self.marker-1][1]


def extract_gdb_history( ):
    hsize = gdb.execute("show history size",False,True)
    hsize = hsize.split()[-1]
    hsize = int(hsize[:-1])
    retd = {} 
    for i in range(0,hsize,10):
#        print("i = '%s'" % (i,) )
        cmds = gdb.execute(f"show commands {i}",False,True).splitlines()
#        print("cmds = '%s'" % (cmds,) )
        for cmd in cmds:
            lc = cmd.split()
            num = lc[0]
            fw = lc[1]
            fwidx = cmd.find(fw)
            cmd = cmd[fwidx:]
            if( cmd.startswith("fz ") ):
                cmd = cmd[3:]
            retd[num] = cmd
    return list(retd.values())

class cmd_fz (vdb.command.command):
    """Fuzzy search the history"
"""

    def __init__ (self):
        super (cmd_fz, self).__init__ ("fz", gdb.COMMAND_RUNNING)
        self.dont_repeat()
        self.last_returned = None

    def complete( self, text, word ):
#        print("text = '%s'" % (text,) )
#        print("word = '%s'" % (word,) )
        if( word is not None ):
            return self.last_returned
        try:
            history = extract_gdb_history()
            fz=fuzzy_history(history,20)
            if( fz.loop() ):
                ret = fz.get()
                self.last_returned = [ret]
            else:
                self.last_returned = []
            print( vdb.prompt.refresh_prompt() + "fz ", end = "" )
            return self.last_returned
        except:
            traceback.print_exc()
            raise
            pass
        return []

    def invoke (self, arg, from_tty):
        if( len(arg) == 0 ):
            print("This special command needs to be invoked as fz<tab><tab>")
            return None
            fz = fuzzy_history([],20)
            fz.after_loop(True)
            history = extract_gdb_history()
            for h in history:
                fz.entry_matches("gdb.his",h)
        else:
            try:
                gdb.execute(arg,from_tty,False)
            except gdb.error as e:
                print(f"gdb.error: {e}")

cmd_fz()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
