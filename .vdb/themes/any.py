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
vdb-asm-colors-breakpoint-disabled-marker           #e45
vdb-asm-colors-breakpoint-marker    #e45
vdb-asm-colors-explanation          #6666ff
vdb-asm-colors-function             #99f
vdb-asm-colors-jumps	#f00;#0f0;#00f;#ff0;#f0f;#0ff
vdb-asm-colors-location             #08a
vdb-asm-colors-marker               #049
vdb-asm-colors-mnemonic             None
vdb-asm-colors-mnemonic-dot         None
vdb-asm-colors-namespace            #ddf
vdb-asm-colors-next-marker          #0f0
vdb-asm-colors-offset               #444
vdb-asm-colors-prefix               None
vdb-asm-colors-variable             #fc8
# diasssembly dot file colors (must be 6 digits)
vdb-asm-colors-addr-dot             #0000c0
vdb-asm-colors-args-dot             #3030a0
vdb-asm-colors-bytes-dot            #005090
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
vdb-asm-showspec-dot                maobnpTr
vdb-asm-showspec                    maodbnpTrjHcx
vdb-asm-callgrind-events            Ir,CEst
vdb-asm-header-repeat               50
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
vdb-ftree-colors-blacklist-member   #334400
vdb-ftree-colors-blacklist-pointer  #ff9900
vdb-ftree-colors-down-cast          #aaffaa
vdb-ftree-colors-invalid            #ff2222
vdb-ftree-colors-limited            #88aaff
vdb-ftree-colors-pretty-print       #76d7c4
vdb-ftree-colors-union              #ffff66
vdb-ftree-colors-variable-name
vdb-ftree-colors-virtual-cast       #ccaaff
# hexdump
vdb-hexdump-colors-header           #ffa
vdb-hexdump-colors-symbols          #f00;#0f0;#00f;#ff0;#f0f;#0ff
# history/fuzzy search
vdb-history-colors-background       #303030
vdb-history-colors-marker           #d1005c
vdb-history-colors-match            #87af87
vdb-history-colors-prompt           #87afd7
vdb-history-colors-statistics       #afaf87
# Code listing
vdb-list-colors-marker              #0f0
# memory/pointer coloring
vdb-memory-default-colorspec        smAa
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
vdb-memory-colors-section-_bss      #609
vdb-memory-colors-section-_comment
vdb-memory-colors-section-_data
vdb-memory-colors-section-_data_rel_ro
vdb-memory-colors-section-_debug_abbrev
vdb-memory-colors-section-_debug_aranges
vdb-memory-colors-section-_debug_info
vdb-memory-colors-section-_debug_line
vdb-memory-colors-section-_debug_loc
vdb-memory-colors-section-_debug_macro
vdb-memory-colors-section-_debug_ranges
vdb-memory-colors-section-_debug_str
vdb-memory-colors-section-_dynamic
vdb-memory-colors-section-_dynstr
vdb-memory-colors-section-_dynsym
vdb-memory-colors-section-_eh_frame
vdb-memory-colors-section-_eh_frame_hdr
vdb-memory-colors-section-_fini
vdb-memory-colors-section-_fini_array
vdb-memory-colors-section-_GCC_command_line
vdb-memory-colors-section-_gcc_except_table
vdb-memory-colors-section-_gnu_hash
vdb-memory-colors-section-_gnu_version
vdb-memory-colors-section-_gnu_version_r
vdb-memory-colors-section-_got
vdb-memory-colors-section-_got_plt
vdb-memory-colors-section-_hash
vdb-memory-colors-section-_init
vdb-memory-colors-section-_init_array
vdb-memory-colors-section-_interp
vdb-memory-colors-section-_note_ABI-tag
vdb-memory-colors-section-_note_stapsdt
vdb-memory-colors-section-_plt
vdb-memory-colors-section-_rela_dyn
vdb-memory-colors-section-_rela_plt
vdb-memory-colors-section-_rodata
vdb-memory-colors-section-_stapsdt_base
vdb-memory-colors-section-_tbss
vdb-memory-colors-section-_tdata
vdb-memory-colors-section-_text     #a0a
vdb-memory-colors-shared            #15c
vdb-memory-colors-stack-foreign     #f70
vdb-memory-colors-stack-own         #070
vdb-memory-colors-unknown           ,,underline
vdb-memory-colors-writeonly         #ff5
# pahole
vdb-pahole-colors-members           #f00;#0f0;#00f;#ff0;#f0f;#0ff
# The prompt
vdb-prompt-colors-0                 #ffff99
vdb-prompt-colors-1                 #ffff99
vdb-prompt-colors-2                 #ffff99
vdb-prompt-colors-3                 #ffff99
vdb-prompt-colors-4                 #ffff99
vdb-prompt-colors-5                 #ffff99
vdb-prompt-colors-6                 #ffff99
vdb-prompt-colors-7                 #ffff99
vdb-prompt-colors-8                 #ffff99
vdb-prompt-colors-9                 #ffff99
vdb-prompt-colors-end               #ffffff
vdb-prompt-colors-frame             #9999ff
vdb-prompt-colors-git               #99ff99
vdb-prompt-colors-host              #ffff4f
vdb-prompt-colors-progress          #ffbb00
vdb-prompt-colors-start             #ffff99
vdb-prompt-colors-thread            #9999ff
vdb-prompt-colors-time              #ffffff
# register view
vdb-register-colors-flags           #adad00
vdb-register-colors-names           #4c0
# rtos
vdb-rtos-colors-active-task         #0a4
vdb-rtos-colors-marked-task         #09e
# function/type shorten
vdb-shorten-colors-templates        #f60
# unwind
vdb-unwind-colors-hint              #f55
vdb-unwind-colors-hint-start        #ff8
# var arg helper
vdb-va-colors-fixed-float           #838
vdb-va-colors-fixed-int             #953
vdb-va-colors-vararg-float          #608
vdb-va-colors-vararg-int            #c43
# vmmap fallback colours
vdb-vmmap-colors-executable         #e0e
vdb-vmmap-colors-readonly           #f03
vdb-asm-breakpoint-numbers "🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹"
vdb-asm-breakpoint-numbers-disabled "🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹"

vdb-asm-colors-breakpoint-marker "#e45"
vdb-asm-colors-breakpoint-disabled-marker "#111,#400"
# reset printing of options while loading
vdb-config-verbosity default
""")

vdb.rich_theme("""
               bar.complete #008822
""")

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
