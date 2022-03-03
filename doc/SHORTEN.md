## shorten
Shortened names are used at multiple places (e.g. assembler output, backtraces, see the corresponding modules for
details). The main ways to reduce the length of a type are by shortening it to its typedef, to another user defined
string, or to fold away template arguments.

## commands
You have a few commands yourself to control and use this:

* `vdb add shorten` adds a  pair of strings that will be replaced for shortening.
* `vdb show shorten` shows all active shorten string pairs
* `vdb load shorten` scans all types for typedefs that are shorter than the type name. This can take a long time for
  binaires with a lot of types
* `vdb shorten` call the shorten module with a type and inspect its result.
* `vdb add foldable` add the template name where the template parameters should be suppressed. If you pass two
  parameters, the first one is interpreted as a regular expression and the fold will only be done when the regexp
  matches the whole function string.
* `vdb show foldable` show all template names where we currently suppress the names

## plugin
The shorten modules causes all `.vdb/shorten/*.py` plugin files to be loaded. This is the ideal place to run your own
code to generate them, as this will prevent the code from ever running when you disable the shorten module completely.

## python calls

You can call import the shorten module and on it call
* `add_shorten` Expects a from and a to as parameters.
* `add_foldable` Expects either
 * A string with a single foldable type
 * A string with newlines, each line is a type
 * A list (or other similar iterable) with single foldable types
* `add_conditional` Simlar to `add_foldable` this expects an additional first parameter that is the regexp condition

## configuration

We have the following parameters:

```
vdb-shorten-colors-templates
```
This is the color the fold ellipsis string will be coloured in.

```
vdb-shorten-fold-ellipsis
```
This is what a template parameter that is foled will be replaced with.

```
vdb-shorten-recursion-limit
```
We apply shortening on shortened symbols too, but stop at this recursion depth.

```
vdb-shorten-verbosity
```
For debugging purposes you can make the parser a bit more verbose


```
vdb-shorten-debug
```
When debug is on the internal parser will do some additional sanity checks and output if it detects something.

```
vdb-shorten-cache
```
Do internal caching of the parser and shortening results.

```
vdb-shorten-lazy-load-typedefs
```
Automatically load and generate from typedefs some shortens. Since this is expensive, this is disabled per default.

