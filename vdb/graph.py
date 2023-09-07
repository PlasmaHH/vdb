#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.config
import vdb.track

import gdb

import traceback
import math
import numpy
import re
import datetime
import os
import sys
import subprocess
import multiprocessing
import shutil
import time
import queue
import abc

import matplotlib.pyplot as plt
import matplotlib.animation as animation


graph_with = vdb.config.parameter("vdb-graph-with", "lines")
gnuplot_bin = vdb.config.parameter("vdb-graph-gnuplot-binary", "" )

#plot_style = vdb.config.parameter("vdb-graph-plot-style","_mpl-gallery")
plot_style = vdb.config.parameter("vdb-graph-plot-style","dark_background")
default_window = vdb.config.parameter("vdb-graph-default-window",60.0)
default_bins = vdb.config.parameter("vdb-graph-default-bins",200)
default_hist_update = vdb.config.parameter("vdb-graph-default-histogram-updates",0.25)
default_line_update = vdb.config.parameter("vdb-graph-default-line-updates",0.2)



xd = [1,2,3]
yd = [1,2,3]

cnt = 3

def update_data( frame, lines ):
    global xd
    global yd
    global cnt
    cnt += 1
    xd.append(cnt)
    yd.append(cnt)
    lines.set_data(xd,yd)


data = None
bar = None
bins = numpy.linspace(-4,4,100) # ???
ax = None

def round(x):
    if( x > 0 ):
        return math.ceil(x)
    else:
        return math.floor(x)

class graph_process:

    def __init__( self ):
        self.process = None
        self.queue = None

    def add( self, data ):
#        print(f"add({data})")
        self.queue.put( ("add",data) )
#        print("P self.queue.qsize() = '%s'" % (self.queue.qsize(),) )

    def set( self, data ):
#        vdb.util.bark() # print("BARK")
        data = numpy.array(data)
#        print("data = '%s'" % (data,) )
        self.queue.put( ("set",data) )
#        print("self.queue.qsize() = '%s'" % (self.queue.qsize(),) )

    @abc.abstractmethod
    def do_add( self, ndata ):
        pass

    @abc.abstractmethod
    def do_set( self, ndata ):
        pass

    def handle_queue( self ):
#        print("update()")
#        print("C self.queue.qsize() = '%s'" % (self.queue.qsize(),) )
        cnt = 0
        try:
            while( ( ndp := self.queue.get(False) ) is not None ):
                cnt += 1
                cmd,ndata = ndp
                match cmd:
                    case "add":
                        self.do_add(ndata)
                    case "set":
                        self.do_set(ndata)
        except queue.Empty:
            pass
        return cnt

    def start( self ):
        if( self.process is not None ):
            return
        self.queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(target = self.run, daemon = True )
        self.process.start()

class hist_process(graph_process):

    def __init__( self ):
        super().__init__()
        self.data = numpy.array([])
        self.num_bins = default_bins.get()
        # TODO update bins dynamically, introduce limiting parameters
        self.bins = numpy.linspace(0,0,self.num_bins) # ???
        self.bar = None
        self.axis = None
        self.range = 0
        self.running = False

    def do_add( self, ndata ):
        self.data = numpy.concatenate( (self.data,ndata ) )

    def do_set( self, ndata ):
        self.data = ndata

    def update( self, frame ):
        cnt = self.handle_queue()
#        print("cnt = '%s'" % (cnt,) )
        if( cnt == 0 ):
            return
#        print(f"update {cnt}")

        # Use something like this for when the bins need to be updated. How do we track it?
#        self.bins = numpy.linspace(-8,8,self.num_bins) # ???
#        _,_,self.bar = self.axis.hist(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)

        try:
            if( len(self.data) == 0 ):
                return
            n,n2 = numpy.histogram(self.data,self.bins)
            maxy = 0
            minx = self.data.min()
            maxx = self.data.max()

            minx = round(self.num_bins*minx)/self.num_bins
            maxx = round(self.num_bins*maxx)/self.num_bins

            range = maxx - minx
            if( self.range != range ):
                self.axis.cla()
                print("minx = '%s'" % (minx,) )
                print("maxx = '%s'" % (maxx,) )
                self.bins = numpy.linspace(minx,maxx,self.num_bins) # ???
#        self.bins = numpy.linspace(-2,2,self.num_bins)
                _,_,self.bar = self.axis.hist(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)
                self.range = range

            for idx,(count,rect) in enumerate(zip(n,self.bar.patches)):
                if( count > 0 and minx == 0 ):
                    minx = idx
                rect.set_height(count)
                maxy=max(maxy,count)
            maxy //= 10
            maxy += 1
            maxy *= 10
            self.axis.set_ylim(top=maxy)
        except:
            traceback.print_exc()

        return self.bar.patches

    def run( self ):
