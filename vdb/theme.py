#!/usr/bin/env python3

import vdb.command
import vdb.config
import rich
import gdb
import sys
import vdb.util
import importlib
import re
import glob
import tomllib
import os

# The idea is that we encapsulate all theming information into one toml structure and all the modules get filled from it
# (if supported)
# We also have some extra non-gdb parameter information for the disassembler mnemonic colors

# Sections [xxx.colors] foo = bar will be translated to vdb-xxx-colors-foo = bar
# and  [xxx] yyy = foo will translate to vdb-xxx-yyy = foo

# In theory one can set all settings with it which should be just fine, people might have a use for that too, no need to
# arbitrarily restrict it to things we deem "visual only". They basically can make their own settings hierarchy

# We will parse themes so far as to know the basic name information but no more (There really is no point checking files
# that will not be loaded anyways). We would probably warn about duplicate names. When the user loads a theme we will
# parse the current file, that way the user can edit and reload while in gdb.

# When a file extends another theme we will parse that and merge stuff on the toml layer, and only then feed unique
# values to config.set().

# rich is a special namespace for configuring rich, we do not forward this to config.set()

# XXX We should add some synthetic event of theme changing so plugins that cache rendered data can invalidate their
# caches

# XXX For now we leave the old "~/.vdb/themes/any.py" config.set based code as-is to later replace it and check if all
# works the same

sample_char = vdb.config.parameter("vdb-theme-sample-char","█")
sample_len = vdb.config.parameter("vdb-theme-sample-len",16)


def show_info( flags ):
    print(f"Current theme '{current_theme_name}' was loaded from '{current_theme.file}'")

rich_conversions = {}
def _gen_theme( ):
    tdict = {}
    for r in range(0,16):
        for g in range(0,16):
            for b in range(0,16):
                short = f"#{r:x}{g:x}{b:x}"
                long  = f"#{r:x}{r:x}{g:x}{g:x}{b:x}{b:x}"
                tdict[short] = long

    rich_conversions.update(tdict)

def _get_rich( col ):
    return rich_conversions.get(col,col)

_gen_theme()

class ThemeStub:
    def __init__( self ):
        self.name = None
        self.file = None
        self.colors = {}

    def add_colors( self, data ):
        for k,d in data.items():
            if( isinstance(d,dict) ):
                self.add_colors(d)
            elif( isinstance(d,str) ):
                dlist = d.split(";")
                for col in dlist:
                    if( not col.startswith("#") ):
                        continue
                    number = self.colors.get(col,0)
                    self.colors[col] = number + 1

    # Returns a rich string as we output it with a rich table later on
    def get_color_sample( self, width = 16 ):
        cnt = 0
        ret = ""
        for x in sorted( self.colors.items(), key = lambda x:x[1], reverse = True ):
            cnt += 1
            col = _get_rich( x[0] )
            X = sample_char.value
            ret += f"[{col}]{X}[/]"
            if( cnt >= width ):
                break
        return ret

known_themes = {}

current_theme_name = None
current_theme = None

def refresh( flags ):
    global known_themes
    known_themes = {}

    print("Refreshing known toml files...")
    for d in vdb.search_dirs:
        for tomlfile in glob.glob(f"{d}/themes/*.toml"):
            with open( tomlfile, "rb" ) as f:
                data = tomllib.load(f)
                try:
                    tname = data["theme"]["name"]
                except KeyError:
                    print(f"File {tomlfile} does not have the necessary global information to be recognized das a theme configuration")
                    continue
                if( "v" in flags ):
                    print(f"Found theme {tname} in {tomlfile}")
                tstub = ThemeStub()
                tstub.file = tomlfile
                tstub.name = tname
                tstub.add_colors(data)

                known_themes[tname] = tstub
    print(f"Found {len(known_themes)} themes")

def toml_load( tname, flags ):
    ts = known_themes.get(tname)
    if( ts is None ):
        raise RuntimeError(f"Unknown theme {tname}")
    fname = ts.file

    with open( fname, "rb" ) as f:
        data = tomllib.load(f)
    vdb.log(f"Loading theme {tname} from {fname}")

    extends = None
    try:
        extends = data["theme"]["extends"]
    except KeyError:
        pass

    if( extends == "default" ):
        load_default(flags)
    elif( extends is not None ):
        try:
            edata = toml_load( extends , flags)
            data = edata | data
        except RuntimeError:
            vdb.log(f"Warning: Could not find base theme {extends}", level = 3)

    return data

all_touched_configs = set()

def set_cfg( name, value ):
    nname = f"vdb-{name}"
#    print(f"config.set('{nname}','{value}')")
    try:
        all_touched_configs.add( nname )
        gdb.execute(f"set {nname} {value}")
    except gdb.error as e:
        print(f"Error setting {nname} to {value} : {e}")


def load_default(flags):
    over = vdb.config.verbosity.value
    vdb.config.verbosity.value = 0
    for cfg in all_touched_configs:
        co = vdb.config.get( cfg )
        if( co is not None ):
            co.set_default()
        else:
            print(f"Now known default value for {cfg}")
    vdb.config.verbosity.value = over
    print("Loaded default settings for all vdb settings touched by previous themes")

