# xi
You can do `xi` for a single or `xi <num>` for executing one or `num` instructions. They will be executed using gdbs
`si` command and then for every step, we record the general purpose register values and at the end print out all
registers nicely before the execution of each instruction (with its address) and the list of changed registers (and
maybe also flags). For many cases we can figure out that some memory has changed and print that out too

![](img/xi.0.png)

## Limitations
Only for instructions where this is explicitly coded the change of memory will be recorded, and there we do not have a
look at the number of bytes changed. 

Also floating point/vector registers are not taking into account usually.

Lastly all memory changes not done by the thread currently being followed will not be detected and/or shown.