#        n,_ = numpy.histogram(self.data,self.bins)

        plt.style.use( plot_style.value )
        fig, self.axis = plt.subplots(layout="tight")

        _,_,self.bar = self.axis.hist(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)
        self.axis.set_ylim(top=55)
        ani = animation.FuncAnimation( fig, self.update, interval=default_hist_update.get()*1000, repeat=False,blit=False,save_count=False)
        print("plt.show()")
        plt.show()
        sys.exit(0)

ht = hist_process()

class plot_process(graph_process):

    def __init__( self ):
        super().__init__()
        self.data = numpy.array([])
        self.timestamps = numpy.array([])
        self.axis = None
        self.range = 0
        self.running = False
        self.lines = None

    def do_add( self, ndata ):
        self.data = numpy.concatenate( (self.data,ndata ) )

    def do_set( self, ndata ):
        self.data = numpy.array(ndata[0])
        self.timestamps = numpy.array(ndata[1])

    def update( self, frame ):
#        vdb.util.bark() # print("BARK")
        cnt = self.handle_queue()
#        vdb.util.bark() # print("BARK")
#        print("cnt = '%s'" % (cnt,) )
        if( cnt == 0 ):
            return
#        vdb.util.bark() # print("BARK")
#        print(f"update {cnt}")

        # Use something like this for when the bins need to be updated. How do we track it?
#        self.bins = numpy.linspace(-8,8,self.num_bins) # ???
#        _,_,self.bar = self.axis.plot(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)

        try:
            if( len(self.data) == 0 ):
                return
            
#            print("self.data = '%s'" % (self.data,) )

#            self.lines.set_data(self.data)
            miny = self.data.min()
            maxy = self.data.max()

            minx = self.timestamps.min()
            maxx = self.timestamps.max()
            if( minx+default_window.get() < maxx ):
                minx = maxx - default_window.get()

            self.axis.set_xlim(minx,maxx)
            self.axis.set_ylim(miny,maxy)

#            print("self.timestamps = '%s'" % (self.timestamps,) )
            self.lines.set_data(self.timestamps,self.data)

#            n,n2 = numpy.plotogram(self.data,self.bins)
#            maxy = 0
#            minx = self.data.min()
#            maxx = self.data.max()

#            minx = round(self.num_bins*minx)/self.num_bins
#            maxx = round(self.num_bins*maxx)/self.num_bins

#            range = maxx - minx
#            if( self.range != range ):
#                self.axis.cla()
#                print("minx = '%s'" % (minx,) )
#                print("maxx = '%s'" % (maxx,) )
#                self.bins = numpy.linspace(minx,maxx,self.num_bins) # ???

#                _,_,self.bar = self.axis.plot(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)
#                self.range = range

#            for idx,(count,rect) in enumerate(zip(n,self.bar.patches)):
#                if( count > 0 and minx == 0 ):
#                    minx = idx
#                rect.set_height(count)
#                maxy=max(maxy,count)
#            maxy //= 10
#            maxy += 1
#            maxy *= 10
#            self.axis.set_ylim(top=maxy)
        except:
            traceback.print_exc()
        return self.lines
#        return self.bar.patches


#def test_line():
#    plt.style.use( plot_style.value )
#    fig, ax = plt.subplots(layout="tight")

#    plt.tight_layout() # call after every resize 
#    fig.text (0.2, 0.88, f"CurrentViewer version", color="yellow",  verticalalignment='bottom', horizontalalignment='center', fontsize=9, alpha=0.7)
#    ax.set_title("FULL TITLE") # No effect?

#    ax.set_xlabel("XLABEL")
#    ax.set_xlim(0,10)

#    ax.set_ylabel("YLABEL")
#    ax.set_ylim(0,10)

#    lines = ax.plot([], [], label="Current")[0]
#    lines.set_data(xd,yd)
#    anim = animation.FuncAnimation(fig, update_data, fargs=(lines,), interval=1000, save_count=3)
#    plt.show() # Blocks as long as the window is shown, so put it into some thread?



    def run( self ):
        plt.style.use( plot_style.value )
        fig, self.axis = plt.subplots(layout="tight")

#        _,_,self.bar = self.axis.plot(self.data,self.bins,lw=1,ec="yellow",fc="green",alpha=0.5)
#        self.axis.set_ylim(top=55)
        self.axis.set_xlim(1.69386530e+09,1.69386530e+09 + 3600)
        self.axis.set_ylim(0,100)
        self.lines = self.axis.plot([], [], label="Current")[0]
        anim = animation.FuncAnimation(fig, self.update, interval=default_line_update.get()*1000, save_count=3)
