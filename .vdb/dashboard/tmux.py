#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

vdb.config.execute("""
dash tmux disassembler dis/5,15
dash tmux registers reg/I
dash tmux ^hexdump$ hd $sp
""")
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
