#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

# Start with tmux new-session\; select-pane -T "source"\; split-window -v\; select-pane -T "disassembler" \; split-window -v\; select-pane -T "hexdump" \; split-window -h \; select-pane -T "registers"
vdb.config.execute("""
dash tmux disassembler dis/5,15
dash tmux registers reg/I
dash tmux ^hexdump$ hd $sp
dash tmux ^source$ List
""")
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
