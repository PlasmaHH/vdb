#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.config
import vdb.track

import gdb

import traceback
import math
import re
import datetime
import os
import subprocess
import shutil



graph_with = vdb.config.parameter("vdb-graph-with", "lines")


"""
Notes...

a relative and an automated relative mode. In relative its timestamps like in track data. In auto mode we start new as
soon as we see the graph drop or change in a predefined way. Obviously not suitable for all cases. Maybe add possibility
to specify these things. Wait for use cases to chose best.

"""

# todo: optionally print to png or output to file
def plot_data( plotlines, tvar, xfirst, xlast, time = False ):
    plotdata = ""

    if( time ):
        plotdata += "set xdata time\n"
        plotdata += "set timefmt \"%s\"\n"

    plotdata += "$data << EOD\n"

    plotdata += plotlines

    plotdata += "\n"
    plotdata += "EOD\n"
    plotdata += f"set xrange [{xfirst:0.11f}:{xlast:0.11f}]\n"
    plotdata += "plot"
    tvidx = 1
    for tv in tvar:
        tvidx += 1
        plotdata += f"$data using 1:{tvidx} with {graph_with.value} title \"{tv}\", "


    plotdata += "\n"
    plotdata += "pause mouse close\n"

#    print("plotdata = '%s'" % plotdata )

    gnuplot = subprocess.Popen( [ "gnuplot" ] , stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = False )
    gnuplot.stdin.write(plotdata.encode())
    gnuplot.stdin.flush()
    gnuplot.stdin.close()
#    print("gnuplot.pid = '%s'" % gnuplot.pid )

    try:
        gnuplot.wait(1)
    except:
        pass

    if( gnuplot.poll() is not None ):
        out = gnuplot.stderr.read()
        print("Gnuplot ERR Output: '%s'" % out )

    print("gnuplot.returncode = '%s'" % gnuplot.returncode )




def extract_graph( argv ):
    name = argv[0]
    gvar = gdb.parse_and_eval(argv[0])

    last = None
    first = None
    try:
        last = int(argv[1])
        last = int(argv[2])
        first = int(argv[1])
    except:
        pass

    print("gvar.type = '%s'" % gvar.type )
    print("gvar = '%s'" % gvar )

    plotlines = ""

    # assume array here
    if( last is None or first is None ):
        print("gvar.type.range() = '%s'" % (gvar.type.range(),) )
        vr = gvar.type.range()
        if( last is None ):
            last = vr[1]
        if( first is None ):
            first = vr[0]

    for i in range(first,last+1):
        try:
            plotlines += "%s %s\n" % (i, gvar[i] )
        except:
            plotlines += "%s %s\n" % (i, gdb.parse_and_eval(f"{name}[{i}]") )

    plot_data(plotlines, [name], first, last, time = False )

def extract_track( tvar ):
    if( len(tvar) == 0 ):
        print("Well, you should tell which track data variables to plot. Do `track show` or  `track data` to check what is available")
        return
    td = vdb.track.tracking_data

    first = 0
    last = 0
    points = 0
    plotlines = ""
    for ts in sorted(td.keys()):
        if( first == 0 ):
            first = ts
        last = ts
        plotline = f"{ts:0.11f} "
        tdata = td[ts]
        for tv in tvar:
            point = tdata.get(tv,None)
            if( point is None ):
                plotline += " - "
            else:
                plotline += f" {point} "
                points += 1
        plotlines += plotline + "\n"
#        print("plotline = '%s'" % plotline )
    if( points == 0 ):
        print("Could not find any points to plot from %s" % tvar )
        return

    plot_data( plotlines, tvar, first, last, time = True )

#    print("tvar = '%s'" % tvar )
#    print("td = '%s'" % td )

"""

Plan:
    various things to iterate that we then put in an array and dump to gnuplot
    - vector, array
    - list, map and set maybe? unordered too?
    - boost intrusive containers?
    - data collected in the track module

    We should have maybe an iteration layer that we then use, which can be re-used in other parts of vdb

    The objects inside the iterables could be int/floats but with some extra configuration or parameters we might be able to extract simple elements

    Maybe we could even extract things in a loop and do 2d and 3d?
"""
class cmd_graph (vdb.command.command):
    """ """

    def __init__ (self):
        gnuplot = shutil.which("gnuplot")
        if( gnuplot is None ):
            raise RuntimeError("gnuplot not found in PATH, refusing to load")
        super (cmd_graph, self).__init__ ("graph", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.result = ""
        self.dont_repeat()

        print("gnuplot = '%s'" % gnuplot )

    def do_invoke (self, argv ):
        print("argv = '%s'" % argv )

        try:
            if( argv[0][0] == "/" ):
                to_png = False
                if( argv[0].find("p") != -1 ):
                    to_png = True

                if( argv[0].find("t") != -1 ):
                    extract_track(argv[1:])
                else:
                    extract_graph(argv[1:])
            else:
                extract_graph(argv)

        except Exception as e:
            traceback.print_exc()

cmd_graph()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
