# Introduction

This is a little introdution into using gdb+vdb. It can also be seen as a primer for using gdb itself, since even
without vdb you can do most of the things here. We will always emphasize where things with vdb are a bit easier.

If you are totally unfamiliar with gdb, you should read the simple crash example first, as it contains details that are
necessary but not repeated for each example.
# A simple crash

## the code

Lets take as an example this little contrived piece of code.

<insert code>

We can clearly see how there is a nullptr being dereferenced, but one can easily imagine a similar situation happening
in a real world example.

## building

To help gdb help you, it is important that you create proper debug info with your executable. This is usually best done
by passing -ggdb3 to gcc. If you use a different compiler, check how to generate the most debug info in its manual.

If you are debugging executables or libraries that are shipped with your linux distribution, often the debugging
information is shipped seperately (as it takes up lots of diskspace and is usually not used by anyone). Check how to
install the necessary packages. For some distros (e.g. OpenSuSE) gdb is enhanced in a way that will give you right away
the command line to install these packages, when you load an executable.

## running
First you load the executable into gdb. This can happen in two ways. The probably most used is

gdb ./simple0

and the maybe less used but sometimes handy version is to start gdb first, and then do

file ./simple0

in both cases two things should happen:

### vdb startup

When you did everything correctly (see install instructions) then vdb will start up when gdb starts, showing all kinds
of "Loading module" and other messages. Given that there is no error happening, vdb will be fully loaded and you being
greeted with a (coloured) prompt:

vdb 12:45:55>

### File loading
Loading a simple executable will usually only result in the message

Reading symbol from ./simple0...

and nothing more. If there is more, watch out for things talking about missing debug info

### actually running
So far, gdb has loaded the file, but not started any execution. The typical way to start execution now is by the run
command, which accepts parameters as if they are at a shells command line

run

You should see some messages among there being

Starting program: ./simple0

(or a similar path). This means your program has started correctly...


## the crash

... but of course, it crashed. After all, thats the example.

So gdb itself is already quite helpful, telling you some basics about the crash:

Program received signal SIGSEGV, Segmentation fault. 
0x00000000004011d3 in copy (f=..., t=...) at simple0.cxx:14 
14         t.data[i] = f.data[i]; 

A segmentation fault is the most common crash, it mostly means that you tried to access memory that you are not allowed
to, usually because its not there because somehow a pointer got a wrong value.

It also tells you nicely in which function the crash was, and if the source is available, the line.

In our case this is not that helpful, since a lot could go wrong. i could be too big, t or f wrong, or data of both. But
which is it?

## the backtrace

Using the command bt

```
vdb 12:22:28 T1#0> bt
 [STACK(OWN)] [STACK(OTHER)] [HEAP] [MMAP] [SHM] [CODE] [BSS] [NULL] [RO] [WO] [RW] [EX] [INV] [INAC] [UNK]
#0  0x00000000004011c0 in ► copy (f="@0x7fffffffd470", t="@0x0") at simple0.cxx:14
    Kernel Signal Handler: Signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) trying to access 0x8 ()
#1  0x0000000000401239 in main (argc="1", argv="0x7fffffffd5a8") at simple0.cxx:24
#2  0x00007ffff7a5c596 in __libc_start_call_main (main="0x4011f8 <main(int, char const**)>", argc="1", argv="0x7fffffffd5a8") at ../sysdeps/nptl/libc_start_call_main.h:58
#3  0x00007ffff7a5c66b in __libc_start_main_impl (main="0x4011f8 <main(int, char const**)>", argc="1", argv="0x7fffffffd5a8", init="<optimized out>", fini="<optimized out>", rtld_fini="<optimized out>", stack_end="0x7fffffffd598") at ../csu/libc-start.c:392
#4  0x00000000004010cf in _start () at ../sysdeps/x86_64/start.S:115
```

we can make gdb print how we got to this point, function wise. If you compare the output with bt/r (the gdb raw output)
you can not only see that we use different colours (See BACKTRACE.md for how to configure things) but there is an
important added line that tells us where in the stacktrace a signal occured, which is frame #0. It tells us not only
that its a segmentation fault, but it also tells us that we tried to access address 0x8. Pretty odd, huh?

Note: due to security concerns, when stepping way outside of the address space of the program, this information is
withheld by the kernel.

## even more detail
Ok, so now we know the line of code where it happened and that it tried to access 0x8. This information is available in
plain old gdb too by inspecting `$_siginfo` and now we could search through the involved variables to guess at which
part we went wrong. But we can go also to the disassembler.

"But I don't know any assembler" you might rightfully say, and thats not the important point here. You can mostly ignore
all the instructions and details, just do a dis/5 (for 5 instructions of context)

Instructions in range 0x4011a6 - 0x4011f7 of copy(v const&, v&)( f@0x7fffffffd470[0x20(%rbp)] = @0x7fffffffd470, t@0x0[-0x7fffffffd450(%rbp)] = @0x0,)
     0x00000000004011c0 5a   <+26>: │╭► 48 8b 45 e8 mov    -0x18(%rbp),%rax @0x7fffffffd438, =@0x7fffffffd470 → [1]'*'
     0x00000000004011c4 4    <+30>: ││  48 8b 50 08 mov    0x8(%rax),%rdx   f.data@@0x7fffffffd478, f.data@=@0x00416eb0
     0x00000000004011c8 3    <+34>: ││  48 8b 45 f8 mov    -0x8(%rbp),%rax  i@-0x8(%rbp), i@@0x7fffffffd448, i@=0x0
     0x00000000004011cc 2    <+38>: ││  48 01 d0    add    %rdx,%rax        %=@0x00416eb0
     0x00000000004011cf 1    <+41>: ││  48 8b 55 e0 mov    -0x20(%rbp),%rdx @0x7fffffffd430, =0x0
  →  0x00000000004011d3 0    <+45>: ││  48 8b 4a 08 mov    0x8(%rdx),%rcx   t.data@@0x8
     0x00000000004011d7      <+49>: ││  48 8b 55 f8 mov    -0x8(%rbp),%rdx  i@-0x8(%rbp), i@@0x7fffffffd448, i@=0x0
     0x00000000004011db      <+53>: ││  48 01 ca    add    %rcx,%rdx        %=0x0
     0x00000000004011de      <+56>: ││  0f b6 00    movzbl (%rax),%eax      @0x00416eb0, =0x0
     0x00000000004011e1      <+59>: ││  88 02       mov    %al,(%rdx)       %=0x0
     0x00000000004011e3 10a  <+61>: ││  48 ff 45 f8 incq   -0x8(%rbp)       i@-0x8(%rbp), i@@0x7fffffffd448, i@=0x0

vdb will helpfully highlight the instruction the program crashed on. It will also tell all kinds of things it knows
about (possibly) accessed memory, and in the last column very helpfully tell us via `t.data@@0x8` that this instruction
most likely tried to access `t.data` which resides at address 0x8. This makes sense if we assume that t itself is a
nullptr, because data is the second variable in that struct. We can quickly confirm this (remember, we use heuristics
that are not always correct):

vdb 12:55:15 T1#0> p t.data
Cannot access memory at address 0x8
vdb 13:07:37 T1#0> p t
$1 = (v &) <error reading variable: Cannot access memory at address 0x0>

so this quickly tells us that t is a nullptr and thanks to vdb we did not have to look around which value is what. While
in this example it would have been easy, sometimes its not so much, and vdb simply makes us spot the culprit quicker.
