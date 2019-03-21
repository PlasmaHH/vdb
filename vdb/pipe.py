#!/usr/bin/env python3
# -*- coding: utf-8 -*-


pipe_commands = { }

def add( cmd, call ):
    global pipe_commands
    pipe_commands[cmd] = call

def call( cmd, data, argv ):
    call = pipe_commands.get(cmd,None)
    if( call is not None ):
        call(data, argv)
    else:
        raise Exception("Unknonwn pipe command %s" % cmd )


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
