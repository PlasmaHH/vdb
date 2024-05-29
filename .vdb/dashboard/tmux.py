#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

# Start with tmux new-session\; select-pane -T "source"\; split-window -v\; select-pane -T "disassembler" \; split-window -v\; select-pane -T "hexdump" \; split-window -h \; select-pane -T "registers"
vdb.config.execute("""
dash tmux disassembler dis/5,15 on:before_prompt on:step
dash tmux registers reg/I on:before_prompt on:step
dash tmux ^hexdump$ hd $sp on:before_prompt on:step
dash tmux ^source$ List on:before_prompt on:step
""")
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
