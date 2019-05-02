#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.command
import vdb.event
import vdb.cache

import gdb

import functools
import traceback
import os
import subprocess
import socket
import sys
import threading
import re


"""
tmux new-session\; select-pane -T "disassembler" \; split-window -v\; select-pane -T "hexdump" \; split-window -h \; select-pane -T "registers"
"""
class target:
    def __init__( self ):
        super().__init__()
        self.enabled = True

class port(target,threading.Thread):
    def __init__( self, hp ):
        super().__init__()
        ahp=hp.split(":")
        host = "0.0.0.0"
        lport = 0
        if( len(ahp) == 1 ):
            lport = int(ahp[0])
        elif( len(ahp) == 2 ):
            host = ahp[0]
            lport = int(ahp[1])
        else:
            raise gdb.error("Invalid host:lport/lport argument %s" % hp )
        # open a listen lport, find a way to accept it asynchronously (threading??) and output to all of them
        # host None means 0.0.0.0
#        print("host = '%s'" % host )
#        print("lport = '%s'" % lport )
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind( (host,lport) )
        sock.listen(1)
        self.sock = sock
        self.host = host
        self.port = lport
        self.enabled = False
        self.targets = []
        self.start()

    def run( self ):
        while True:
            a,r = self.sock.accept()
#            print("(a,) = '%s'" % (a,) )
            self.targets.append(a)
            a.send(b"CONNECTED\n")
            self.enabled = True

    def write( self, data ):
        remaintargets = []
        for t in self.targets:
            try:
                t.send(data.encode("utf-8"))
                remaintargets.append(t)
            except:
                pass
        self.targets = remaintargets
        if( len(self.targets) == 0 ):
            self.enabled = False

    def name( self ):
        return "port"

    def target( self ):
        clts = f"[{len(self.targets)}]"
        if( self.host == "0.0.0.0" ):
            return f"*:{self.port} {clts}"
        else:
            return f"{self.host}:{self.port} {clts}"

tty_cache = { }

class tty(target):

    def try_open( self, fn, mode = "w" ):
        fn = os.path.realpath(fn)
        global tty_cache
        f = tty_cache.get(fn)
        if( f is None ):
            f = open(fn,mode)
            if( f is not None ):
                tty_cache[fn] = f
        return f

    def __init__( self, tty_name ):
        super().__init__()
        self.tty = tty_name

        f = self.try_open(tty_name)
        if( f is None ):
            f = self.try_open("/dev/" + tty_name)
        if( f is None ):
            raise gdb.error(f"Could not open {tty_name} ({fn})")
        self.file = f

    def write( self, output ):
        self.file.write(output)

    def name( self ):
        return "tty"

    def target( self ):
        return str(self.tty)

class tmux(tty):
    def __init__( self, pane_name ):
        p = subprocess.run([ "tmux", "list-panes","-a","-F","#{pane_title}{|}#{pane_tty}" ], encoding = "utf-8", stdout = subprocess.PIPE )
#        print("p = '%s'" % p )
        output = p.stdout.splitlines()
        tty = None
        self.pane = pane_name
        for line in output:
            line = line.split("{|}")
#            print("line = '%s'" % line )
            # or regex?
#            if( line[0] == pane_name ):
            if( re.match( pane_name, line[0] ) ):
                tty = line[1]
                break
        if( tty is None ):
            raise gdb.error("Could not find tmux pane named %s" % pane_name )
#        print("tty = '%s'" % tty )
        super().__init__(tty)

    def name( self ):
        return "tmux"

    def target( self ):
        return f"{self.pane} ({self.tty})"

class dashboard:
    def __init__( self ):
        # support multiple targets, run through them
        self.output = None
        self.id = vdb.util.next_id("dashboard")
        self.command = None
        self.enabled = True
        self.cls = True
        self.last_time = 0

    def do_output( self ):
        sw = vdb.cache.stopwatch()
        sw.start()
#        print("some dashboard: %s" % self.command)
        cout = gdb.execute(self.command,False,True)

#        print("cout = '%s'" % cout )
        if( self.cls ):
            self.output.write("\033[2J\033[H")
        self.output.write(cout)
        sw.stop()
        self.last_time = sw.get()


    def on_event( self ):
        if( not self.enabled ):
            return
        if( self.output is not None ):
            if( self.output.enabled ):
                self.do_output()
dash_events = { }

def show_dashboard( ):
    tbl = []
    tbl.append( ["EN","CLS","ID","Type","Target","Event(s)","Command","ExTime"] )
    for on,evl in dash_events.items():
        for db in evl:
#            print("on = '%s'" % on )
#            print("db = '%s'" % db )
            en = "N"
            if( db.enabled ):
                en = "Y"
            id = db.id
            typ = db.output.name()
            tgt = db.output.target()
            ev = on
            cmd = db.command
            cls = "N"
            if( db.cls ):
                cls = "Y"
            t = db.last_time

            line  = [str(en),str(cls),str(id),str(typ),str(tgt),str(ev),str(cmd),str(t)]
            tbl.append(line)
            # Enabled ID   Type  target  event(s)   command
    txt = vdb.util.format_table(tbl)
    print(txt)

def trigger_dashboard( id, to ):
    id = int(id)
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                db.enabled = to
                return

def trigger_cls( id, to ):
    id = int(id)
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                db.cls = to
                return

def add_board( tgt, argv ):
    cmd = " ".join(argv)
#    print("cmd = '%s'" % cmd )
    db = dashboard()
    global dash_events
    db.output = tgt
    db.command = cmd
    delist = dash_events.setdefault("before_prompt",[])
    delist.append(db)


def call_dashboard( argv ):
    # type: tmux,port,tty
    # subcommands: list,enable,disable,erase
    if( len(argv) == 0 ):
        raise gdb.error("You need to give at least some parameter")
#    print("argv = '%s'" % argv )
    if( argv[0] == "tty" ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard tty, need at least 2 parameters")
        tgt = tty(argv[1])
        add_board(tgt,argv[2:])
    elif( argv[0] == "tmux" ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard tmux, need at least 2 parameters")
        tgt = tmux(argv[1])
        add_board(tgt,argv[2:])
    elif( argv[0] == "port" ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard port, need at least 2 parameters")
        tgt = port(argv[1])
        add_board(tgt,argv[2:])
    elif( argv[0] == "show" ):
        show_dashboard()
    elif( argv[0] == "enable" ):
        trigger_dashboard(argv[1],True)
    elif( argv[0] == "disable" ):
        trigger_dashboard(argv[1],False)
    elif( argv[0] == "cls" ):
        trigger_cls(argv[1],True)
    elif( argv[0] == "nocls" ):
        trigger_cls(argv[1],False)
    else:
        print("%s? What do you mean?" % argv[0])



@vdb.event.before_prompt("before_prompt")
def dash_on(evname):
    for ev in dash_events.get(evname,[]):
        ev.on_event()



class cmd_dashboard (vdb.command.command):
    """Shows a dashboard of a specified memory range"""

    def __init__ (self):
        super ().__init__ ("dashboard", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:

#            import cProfile
#            cProfile.runctx("call_dashboard(argv)",globals(),locals())
            call_dashboard(argv)
        except gdb.error as ge:
            print(ge)
        except:
            traceback.print_exc()
            raise
            pass

cmd_dashboard()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
