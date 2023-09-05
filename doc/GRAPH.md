# Graph module

> **Note:** This module is very experimental and things will change a lot and break on the way.

## gnuplot vs. matplotlib
We can use two ways to generate graphs. One is calling gnuplot to generate a static image ( optionally into a file ), or
use matplotlib to generate a window with the graph that can interactively update.

Where possible we will try to detect the availability of either and just not be able to use the specific commands
instead of failing to load.

Per default we use matplotlib, Use `/g` to switch to gnuplot instead.

## matplotlib
Matplotlib has various styles, you can specify which one to use via the `vdb-graph-plot-style` setting.

### histograms
Use `/h <varname>` to create a histogram. It will open a matplotlib window that contains a histogram with `vdb-graph-default-bins`
bins. It will use all the data it can get from the `<varname>` in the track data. Should the track data not contain
anything, the graph will not update.

Unified data collection is supported ( see [track module](doc/TRACK.md) ).

The graph will update every `vdb-graph-default-histogram-updates` seconds. The actual data is sent from within the track
module and is updated each time the track is triggered (either on breakpoints or on the interval timer).

The x and y axis will automatically update to fit the data.

![](doc/img/graph.0.png)
### line graphs
Using `/l <varname>` will create a line graph with the values from the track variable `<varname>` and its timestamps.
The graph will update every `vdb-graph-default-line-updates` seconds.

The x and y axis are automatically updated each time. After `vdb-graph-default-window` seconds, the graph starts
scrolling instead of just adding more and more data to the right.

![](doc/img/graph.1.png)
