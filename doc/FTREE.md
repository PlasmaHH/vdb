# ftree
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
	void* ptr = &m;
	void* ptrptr = &ptr;
	nunion NU;
	nunion nu[2];
};
```

could be displayed as

![](img/ftree.0.png)


## Commands

### `ftree`
The ftree command expects a pointer to an object. It will create a dot file based on the filename configured in
`vdb-ftree-filebase`. The string there will be fed through strftime and then `.dot` will be appended to it. The default
is `ftree` so it will always overwrite the last one. Using `ftree.%s` will be the most trivial way to create a file for
each invocation. The default depth limit for the tree is at 70, you can specify another limit as the second parameter.

After the dot file is created, the generated filename will be fed to the string format in `vdb-ftree-dot-command` and
the created command will be executed, usually to display the generated file directly.

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

## Special Filter Functionality

Via the plugin mechanism you can put into the `.vdb/ftree/` dir a python file that imports the ftree module and calls
some functions for the following functionalities. For examples it is best to look at the existing source code. There is
always one add and one set function. The add function adds one to the existing list, the other sets the whole list. This
is useful when you don't want to use the built in functionality.

### Downcasting to hidden types
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
* `{add,set}_member_cast_filter` This is basically the same, but for members of a node. The resulting type therefore is
  not a pointer type.

### Pretty print filters

For certain types we may want to use the gdb pretty printer to obtain the output rather than to extract all the members.
This is mostly useful for things like `std::string` where we usually don't care about the internals and just about the
value.

* `{add,set}_pretty_print_types` adds a regex that will match a type that will then always be pretty printed. Note that
  when the type exists as a typedef, sometimes you need to match the typedef name.

### Expansion blacklists
Sometimes you are not interested in certain members at all or don't want the system to follow certain pointers. With
this mechanism you can blacklist those. Table cells will be coloured according to the
`vdb-ftree-colors-blacklist-pointer` and `vdb-ftree-colors-blacklist-member` settings.

* `{add,set}_pointer_blacklist` expects an object path blacklist that will prevent a pointer from being followed to the
next node.
* `{add,set}_member_blacklist` Does not expand the member with the name, but still prints the name.


### dynamic array/vector type detection
For types like `std::vector` there is usually internally a pointer to the object being stored, but the type system has
no idea that it is pointing to an array, not a single object. Similar to the hidden type thing we have a regex mechanism
that can be used to access other members that then can be used to determine the amount of elements.

The setting `vdb-ftree-array-elements` is a comma separated list of python like element indices, that is when they are
negative they are counted from the back of the array. Since arrays can be very long, this limits the amount of things
displayed. Per default its the first and last four items.


* `{add,set}_array_element_filter` adds a regex and a callable, the callable should return the amount of elements in the
  array. Optionally the callable can be replaced by a string that will then be fed to a format with the regex match as a
  parameter. This will then be the object path to the amount of elements.


