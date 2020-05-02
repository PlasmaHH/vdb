
# Backtrace module

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

Addresses (in the address column) is some special beast. Since the gdb decoration mechanism only allows us to return
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
## Commands
We provide the following commands
### `bt`
This should be your default. It will do all the filtering and sometimes write some additional data.
### `bt/r`
This is like `bt` but disables the filter aka. raw. You should not see additional data, but the unfiltered plain gdb output.
### `bt/f`
This is like `bt` but also passes the `full` parameter to backtrace to show all local variables per stackframe. These are not currently filtered.
### `backtrace`
This is an unmodified gdb version, that is running the decorator, but not additional filters and outputs. It may be overridden by additional gdb plugins that you have. This has the added disadvantage that the `n` showspec doesn't have any effect, as well as the RTTI warning filter not working.


