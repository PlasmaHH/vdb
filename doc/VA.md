#  va module 

With this module you get the `va` command which allows you to inspect the passed arguments. This depends on a lots of
heuristics and can fail especially when

* The passed argument combination is unusual
* Compiler optimization gets in our way
* arguments are forwarded to other vararg functions that reuse the structure

The key object here is a va_list object that must be available within the called function somehow.

## `va` command

The command has several parameters that are often optional, but in the case the automatic can't do it, you can help
specific parts of it by providing the necessary information.

### No arguments or passing the `va_list`
Calling it this way will automatically try to find a `va_list` type in the current scope. If it can't it will tell you
and you have to specify the variable name yourself.

### `format=` specifier

You can set a default format via the `vdb-va-default-format` for this or override it by specifying it on the command
line. It is a specification about how the call is most likely structured. From the `va_list` alone it is often not
possible to figure out the amount and order of certain types. The string can be a combination of the following
characters (uppercase always means it is a fixed argument, prepending the varargs)

* `*` The asterisk will mean that the last string is parsed as a printf format string and the output is tried to recover
  from there. On its own it means to show as much as possible
* `i`,`l`,`u` and `j` are specifiers for integers. `i` and `l` are the 32 and 64 bit signed versions and `u` and `j` are
  the respective unsigned versions
* `s` is a string (char pointer).
* `p` is a specifier for formatting an integer as a hex pointer output.
* `f` and `d` are for float and doubles

The most common semi-automatic value used for printf is possibly `S*`.

### `gp_offset=` and `fp_offset=` specifiers
Especially when forwarding arguments, or when otherwise not (yet) properly filling the `va_list` structure, specifying
this will allow you to work completely without a `va_list` structure if necessary.

## configuration

Further configuration options are

```
vdb-va-colors-fixed-float
vdb-va-colors-vararg-float
vdb-va-colors-fixed-int
vdb-va-colors-vararg-int
```
These are the default colors for the various kinds of arguments when being printed.


Values lower than `vdb-va-int-limit` will always be treated as int.


The minimal number of characters to be considered an ascii string when encountering a pointer is `vdb-va-min-ascii` 


When the absolute value of the binary exponent exceeds `vdb-va-max-exponent` the double is considered invalid

For the parameters passed on the stack, at most `vdb-va-max-overflow-int` or `vdb-va-max-overflow-vector` will ever be
considered.


