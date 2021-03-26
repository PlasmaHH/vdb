## ssh
We provide some "remote debugging" features that are based around logging into another host via ssh and debugging
something there (a live process or some core file). 

Note: currently only non-interactive authentication is supported since we intercept all terminal i/o of ssh.

### `attach` to process

While in classical gdb/gdbserver you have to setup a communication path yourself, the attach mechanism will try to take
care of all of that, so you have to do only the following command:

```
ssh <hostname> attach <pid-or-name>
```

which will login to the given host, try to figure out what pid the name is referring to (see configuration for options
to control that), copy over the binary (shared objects can be accessed through gdbserver, the executable not) and attach
to the process via gdbserver. So the only thing that has to be available on the other host is a somewhat recent
gdbserver.

When the prompt module is active, this will also change the prompt to make it clear that you are attached to a remote
process.

### `run` a process

Similarly to the attach, using run will try to run the given command as if it was on the command line. Be aware that
since it starts the process in the gdbserver in a very early state before main, a lot of shared objects may not be
resolved, thus you might need to issue a `vmmap refresh`.

### debug `core` file

For cases where on the remote system there is a core file, the `core` subcommand is useful. You don't need anything on
the remote host, as everything is copied locally (gdbserver can't read corefiles anyways). For example the command

```
ssh <hostname> core core.ftree_30563_1556640000_6_1001_101
```

Will initiate a complex chain of events that will try to find the core files generating binary, then the shared objects
that are loaded, copies it all over and instructs gdb to only ever use these shared objects instead of local ones. The
files are cached so that for a future invocation you will not have to do the copying again. Since we don't know when you
are done, you have to clean them up yourself. You also have some control over these files

Additionally we try to find and copy debug files and shared objects that have been loaded via `dlopen()`. The mechanism
isn't perfect, but you can always manually copy the debug files into the lib directory, just name them the same as the
`.so` file but add `.debug` to the filename.

In case the binary that has created the corefile was overwritten you can give the name of a binary as a parameter after
the core file name to override automatic detection of which file created the core file.

### Remote csum cache
Instead of calculating the checksum for a remote file, the copy functionality can also take the checksum from a cache.
The only way to add to the cache is via the command `ssh csum <host>:<file> <csum>` which will be mostly useful for when
the core and/or binary file has already been copied over but is so huge that even calculating the checksum takes too
long to be useful. Usually this is then put into a project specific configuration file.

### configuration

For the attach command you can change the way it tries to get the pid of the process name you supply. The most versatile
tool here is pgrep, but in case its not available you should probably configure `/sbin/pidof` (yeah, full path, a lot of
systems don't have `/sbin` in their `PATH`). The `%s` in it will be replaced by the parameter you pass to the command.

```
vdb-ssh-pid-cmd
```

All copying commands do checksumming  on the remote to see if they have to copy it over. This tells which command to
use. Since all commands have timeouts on the ssh connection, and checksumming can sometimes take a long time on slow
systems which huge core files, we offer a way to give a float in seconds of the timeout for that specific checksum
command.
```
vdb-ssh-checksum-command
vdb-ssh-checksum-timeout
```

You can tell scp to use compression (be careful, when you use ssh master sockets this is overridden by the first opened
ssh connection), though it only helps if you debug over the internet. The temporary files used in the cache will be
stored under the given name, you can change it if you e.g. want to store them all at one place to have it easier to wipe
them all. You always have to put `{tag}` and `{csum}` in there, otherwise you will have files overwriting each other.

```
vdb-ssh-scp-compression
vdb-ssh-tempfile-name
```

Since this plugin will open an ssh tunnel for the gdb tcp connection to go over, we have to chose a port. We check if
its available on the remote as well as the local system. This allows you to chose the range we can chose from. You can
set it to a single port too.

```
vdb-ssh-valid-ports
```

In some circumstances we want to make you aware of that we are on a remote system all the time, so when the prompt
module is active, we change the prompt. These options let you customize the prompt for this.

```
vdb-ssh-colors-prompt
vdb-ssh-prompt-text
```

When copying over core files via the ssh mechanism we need to setup our own environment. Unfortunately this means that
gdb is unable to match things like auto load python files for pretty printing. This option (defaults to True) tries to
symlink known files so they are picked up. You can disable it if it makes stupid things.
```
vdb-ssh-fix-autoload
```

