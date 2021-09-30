## types
Sometimes you are debugging a binary or a corefile which does not have the debug information you need. In this case you
might want to load some type definitions on the fly, but unfortunately gdb does not have direct support for it. What we
can do however is to compile an object file with the desired information and load it into the current instance. This can
even be used for certain file formats and similar. We therefore provide a few tools to automate that.

### `create` a type

For simple types, you can just create them on the fly. The command 

```
types create foo struct foo { int x; };
```
will compile a file (and load it) that will contain the struct definition and create a variable using the type `foo` and
then load that symbol table. After that you should be able to see the type and use it.

### `load` a type
For more complex types, using the command
```
types load foo test.h
```
will compile and load a file including the `test.h` and creating a variable of the type `foo`. This can be an existing
header, or your own local creation for more convenience.

Additionally we try to scan the systems include directory for all kinds of types and have it possible for them to omit
the filename. This only works when ctags is installed.

### configuration
```
vdb-types-ctags-cmd
```
Use this command as ctags. We expect an exuberant ctags compatible version, which may be named/located differently for
your case.


```
vdb-types-ctags-parameters
```
In case you need to change the parameters to ctags for whatever reason


```
vdb-types-ctags-files
```
The files/directories to scan. Can be comma sperarated list.


```
vdb-types-cache
```
Whether or not to do the caching of the type information. Regeneration of the cache will be done always, but this makes
the last state available right at the start (scanning whole trees can take minutes)