def load_cfg( prefix, vl ):
    # Disable and re-enable config verbosity
    cfg_verb = vdb.config.verbosity.value
    vdb.config.verbosity.value = None
    try:
        for k,v in vl.items():
            if( isinstance(v,dict) ):
                load_cfg(f"{prefix}-{k}",v)
            elif( isinstance(v,str) ):
                set_cfg(f"{prefix}-{k}",v)
            else:
                raise RuntimeError(f"Unsupported type {type(v)} in toml config")
    finally:
        vdb.config.verbosity.value = cfg_verb


# XXX toml syntax requires the key to be in quotes when it contains a dot. maybe we can "fix" that after the fact so the
# user can write repr.str instead of "repr.str"
def load_rich( vl ):
    theme = vl
    import rich.theme
    vdb.util.reload_console( force_terminal = True, color_system = "truecolor", theme = rich.theme.Theme(theme) )

def _gdb_set( key, sub, val ):
    if( len(val) ):
#        print(f"_gdb_set( {key=}, {sub=}, {val=} )")
        gdb.execute(f"set style {key} {sub} {val}")

def load_gdb( vl ):
    for k,v in vl.items():
        v += ",,"
        vv = v.split(",")
        _gdb_set( k, "foreground", vv[0] )
        _gdb_set( k, "background", vv[1] )
        _gdb_set( k, "intensity" , vv[2] )

def theme_load( tname, flags ):

    if( tname == "default" ):
        load_default(flags)
    else:
        toml_data = toml_load( tname , flags)
        fname = known_themes.get(tname)
        global current_theme
        current_theme = fname
        global current_theme_name
        current_theme_name = tname

        for k,vl in toml_data.items():
            match k:
                case "theme":
                    pass
                case "rich":
                    load_rich(vl)
                case "gdb":
                    load_gdb(vl)
                case _:
                    load_cfg(k,vl)


    vdb.event.exec_hook("theme")


def toml_save( tname, file, flags ):

    tomldata = {}
    for name,cfg in vdb.config.registry.items():
        if( name.find("-colors-") == -1 ):
            continue
        vn = name.split("-",3)
#        print(f"{vn=}")
        assert( vn[2] == "colors" )
        key = f"{vn[1]}.colors"
        section = tomldata.setdefault( key, {})
        section[ vn[3] ] = str(cfg.value)


    if( not "f" in flags ):
        if( os.path.exists(file) ):
            raise RuntimeError(f"{file} already exists, won't override unless /f is given")

    ktf = known_themes.get(tname)
    # Check if a theme by that name is already known
    if( ktf is not None ):
        ktfname = ktf.file
        if( ktfname != file ):
            vdb.log(f"Warning: {ktfname} already contains a theme named {tname}, recommend to chose another name",level=1)

    with open(file,"w") as f:
        f.write(f'[theme]\nname = "{tname}"\n\n')
        for key,section in tomldata.items():
            f.write(f"[{key}]\n")
            for k,v in section.items():
                f.write(f'{k} = "{v}"\n')
            f.write("\n")
    vdb.log(f"Saved theme {tname} to {file}")

def toml_list( flags ):
    print("This is the list of known themes and their toml files:")

    table = rich.table.Table("Name", "File", "Sample", expand=False,row_styles = ["","on #222222"])

    for n,f in sorted(known_themes.items()):
        table.add_row( n, f.file, f.get_color_sample(sample_len.value) )

    vdb.util.console.print(table)

def theme_next( flags ):
    use_next = False
    first_theme = None
    for n,_ in known_themes.items():
        if( first_theme is None ):
            first_theme = n
        if( use_next ):
            return theme_load( n, flags )
        if( n == current_theme_name ):
            use_next = True
    theme_load( first_theme, flags )

# Use this mechanism to make sure everything is loaded and has their config options setup so we can then fill it
def start( ):
    refresh("")
    if( vdb.cfgtheme.value ):
        theme_load(vdb.cfgtheme.value,"")

# XXX Add a save command (use /f to overwrite). It will probably not support multiple files, its thought of as a
# starting point. How to figure what to write? All colors configs plus a few that are specially marked by plugins?
class cmd_theme (vdb.command.command):
    """
theme refresh             - scans the directories for new toml files
theme list                - list known themes
theme save <name> <file>  - save current theme in a file
theme next                - Activates the next theme in the known list
theme default             - Resets everything to default
theme <theme>             - Loads theme with that name
"""

    def __init__ (self):
        super (cmd_theme, self).__init__ ("theme", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.needs_parameters = False

    def do_invoke (self, argv ):
        argv,flags = self.flags(argv)
        if( len(argv) == 0 ):
            show_info(flags)
            return

        dont_repeat = True
        subcommand = argv[0]
        argv = argv[1:]
        match( subcommand ):
            case "refresh":
                refresh(flags)
            case "list":
                toml_list(flags)
            case "save":
                toml_save( argv[0], argv[1], flags )
            case "next":
                theme_next(flags)
                dont_repeat = False
            case _:
                theme_load(subcommand,flags)

        if( dont_repeat ):
            self.dont_repeat(not dont_repeat)

cmd_theme()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
