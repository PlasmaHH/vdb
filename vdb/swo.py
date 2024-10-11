#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import sys
import threading
import select
import time

import gdb

import vdb.command
import vdb.color

import rich.console


default_host = vdb.config.parameter("vdb-swo-host","localhost")
default_port = vdb.config.parameter("vdb-swo-port",22888)

flush_timeout = vdb.config.parameter("vdb-swo-flush-timeout", 50, docstring = "Timeout after which a buffer that did not receive anything will be flushed" )
flush_watermark = vdb.config.parameter("vdb-swo-flush-watermark", 64, docstring = "If this much bytes are in the buffer it will be flushed")
auto_reconnected = vdb.config.parameter("vdb-swo-auto-reconnect", True )


default_colors = vdb.config.parameter("vdb-swo-colors", "#ffffff;#ffff77;#ff9900;#ff7777;#00ff00;#0000ff;#ff00ff;#00ffff;#88aaff;#aa00aa" , gdb_type = vdb.config.PARAM_COLOUR_LIST )

# TODO
# sync/async mode: only output what was captured "before_prompt"

swo_colors = []
swo_rich = []
for i in range(0,10):
    swo_colors.append( vdb.config.parameter( f"vdb-swo-colors-{i}", default_colors.elements[i], gdb_type = vdb.config.PARAM_COLOUR ) )
    swo_rich.append( vdb.config.parameter( f"vdb-swo-use-rich-{i}", False ) )

class SWO:

    class ChannelBuffer:
        def __init__( self, channel ):
            self.channel = channel
            self.buffer = ""
            self.last_flushed = time.time()
            # XXX Guess we should attach the output target later here

        # other output modules should overwrite this?
        def output( self, data ):
            print(data,end="")
        
        def flush( self ):
            idx = self.channel % len(swo_colors)
            if( swo_rich[idx].value ):
                vdb.util.console.print( self.buffer, end = "" )
            else:
                color = swo_colors[self.channel % len(swo_colors)].value
                self.output( vdb.color.color(self.buffer,color) )
            self.buffer = ""
            self.last_flushed = time.time()

        def check_timeout( self, now ):
            if( self.last_flushed + flush_timeout.value/1000.0 >= now ):
                self.flush()

        def add( self, payload ):
            char = payload.decode("raw_unicode_escape")
            self.buffer += char
            if( char == "\n" or len(self.buffer) >= flush_watermark.value ):
                self.flush()

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
            pr,pw,pe = select.select( [ self.sock ], [], [], timeout )
            if( len(pr) > 0 ):
                data = self.sock.recv(1024)
                self.buffer += data
                if( len(self.buffer) > 2 ):
                    self.decode()
            self.check_timeouts()
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
            self._decode_packet()

    def _decode_packet( self ):
        headerbyte = self.buffer[0]
#        print("########################################")
#        print(f"{headerbyte=:#x}")
#        print(f"{bin(headerbyte)=}")
        payload_map = {
                0b01 : 1,
                0b10 : 2,
                0b11 : 4
                }

        if( headerbyte == 0 ):
            print("SYNC")
        elif( headerbyte == 0b01110000 ):
            print("OVERFLOW")
        # 0bCDDD0000, DDD not 0b000 or 0b111
        elif( headerbyte & 0b00001111 == 0 ):
            print("Possible Timestamp")
            if( headerbyte & 0b01110000 == 0b01110000 or headerbyte & 0b0111000 == 0 ):
                print("Uh, no timestamp")
        if( headerbyte & 0b00001011 == 0b0000100 ):
            print("Extension Header")
        elif( headerbyte & 0b11011111 == 0b10010100 ):
            print("Global Timestamp")
        elif( headerbyte & 0b10001111 == 0b00000100 ):
            print("Reserved 1")
        elif( headerbyte & 0b01111111 == 0b01110000 ):
            print("Reserved 2")
        elif( headerbyte & 0b11011111 == 0b10000100 ):
            print("Reserved 3")
        elif( headerbyte & 0b11001111 == 0b11000100 ):
            print("Reserved 4")

        if( headerbyte & 0b00000011 != 0 ):
#            print("Source Packet")
            plb = headerbyte & 0b00000011
            payload_len = payload_map[plb]
#            print(f"{plb=}")
#            print(f"{payload_len=}")
            if( payload_len >= len(self.buffer) ):
            # Not enough data in buffer
                return
            payload = self.buffer[1:payload_len+1]
            source = headerbyte & 0b11111000
            source <<= 3
#            print(f"{source=}")

            if( headerbyte & 0b00000100 == 0 ):
#                print("Instrumentation Packet")
#                print(f"{payload=}")
                self.add_payload(source,payload)
            else:
                print("Hardware Source")
                print(f"{payload=}")
            self._consume(1+payload_len)
        else:
            self._consume(1)



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

class cmd_swo (vdb.command.command):
    """
    Control swo comms
"""

    def __init__ (self):
        super ().__init__ ("swo", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            if( len(argv) == 0 ):
                argv.append(None) # to trigger usage()

            match argv[0]:
                case "start":
                    start_swo(flags,argv[1:])
                case "stop":
                    stop_swo(flags,argv[1:])
                case _:
                    print(f"Unrecognized command {argv[0]}")
                    self.usage()

        except:
            vdb.print_exc()
            raise
        self.dont_repeat()

cmd_swo()
# TODO
# optional output of the function/context/symbol in one column
# vim: tabstop=4 shiftwidth=4 expandtab ft=python

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
