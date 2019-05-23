#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config

vdb.config.set("""
# don't print all the settings
vdb-config-verbosity 0
# disassembly colors
vdb-asm-colors-addr                 None
vdb-asm-colors-args                 #99f
vdb-asm-colors-bytes                #059
vdb-asm-colors-bytes                #99f
vdb-asm-colors-function             #99f
vdb-asm-colors-jumps	#f00;#0f0;#00f;#ff0;#f0f;#0ff
vdb-asm-colors-mnemonic             None
vdb-asm-colors-namespace            #ddf
vdb-asm-colors-next-marker          #0f0
vdb-asm-colors-offset               #444
vdb-asm-colors-prefix               None
# diasssembly dot file colors (must be 6 digits)
vdb-asm-colors-addr-dot             #0000c0
vdb-asm-colors-args-dot             #3030a0
vdb-asm-colors-bytes-dot            #005090
vdb-asm-colors-bytes-dot            #9090f0
vdb-asm-colors-call-dot             #6600ff
vdb-asm-colors-function-dot         #9090f0
vdb-asm-colors-jump-dot             #000088
vdb-asm-colors-jump-false-dot       #ff0000
vdb-asm-colors-jump-true-dot        #00ff00
vdb-asm-colors-mnemonic-dot         None
vdb-asm-colors-namespace-dot        #d0d0f0
vdb-asm-colors-next-marker-dot      #008000
vdb-asm-colors-offset-dot           #909090
vdb-asm-colors-prefix-dot           None
vdb-asm-showspec-dot                maobnprT
vdb-asm-showspec                    maodbnprT
# backtrace colours
vdb-bt-address-colorspec	ma
vdb-bt-showspec                     naFPS
vdb-bt-colors-address               None
vdb-bt-colors-default-object        #ffbbff
vdb-bt-colors-filename              #ffff99
vdb-bt-colors-function              #99f
vdb-bt-colors-namespace             #ddf
vdb-bt-colors-object-file           #ffbbbb
vdb-bt-colors-rtti-warning          #c00
vdb-bt-colors-selected-frame-marker #0f0
#ftree
vdb-ftree-colors-arrows	#ff0000;#00ff00;#0000ff;#ff8000;#ff00ff;#00ffff
vdb-ftree-colors-blacklist-member	#334400
vdb-ftree-colors-blacklist-pointer	#ff9900
vdb-ftree-colors-down-cast	#aaffaa
vdb-ftree-colors-invalid	#ff2222
vdb-ftree-colors-limited	#88aaff
vdb-ftree-colors-pretty-print	#76d7c4
vdb-ftree-colors-union	#ffff66
vdb-ftree-colors-variable-name
vdb-ftree-colors-virtual-cast	#ccaaff
# hexdump
vdb-hexdump-colors-header           #ffa
vdb-hexdump-colors-symbols	#f00;#0f0;#00f;#ff0;#f0f;#0ff
# memory/pointer coloring
vdb-memory-colors-ascii             #aa0
vdb-memory-colors-bss               #609
vdb-memory-colors-code              #a0a
vdb-memory-colors-executable        #d4f
vdb-memory-colors-heap              #55b
vdb-memory-colors-inaccessible      #f33
vdb-memory-colors-invalid           #16f
vdb-memory-colors-mmap              #11c
vdb-memory-colors-nullpage          #f33
vdb-memory-colors-readonly          #99f
vdb-memory-colors-readwrite         None

vdb-memory-colors-shared            #15c
vdb-memory-colors-stack-foreign     #f70
vdb-memory-colors-stack-own         #070
vdb-memory-colors-unknown           ,,underline
vdb-memory-colors-writeonly         #ff5
# pahole
vdb-pahole-colors-members	#f00;#0f0;#00f;#ff0;#f0f;#0ff
# The prompt
vdb-prompt-colors-text	#ffff99
# register view
vdb-register-colors-names           #4c0
# function/type shorten
vdb-shorten-colors-templates        #f60
# reset printing of options while loading
vdb-config-verbosity default
""")

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
