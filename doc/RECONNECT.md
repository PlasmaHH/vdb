# Reconnect module

The reconnect module automatically tracks the current remote debugging connection and provides a quick way to reconnect
if the connection is lost or needs to be reestablished.

## Overview

When debugging remotely (e.g., via gdbserver), the connection can sometimes be lost due to network issues, target resets,
or other reasons. Instead of manually typing the full `target remote` command again, the reconnect module remembers the
last connection details and allows reconnection with a single command.

## How It Works

The module monitors gdb connection events and automatically stores the connection type and details (host, port) whenever
a new connection is established. This happens transparently in the background.

The connection details are captured at the following points:

1. When a connection is removed (via the `connection_removed` event)
2. Before the first prompt is displayed at startup

## Commands

### `reconnect`

Reconnects to the last known remote target. This is equivalent to typing:

```
target remote <host>:<port>
```

or

```
target extended-remote <host>:<port>
```

depending on the connection type that was stored.

If no previous connection was recorded, an error message is displayed.

```
(gdb) reconnect
Reconnecting to localhost:3333
```

## Use Cases

### Target Reset During Debugging

After a target MCU resets and gdbserver reconnects, the local gdb session may lose its connection. Running `reconnect`
quickly reestablishes the session.

### Network Interruption

If the debug probe disconnects briefly (USB dropout, network glitch), use `reconnect` to restore the session without
having to remember the exact connection string.

### Switching Between Targets

When working with multiple targets, you can reconnect to a previous target quickly.

## Limitations

- Only the most recent connection is remembered. If you switch between multiple targets, only the last one is stored.
- The module relies on gdb's connection events, which may not capture all connection scenarios.
- Connection details are stored in memory and will be lost if gdb is restarted.

## Configuration

There are no user-configurable parameters for the reconnect module. It operates automatically in the background.