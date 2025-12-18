#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import collections
import socket
import sys
import threading
import select
import time
import re
import struct

import gdb

import vdb.command
import vdb.color
import vdb.util


import rich.console


default_host = vdb.config.parameter("vdb-swo-host","localhost")
default_port = vdb.config.parameter("vdb-swo-port",22888)

flush_timeout   = vdb.config.parameter("vdb-swo-flush-timeout", 50, docstring   = "Timeout after which a buffer that did not receive anything will be flushed" )
flush_watermark = vdb.config.parameter("vdb-swo-flush-watermark", 64, docstring = "If this much bytes are in the buffer it will be flushed")
auto_reconnect  = vdb.config.parameter("vdb-swo-auto-reconnect", True )

default_colors = vdb.config.parameter("vdb-swo-colors", "#ffffff;#ffff77;#ff9900;#ff7777;#00ff00;#0000ff;#ff00ff;#00ffff;#88aaff;#aa00aa" , gdb_type = vdb.config.PARAM_COLOUR_LIST )

show_packet_type = vdb.config.parameter("vdb-swo-show-packet-type",False)
auto_start = vdb.config.parameter("vdb-swo-autostart",False, docstring = "Autostarts before the first prompt" )

# TODO
# sync/async mode: only output what was captured "before_prompt"

swo_colors = []
swo_rich = []
short_rich = []

for i in range(0,10):
    swo_colors.append( vdb.config.parameter( f"vdb-swo-colors-{i}", default_colors.elements[i], gdb_type = vdb.config.PARAM_COLOUR ) )
    swo_rich.append( vdb.config.parameter( f"vdb-swo-use-rich-{i}", True ) )
    short_rich.append( vdb.config.parameter( f"vdb-swo-short-rich-{i}", True ) )


rich_map = {}

def update_replacements( cfg ):
    rich_map.clear()
    for k,v in cfg.elements:
        rich_map[k] = v
        k = k.lower()
        if( k not in rich_map ):
            rich_map[k] = v

rich_replacements = vdb.config.parameter("vdb-swo-rich-replacements", "R:#ff0000,G:#00ff00,B:#0000ff", gdb_type = vdb.config.PARAM_ARRAY, on_set = update_replacements )

pc_counters = collections.defaultdict(int)
pc_total = 0
pc2function_cache = {}

def add_pc_counter( addr ):
    pc_counters[addr] += 1
    global pc_total
    pc_total += 1

class SWO:

    rich_re = re.compile(r"\[(.*?)\]")

    class ChannelBuffer:
        def __init__( self, channel ):
            self.channel = channel
            self.buffer = ""
            self.last_flushed = time.time()
            self.force_flush = False
            # XXX Guess we should attach the output target later here

        # other output modules should overwrite this?
        def output( self, data ):
            db = channel_outputs.get(self.channel)
            if( db is not None ):
                db.write(data)
            else:
                print(data,end="")

        def _expand_rich( self, data ):
            newdata = data
            for rp in SWO.rich_re.findall( data ):
                mapto = rich_map.get(rp)
                if( mapto is not None ):
                    newdata = newdata.replace(f"[{rp}]",f"[{mapto}]")
            return newdata

        def flush( self ):
            idx = self.channel % len(swo_colors)
            if( swo_rich[idx].value ):
#                print("RICH FLUSH")
                # We might get half of a rich or ansii escape sequence or so here. 
                data = self.buffer
#                print(f"BUFFER: {data}")

                if( short_rich[idx].value ):
                    data = self._expand_rich( data )
#                print(f"EXPANDED BUFFER: {data}")
                # rich for some reason doesn't like this, so we try to hide it
                data = data.replace("\x1b[","_ANSI_ESCAPE_SEQUENCE_")
#                print(f"ESCAPED BUFFER: {data}")

                try:
                    with vdb.util.console.capture() as cap:
                        vdb.util.console.print( data, end = "" )
                    outputdata = str( cap.get() )
#                    print(f"ENRICHED BUFFER: {outputdata=}")
                    # rich is done, we can revert the extra escaping
                    outputdata = outputdata.replace("_ANSI_ESCAPE_SEQUENCE_","\x1b[")
