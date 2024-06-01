#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import vdb.command
import vdb.event
import vdb.util
import vdb.config

import gdb

import functools
import traceback
import os
import subprocess
import socket
import sys
import threading
import re
import datetime


"""
tmux new-session\; select-pane -T "disassembler" \; split-window -v\; select-pane -T "hexdump" \; split-window -h \; select-pane -T "registers"
"""
show_stat = vdb.config.parameter("vdb-dash-show-stats",False)
disable_silent = vdb.config.parameter("vdb-dash-disable-silent",False)
auto_time = vdb.config.parameter("vdb-dash-auto-disable-time", 10.0 )
append_time = vdb.config.parameter("vdb-dash-append-time",True)
time_format = vdb.config.parameter("vdb-dash-append-time-format","%c {runtime:10.4f}s")

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

    def flush( self ):
        pass

    def name( self ):
        return "port"

    def target( self ):
        clts = f"[{len(self.targets)}]"
        if( self.host == "0.0.0.0" ):
            return f"*:{self.port} {clts}"
        else:
            return f"{self.host}:{self.port} {clts}"

class null(target):

    def __init__( self ):
        super().__init__()

    def write( self, output ):
        return len(output)

    def flush( self ):
        return None

    def name( self ):
        return "null"

    def target( self ):
        return None



tty_cache: dict[str,str] = { }

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
            raise gdb.error(f"Could not open {tty_name} ({tty_name})")
        self.file = f

    def write( self, output ):
        return self.file.write(output)

    def flush( self ):
        return self.file.flush()

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
            vline = line.split("{|}")
#            print("line = '%s'" % line )
            # or regex?
#            if( line[0] == pane_name ):
            if( re.match( pane_name, vline[0] ) ):
                tty = vline[1]
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

    def set_state( self, to , reason = None ):
        if( self.enabled != to ):
            if( self.output is not None ):
                nst = "Disabled"
                if( to is True ):
                    nst = "Enabled"

                if( disable_silent.value is not True ):
                    self.output.write(f"{nst} dashboard {self.id}, reason: {reason}" )
                    self.output.flush()
        self.enabled = to

    def enable( self, reason ):
        self.set_state(True,reason)

    def disable( self, reason ):
        self.set_state(False,reason)

    def do_output( self ):
        sw = vdb.util.stopwatch()
        sw.start()
        cout=""
#        print("some dashboard: %s" % self.command)
        try:
            cout = gdb.execute(self.command,False,True)
        except gdb.error as ge:
            cout = "dashboard: %s" % str(ge)
        except:
            cout = traceback.format_exc()

#        print("cout = '%s'" % cout )
        if( self.cls ):
            self.output.write("\033[2J\033[H")
        if( show_stat.value ):
            sw.stop()
            sofar = sw.get()
            bts = len(cout)
            self.output.write(f"{sofar:.7}s, {bts}B\n")
        self.output.write(cout)
        self.output.flush()
        sw.stop()
        self.last_time = sw.get()
        if( append_time.value is True ):
            runtime = sw.get()
            now = datetime.datetime.now().strftime(time_format.value)
            now = now.format(**locals())
            self.output.write(now)
            self.output.flush()
        if( self.last_time > auto_time.fvalue ):
            self.disable("Execution time exceeded: %s" % auto_time.value )



    def on_event( self ):
        if( not self.enabled ):
            return
        if( self.output is not None ):
            if( self.output.enabled ):
                self.do_output()
dash_events: dict[str,list[dashboard]] = { }

def show_dashboard( ):
    tbl = []
    tbl.append( ["EN","CLS","ID","Type","Target","Event(s)","Command","ExTime"] )
    id2events = {}
    id2dash = {}
    for on,evl in dash_events.items():
        for db in evl:
            id2events.setdefault(db.id,[]).append(str(on))
            id2dash[db.id] = db

    for id,db in id2dash.items():
        en = "N"
        if( db.enabled ):
            en = "Y"
        typ = db.output.name()
        tgt = db.output.target()
        ev = ",".join(id2events[id])
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
                db.set_state( to, "command" )
                return

def trigger_cls( id, to ):
    id = int(id)
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                db.cls = to
                return

class output_redirect:

    def __init__( self, output ):
        self.output = output
        self.enabled = True
        self.id = vdb.util.next_id("dashboard")
        self.command = "<log>"
        self.cls = False
        self.last_time = 0

    def set_state( self, to , reason = None ):
        self.enabled = to

    def print( self, msg ):
        if( not self.enabled ):
            print(msg)
#        print("Redirecting output %s" % msg )
#        print("self.output.tty = '%s'" % (self.output.tty,) )
#        print("self.output.file = '%s'" % (self.output.file,) )
        ret = self.output.write(msg)
