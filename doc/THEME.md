
# Themes

Due to the massive number of color settings you can create themes via toml files. 


## File format
The format is rather simple:

```toml
[theme]
name = "mandatory name that must be unique"

[asm.colors]
function = "#548598"
```

This will be translated into setting `vdb-asm-colors-function`  to `#548598`.

Theoretically you can use this to set more than the colors, though the shipped themes will generally just set colors,
you can use all other settings too

### Existing

In the example `.vdb`  directory we have a bunch of themes. These are all AI generated. You can use them as a starting
point, or as-is if you are happy with them.

### Extending 

By using `extends = "xyz"`  you can base your theme on another, first `xyz`  will be loaded and then yours on top of
that


### rich themes

At some places we use the rich python library (e.g. for some progress bars). You can style these by using the special
section 

```
[rich]
bar.complete = "#bf2943"
```

Where you can set the progress bar completion style. Consult the rich documentation for all the formats you can set
there.

# Commands

Theming can be controlled via a couple of commands
## `theme refresh`

If you created a new theme, run this command. It will scan all `.vdb`  dirs for new theme files.

## `theme list`

List known theme names along with their files

## `theme save <name> <file>`

Will save all current settings that contain `-colors-`  in their name to a toml file you specify. Unless using it as
`theme/f`  it will not overwrite an existing file.

## `theme next`

This will activate the next theme in the themes list.

To get a good overview, repeatedly execute it while having dashboards with intresting command output on another
terminal. This will make that one refresh with the new theme each time.

## `theme default`

Resets the theme to its default hardcoded state

## `theme <name>`

Loads the theme with the given name. Must be exactly as written in the list.

# Settings

There isn't directly any setting for the module, but you can set the `vdb-theme` setting in your init file and it will
activate that one.