#                    print(f"UNESCAPED BUFFER: {outputdata}")
                except rich.errors.MarkupError:
                    # rich didn't do anything, we can revert the extra escaping
                    outputdata = data.replace("_ANSI_ESCAPE_SEQUENCE_","\x1b[")
                    print(f"ERROR: {outputdata}")
            else:
                outputdata = self.buffer

            color = swo_colors[self.channel % len(swo_colors)].value
            outputdata = vdb.color.color(outputdata,color)

            self.output( outputdata )
            self.buffer = ""
            self.force_flush = False
            self.last_flushed = time.time()

        def check_timeout( self, now ):
            if( self.force_flush or self.last_flushed + flush_timeout.value/1000.0 >= now ):
                self.flush()

        def add( self, payload ):
            char = payload.decode("raw_unicode_escape")
            self.buffer += char
            if( char == "\n" ):
                self.flush()
            # Let the next timeout check trigger. This allows us to process the whole swo buffer at once even if we hit
            # the watermark
            if( len(self.buffer) >= flush_watermark.value ):
                self.force_flush = True

    def __init__( self, host, port ):
        self.host = host
        self.port = port

        self._connect()
        self.buffer = b""
        self.channels = {}
        self.keep_running = True
        self.thread = threading.Thread(target = self.wrap_run)
        self.console = vdb.util.console
        self.thread.start()

    def wrap_run( self ):
        try:
            self.run()
        except:
            self.console.print_exception(show_locals=True)

    def _connect( self ):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect( (self.host,self.port) )

    def check_timeouts( self ):
        now = time.time()
        for channel, cbuf in self.channels.items():
            cbuf.check_timeout(now)

    def run( self ):
        print("Starting SWO thread...")
        timeout = 0.1
        while self.keep_running and vdb.keep_running:
            try:
                pr,pw,pe = select.select( [ self.sock ], [], [], timeout )
                if( len(pr) > 0 ):
                    data = self.sock.recv(1024)
                    self.buffer += data
                    if( len(self.buffer) > 2 ):
                        self.decode()
                self.check_timeouts()
            except ConnectionResetError as e:
                print(f"SWO Connection lost: {e}")
                if( not auto_reconnect.value ):
                    break
                self._connect()
        print("Exiting SWO Thread...")


    def stop( self ):
        print("Stopping SWO Thread...",end="")
        self.keep_running = False
        self.thread.join()

    def _consume( self, amount ):
        if( amount > len(self.buffer) ):
            raise RuntimeError(f"Trying to consume {amount} bytes, but buffer size is only {len(self.buffer)}")
        self.buffer = self.buffer[amount:]

    def _dump( self ):
        for c,buf in self.channels.items():
            print(f"Channel {c}:")
            print(buf)

    def add_payload( self, source, payload ):
#        print(f"add_payload( {source=}, {payload=} )")
        cbuf = self.channels.get(source)
        if( cbuf is None ):
            cbuf = SWO.ChannelBuffer(source)
            self.channels[source] = cbuf

        cbuf.add(payload)
#        ip = int.from_bytes(payload)
#        c = chr(ip)
#        print(c,end="")
#        print(f"b{ip:08b}")


    def decode( self ):
#        print("Decoding...")
#        self.buffer = b""
#        return
        while( len(self.buffer) > 1 ):
            if( self._decode_packet() ):
                break

    payload_map = {
            0b01 : 1,
            0b10 : 2,
            0b11 : 4
            }

    def _decode_packet( self ):
        headerbyte = self.buffer[0]
#        print("########################################")
#        print(f"{headerbyte=:#x}")
#        print(f"{self.buffer=}")
#        print(f"{bin(headerbyte)=}")

        # Just informative for debugging, might not be entirely correct. Protocol format from DDI 0403 for armv7 and 
        # DDI 0553 for armv8
        if( show_packet_type.value ):
            if( headerbyte == 0 ):
                print("SYNC")
            elif( headerbyte == 0b01110000 ):
                print("OVERFLOW")
            # 0bCDDD0000, DDD not 0b000 or 0b111
            elif( headerbyte & 0b00001111 == 0 ):
                print("Possible Timestamp")
                ddd = headerbyte & 0b01110000
                if( ddd == 0b01110000 or ddd == 0 ):
                    print("Uh, no timestamp")
            # don't elif because it may have been soemthing else than a timesampt
            if( headerbyte & 0b00001011 == 0b00001000 ): # 0bCDDD1S00
                print("Extension Header")
            elif( headerbyte & 0b11011111 == 0b10010100 ): # 0b10T10100
                print("Global Timestamp")
            elif( headerbyte & 0b10001111 == 0b00000100 ): # 0b0xxx0100
                print("Reserved 1")
            elif( headerbyte == 0b1110000 ):
                print("Reserved 2")
            elif( headerbyte & 0b11011111 == 0b10000100 ): # 0b10x00100
                print("Reserved 3")
            elif( headerbyte & 0b11001111 == 0b11000100 ): # 0b11xx0100
                print("Reserved 4")
            elif( headerbyte & 0b100 == 0 ): # 0bAAAAA0SS SS != b00
                print("Instrumentation")
            elif( headerbyte & 0b100 == 0b100 ): # 0bAAAAA0SS SS != b00
                print("Hardware source")
            else:
                # If this happens we are most likely out of sync with the stream
                print(f"Unknown Headerbyte {headerbyte:#0x}")

        # XXX Rate limit in case of messing up with settings?
        if( headerbyte == 0b01110000 ):
            print("SWO OVERFLOW")
        if( headerbyte == 0x0e ):
            if( len(self.buffer) < 3 ):
                return True

            # exception trace packet, ignore (might be useful later on)
            self._consume(3)
        # A source packet
        elif( headerbyte & 0b00000011 != 0 ):
