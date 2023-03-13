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
        p = subprocess.run([ "tmux", "list-panes","-a","-F","#{pane_title}{|}#{pane_tty}{|}#{session_name}" ], encoding = "utf-8", stdout = subprocess.PIPE )
#        print("p = '%s'" % p )
        output = p.stdout.splitlines()
        tty = None
        ps = pane_name.split("@")
        print("ps = '%s'" % (ps,) )
        if( len(ps) == 2 ):
            self.pane = ps[0]
            self.session = ps[1]
        else:
            self.pane = pane_name
            self.session = None
        print("self.pane = '%s'" % (self.pane,) )
        print("self.session = '%s'" % (self.session,) )
        for line in output:
            line = line.split("{|}")
            print("line = '%s'" % line )
            # or regex?
            if( re.match( self.pane, line[0] ) ):
                if( self.session is not None ):
                    if( re.match( self.session, line[2] ) ):
                        tty = line[1]
                else:
                    tty = line[1]
                    break
        if( tty is None ):
            raise gdb.error("Could not find tmux pane %s" % pane_name )
        print("tty = '%s'" % tty )
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
                db.set_state( to )
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

def add_board( tgt, argv ):
#    vdb.util.bark() # print("BARK")
    global dash_events
    # A special "log" command that basically means to redirect stuff to that dashboard
    if( argv[0] == "log" ):
        od = output_redirect(tgt)
        vdb.util.console_logprint = od.print
        dash_events.setdefault("before_prompt",[]).append(od)
        return
    cmd = " ".join(argv)
#    print("cmd = '%s'" % cmd )
    db = dashboard()
    db.output = tgt
    db.command = cmd
    delist = dash_events.setdefault("before_prompt",[])
    delist.append(db)

def del_board( id ):
    id = int(id)
    global dash_events
    for on,evl in dash_events.items():
        for db in evl:
            if( db.id == id ):
                evl.remove(db)
#                db.enabled = to
                return

def tmux_panes( ):
    cmd = [ "tmux", "list-panes", "-a", "-F", "#{pane_id}{|}#{pane_title}{|}#{pane_tty}{|}#{session_name}" ]
    p = subprocess.run( cmd, encoding = "utf-8", stdout = subprocess.PIPE )
    print("p.stdout = '%s'" % (p.stdout,) )
    output = p.stdout.splitlines()
    pane2id = {} # plane mappings of pane names to id|tty pair
    session = {} # the same mapping but per session name
    for pane in output:
        pane_id,pane_title,pane_tty,session_name = pane.split("{|}")
        ses_pane2id = session.setdefault(session_name,{})
        pane2id[pane_title] = ( pane_id, pane_tty )
        ses_pane2id[pane_title] = ( pane_id, pane_tty )
    print("pane2id = '%s'" % (pane2id,) )
    print("session = '%s'" % (session,) )
    return ( session, pane2id )

def run_tmux( args ):
    cmd  = [ "tmux" ] + args
    print("cmd = '%s'" % (cmd,) )
    p = subprocess.run( cmd, encoding = "utf-8", stdout = subprocess.PIPE )
    return p

