#!/usr/bin/env python3


import vdb.command
import vdb.color
import vdb.util
import vdb.memory

import gdb
import rich.console
import time

# XXX Provide different implementations for idfferent rtt flavours
# Combine the rich stuff with swo, make a higher level config out of it
silence = True
class segger_rtt_channel:

    rtt_channels = {}

    def __init__( self ):
        self.read_offset = 0
        self.channel = 0
        self.struct = None
        self.buffer = None
        self.size = None
        self.watchpoint = None

    @staticmethod
    def get( channel ):
        rtt0 = segger_rtt_channel.rtt_channels.get(channel)
        if( rtt0 is None ):
            rtt0 = segger_rtt_channel()
            RTT = gdb.parse_and_eval("_SEGGER_RTT")
            rtt0.struct = RTT["aUp"][channel]
            rtt0.read_offset = rtt0.struct["RdOff"]
            rtt0.buffer = rtt0.struct["pBuffer"]
            rtt0.size = rtt0.struct["SizeOfBuffer"]
            rtt0.channel = channel
            segger_rtt_channel.rtt_channels[channel] = rtt0
        return rtt0

    def update( self ):
        wroff = self.struct["WrOff"]
        # Nothing new to read
        if( wroff == self.read_offset ):
            return ""
        # It wrapped around, read the first piece until end of buffer
        # XXX Check for off  by one errors

        alldata = ""
        if( self.read_offset > wroff ):
            data = vdb.memory.read_uncached( self.buffer + self.read_offset, self.size - self.read_offset )
            datas = data.tobytes().decode("utf-8")
            alldata += datas
            self.read_offset = 0

        if( wroff > self.read_offset ):
            data = vdb.memory.read_uncached( self.buffer + self.read_offset, wroff - self.read_offset )
            datas = data.tobytes().decode("utf-8")
            alldata += datas
            self.read_offset = wroff
        self.struct["RdOff"].assign(self.read_offset)
        return alldata

    def _ensure_watch( self ):
        if( self.watchpoint is not None ):
            return
        self.watchpoint = gdb.Breakpoint( f"_SEGGER_RTT.aUp[{self.channel}].WrOff", gdb.BP_WATCHPOINT, gdb.WP_WRITE )

    def watch( self ):
        self._ensure_watch()
        with vdb.util.silence(silence):
#            vdb.util.bark() # print("BARK")
            #gdb.execute("continue",True)
            gdb.execute("interpreter-exec mi4 -exec-continue")
#            vdb.util.bark() # print("BARK")

    def unwatch( self ):
        if( self.watchpoint is not None):
            self.watchpoint.delete()
        self.watchpoint = None


def rtt( channel ):
    rtt0 = segger_rtt_channel.get(channel)
    data = rtt0.update()
    print(data,end="")

def stream( flags, argv ):
    channel = 0
    if( len(argv) ):
        channel = int(argv[0])
    rtt = segger_rtt_channel.get( channel )
    try:
        while True:
#            vdb.util.bark() # print("BARK")
#            rtt.unwatch()
            with vdb.util.timeout(1):
#                vdb.util.bark() # print("BARK")
                with vdb.util.silence(silence):
                    if( rtt.watchpoint is not None ):
                        gdb.execute(f"disable {rtt.watchpoint.number}")
#                    vdb.util.bark() # print("BARK")
#                    gdb.execute("continue",True)
                    gdb.execute("interpreter-exec mi4 -exec-continue")
                    if( rtt.watchpoint is not None ):
                        gdb.execute(f"enable {rtt.watchpoint.number}")
#                    vdb.util.bark() # print("BARK")
#            vdb.util.bark() # print("BARK")
            rtt.watch()
#            vdb.util.bark() # print("BARK")
            data = rtt.update()
            print(data,end="",flush=True)
#            vdb.util.bark() # print("BARK")
    except KeyboardInterrupt:
        print(f"Keyboard interrupted, stopping to stream channel {channel}")
        return
    finally:
        rtt.unwatch()


class cmd_rtt (vdb.command.command):
    """
    Control rtt comms
"""

    def __init__ (self):
        super ().__init__ ("rtt", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)

    def do_invoke (self, argv ):
        try:
            argv,flags = self.flags(argv)
            if( len(argv) == 0 ):
                argv.append(None) # to trigger usage()

            match argv[0]:
                case "stream":
                    stream( flags, argv[1:] )
                case "start":
                    start_rtt(flags,argv[1:])
                case "stop":
                    stop_rtt(flags,argv[1:])
                case "status":
                    status_rtt(flags,argv[1:])
                case "dash":
                    link_dash(flags,argv[1:])
                case _:
                    print(f"Unrecognized command {argv[0]}")
                    self.usage()

        except:
            vdb.print_exc()
            raise
        self.dont_repeat()

cmd_rtt()


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
