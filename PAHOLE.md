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