#        ani = animation.FuncAnimation( fig, self.update, interval=100, repeat=False,blit=False,save_count=False)
#        print("plt.show()")
        plt.show()
        sys.exit(0)



pp = plot_process()


# data must be a dict of ID: data ( where data can be anything a lower layer understands ). ndata should be an iteraable
# thing that returns ID,data tuples
# two modes: put IDs in the order they came in, or sort them by ID ( in which case a binary tree like container is more
# useful than a has dict() )


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

"""

Idea for how things could work out... First we have the track stuff ( Later we might add commands that do graph
definition and track at once )

TODO: figure out if multiple windows work too (each in its own thread possibly?)

graph <ID0>,<ID1> @<window0>
- This would plot all track data points that have ID0 and ID1 in the same timestamp, putting it into window0

graph <ID2> @<window1>
- Plots ID2 and timestamps into window1

graph <ID2> @<window1>:2
- Add ID2 on the window1 but use a secondary y axis instead ( how do we do that? subplot? twinx?)

(If matplotlib does not directly have the ability for a full secondary axis, provide a fake converision function between both axis)
We can add to any window as long as the X axis for the data is the same.

TODO: 
- For all setups where we have X and Y values, maybe add a toggle button to replace the X values by timestamps?
- (toggle) button for "axis autoscale once", "linear /log10 / log2 ?"

"""

xd = [1,2,3]
yd = [1,2,3]

cnt = 3

def update_data( frame, lines ):
    vdb.util.bark() # print("BARK")
    global xd
    global yd
    global cnt
    cnt += 1
    xd.append(cnt)
    yd.append(cnt)
    lines.set_data(xd,yd)

start_t = None

def prompt():
    vdb.prompt.display()

def event( ):
    now = time.time()
    dif = now - start_t
    if( dif > 2 ):
        gdb.execute("interrupt")
#        gdb.post_event(prompt)
    else:
        print(f"\rTime spent: {dif}s",end="",flush=True)
        gdb.post_event(event)

#    gdb.execute("\n")

def test2( argv ):
    vdb.util.bark() # print("BARK")
    global start_t
    start_t = time.time()
    gdb.post_event(event)
    vdb.util.bark() # print("BARK")
    gdb.execute("continue")
    vdb.util.bark() # print("BARK")


def extract_graph( argv ):
    return test2(argv)
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

# For performance reasons it would be useful to have a pub/sub model where we can listen to (single) track items and get
# notified when something new is added. For now just hook into the stop event to refresh the complete set of track data

current_track_var = None
gt = None

@vdb.event.gdb_exiting()
def exit_gdb( ):
    if( gt is not None and gt.process is not None ):
        gt.process.join()

@vdb.event.stop()
def refresh_track( ):
    global gt
    if( gt.process is None ):
        return
#    vdb.util.bark() # print("BARK")
    if( gt == pp ):
        alldata,tsdata = extract_track( current_track_var,False,timeseries = True)
        gt.set( (alldata,tsdata) )
    else:
        alldata,_ = extract_track( current_track_var,False,timeseries = False)
        gt.set(alldata)
#    print("alldata = '%s'" % (alldata,) )
    gt.process.join(timeout=0)
#    gt.process.join()
#    vdb.util.bark() # print("BARK")
#    print("gt.process.is_alive() = '%s'" % (gt.process.is_alive(),) )
#    print("gt.process.exitcode = '%s'" % (gt.process.exitcode,) )
#    print("multiprocessing.active_children() = '%s'" % (multiprocessing.active_children(),) )
    try:
        xwait = os.waitpid(gt.process.pid,os.WNOHANG)
    except:
#    print("xwait = '%s'" % (xwait,) )
#    if( not gt.process.is_alive() ):
        gt.process.join()
        gt.queue.close()
        gt.queue.cancel_join_thread()
        gt.process = None
        gt.queue = None
        print("Matplotlib process is not alive anymore, interrupting track if possible")
        vdb.track.interrupt()
#    vdb.util.bark() # print("BARK")

def follow_track_histogram( tvar, relative_ts ):
    global gt
    global current_track_var
    current_track_var = tvar
    gt = ht
    ht.start()
    refresh_track()

def follow_track_lines( tvar, relative_ts ):
    global gt
    global current_track_var
    current_track_var = tvar
    gt = pp
    pp.start()
    refresh_track()


