# RTT module

The RTT (Real Time Transfer) module provides support for reading SEGGER RTT output from embedded targets. RTT is a
communication mechanism that allows the target microcontroller to send output to the host without using physical
communication interfaces like UART.

## Overview

SEGGER RTT works by using shared memory buffers between the target and the host. The target writes to these buffers,
and the host (via this module) reads from them. This requires that the target binary contains the SEGGER RTT library
and that the `_SEGGER_RTT` global symbol is available.

## Commands

### `rtt stream [channel]`

Continuously streams RTT output from the specified channel (default: 0). This command runs in a loop, using watchpoints
on the write offset to detect new data. The stream continues until interrupted with Ctrl+C.

```
(gdb) rtt stream
Hello from MCU!
Sensor value: 42
^CKeyboard interrupted, stopping to stream channel 0
```

### `rtt start`

Starts RTT monitoring. This is a placeholder for future functionality to automatically start RTT capture.

### `rtt stop`

Stops RTT monitoring. Placeholder for future functionality.

### `rtt status`

Shows the current RTT status. Placeholder for future functionality.

### `rtt dash`

Links RTT output to a dashboard. Placeholder for future functionality.

## How It Works

The module works by:

1. Finding the `_SEGGER_RTT` global structure in target memory
2. Reading the RTT channel buffer configuration (buffer pointer, size, read/write offsets)
3. Setting up a watchpoint on the write offset to detect when new data is available
4. Reading new data when the watchpoint is triggered

## Requirements

- The target must be linked with the SEGGER RTT library
- The `_SEGGER_RTT` symbol must be available in the binary
- Hardware watchpoint support is recommended for efficient data detection
- The target and host must share memory (e.g., via gdbserver or a debug probe)

## Limitations

- Only supports the standard SEGGER RTT format
- Requires the target to be stopped for initial buffer setup
- Watchpoint-based detection may have performance implications on some targets
- Start/stop/status commands are currently placeholders

## Configuration

There are no user-configurable parameters for the RTT module at this time.