def do_xmux( argv ):
    print("argv = '%s'" % (argv,) )

    spanes,panes = tmux_panes()

    spp = argv[0]

    pane_size = None
    if( spp[-1] == "]" ): # end is [#] size spec
        spp,pane_size = spp[:-1].split("[")

    print("spp = '%s'" % (spp,) )
    print("pane_size = '%s'" % (pane_size,) )

    dash_alias = None
    spl = spp.split("|")
    if( len(spl) > 1 ):
        spp,dash_alias = spl

    print("spp = '%s'" % (spp,) )
    print("dash_alias = '%s'" % (dash_alias,) )

    spl = spp.split(":")
    old_pane = None
    new_pane = None
    if( len(spl) > 1 ):
        old_pane = spl[0]
        new_pane = spl[1]
    else:
        new_pane = spp

    print("old_pane = '%s'" % (old_pane,) )
    print("new_pane = '%s'" % (new_pane,) )

    old_session = None

    spl = old_pane.split("@")
    if( len(spl) > 1 ):
        old_pane = spl[0]
        if( len(old_pane) == 0 ):
            old_pane = None
        old_session = spl[1]

    print("old_pane = '%s'" % (old_pane,) )
    print("old_session = '%s'" % (old_session,) )

    print("spanes = '%s'" % (spanes,) )
    output_pane_id = None
    created = False
    spanes,panes = tmux_panes()
    # The old session could not be found, no matter what, we need to create it
    if( old_session is not None and old_session not in spanes ):
        print(f"tmux session {old_session} not found, creating")
        create_cmd = [ "new-session", "-d", "-s", old_session ]
        p = run_tmux( create_cmd )
        created = True
        spanes,panes = tmux_panes() # update information
        # should contain onl that one element, the pane with the new session
        npane = spanes[old_session]
        pane_id,_ = next(iter(npane.values()))
        print("NEW SESSION")
        print("npane = '%s'" % (npane,) )
        print("pane_id = '%s'" % (pane_id,) )

        output_pane_id = pane_id
        if( old_pane is not None ):
            name_cmd = [ "select-pane", "-t", pane_id, "-T", old_pane ]
            p = run_tmux( name_cmd )
        spanes,panes = tmux_panes() # update information

    # detailed cases:
    # input    : oldpane@session:newpane
    # case 0.1 : no session with that name
    #   result : one new session, two panes, one with the old name, one with the new one
    # case 0.2 : session with that name, no oldpane, newpane present
    # case 0.3 : session with that name, no oldpane, no newpane present
    # case 0.4 : session with that name, oldpane, no newpane present
    # case 0.5 : session with that name, oldpane, newpane present
    # input    : @session:newpane
    # case 1.1 : no session with that name
    #   result : session created, single pane with name newpane
    # case 1.2 : session with that name, newpane present
    #   result : take newpane for output
    # case 1.3 : session with that name, no newpane present
    #   result : create a new pane out of the last pane of that session
    # input    : oldpane:newpane
    # session will be determined by oldpane. If oldpane cannot be found or is duplicated, an error will be thrown
    # case 2.4 : session with that name, oldpane, no newpane present
    #   result : newpane is split of oldpane
    # case 2.5 : session with that name, oldpane, newpane present
    #   result : take newpane for the output
    # input    : newpane
    # case 3.1 : No way to really find any session or oldpane, no creation of new panes. If its there already, use it,
    # if not, error out

    # when no old pane was chose, take the selected one and rename it to the new pane name
    if( old_pane is None ):
        name_cmd = [ "select-pane", "-T", new_pane ]
        p = run_tmux( name_cmd )
        spanes,panes = tmux_panes() # update information
    else:
        active_spanes = spanes.get(old_session,panes)
        print("Need to find old pane@session")
        pane_id,_ = active_spanes.get(old_pane,None)
        # try to find the old pane by ID and select it
        print("old_session = '%s'" % (old_session,) )
        print("old_pane = '%s'" % (old_pane,) )
        print("pane_id = '%s'" % (pane_id,) )
        run_tmux( [ "select-pane", "-t", pane_id ] )

    active_spanes = spanes.get(old_session,panes)
    print("active_spanes = '%s'" % (active_spanes,) )

    split_options = []
    if( argv[1][0] == "-" ):
        split_options = [ argv[1] ]
        argv = argv[1:]

    # here either the old_pane is selected or if not present
    if( new_pane not in active_spanes ):
        print(f"Need to create new pane {new_pane}")
        p = run_tmux( [ "split-window" ] + split_options )
        p = run_tmux( [ "select-pane", "-T", new_pane ] )
    tgt = tmux(new_pane)
    add_board(tgt,argv)

    if( created ):
        print(f"tmux session '{old_session}' created. Do a tmux at -t '{old_session}' in another window/terminal to attach to it") 
#        print("p = '%s'" % p )

def call_dashboard( argv ):
    # type: tmux,port,tty
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
    elif( "xmux".startswith(argv[0]) ):
        do_xmux( argv[1:] )
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



@vdb.event.before_prompt("before_prompt")
def dash_on(evname):
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
            print("dashboard: %s" % ge)
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_dashboard()

# TODO/Ideas
# modifier to show top/bottom N rows of command only


### maybe the stuff below needs to go into another module? We will probably depend on tmux a lot

# Dashboard will have the possibility to set aliases instead of just IDs by which we can mention them in views
# xmux advanced dash target will instead of using an existing tmux create one. If the session does not exist, create it.
# If the pane does not exist, create it. Use -xyz parameters as tmux split-window parameters. Don't support everything,
# just the most common stuff. People can always call tmux to tweak things later on the created panes.
# <pane-to-split>:<new-pane>
# pane-to-split can be pane@session or just pane or @session to mean any pane at that session
# Having no : means to just select that pane, no split options possible here, everything will be forwarded to the tmux
# target
# dash xmux pane1@session1:pane2 -vb registers
# a |alias after it makes this an alias for the tmux object with that name. Duplicates make this an error. To be used
# for enable/disable views. Maybe later for closing a pane when there is no view? But then how to reopen in the right
# layout...
# 
# If session "session1" does not exist create it. Select pane1 if it exists, and then via -vb create a new pane with the
# -l size 66 named pane2. Both could be omitted, making things nameless. If pane1 does not exist, give a notice and
# split the currently selected pane instead.
# pass the registers command to the tmux command with "^pane2$" in the name, but select for session name too. Extend
# tmux syntax to support sessions too for that
# If there is no session but also no pane specified, try to be smart about it and when possible select the session that
# the current gdb runs in. Maybe make that configureable. This way we can just start gdb in a tmux and startup the
# layout
# 
# 
# views will be based on self controlled tmux panes/windows.
# view add <session> <dash ID/name> <tmux options for layout>
#
# view add <session> { commands to setup a dash that will then automatically added }
def call_view( argv ):
    vdb.util.bark() # print("BARK")

class cmd_view (vdb.command.command):
    """
Manage dashboard views
    """

    def __init__ (self):
        super ().__init__ ("view", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv):
        try:

#            import cProfile
#            cProfile.runctx("call_view(argv)",globals(),locals())
            call_view(argv)
        except gdb.error as ge:
#            traceback.print_exc()
            print("view: %s" % ge)
        except:
            traceback.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_view()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
