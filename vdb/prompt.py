#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.color
import vdb.config

import gdb

def defer_set_prompt( v ):
    set_prompt()

prompt_color = vdb.config.parameter( "vdb-prompt-colors-text","#ffff99", gdb_type = vdb.config.PARAM_COLOUR, on_set = defer_set_prompt )
prompt_text = vdb.config.parameter( "vdb-prompt-text","vdb> ", on_set = defer_set_prompt )

# TODO introduce hooks to dynamically insert information, use format string like substitutions for them.
# Possible information includes (maybe we can colour code something too?)
# Program state
# load
# memory usage
# time
# selected frame
# selected thread

def set_prompt( ):
    prompt = prompt_text.value
    # these special characters will make libreadline handle searches better
    prompt = "\x02" + prompt + "\x01" # STX + prompt + SOH
    prompt = vdb.color.color(prompt,prompt_color.value)
    prompt = "\x01" + prompt + "\x02" # SOH + prompt + STX
    gdb.execute('set prompt %s' % prompt)

set_prompt()

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