#            print("Source Packet")
            plb = headerbyte & 0b00000011
            payload_len = self.payload_map[plb]
            if( payload_len >= len(self.buffer) ):
#                print(f"{payload_len=}, {len(self.buffer)=}")
            # Not enough data in buffer, don't consume anything
                return True
            payload = self.buffer[1:payload_len+1]
            source = headerbyte & 0b11111000
            source >>= 3

            if( headerbyte & 0b00000100 == 0 ):
#                print(f"{source=}")
                self.add_payload(source,payload)
            elif( headerbyte & 0b00000100 == 0b100 ):
                if( payload_len == 1 ):
                    addr = int(payload[0])
                elif( payload_len == 4 ):
                    addr = struct.unpack("I",payload)[0]
                else:
                    print("Invalid PC trace payload len, skipping")
                    self._consume(1)
                    return
#                print(f"PC TRACE? {source=}, {headerbyte=}, {addr=:#0x}")
                # XXX We might want to forward this into yet another thread for performance reasons to be able to really
                # fast read these. Also this might be more useful to have that thread then hold a lock over the
                # pc_counters dict so we can have our report etc. functionality run while swo is still active
                add_pc_counter(addr)
            else:
                print(f"Unknown Source ({headerbyte:#0x})")
                print(f"[{len(payload)}]:{payload=}")
            self._consume(1+payload_len)
        # XXX The timestamp and extension packets have a payload, we do not parse them, this might throw us off!
        elif( headerbyte & 0b11011111 == 0b10010100 ): # 0b10T10100
            print("NOT IMPLEMENTED: GLOBAL TIMESTAMP. Expect desync")
            self._consume(1)
        elif( headerbyte & 0b00001011 == 0b00001000 ): # 0bCDDD1S00
            print("NOT IMPLEMENTED: EXTENSION. Expect desync")
            self._consume(1)
        elif( headerbyte == 0 ):
            # sync
            self._consume(1)
        elif( headerbyte == 0b10000000 ):
            # last sync
            self._consume(1)
        elif( headerbyte & 0b00001111 == 0 ): # 0xCDDD0000 => timestamp but only when DDD is not 0b000 or 0b111 (who thinks of such weird formats?)
            ddd = headerbyte & 0b01110000
            if( ddd != 0b01110000 and ddd != 0 ):
                print("NOT IMPLEMENTED: LOCAL TIMESTAMP. Expect desync")
#                print(f"[{len(payload)}]:{payload=}")
            else:
                print(f"{headerbyte=}")
                print(f"{ddd=}")
            self._consume(1)
        else: # no idea what we have here, last effort to just eat it
            self._consume(1)

channel_outputs = {}

def link_board( channel, dashboard ):
    channel_outputs[channel] = dashboard

swo = None

def start_swo( flags, argv ):
    global swo

    host = default_host.value
    port = default_port.value
    # XXX Support passing at command line

    stop_swo(None,None)
    swo = SWO(host,port)

@vdb.event.gdb_exiting()
def stop_swo( flags = None, argv = None ):
    global swo
    if( swo is not None ):
        swo.stop()
        swo = None

def status_swo( flags, argv ):
    if( swo is None ):
        print("swo is not active")
        return
    tbl = [[ "Channel", "Buffersize", "Last Flushed", "Dashboard" ]]
    tbl.append(None)
    for ch,cbuf in swo.channels.items():
        row = []
        row.append( ch )
        row.append( len(cbuf.buffer) )
        row.append( cbuf.last_flushed )
        db = channel_outputs.get( ch )
        if( db is None ):
            row.append( "none" )
        else:
            row.append( db.id )
        tbl.append(row)
    vdb.util.print_table(tbl)

