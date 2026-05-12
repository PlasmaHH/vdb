# SWO module

The SWO (Serial Wire Output) module captures and displays output from ARM Cortex-M targets via the SWO pin. This is a
unidirectional output channel used by microcontrollers for debugging output, profiling, and tracing.

## Overview

The module connects to a TCP server (typically provided by a debug probe like J-Link) that decodes the raw SWO protocol
and forwards the data. The vdb SWO module then parses the protocol packets, routes data to the appropriate channels,
and displays it with proper formatting and coloring.

## Protocol Support

The module implements parsing of the SWO protocol as defined in ARM DDI 0403 (ARMv7) and DDI 0553 (ARMv8). The following
packet types are supported:

- **Source packets** - Data from ITM (Instrumentation Trace Macrocell) channels
- **Sync packets** - Protocol synchronization
- **Overflow packets** - Detected and reported
- **Timestamp packets** - Local and global timestamps (detection only, not fully parsed)
- **Extension packets** - Detection only
- **PC trace packets** - Hardware trace source with 1-byte or 4-byte payload

## Commands

### `swo start`

Starts the SWO capture thread. Connects to the configured host and port and begins decoding the SWO protocol stream.
The capture runs in a background thread.

```
(gdb) swo start
Starting SWO Thread...
```

### `swo stop`

Stops the SWO capture thread.

```
(gdb) swo stop
Stopping SWO Thread...done
```

### `swo status`

Displays a table with the status of all active SWO channels:

```
(gdb) swo status
+---------+------------+--------------+-------------+
| Channel | Buffersize | Last Flushed | Dashboard   |
+---------+------------+--------------+-------------+
|       0 |          0 |    1234.5678 | none        |
|       1 |         42 |    1234.5679 | none        |
+---------+------------+--------------+-------------+
```

### `swo dash <channel> <dashboard_id_or_command>`

Links a SWO channel to a dashboard for continuous display. The second argument can be either a dashboard ID number or a
dashboard creation command.

```
(gdb) swo dash 0 1          # Link channel 0 to dashboard ID 1
(gdb) swo dash 0 tmux foo   # Create a new tmux dashboard and link channel 0
```

### `swo pc_report [limit] [/maxrows]`

Generates a report of PC trace data, showing instruction counts per function. The data is collected from hardware trace
packets and aggregated by function name.

Optional parameters:
- `limit` - Minimum instruction count or percentage threshold to display
- `/maxrows` - Maximum number of rows to display

### `swo pc_clear`

Clears all collected PC trace counters.

### `swo pc_lru`

Shows the most recent PC addresses captured from hardware trace. Requires `vdb-swo-pc-trace-lru` to be set.

## Configuration

### Connection Settings

```
vdb-swo-host
```
The hostname or IP address of the SWO TCP server (default: `localhost`).

```
vdb-swo-port
```
The TCP port of the SWO server (default: `22888`).

### Buffering and Flushing

```
vdb-swo-flush-timeout
```
Timeout in milliseconds after which an idle buffer will be flushed (default: `50`).

```
vdb-swo-flush-watermark
```
If the channel buffer reaches this many bytes, it will be flushed immediately (default: `64`).

### Auto-reconnect

```
vdb-swo-auto-reconnect
```
Automatically reconnect to the SWO server if the connection is lost (default: `True`).

### Display

```
vdb-swo-colors
```
Comma-separated list of default colors for channels (up to 10 channels). Individual channel colors can be overridden
with `vdb-swo-colors-N`.

```
vdb-swo-colors-N
```
Color for channel N (where N is 0-9).

```
vdb-swo-use-rich-N
```
Whether to use rich text rendering for channel N (default: `True`).

```
vdb-swo-short-rich-N
```
Whether to use short rich text mode for channel N (default: `True`).

```
vdb-swo-show-packet-type
```
Show packet type information during decoding (useful for debugging, default: `False`).

```
vdb-swo-rich-replacements
```
Rich text color replacements in the format `TAG:COLOR`. For example: `R:#ff0000,G:#00ff00,B:#0000ff`.

### Auto-start

```
vdb-swo-autostart
```
Automatically start SWO capture before the first prompt is displayed (default: `False`).

### PC Tracing

```
vdb-swo-pc-trace-file
```
File path to write PC trace data to CSV (empty = disabled).

```
vdb-swo-pc-trace-lru
```
Maximum number of recent PC addresses to track in the LRU queue (0 = disabled).

## Channel Colors

Each SWO channel (0-9) can be assigned a different color. The colors are applied when the channel buffer is flushed.
The module uses the `rich` library for text rendering, which supports ANSI escape sequences and rich markup.

## Rich Text Support

The SWO module can process SEGGER-style rich text formatting codes. Characters in brackets like `[R]` (red), `[G]`
(green), `[B]` (blue) are mapped to colors defined in `vdb-swo-rich-replacements`.

## PC Trace

When the target sends PC trace packets (hardware trace source), the module can:

1. Count instruction executions per address
2. Map addresses to function names
3. Generate profiling reports showing CPU time distribution

This feature requires hardware trace support on the target and debug probe.

## Limitations

- Timestamp and extension packets are detected but not fully parsed, which may cause desync
- PC trace functionality is primarily designed for Cortex-M targets
- The module assumes a TCP server is available to decode raw SWO protocol
- Rich text rendering may fail for certain escape sequences