#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.color
import vdb.config
import vdb.util
import vdb.event

import gdb
import gdb.types


# XXX Unfortunately gdb currently does not offer a "new connection" type of event, as such we have to try and figure out
# on based on other events that there was a new connection
last_used_connection = None
def store_inferior( conn ):
    if( conn is None ):
        conn = gdb.selected_inferior().connection
    global last_used_connection
    print(f"Saving new remote connection {conn}, overwriting old {last_used_connection}")
    last_used_connection = conn

@vdb.event.connection_removed()
def _conrem( oldconn ):
    store_inferior( oldconn.connection)

@vdb.event.before_first_prompt()
def _bfp():
    store_inferior( None )

def reconnect( argv, flags ):
    if( last_used_connection is None ):
        print("Cannot reconnect, no previous connection recorded")

    print(f"Reconnecting to {last_used_connection.details}")
    cmd = f"target {last_used_connection.type} {last_used_connection.details}"
    gdb.execute(cmd)

class cmd_reconnect(vdb.command.command):
    """
    Stores new inferiors connection information and provides an easy way to reconnect it the connection got lost
    """

    def __init__ (self):
        super ().__init__ ("reconnect", gdb.COMMAND_DATA)
        self.needs_parameters = False

    def do_invoke (self, argv:list[str] ):
        self.dont_repeat()

        argv,flags = self.flags(argv)
        reconnect(argv,flags)

cmd_reconnect()
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
