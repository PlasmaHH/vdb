# vmmap module

This module ties together information from various sources and provides access to this information under a unified
interface. Internally it relies on the memory module which does the heavy lifting and is queried by this module.

## Commands
### `vmmap`
Without parameters it shows a list of memory ranges and colours their addresses according to the memory types. The ranges can overlap. Additionally it shows section names and source files.

Different components of gdb provide different section names, if there is an alternative name it will be shown in []. Also the file information can differ, as some show the file name that was used to load, others dereference all symlinks.

As one of the parameters it accepts a colorspec, the other is an address. If the address lies within overlapping sections it will show the smallest matching section.

### `vmmap/s`
Short version of the memory map information.

### `vmmap refresh`
Re-read the memory map information by triggering the memory module to re-parse all sources. This also happens automatically at most stop events.

### `vmmap <expr>`
Checks the expression/address and displays all details known about that memory region, including access type, memory type, and section information.

### `vmmap <expr> <colorspec>`
Same as above but uses the specified colorspec for coloring.

### `vmmap visual`
Displays a visual representation of memory layout, showing memory clusters as ASCII art. It groups memory regions into clusters separated by gaps and displays them using block characters. This is useful for getting an overview of memory usage patterns.

## Configuration

* `vdb-vmmap-colors-executable` Colour for executable memory regions (default `#e0e`).
* `vdb-vmmap-colors-readonly` Colour for readonly memory regions (default `#f03`).
* `vdb-vmmap-colors-empty` Colour for empty/unmapped regions in visual display (default `#151515`).
* `vdb-vmmap-visual-max-size` Maximum width of the visual display in characters (default `8192`).
* `vdb-vmmap-wrapat` Line wrap width for visual display (default `0` = auto-detect terminal width).
* `vdb-vmmap-chars` Characters used for the visual display, from empty to full (default ` ▂▃▄▅▆▇█`).