def extract_track( tvar, relative_ts, timeseries = False ):
    if( len(tvar) == 0 ):
        print("Well, you should tell which track data variables to plot. Do `track show` or  `track data` to check what is available")
        return
    td = vdb.track.tracking_data

    ts_offset = 0
    first = None
    last = 0
    points = 0
    plotlines = ""

    ids = []
    # extract all numbers from all the things we need
    # check if its 
    # - a track id
    # - a breakpoint id
    # - a breakpoint expression
    for tv in tvar:
        tvi = None
        found = False
        try:
            tvi = int(tv)
            ts = vdb.track.by_number( tvi )
            if( len(ts) > 0 ):
                ids.append(tvi)
                found = True
            else: # ok might still be a breakpoint id?
                ts = vdb.track.by_id( str(tvi) )
                for t in ts :
                    ids.append( t.number )
                    found = True
        except: # its not even an integer
            pass
        if( not found ):
            # ok, might be a 1.2 breakpoint ID ...
            ts = vdb.track.by_id( str(tv) )
            if( len(ts) > 0 ):
                for t in ts :
                    ids.append( t.number )
            else:
                # ok, is it maybe an expression? Or a name?
                for n,t in vdb.track.trackings_by_number.items():
                    if( t.expression == tv ):
                        ids.append(t.number)
                    if( t.name == tv ):
                        ids.append(t.number)

#    print("tvar = '%s'" % (tvar,) )
#    print("ids = '%s'" % (ids,) )
    ret = []
    retts = []
    for stamp,ts in td.items():
#        print("ts = '%s'" % (ts,) )
        for id in ids:
            point = ts.get(id,None)
#            print("point = '%s'" % (point,) )
            if( point is not None ):
                if isinstance(point,list):
                    if( not timeseries ):
                        # Here we could like, try to fake timestamps by smoothly interpolating? At least make it an
                        # option then
                        for p in point:
                            ret.append(float(p))
                else:
                    if( timeseries ):
                        retts.append(float(stamp))
                    ret.append(float(point))

    return (ret,retts)


    for ts in sorted(td.keys()):
        kts = ts
        ts = ts - ts_offset
        if( first == None ):
            if( relative_ts ):
                ts_offset = ts
                ts = 0
            first = ts

        last = ts
        plotline = f"{ts:0.11f} "
        tdata = td[kts]
        for id in ids:
            point = tdata.get(id,None)

            if( point is None ):
                plotline += " - "
            else:
                plotline += f" {point} "
                points += 1
        plotlines += plotline + "\n"
#        print("plotline = '%s'" % plotline )
    if( points == 0 ):
        print("Could not find any points to plot from %s (keys are %s)" % (tvar,vdb.track.trackings_by_number.keys() ) )
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
    """Graphically display data from arrays and track command (using gnuplot)

graph    <var> - extract data from variable var and display in 2D with gnuplot
graph/p  <var> - extract data but output to a png
graph/t  <id>  - use the track id or expression as the data input
graph/rt <id>  - use relative timestamps with the id
"""

    def check_for_gnuplot( self ):

        if( len( gnuplot_bin.value ) > 0 ):
            gnuplot = gnuplot_bin.value
            gnuplot=os.path.expanduser(gnuplot)
            if( not os.path.exists(gnuplot) ):
                raise RuntimeError(f"gnuplot is configured as {gnuplot_bin.value} but nothing can be found there, cannot use /g")
        else:
            gnuplot = shutil.which("gnuplot")
            if( gnuplot is None ):
                raise RuntimeError("gnuplot not configured or found in PATH, cannot use /g")
            print(f"Autodetected gnuplot binary as {gnuplot}")

    def __init__ (self):
        super (cmd_graph, self).__init__ ("graph", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.result = ""

    def do_invoke (self, argv ):

        try:
            argv,flags = self.flags(argv)
            to_png = False
            relative_ts = False
            gnuplot = False

            if( "p" in flags ):
                to_png = True
            if( "g" in flags ):
                gnuplot = True
                self.check_for_gnuplot()
            if( "r" in flags ):
                relative_ts = True
            if( "l" in flags ):
                if( gnuplot ):
                    extract_track(argv,relative_ts)
                else:
                    follow_track_lines(argv,relative_ts)
            elif( "h" in flags ):
                if( gnuplot ):
                    extract_track(argv,relative_ts)
                else:
                    follow_track_histogram(argv,relative_ts)
            else:
                extract_graph(argv)

        except Exception as e:
            traceback.print_exc()
        self.dont_repeat()
        vdb.util.bark() # print("BARK")

cmd_graph()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
