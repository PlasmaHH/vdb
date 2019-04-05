# VDB
A set of python visual enhancements for gdb.

---

**NOTE**
This is work in progress and not yet ready for real world usage, it is more of an experiment of what is possible

---


<!-- vim-markdown-toc GFM -->

* [VDB](#vdb)
	* [Overview](#overview)
	* [Quickstart](#quickstart)
	* [Disabling modules](#disabling-modules)
* [Modules](#modules)
	* [prompt](#prompt)
		* [Configuration](#configuration)
	* [backtrace](#backtrace)
		* [Commands](#commands)
			* [`bt`](#bt)
			* [`bt/r`](#btr)
			* [`bt/f`](#btf)
			* [`backtrace`](#backtrace-1)
	* [vmmap](#vmmap)
		* [Commands](#commands-1)
			* [`vmmap`](#vmmap-1)
	* [register](#register)
		* [Commands](#commands-2)
			* [`reg`](#reg)
			* [`reg/s` (short)](#regs-short)
			* [`reg/e` (expanded)](#rege-expanded)
			* [`reg/a` (all)](#rega-all)
			* [`reg/f` (full)](#regf-full)
	* [hexdump](#hexdump)
		* [Commands](#commands-3)
			* [`hd`](#hd)
	* [asm](#asm)
		* [Commands](#commands-4)
			* [`dis`](#dis)
			* [`dis/<context>`](#discontext)
			* [`dis/d`](#disd)
			* [`dis/r`](#disr)
	* [grep](#grep)
	* [pahole](#pahole)
		* [Commands](#commands-5)
			* [`pahole`](#pahole-1)
			* [`pahole/c`](#paholec)
			* [`pahole/e`](#paholee)
	* [ftree](#ftree)
		* [Commands](#commands-6)
			* [`ftree`](#ftree-1)
		* [Special Filter Functionality](#special-filter-functionality)
			* [Downcasting to hidden types](#downcasting-to-hidden-types)
			* [Pretty print filters](#pretty-print-filters)
			* [Expansion blacklists](#expansion-blacklists)
			* [dynamic array/vector type detection](#dynamic-arrayvector-type-detection)
* [global functionality](#global-functionality)
	* [shorten](#shorten)
	* [pointer (chaining)](#pointer-chaining)
	* [memory layout](#memory-layout)
	* [type layout](#type-layout)
* [Configuration](#configuration-1)
	* [gdb config](#gdb-config)
	* [Color settings](#color-settings)
		* [colorspec](#colorspec)
* [Plugins](#plugins)
* [Themes](#themes)

<!-- vim-markdown-toc -->

## Overview
vdb aims to display as much information as it can without cluttering the
display. It can filter and colorize output, and when the terminal isn't enough
anymore it creates dot graphs and images.

It tries to be as minimally invasive as possible, allowing to disable certain
modules and commands to not interfere with other python plugins.

## Quickstart
First clone the repo
```
git clone https://github.com/PlasmaHH/vdb.git
```
Install dependencies from the `requirements.txt` or install as a package.
Then add this to your `~/.gdbinit`
```
source ~/git/vdb/vdb.py
vdb start
```
In case a depdendency is not available, the module needing it will not load, but all others should. In practice this
means screens full of error messages and a limited feature set, but for a lot of modules plain pyhton is enough. The
most noteable exception though is the ansicolor module which of course  is necessary since basically all features are
about colours.
## Disabling modules
There is one boolean gdb option per module. Setting those to off before `vdb
start` will prevent the corresponding module from being loaded. Once loaded a
module cannot be unloaded.
```
vdb-enable-prompt
vdb-enable-backtrace
vdb-enable-register
vdb-enable-vmmap
vdb-enable-hexdump
vdb-enable-asm
```
Additionally there is the gdb config 
```
vdb-available-modules
```
available which will not only allow for a more concise way to disable modules, it will also control the order in which
they are loaded. Must be set before a vdb start and contains a comma separated list.

The drawback however is that you will miss out new modules when updating, as they are not in the list.
# Modules
## prompt
This module allows you to configure the prompt to display more information.

For now this only sets the prompt to `vdb> ` in a certain colour. In the future we will add more information about the
currently running program or core file, maybe we can hack together a good multiline or airline prompt.

XXX Maybe as a first one the thread that is selected, as for breakpoints or other things this changes unintuitively.
Maybe also add a feature to autoselect a thread or a frame (given by some complex path?)
### Configuration

* `vdb-prompt-colors-text` The colour of the whole standard prompt
* `vdb-prompt-text` The text of the prompt, defaults to `vdb> `

## backtrace
We provide a backtrace decorator with various colouring options. It will also show some information about whether something
is inlined or some information about signals and crashes.

![](img/bt.png)

* `vdb-bt-colors-namespace` Colour all namespace names (for the purpose of this plugin, this includes class type names)
* `vdb-bt-colors-address` Addresses in the address column. Set this to none to use the global pointer colours by memory area type.
* `vdb-bt-colors-function` Function name (without any namespace and template parameters)
* `vdb-bt-colors-selected-frame-marker` The marker that shows which frame gdb has currently selected
* `vdb-bt-colors-filename` The filename (and line number) of the source code for this frame
* `vdb-bt-colors-object-file` The object file, in case the file and line numbers are unavailable
* `vdb-bt-colors-default-object` In case the two above could not be determined, show whatever gdb would have shown per
  default (usually the object name)
* `vdb-bt-colors-rtti-warning` Sometimes gdb can't properly access the RTTI information. While we try to be as good as
  possible in recovering it, gdb outputs warnings. They are usually suppressed and just a small string displayed in this
  colour.

Addresses (in the address column) is some special biest. Since the gdb decoration mechanism only allows us to return
integers/pointers, we are forced to hack around this by putting the strings elsewhere. There are situations  where this
can look funny. You can use the following setting to disable the colouring then. 
```
vdb-bt-color-addresses=true
```
Per default the colour is chosen by the
pointer color according to the colorspec (See section colorspec) below.
```
vdb-bt-address-colorspec="ma"
```
The showspec setting
```
vdb-bt-showspec="naFPs"
```


tells what should be displayed in the backtrace. Missing items are suppressed. The string can contain (in any order)
* `n` The frame number.
* `a` The address, coloured according to the above settings
* `f` or `F` the function name. For `F` we use the full name (minuse folds and shortens), for `f` we display just the
  name without any parameters or templates.
* `p` or `P` shows the parameters of the function. For `p` we only show the names, for `P` we also try to get gdb to
  print some values for them
* `s` shows the source of that frame. Can be a source file (with line) or some object file name.

You can also change the marker for the selected frame, this may be useful if your terminal does not support the default utf8 character.
```
vdb-bt-selected-frame-marker
```
### Commands
We provide the following commands
#### `bt`
This should be your default. It will do all the filtering and sometimes write some additional data.
#### `bt/r`
This is like `bt` but disables the filter aka. raw. You should not see additional data, but the unfiltered plain gdb output.
#### `bt/f`
This is like `bt` but also passes the `full` parameter to backtrace to show all local variables per stackframe. These are not currently filtered.
#### `backtrace`
This is an unmodified gdb version, that is running the decorator, but not additional filters and outputs. It may be overridden by additional gdb plugins that you have. This has the added disadvantage that the `n` showspec doesn't have any effect, as well as the RTTI warning filter not working.

## vmmap
A module that allows access to the internal information of memory maps. It ties together information from the sources of
* `info files`
* `maint info sections`
* `info proc mapping`
### Commands
#### `vmmap`
Without parameters it shows a list of memory ranges and colours their addresses according to the memory types. The ranges can overlap. Additionally it shows section names and source files.

Different components of gdb provide different section names, if there is an alternative name it will be shown in []. Also the file information can differ, as some show the file name that was used to load, others dereference all symlinks.

As one of the parameters it accepts a colorspec, the other is an address. If the address lies within overlapping sections it will show the smallest matching section.
## register

### Commands

#### `reg`
This command is like `info register` just with a bit more information and options. It can display the most basic
registers or an existed version of all registers. Just a hex value overview, or a detailed dereference chain. It
colouors the pointer according to where they point to (see the legend of the command). It tries to detect when a pointer
value is invalid, but contains an ascii string instead (hints to it being read from re-used memory). It has the
following variants (and defaults to what is configured in `vdb-register-default`, which itself defaults to `/e`):
#### `reg/s` (short)
![](img/reg.s.png)
#### `reg/e` (expanded)
![](img/reg.e.png)
#### `reg/a` (all)
![](img/reg.a.png)
#### `reg/f` (full)
(not yet implemented)

## hexdump
This module provides a coloured hexdump of raw memory, possibly annotated in various ways.

### Commands

#### `hd`
This command dumps the range of memory specified by the parameter. If you omit the second size parameter, it will be set
to the value of `vdb-hexdump-default-len`. It will try to dump that many bytes, if along the way it reaches a point
where memory will not be accessible anymore, it stops.

![](img/hd.png)

If it knows the memory belongs to some symbol, it will colour it in a specific colour and annotate the symbol at the
side. You can control the color with the semicolon separated list of colours in the `vdb-hexdump-colors-symbols` setting.

The setting
```
vdb-hexdump-colors-header
```
controls the colour of the header (the one that should make it a bit simpler to find certain bytes). 
## asm
This is a disassembler module

### Commands

#### `dis`
This is a "plain" disassembly. It expects a gdb expression as a parameter that would be accepted by gdbs `disassemble`
command.

The displayed data can be controlled by the following showspec setting

```
vdb-asm-showspec
```

The order is fixed and the showspec entries mean the following:

* `m` Shows a marker (configured by `vdb-asm-next-marker`) for the next-to-be-executed instruction
* `a` Shows the address
* `o` Shows the offset
* `d` Shows a tree view of the known jumps in the current listing. They are coloured in a round robin fashion. It tries
  to detected computed jumps but isn't very good in it.
* `b` Shows the instruction bytes
* `n` Shows the mnemonic (along with its prefix).
* `p` Shows the parameters to the mnemonic
* `r` Shows a reference, this is mostly arbitrary text that the disassembler gave us (or text that we failed to parse properly)
* `t` or `T` Shows for jump and call targets the target name, run through the standard shorten and colour mechanism


The following settings control the colours
```
vdb-asm-colors-namespace
vdb-asm-colors-function
vdb-asm-colors-bytes
vdb-asm-colors-next-marker
vdb-asm-colors-addr
vdb-asm-colors-offset
vdb-asm-colors-bytes
vdb-asm-colors-prefix
vdb-asm-colors-mnemonic
vdb-asm-colors-args
```

Additionally `vdb-asm-colors-jumps` is a semicolon separated list of colours to use for the jump tree view.

If you set the addr colour to `None` (default) it will use the standard pointer colouring. If you set the mnemonic
colouring to `None` (default) it will use a list of regexes to check for which colouor to chose for which mnemonic. Same
for the prefix.

You have a little more control over the way offset is formatted by using the setting `vdb-asm-offset-format` which
defaults to `<+{offset:<{maxlen}}>:` where `offset` is the offset value and `maxlen` is the maximum width of an integer
encountered while parsing the current listing.

![](img/disassemble.png)

In case your tree view is very wide, you might
like setting the option `vdb-asm-tree-prefer-right` to make the arrows prefer being more on the right side.
#### `dis/<context>`
This limits the displayed disassembly to the context of the passed amount of lines around the `$rip` marker. Should
there be no such marker, this has no special effect. Note that the whole disassembly will be generated, filtered, and
rendered (at least partially), just the output of the other lines suppressed, so if you want this for speedup, this
isn't for you. The benefit however is that the jump tree view will be completely fine.

#### `dis/d`
Outputs the disassembler just like the plain format, additionally creates a `dis.dot` file that will contain a dotty
representation of what we think might be basic blocks and (conditional) jump instructions. It will also try to start
dot with the command specified in `vdb-asm-`

The following example is the same as the disassembler listing above. It doesn't use the `r` and `t` showspecs for
brevity.

![](img/dis.dot.png)

The whole settings for colours of the terminal listing exist too for the dot ones, just append `-dot` to the setting
name. The showspecs are the same with the exception of the tree view. The layout of graphviz can sometimes be a mess,
therefore we offer the following ways to influence things in the graph (besides colour):

* `vdb-asm-prefer-linear-dot` configures that the layout should give priority to the order of instructions when laying
  out the graph (makes dot edges unconstrained for non consecutive instructions). Can get a bit messy when there are
  unconditional jumps.
* `vdb-asm-font-dot` is a comma separated list of fonts. It is embedded int the `.dot` file and the exact format depends
  on how your graphviz is compiled, on the majority of the system it should be the names you can get via `fc-list`.
#### `dis/r`

This calls the gdb disassembler without any formatting
## grep
When loading this module, all our commands support a pipe like syntax to call grep on the output. The data will be piped
to an externally called grep, as well as the parameters to grep.

![](img/grep.png)

## pahole
This is an enhanced and redone version of the pahole python command that once came with gdb. It has support for virtual
inheritance and a possibly more useful layout display. Bitfield support is missing for now as well as proper support for
unions. Type names are shortened via the standard mechanism where possible.
### Commands

#### `pahole`
This expects a type and can have one of two flavours, see below. Setting `vdb-pahole-default-condensed` will change the
default, but you can always override with `/c` or `/e`

The following examples are for the following code:
<table>
<tr>
<td>

```c++
struct f0 {
	char c;
	uint32_t x;
	virtual ~f0(){}
};

struct f1 : f0 {
	char c;
	uint32_t x;
	virtual ~f1(){}
};

struct f2 : f1,f0 {
	char c;
	uint32_t x;
	virtual ~f2(){}
	char o;
};
```
</td>
<td>

```c++
struct innerst {
	int i;
	double po;
};

struct small {
	char c = 'C';
	uint16_t x = 0x8787;
	char h = 'H';
};

struct big {
	uint64_t n = 0x7272727272727272;
};

struct morev : virtual small, virtual big, virtual innerst {
	uint64_t y = 0x4b4b4b4b4b4b4b4b;
	uint16_t p = 0x1515;
	char u = 'U';
};

```
</td>
</tr>
</table>


#### `pahole/c`
This shows the types layout in a condensed format, one line per member, showing which bytes belong to it in the front

![](img/pahole.f.c.png)
![](img/pahole.m.c.png)

#### `pahole/e`
This shows the layout in an extended format, one line per byte.

![](img/pahole.f.e.png)
![](img/pahole.m.e.png)


## ftree
The ftree module allows for creation of dotty files that create a tree (or directed graph) out of a datastructure.

For example, the following structure filled with life 

```c++
struct xtree
{
	std::string str{"HELLO WORLD"};
	std::string& xstr = str;
	std::unordered_map<int,int> u;
	std::vector<int> v { 1,2,3,4,5,6,7,8 };
	std::vector<std::string> sv { "1","2","3","4","5","6" };
	std::array<double,13> a;
	std::map<int,int> m;
	std::map<int,int> bl;
	std::list<std::string> l { "A","B","L" };
};
```

could be displayed as

![](img/ftree.0.png)


### Commands

#### `ftree`
The ftree command expects a pointer to an object. It will create a dot file based on the filename configured in
`vdb-ftree-filebase`. The string there will be fed through strftime and then `.dot` will be appended to it. The default
is `ftree` so it will always overwrite the last one. Using `ftree.%s` will be the most trivial way to create a file for
each invocation.

After the dot file is created, the generated filename will be fed to the string format in `vdb-ftree-dot-command` and
the created command will be excuted, usually to display the generated file directly.

Pointers will be displayed with their value, and a dot edge drawn to the object it points to. Cells will be colored
according to the following settings:

* `vdb-ftree-colors-invalid` When the memory is inaccessible, the background of that table cell will be this color. Various other kinds of exceptions generated during the creation of the target node can unfortunately also lead to that
colour.
* `vdb-ftree-colors-union` When this field is a union, it will have this colour. This means that all the direct
  subfields share the same memory.
* `vdb-ftree-colors-virtual-cast` is the color of a node when the pointer was pointing to a base class but we determined
  it really is a derived object.
* `vdb-ftree-colors-down-cast` When the downcast filter mechanism decided to change the nodes type, it will be colored
  in this color. Depending on the actual circumstances this and the virtual cast color can compete with each other and
  only one wins.

Additionally the following settings influence the generated graph:

* `vdb-ftree-shorten-head` When the type string in the nodes header is too long, it will be shortened and this amount of characters will be taken from the type names head
* `vdb-ftree-shorten-tail` Same as head, but for tail
* `vdb-ftree-verbosity` Setting this to  4 or 5 will create some debug output about the type matching for the cast and array filters. Usually you want to set this to fine tune the regex.

### Special Filter Functionality

Via the plugin mechanism you can put into the `.vdb/ftree/` dir a python file that imports the ftree module and calls
some functions for the following functionalities. For examples it is best to look at the existing source code. There is
always one add and one set function. The add function adds one to the existing list, the other sets the whole list. This
is useful when you don't want to use the built in functionality.

#### Downcasting to hidden types
When there is a pointer of a base class type, we try to get the dynamic type via RTTI from gdb. If the type has integers
as template parameters (or some other corner cases) gdb will sometimes fail to find the type information (because the
internal string representation does not match up) and then we try to work around that. 

Sometimes there is a pointer pointing to base classes of a non-virtual type, thus we don't have any RTTI. In that case
we have a mechanism that gets a type path (that is all the types and members involved that lead to it), applies a regex
to it, and then transforms it into a new type string and then cast it to that. See the examples for some `std::`
containers that have nodes. They are accessed through a base class and then `static_cast`ed to the right type, thus we
have to do the same.

Functions to call

* `{add,set}_node_downcast_filter` add a regex and a callable object. When the type matches, the callable will be called
  with the regex match object, gdb.Value and object path. The result is either None or a gdb.Type that the node pointer
  will be caste to before a new node will be extracted from it.
* `{add,set}_member_cast_filter` This is basially the same, but for members of a node. The resulting type therefore is
  not a pointer type.

#### Pretty print filters

For certain types we may want to use the gdb pretty printer to obtain the output rather than to extract all the members.
This is mostly useful for things like `std::string` where we usually don't care about the internals and just about the
value.

* `{add,set}_pretty_print_types` adds a regex that will match a type that will then always be pretty printed. Note that
  when the type exists as a typedef, sometimes you need to match the typedef name.

#### Expansion blacklists
Sometimes you are not interested in certain members at all or don't want the system to follow certain pointers. With
this mechanism you can blacklist those. Table cells will be coloured according to the
`vdb-ftree-colors-blacklist-pointer` and `vdb-ftree-colors-blacklist-member` settings.

* `{add,set}_pointer_blacklist` expects an object path blacklist that will prevent a pointer from being followed to the
next node.
* `{add,set}_member_blacklist` Does not expand the member with the name, but still prints the name.


#### dynamic array/vector type detection
For types like `std::vector` there is usually internally a pointer to the object being stored, but the type system has
no idea that it is pointing to an array, not a single object. Similar to the hidden type thing we have a regex mechanism
that can be used to access other members that then can be used to determine the amount of elements.

The setting `vdb-ftree-array-elements` is a comma seperated list of python like element indices, that is when they are
negative they are counted from the back of the array. Since arrays can be very long, this limits the amount of things
displayed. Per default its the first and last four items.


* `{add,set}_array_element_filter` adds a regex and a callable, the callable should return the amount of elements in the
  array. Optionally the callable can be replaced by a string that will then be fed to a format with the regex match as a
  parameter. This will then be the object path to the amount of elements.

# global functionality
There is some functionality used by multiple modules. Whenever possible we load this lazily so it doesn't get used when
you suppress loading of the modules that load it.
## shorten
There is a configurable way to shorten type names. We will have
* replacements, which plainly replace one string by another. (For now this is string replace only, maybe we should use
  regexes here)
* template folding. We have a list of types (or maybe we should use regexes here too?) that we mark and then we fold the
  complete list of template parameters into one empty list (and colour that).

## pointer (chaining)
The submodule for pointer colouring supports chaining them as well, which will lead to a string of dereferenced pointers
until a determined length is reached or something useful is found. You can find examples in the register commands. It
uses internally the memory layout module

## memory layout
Provides information about the memory layout gathered from various sources. Primary source of information for the vmmap
command as well as the pointer colouring.

## type layout
This is the submodule that is responsible for parsing gdb type information and reconstructing an in-memory layout. This
is mainly used by the pahole command.

# Configuration
The configurability is using two mechanisms. One is the gdb settings. Besides
the module loading settings, all settings are only available after a `vdb
start`.
## gdb config
Setting any string based configuration option to the special value `default` will reset it to the built in default. You
can set them in the .gdbinit file after the `vdb start` command, or you can provide a `~/.vdbinit` file that will be
sourced into gdb when it exists. When the setting <whatever we chose for it> is enabled, we will also read the
./.vdbinit after it, which can be project specific. If that doesn't exist we go down the filesystem until we either find
one, or we reach ~/ (which we already loaded) or /.

## Color settings
All modules that colour their output have settings of the form
```
vdb-<modulename>-color-<elementname>
```
to control the colour of their elements. You can use anything that the python ansicolors module can understand, that is
colours as css style (`#f0f` or `#ff00ff`) or named colours. Per default the colour is the foreground colour, but the
colour can also be a comma seperated list of foreground,background and style. As a style you can chose the standard ansi
style specifications like _underline_. Setting it to `None` will disable any ansi colouring for that element.

Alternatively the upcoming themes mechanism will provide a way to easily bundle all colour information into one python
file
### colorspec
The colorspec is a string made out of any of the following letters. It determines which mechanism will color a pointer.
The first matchin mechanism to return a color stops the search, if none is found, no coloring is done.

* `A` colours the pointer in case it is detected that the *pointer value itself* is a valid ascii (utf8) string. The
  heuristic for this isn't perfect but often good enough to easily detect that some pointer dereference got wrong.
* `a` this colours by the access type (see vmmap module)
* `m` this colours by the memory type (see vmmap module)
* `s` this colours by the section name (see vmmap module)

# Plugins
This is more an extended way to configure and hack things, but we may also provide hooks for extending the
functionality.

Each module has its own path in `~/.vdb/` where arbitrary python files can reside. Whenever the module is enabled by the
gdb setting, the files from that directory are imported. Similar to the `.vdbinit`, we search for a `.vdb` directory in
the current one, and all above that and load all the file we find there, stopping with the search once we found it.


Note to self: should we maybe have a setting that determines if we stop or continue loading? maybe three modes? stop,
forward and backward? So we can have global, project and subproject specific files that override each other?
# Themes
Themes are not really special files themselves, they are python plugins that provide a package of all the necessary code
to change colours to a specific predetermined set. Unlike all the other plugins, themes are selectively loaded, thus you
can have many in the subdirectory, they will all be ignored, just the one configured not.

You can set the theme by setting

```
vdb-theme
```

to the name of the theme/python module to load from the directory `$HOME/.vdb/themes`. You don't specify the `.py`
ending, but the file must have it. Themes will be loaded when you do `vdb start` (most likely in your `.gdbinit`).

