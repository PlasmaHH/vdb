#!/usr/bin/env python3

import vdb.command
import rich
import rich.table
import gdb
import time
import sys
import vdb.util
import importlib
import re
import serial.tools.list_ports
import vdb.svd

scan_retries = vdb.config.parameter("vdb-bmp-scan-retries",3,docstring="Number of bmp swd/jtag scan retries")
retry_delay  = vdb.config.parameter("vdb-bmp-retry-delay", 0.25, docstring="Time in seconds to wait until the next retry")
all_mem_accessbile = vdb.config.parameter("vdb-bmp-all-mem-accessible", True, docstring="Whether to make all memory addresses accessible for gdb in order to access mmapped registers")

def dev_list( ):
    tbl = rich.table.Table(
        "Device", "hwid", "Serial", "Manufacturer", "Product", "VID", "PID", "Name", "Bus", "Interface", "Description",
                        row_styles = ["on #222222",""], title = "Found Blackmagic Probes" )

    for sp in serial.tools.list_ports.comports():
        if( sp.interface is None ):
            continue
        if( re.search("black.*magic.*gdb",sp.interface,re.IGNORECASE) is None ):
            continue
        if( sp.vid ):
            vid = f"{sp.vid:#06x}"
        else:
            vid = "???"
        if( sp.pid ):
            pid = f"{sp.pid:#06x}"
        else:
            pid = "???"
        tbl.add_row( sp.device, sp.hwid, sp.serial_number, sp.manufacturer, sp.product, vid, pid,
                    sp.name, sp.location, sp.interface, sp.description )

    vdb.util.console.print(tbl)

def _load_svd( cand, keep, mcu = None ):
    best = None
    best_registers = 0
    # Basically try to find the first match with the most registers
    for k,svd in vdb.svd.devices.items():
        for c in cand:
            if( k.find(c) != -1 ):
                if( mcu is not None ):
                    if( svd.cpu.get_name().find(mcu) == -1 ):
                        continue
                numreg = len(svd.registers)
                if( numreg > best_registers ):
#                    if( best is not None ):
#                        print(f"Replacing {best.name}[{len(best.registers)}] with", end = "" )
                    best_registers = numreg
                    best = svd
#                    print(f" {best.name}[{len(best.registers)}]")

    if( best is None ):
        vdb.log(f"Failed to find svd file for {cand}",level=2)
    else:
        vdb.log(f"Loading svd definitions for {best.name} ({best.cpu})", level = 3)
        vdb.svd.svd_load( best.name, keep )
    # return best for later use
    return best

def _find_mcu( ):
    # So what will we do when we find multiple? Per default, take the first one. We can also take a parameter that will
    # be either interpreted as integer or as a kind of regex filter for the mcu, but lets see a multiple scan result
    # first (might need a board with a real jtag bus for this)
    scanresult = gdb.execute( "monitor auto_scan", False, True )
    scanresult = scanresult.replace("\x00","\\0x00")
#    print(f"{scanresult=}")
    # XXX Check if we parse this right, after all we only have one example yet ^^

    index = None
    for sl in scanresult.split("\n"):
        m = re.search(r"([0-9]+)\s+(.*?)\s+(.*)",sl)
        if( m is None ):
            continue
        index = int(m.group(1))
        soc = m.group(2)
        mcu = m.group(3)
    if( index is None ):
        raise RuntimeError(f"Probe could not find any attached targets:\n{scanresult}")

    return index,soc,mcu


def attach( flags ):
    device = None
    for sp in serial.tools.list_ports.comports():
        if( sp.interface is None ):
            continue
        if( re.search("black.*magic.*gdb",sp.interface,re.IGNORECASE) is not None ):
            device = sp.device
            break

    if( device is None ):
        raise RuntimeError("Could not find any black magic probe")

    vdb.log(f"Connecting to auto detected probe at {device}", level = 3 )
    gdb.execute( f"target extended-remote {device}")
    version = gdb.execute( "monitor version", False, True )
    version = version.split("\n")[0]
    vdb.log(f"Found BMP '{version}', scanning for attached devices")
    # In case the mcu is not part of the list we might be able to detect it from the parsed soc info

    retries = 0
    while True:
        try:
            index,soc,mcu = _find_mcu()
            break
        except:
            retries += 1
            if( retries > scan_retries.value ):
                raise
            vdb.log(f"auto scan returned failure, retrying ({retries}/{scan_retries.value})",level=2)
            time.sleep( retry_delay.fvalue )

    if( "s" in flags ):
        print(f"Trying to load necessary svd files for {soc} {mcu}")
        # blackmagic sometimes gives back multiple models at once, scan for all of them
        for s in soc.split("/"):
            vdb.svd.svd_scan([s],False)
        vdb.svd.svd_scan([mcu],False)


        svd = _load_svd( soc.split("/"), False )
        mcucpu = svd.cpu.get_name().split()[0]
        svdmcu = _load_svd( [ mcu ], True, mcucpu )
        if( svdmcu is None ):
            svdmcu = _load_svd( [ mcu ], True )

    if( all_mem_accessbile.value ):
        sval = "off"
    else:
        sval = "on"
    gdb.execute(f"set mem inaccessible-by-default {sval}")
    # Finally all is good? Then attach to it
    gdb.execute(f"attach {index}")
    # Just for fun, ignore if it doesnt work
    try:
        gdb.execute("monitor uid")
    except:
        pass


class cmd_bmp (vdb.command.command):
    """bmp is for the black magic probe support.
bmp list   - list found probes
bmp attach - automatically attach to the first probe and target found
bmp/s attach - attach and load necessary svd files
"""

    def __init__ (self):
        super (cmd_bmp, self).__init__ ("bmp", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = True

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)

        match( argv[0] ):
            case "list":
                dev_list()
            case "attach":
                attach(flags)
            case _:
                raise RuntimeError(f"Unknown subcommand {argv[0]}")

        self.dont_repeat()

cmd_bmp()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
