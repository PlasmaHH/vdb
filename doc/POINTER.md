# Pointer module

The pointer module provides functionality for pointer colorization, chaining, and dereferencing. It is used internally by
multiple other modules (register, hexdump, backtrace, asm, etc.) to provide consistent and informative pointer display.

## Pointer Colorization

The primary function of the pointer module is to colorize pointer values based on the known memory layout. When a pointer
is displayed, it is colored according to where it points in memory (stack, heap, code, BSS, etc.).

The colorization uses the `colorspec` from the vmmap module to determine which coloring mechanism to apply:

* `A` - Colors the pointer if the *pointer value itself* is detected as a valid ASCII (UTF-8) string
* `a` - Colors by memory access type (see vmmap module)
* `m` - Colors by memory type (see vmmap module)
* `s` - Colors by section name (see vmmap module)

## Pointer Chaining

One of the most useful features is pointer chaining, which automatically dereferences pointers recursively and displays
them as a chain of arrows. This continues until a maximum depth is reached or a "useful" terminal value is found.

### tailspec (chain termination)

The `tailspec` determines when pointer chaining should stop and what to display at the end of the chain. The following
specifiers are supported:

* `a` - Points to an ASCII string (displays the string content)
* `x` - Points to executable memory (displays the disassembled instruction)
* `n` - Points to a named object (stops chaining, the name is already shown by annotation)
* `d` - Points to a valid double-precision floating-point value
* `D` - The pointer value itself is interpretable as a double-precision floating-point value

### Configuration

The following settings control pointer chaining behavior:

* `vdb-pointer-arrow-right` - Arrow character for forward dereference (default: ` → `)
* `vdb-pointer-arrow-left` - Arrow character for backward reference (default: ` ←  `)
* `vdb-pointer-arrow-infinity` - Arrow for self-referencing pointers (default: ` ↔ `)
* `vdb-pointer-ellipsis` - Character shown when chain depth is exceeded (default: `…`)
* `vdb-pointer-min-ascii` - Minimum number of printable characters to detect an ASCII string (default: 3)
* `vdb-pointer-max-exponents` - Comma-separated pair of exponents for double detection heuristic (default: `-6,15`)

### Usage in Other Modules

Pointer chaining is used by various modules. Each module can configure its own `tailspec`:

* **register module** - Uses `vdb-register-tailspec` to control pointer display for register values
* **asm module** - Uses `vdb-asm-tailspec` for constant and immediate value annotation
* **hexdump module** - Uses `hexdump/p` for pointer array display

## Pointer Annotation

The module can annotate pointers with symbol names when the pointer falls within a known symbol's range. This is done
via the `annotate()` function which queries gdb's symbol table.

## ASCII String Detection

When a pointer value appears to point to a printable ASCII/UTF-8 string, the module will detect and display it. The
detection requires at least `vdb-pointer-min-ascii` consecutive printable characters. This helps identify cases where a
pointer value was incorrectly set to an ASCII string instead of a valid memory address.

## Double Value Detection

The module can detect when a pointer value, when interpreted as a double-precision floating-point number, represents a
valid double value. The heuristic uses the binary exponent range specified in `vdb-pointer-max-exponents` to filter out
false positives (e.g., all-zero bytes).

## Internal API

The module provides the following functions for use by other vdb modules:

* `color(ptr, archsize)` - Returns colorized pointer string with memory type information
* `chain(ptr, archsize, maxlen, test_for_ascii, minascii, last, tailspec, do_annotate)` - Returns a pointer chain string
* `annotate(ptr)` - Returns symbol annotation for a pointer
* `as_c_str(ptr, maxlen)` - Reads a C-string from a pointer address
* `as_tailspec(ptr, minasc, spec)` - Evaluates a tailspec for a given pointer
* `dereference(ptr)` - Dereferences a gdb pointer value

## Examples

### Pointer Chain Display

```
0x7fffffffd470 → 0x00416eb0 → [5]'hello'
```

This shows a pointer at `0x7fffffffd470` pointing to `0x00416eb0` which contains the ASCII string "hello".

### Self-Referencing Pointer

```
0x555555555000 ↔ 0x555555555000
```

The infinity arrow indicates a pointer that points to itself.

### Chain Depth Exceeded

```
0x7fffffffd470 → 0x555555555000 → 0x7fffffffd3e0 → …
```

The ellipsis indicates the maximum chain depth was reached.