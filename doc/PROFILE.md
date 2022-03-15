# profile module

This module simply passes the argument to gdb again, but wraps it inside a python cProfile call. This will cause all
python related things to be profiled.

## Commands
### `profile`
Runs the passed command as if it was executed on the command line and displays some information
### `profile/d`
Additionally starts a dotty graph to show more. Needs dot and gprof2dot installed. If thats not the case, there might be
an error, or it will silently be ignored.

