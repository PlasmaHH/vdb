# rtos module
This module tries to provide support for realtime operating systems, mostly those for embedded systems running in a
single address space.

Currently the following are supported:

* SEGGER embOS

Future versions of this plugin may support more (we need to be able to play with them) and also auto detect which one is
active so you can uniformly always use the rtos and its subcommands.
## `rtos`  command

The rtos command tries to display a list of tasks among with other useful information that may vary for the OS flavors.

### embOS

The rtos task list for embOS contains:

* ID
* Name
* Stack pointer (Only valid for suspended tasks)
* Priority
* Status (Waiting, sleeping etc.)
* Program counter
* Optional link register or return address (mostly for cooperative tasks)

## `rtos bt` subcommand

This will output the same lines as `rtos`  but additionally tries to recoved a backtrace in the usual format. Since the
support in gdb for faking a stacktrace is limited, this sometimes fails to unwind far enough.

One gdb has better support for "green threads" we expect this to improve.
