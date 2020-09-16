## track

The `track` command allows you to track the data of gdb expressions on hitting breakpoints. While this module is active,
whenever a breakpoint is hit an internal callback will be called, this may be a performance issue for some. All
breakpoints that have a trackpoint attached will automatically continue when hit, making data collection an automated
task.

### `track show`

Shows the currently known breakpoints (similar to `info break`) along with the information about registered tracking
information.

![](img/track.0.png)

### `track <num|location> <expression>`
This will  use gdbs existing breakpoint no `num` and will execute `expression` each time, recording the resulting string
along with a timestamp.

Instead of giving a number in `num` you can also provide an expression that will then be given to gdb to create a new
breakpoint. This breakpoint however will remain active even after the trackpoint has been deleted. Be careful though
that you may end up with multiple breakpoints for the same address which may incur a performance hit. We try to filter
out by the location string you passed, but what gdb gives us may not always be the same you passed, thus we can not
distinguish.

### `track data`
This shows a table with all the collected data. In (default) relative mode, all timestamps are relative to the first
recording. You can set `vdb-track-time-relative` to disable this and use local timestamps instead (useful for long
running programs where the breakpoint is only hit occasionally). Note that this will display the string from the
expression per table entry without any further formatting, as such it is most wise to use expressions only that have
small outputs.

Setting `vdb-track-clear-at-start` to off will disable the automated clearing of tracking data when (re)starting a
process.

If at a specific breakpoint an expression did not yield any output (or caused an exception) this field will remain
empty.

![](img/track.1.png)
### `track del`
This deletes a track entry by the number shown in `track show`, just like `del` does for breakpoints. You can specify
multiple trackpoints.


### `track clear`
Clears the data cache displayed by `track data`.


