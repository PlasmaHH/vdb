# The svd module

The CMSIS standard offers for a µC to come with an svd file that will describe mostly the registers and some other low
level features of the controller. We support (partially) these files and the registers that are mapped to memory
addresses. To do that use the svd module (enable by default) and configure some directory containing the svd files you
want to use.

## Scanning for files
At startup the svd module scans the directories mentioned in `vdb-svd-directories` for files with `.svd` ending and
parses them.

You can set `vdb-svd-auto-scan` to off and then manually do the scan with the `svd scan` command if you don't want this
to happen at every startup.

With the setting `vdb-svd-scan-recursive` you can control whether the directories are scanned recursively or not.

Setting `vdb-svd-scan-silent` to off will cause every file ( and the resulting device name ) to be printed (instead of a
progress bar).

Using the regexp of `vdb-svd-scan-filter` you can limit the filenames that are being scanned. This way you can have all
your svd files in one directory but with a setting per project you only load a few.

## Loading the definitions
Use `svd list` to list the definitions (add `/v` to see a bit more information). The command accepts a regular
expression to filter the list by the name.

With `svd load` you actually load the definitions into the system and can then access the registers (see *accessing the
registers* part)
## Deferred parsing
If you set `vdb-svd-parse-delayed` then at the scan step only the device name is extracted ( not fully xml parsed ) and
only on an `svd load` command it will do so. This will significantly speed up scanning of files but may not properly
display the information of `svd list`.
## background parsing
Setting `vdb-svd-scan-background` will cause the parsing to be done in the background. This will most likely interfere
with some gdb internals and cause problems and crashes. In a later versions this might be fixed.
## accessing the registers
After something has been loaded, you can access the registers with `reg/m`  or `reg/M`. Since there are usually many (
often thousands) you should use the filter parameter to only display registers matching that name. Also have a look at
the blacklist feature in the registers module.

## Possible issues

* Sometimes you will have multiple svd files defining the same device. In that case a devie with a suffix name will be
  created to distinguish the two. Use `svd/v list` if necessary to see which originates from which file.
* Parse errors. By using the python xml parser we need to be somewhat strict with at least the xml syntax. This is known
  to cause some files to not be loaded at all.
* Memory usage can be high if you have lots and lots of files as we save a lot of information per register and field.