def pc_trace( flags, argv ):
    # XXX can we provide something similar to that on x86 linux?
    print("Not yet implemented: would enable PC tracing on cortex-m targets")

    # XXX Misuse this subcommand for debugging output trigger
    print(f"{pc_counters=}")


def pc_clear( flags, argv ):
    global pc_counters
    pc_counters = collections.defaultdict(int)
    global pc_total
    pc_total = 0

def pc_report( flags, argv ):
    pc_functions = collections.defaultdict(int)
    # First boil down everything to the function level
    total = 0

    prog = vdb.util.progress_bar(num_completed = True, spinner = True)
    num = len(pc_counters)
    pt = prog.add_task(f"Scanning {pc_total} occurences in {num} different addresses", total = num )
    prog.start()

    for e,(k,v) in enumerate(sorted(pc_counters.items(),reverse=True)):
        prog.update( pt, completed = e )
        s = vdb.memory.get_gdb_sym_name( k )
#        print(f"{k:#0x} => {s=}")
#        assert isinstance(s,str)
        pc_functions[s] += v
        total += v
    prog.stop()

    ins_limit = 0
    pct_limit = 0
    if( len(argv) > 0 ):
        try:
            ins_limit = int(argv[0])
        except ValueError:
            pct_limit = float(argv[0])

    maxrows = 2**31
    if( len(flags) > 0 ):
        maxrows = int(flags)

    table = rich.table.Table( "Pct", "#Ins", "Function", expand=False,row_styles = ["on #222222",""])
    # Now iterate sorted by number of instructions
    for e,(k,v) in enumerate(sorted( pc_functions.items(), key = lambda x: x[1], reverse = True)):
        if( e >= maxrows ):
            break
        pct = 100.0 *  (v / total)
        if( pct < pct_limit ):
            break
        if( v < ins_limit ):
            break
        if( k is None ):
            k = "[i]Sleep Mode[/i]"
        if( k == 0xffffffbc ):
            k = "[i]Return from ISR[/i]"
        table.add_row( f"{pct:0.03f}", str(v), k )
    vdb.util.console.print(table)

def link_dash( flags, argv ):
    print(f"link_dash({flags},{argv})")
    if( len(argv) < 2):
        raise RuntimeError("Expecting at least two args to dash link")
    channel = int(argv[0])
    try:
        dashboard = int(argv[1])
        db = vdb.dashboard.get_dashboard(dashboard)
        if( db is None ):
            raise RuntimeError(f"Could not find a dashboard with ID {dashboard}. Use 'dash show' to list available ones.")
    except ValueError:
    # if its not a number we create a new one using that text as if it was a dash command
        db = vdb.dashboard.call_dashboard(argv[1:] + [ "*" ])
        if( db is None ):
            raise RuntimeError(f"Failed to use '{argv[1:]}' to create a dashboard.")
    print(f"{db=}")
    link_board( channel, db )
    # swo dash 0 1 # link channel 0 output into dashboard id 1
    # swo dash 0 tmux foobar # link channel 0 output into a new tmux dashboard

@vdb.event.before_first_prompt()
def maybe_autostart( ):
    if( not auto_start.value ):
        return
    try:
        print(f"Autostarting SWO to {default_host.value}:{default_port.value}...", end="")
        start_swo("","")
    except Exception as e:
        print(f"Failed : {e}")
    print("done")

class cmd_swo (vdb.command.command):
    """
    Control swo comms
"""

    def __init__ (self):
        super ().__init__ ("swo", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = True

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)

        match argv[0]:
            case "start":
                start_swo(flags,argv[1:])
            case "stop":
                stop_swo(flags,argv[1:])
            case "status":
                status_swo(flags,argv[1:])
            case "dash":
                link_dash(flags,argv[1:])
            case "pc_trace":
                pc_trace(flags,argv[1:])
            case "pc_clear":
                pc_clear(flags,argv[1:])
            case "pc_report":
                pc_report(flags,argv[1:])
            case _:
                print(f"Unrecognized command {argv[0]}")
                self.usage()

        self.dont_repeat()

cmd_swo()

def main( ):
    swo = SWO("localhost",22888)
    for i in [ "Text", "This [R]red[/] is" ]:
        x = swo._expand_rich( i )
        print(f"{x=}")


if __name__ == '__main__':
    main()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
