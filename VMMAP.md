# vmmap module

This module ties together information from various sources and provides access to this information under a unified
interface. Internally it relies on the memory module which does the heavy lifting and is queried by this module.

## Commands
### `vmmap`
Without parameters it shows a list of memory ranges and colours their addresses according to the memory types. The ranges can overlap. Additionally it shows section names and source files.

Different components of gdb provide different section names, if there is an alternative name it will be shown in []. Also the file information can differ, as some show the file name that was used to load, others dereference all symlinks.

As one of the parameters it accepts a colorspec, the other is an address. If the address lies within overlapping sections it will show the smallest matching section.