#        print("ret = '%s'" % (ret,) )
        ret = self.output.write("\n")
#        print("ret = '%s'" % (ret,) )
        ret = self.output.flush()
#        print("ret = '%s'" % (ret,) )
    def on_event( self ):
        return None

def modify_board( argv ):
    id = int(argv[0])
    argv = argv[1:]
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                old = db.command
                db.command = " ".join(argv)
                print(f"Modified dash {id} to {db.command} (old was {old})")

def add_events( events, d ):
    for e in events:
        dash_events.setdefault(e,[]).append(d)
        vdb.event.on(e,dash_on,e)

def add_board( tgt, argv ):
#    vdb.util.bark() # print("BARK")
    global dash_events
    events = set( [ "before_prompt" ] )
    nevents = set()

    nargv = []
    for a in argv:
        if( a.startswith("on:") ):
            nevents.add( a[3:] )
        else:
            nargv.append(a)
    argv = nargv

    if( len(nevents) != 0):
        events = nevents
#    print(f"{events=}")

    # A special "log" command that basically means to redirect stuff to that dashboard
    if( argv[0] == "log" ):
        od = output_redirect(tgt)
        vdb.util.console_logprint = od.print
        add_events(events,od)
        return
    cmd = " ".join(argv)
#    print("cmd = '%s'" % cmd )
    db = dashboard()
    db.output = tgt
    db.command = cmd
    add_events(events,db)

def del_board( id ):
    id = int(id)
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                evl.remove(db)
#                db.enabled = to
                return

def call_dashboard( argv ):
    # ?type: tmux,port,tty
    # subcommands: list,enable,disable,erase
    if( len(argv) == 0 ):
        raise gdb.error(cmd_dashboard.__doc__)
#    print("argv = '%s'" % argv )
    if( "tty".startswith(argv[0]) ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard tty, need at least 2 parameters")
        tgt = tty(argv[1])
        add_board(tgt,argv[2:])
    elif( "null".startswith(argv[0]) ):
        tgt = null()
        add_board(tgt,argv[1:])
    elif( "tmux".startswith(argv[0]) ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard tmux, need at least 2 parameters")
        tgt = tmux(argv[1])
        add_board(tgt,argv[2:])
    elif( "port".startswith(argv[0]) ):
        if( len(argv) < 3 ):
            raise gdb.error("dashboard port, need at least 2 parameters")
        tgt = port(argv[1])
        add_board(tgt,argv[2:])
    elif( "delete".startswith(argv[0]) ):
        del_board(argv[1])
    elif( "show".startswith(argv[0]) ):
        show_dashboard()
    elif( "enable".startswith(argv[0]) ):
        trigger_dashboard(argv[1],True)
    elif( "disable".startswith(argv[0]) ):
        trigger_dashboard(argv[1],False)
    elif( "modify".startswith(argv[0]) ):
        modify_board(argv[1:])
    elif( "cls".startswith(argv[0]) ):
        trigger_cls(argv[1],True)
    elif( "nocls".startswith(argv[0]) ):
        trigger_cls(argv[1],False)
    else:
        print("%s? What do you mean?" % argv[0])

def dash_on(evname):
#    print(f"dash_on({evname=})")
    for ev in dash_events.get(evname,[]):
        ev.on_event()



class cmd_dashboard (vdb.command.command):
    """Automatically run commands to display information on various outputs to assemble dashboards

dashboard <subcommand> [<parameters>]

Available subcommands:

tty <tty>   <command> - Output on the specified tty, /dev/ may be omitted
tmux <pane> <command> - Searches for a tmux pane matching the regex <pane>
port <port> <command> - opens a server at port <port> and outputs there

delete <id>           - deletes board with the given <id>
enable <id>           - enables the (previously disabled) board with <id>
disable <id>          - disables the board with <id> (no longer outputs, but keeps connection)
cls <id>              - Enables clearing screen (^L) before sending everything
nocls <id>            - Don't cleare screen before sending
modify <id> <command> - change the command of the given ID
show                  - Show an overview over the existing dashboards and their targets

The command will be run before displaying a prompt and then output to the dashboard chosen

Remember that you can use dash as short as long as no other command collides with it
    """

    def __init__ (self):
        super ().__init__ ("dashboard", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv):
        try:

#            import cProfile
#            cProfile.runctx("call_dashboard(argv)",globals(),locals())
            call_dashboard(argv)
        except gdb.error as ge:
#            traceback.print_exc()
            vdb.util.log(f"dashboard: {ge}", level=vdb.util.Loglevel.warn)

        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_dashboard()

# TODO/Ideas
# modifier to show top/bottom N rows of command only

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
