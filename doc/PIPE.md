# Pipe module

The pipe module allows piping the output of gdb commands through external shell commands and utilities. It provides three
types of piping: standard shell commands, wrapped gdb commands, and external tools.

## Shell Commands

Basic shell commands can be used to filter gdb output. By default, the following commands are available:

```
sed, hl:grep --color=always -C50000, grep, egrep, tee, head, tail, uniq, sort, less, cat, wc
```

### Usage

After running a gdb command, pipe its output using:

```
(gdb) info registers | head -5
(gdb) bt | grep main
(gdb) x/100bx $sp | less
```

Some commands in the configuration can have aliases. For example `hl:grep --color=always -C50000` creates a pipe command
named `hl` that runs `grep --color=always -C50000`.

### Configuration

```
vdb-pipe-commands
```

Comma-separated list of shell commands that can be used for piping. Each entry can be either a simple command name, or
an `alias:command args` pair where the alias becomes the pipe command name.

## Wrapped Commands

Certain gdb commands are wrapped to provide pipe support. The wrapped commands are available with a capitalized name:

```
Python, Show, Info, Help, X, Print, Set, Maint, Monitor
```

### Usage

```
(gdb) Print $pc | less
(gdb) Info files | grep loaded
(gdb) Show config vdb | head
```

The wrapped command intercepts the output and allows piping it through shell commands.

### Configuration

```
vdb-pipe-wrap
```

Comma-separated list of gdb command names to wrap. These commands will be available with a capitalized first letter.

## External Commands

External tools can be registered as gdb commands. These tools receive the current executable file name as a parameter
automatically.

### Default External Commands

```
bat, binwalk, objdump, tmux, addr2line:-e {file} -a
```

### Usage

```
(gdb) objdump -d -S
(gdb) addr2line 0x400520
(gdb) bat src/main.c
```

For commands with predefined arguments (like `addr2line:-e {file} -a`), the `{file}` placeholder is replaced with the
current executable file path. User-provided arguments are inserted before the file argument.

To skip the automatic file argument, use the `/r` flag:

```
(gdb) objdump/r -h /path/to/other/file
```

### Configuration

```
vdb-pipe-externals
```

Comma-separated list of external commands. Each entry can be either a simple command name, or a `command:args` pair
where `args` can contain `{file}` as a placeholder for the current executable file path.

## Examples

### Filtering Register Output

```
(gdb) reg | grep sp
(gdb) reg | hl stack
```

### Examining Memory with Less

```
(gdb) x/200bx $sp | less
```

### Using Objdump on Current Binary

```
(gdb) objdump -d --disassemble=main
```

### Piping Backtrace

```
(gdb) bt | grep -v frame
(gdb) bt | wc