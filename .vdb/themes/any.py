#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

vdb.config.set("""
# don't print all the settings
vdb-config-verbosity 0
# disassembly colors
vdb-asm-colors-namespace            #ddf
vdb-asm-colors-function             #99f
vdb-asm-colors-bytes                #99f
vdb-asm-colors-next-marker          #0f0
vdb-asm-colors-addr                 None
vdb-asm-colors-offset               #444
vdb-asm-colors-bytes                #059
vdb-asm-colors-prefix               None
vdb-asm-colors-mnemonic             None
vdb-asm-colors-args                 #99f
# diasssembly dot file colors (must be 6 digits)
vdb-asm-colors-namespace-dot        #d0d0f0
vdb-asm-colors-function-dot         #9090f0
vdb-asm-colors-bytes-dot            #9090f0
vdb-asm-colors-next-marker-dot      #008000
vdb-asm-colors-addr-dot             #0000c0
vdb-asm-colors-offset-dot           #909090
vdb-asm-colors-bytes-dot            #005090
vdb-asm-colors-prefix-dot           None
vdb-asm-colors-mnemonic-dot         None
vdb-asm-colors-args-dot             #3030a0
vdb-asm-colors-jump-false-dot       #ff0000
vdb-asm-colors-jump-true-dot        #00ff00
vdb-asm-colors-jump-dot             #000088
vdb-asm-colors-call-dot             #6600ff
vdb-asm-showspec                    maodbnprT
vdb-asm-showspec-dot                maobnprT
# backtrace colours
vdb-bt-colors-namespace             #ddf
vdb-bt-colors-address               None
vdb-bt-colors-function              #99f
vdb-bt-colors-selected-frame-marker #0f0
vdb-bt-colors-filename              #ffff99
vdb-bt-colors-object-file           #ffbbbb
vdb-bt-colors-default-object        #ffbbff
vdb-bt-colors-rtti-warning          #c00
vdb-bt-showspec                     naFPs
# hexdump
vdb-hexdump-colors-header           #ffa
# memory/pointer coloring
vdb-memory-colors-nullpage          #f33
vdb-memory-colors-unknown           ,,underline
vdb-memory-colors-ascii             #aa0
vdb-memory-colors-stack-own         #070
vdb-memory-colors-stack-foreign     #f70
vdb-memory-colors-heap              #55b
vdb-memory-colors-mmap              #11c
vdb-memory-colors-shared            #15c
vdb-memory-colors-code              #a0a
vdb-memory-colors-bss               #609
vdb-memory-colors-readonly          #99f
vdb-memory-colors-writeonly         #ff5
vdb-memory-colors-readwrite         None
vdb-memory-colors-executable        #d4f
vdb-memory-colors-inaccessible      #f33
vdb-memory-colors-invalid           #16f
# register view
vdb-register-colors-names           #4c0
# function/type shorten
vdb-shorten-colors-templates        #f60
# reset printing of options while loading
vdb-config-verbosity default
""")

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
