#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.color
import vdb.config
import vdb.event

import subprocess
import time
import re

import gdb

def defer_set_prompt( v ):
    reset_prompt()


prompt_color = 10*[None]
prompt_text = 10*[None]


prompt_base = vdb.config.parameter( "vdb-prompt-base","{start}{0}{1}{2}{3}{4}{git}{5}{6}{7}{8}{9}{[:host:]}{end}", on_set = defer_set_prompt )

for i in range(0,10):
    prompt_color[i] = vdb.config.parameter( "vdb-prompt-colors-%s" % i, "#ffff99", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
    prompt_text[i]  = vdb.config.parameter( "vdb-prompt-text-%s" % i,   "",        on_set = defer_set_prompt )

prompt_text_start = vdb.config.parameter( "vdb-prompt-text-start", "vdb", on_set = defer_set_prompt )
prompt_text_end = vdb.config.parameter( "vdb-prompt-text-end",     "> ",  on_set = defer_set_prompt )

prompt_color_start = vdb.config.parameter( "vdb-prompt-colors-text-start", "#ffff99", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_color_end = vdb.config.parameter( "vdb-prompt-colors-text-end",     "#ffffff", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )

prompt_git          = vdb.config.parameter( "vdb-prompt-git",                False,      on_set = defer_set_prompt )
prompt_color_git    = vdb.config.parameter( "vdb-prompt-colors-text-git",    "#99ff99", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_color_thread = vdb.config.parameter( "vdb-prompt-colors-text-thread", "#9999ff", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_color_time   = vdb.config.parameter( "vdb-prompt-colors-text-time",   "#ffffff", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_color_frame  = vdb.config.parameter( "vdb-prompt-colors-text-frame",  "#9999ff", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_color_host  = vdb.config.parameter( "vdb-prompt-colors-text-host",  "#ffff4f", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )

# TODO introduce hooks to dynamically insert information, use format string like substitutions for them.
# Possible information includes (maybe we can colour code something too?)
# Program state
# load
# memory usage
# time
# selected frame
# selected thread

git_cache_time = 0
git_cache_prompt = ""

def get_git_prompt( ):
    global git_cache_time
    global git_cache_prompt
    if( prompt_git.value is True ):
        try:
            if( time.time() > (git_cache_time+10) ):
                git_cache_time = time.time()
                gitresult=subprocess.check_output( "git rev-parse --abbrev-ref HEAD".split(), stderr = subprocess.STDOUT ).decode("utf-8")
                gitresult=gitresult.split()[0]
                if( len(gitresult) > 0 ):
                    git_cache_prompt = " [%s]" % gitresult
                else:
                    git_cache_prompt = ""
        except:
            pass
    else:
        git_cache_prompt = ""
        git_cache_time = 0
    return git_cache_prompt

def set_prompt( txt ):
    gdb.execute('set prompt %s' % txt )

cached_prompt_base = ""
def get_prompt_base( ):
    prompt = prompt_base.value
    for i in range(0,len(prompt_text)):
        ptxt = prompt_text[i].value
        if( len(ptxt) > 0 ):
            ptxt = vdb.color.color_rl( ptxt, prompt_color[i].value )
        prompt = prompt.replace("{%s}" % i, ptxt )

    prompt = prompt.replace( "{start}", vdb.color.color_rl( prompt_text_start.value , prompt_color_start.value ))
    prompt = prompt.replace( "{end}", vdb.color.color_rl( prompt_text_end.value, prompt_color_end.value ))

    return prompt

has_key = {}

def get_thread( ):
    try:
        return str(gdb.selected_thread().num)
    except:
        pass
    return None

def get_frame( ):
    try:
        fr=gdb.execute("fr",False,True)
        fr=fr.split()
        fr=fr[0]
        fr=fr[1:]
        return fr
    except:
        return None

def prompt_replace( prompt, fmt, txt, col ):
    if( col is not None and txt is not None and len(col) > 0 and len(txt) > 0 ):
        txt = vdb.color.color_rl(txt,col)
#    print("fmt = '%s'" % fmt )
#    print("txt = '%s'" % txt )
    re_fmt = "{([^}:]*)[:]*" + fmt + "[:]*([^}]*)}"
    if( txt is not None ):
        re_txt = "\g<1>" + txt + "\g<2>"
    else:
        re_txt = ""
#    prompt = prompt.replace(fmt,txt)
    prompt = re.sub(re_fmt,re_txt,prompt)
    return prompt

host = None
def set_host( nh ):
    global host
    host = nh
    reset_prompt()

def get_host( ):
    return host

@vdb.event.before_prompt()
def refresh_prompt( ):
    global cached_prompt_base
    # first do all the fixed values
    prompt = cached_prompt_base
#    print("has_key = '%s'" % has_key )
    # now do all the dynamic ones, later we might want to do it for each time the prompt is called
    if( has_key["git"] ):
        prompt = prompt_replace(prompt,"git", get_git_prompt(), prompt_color_git.value )
    if( has_key["time"] ):
        prompt = prompt_replace(prompt,"time",time.strftime( " %H:%M:%S", time.localtime() ),prompt_color_time.value )
    if( has_key["thread"] ):
        prompt = prompt_replace(prompt,"thread",get_thread(),prompt_color_thread.value )
    if( has_key["frame"] ):
        prompt = prompt_replace(prompt,"frame",get_frame(),prompt_color_frame.value )
    if( has_key["host"] ):
        prompt = prompt_replace(prompt,"host",get_host(),prompt_color_host.value )
    set_prompt(prompt)

def check_format( fmt ):
    global has_key
    re_fmt = "{[^}]*[:]*" + fmt + "[:]*.*}"

    if( re.search(re_fmt,cached_prompt_base ) ):
        has_key[fmt] = True
        return True
    has_key[fmt] = False
    return False

def reset_prompt( ):
    global cached_prompt_base
    cached_prompt_base = get_prompt_base()
    check_format("git")
    check_format("time")
    check_format("frame")
    check_format("thread")
    check_format("host")

    if( prompt_git.value is False ):
        has_key["{git}"] = False
        cached_prompt_base = cached_prompt_base.replace("{git}","")

    refresh_prompt()

reset_prompt()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
