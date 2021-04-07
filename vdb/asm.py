#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.shorten
import vdb.color
import vdb.pointer
import vdb.dot
import vdb.command
import vdb.arch

import gdb

import re
import traceback
import sys
import os

asm_colors = [
        ( "j.*", "#f0f" ),
        ( "b.*", "#f0f" ),
        ( "mov.*", "#0ff" ),
        ( "cmp.*|test.*", "#f99" ),
        ( "call.*", "#6666ff" ),
        ( "ret.*", "#8f9" ),
        ]

asm_colors_dot = [
        ( "j.*", "#f000f0" ),
        ( "b.*", "#f000f0" ),
        ( "mov.*", "#007f7f" ),
        ( "cmp.*|test.*", "#f09090" ),
        ( "call.*", "#6666ff" ),
        ( "ret.*", "#308020" ),
        ]

pre_colors = [
        ( "lock.*","#f0f" ),
        ( "rep.*","#f29" ),
        ]

pre_colors_dot = [
        ( "lock.*","#f000f0" ),
        ( "rep.*","#f02090" ),
        ]

next_marker = vdb.config.parameter("vdb-asm-next-marker", " → " )
next_marker_dot = vdb.config.parameter("vdb-asm-next-marker-dot", " → " )

next_mark_ptr     = vdb.config.parameter("vdb-asm-next-mark-pointer", True )
shorten_header    = vdb.config.parameter("vdb-asm-shorten-header", False )
prefer_linear_dot = vdb.config.parameter("vdb-asm-prefer-linear-dot",False)

offset_fmt = vdb.config.parameter("vdb-asm-offset-format", "<{offset:<+{maxlen}}>:" )
offset_txt_fmt = vdb.config.parameter("vdb-asm-text-offset-format", "<+{offset:<{maxlen}}>:" )
offset_fmt_dot = vdb.config.parameter("vdb-asm-offset-format-dot", " <{offset:<+{maxlen}}>" )
offset_txt_fmt_dot = vdb.config.parameter("vdb-asm-text-offset-format-dot", " <+{offset:<{maxlen}}>" )

color_ns       = vdb.config.parameter("vdb-asm-colors-namespace",   "#ddf", gdb_type = vdb.config.PARAM_COLOUR)
color_function = vdb.config.parameter("vdb-asm-colors-function",    "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#99f", gdb_type = vdb.config.PARAM_COLOUR)
color_marker   = vdb.config.parameter("vdb-asm-colors-next-marker", "#0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_addr     = vdb.config.parameter("vdb-asm-colors-addr",        None,   gdb_type = vdb.config.PARAM_COLOUR)
color_offset   = vdb.config.parameter("vdb-asm-colors-offset",      "#444", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes    = vdb.config.parameter("vdb-asm-colors-bytes",       "#059", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix   = vdb.config.parameter("vdb-asm-colors-prefix",      None,   gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic = vdb.config.parameter("vdb-asm-colors-mnemonic",    None,   gdb_type = vdb.config.PARAM_COLOUR)
color_args     = vdb.config.parameter("vdb-asm-colors-args",        "#99f", gdb_type = vdb.config.PARAM_COLOUR)



color_ns_dot       = vdb.config.parameter("vdb-asm-colors-namespace-dot",       "#d0d0f0", gdb_type = vdb.config.PARAM_COLOUR)
color_function_dot = vdb.config.parameter("vdb-asm-colors-function-dot",        "#9090f0", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes_dot    = vdb.config.parameter("vdb-asm-colors-bytes-dot",           "#9090f0", gdb_type = vdb.config.PARAM_COLOUR)
color_marker_dot   = vdb.config.parameter("vdb-asm-colors-next-marker-dot",     "#008000", gdb_type = vdb.config.PARAM_COLOUR)
color_addr_dot     = vdb.config.parameter("vdb-asm-colors-addr-dot",            "#0000c0", gdb_type = vdb.config.PARAM_COLOUR)
color_offset_dot   = vdb.config.parameter("vdb-asm-colors-offset-dot",          "#909090", gdb_type = vdb.config.PARAM_COLOUR)
color_bytes_dot    = vdb.config.parameter("vdb-asm-colors-bytes-dot",           "#005090", gdb_type = vdb.config.PARAM_COLOUR)
color_prefix_dot   = vdb.config.parameter("vdb-asm-colors-prefix-dot",               None, gdb_type = vdb.config.PARAM_COLOUR)
color_mnemonic_dot = vdb.config.parameter("vdb-asm-colors-mnemonic-dot",             None, gdb_type = vdb.config.PARAM_COLOUR)
color_args_dot     = vdb.config.parameter("vdb-asm-colors-args-dot",            "#3030a0", gdb_type = vdb.config.PARAM_COLOUR)

color_jump_false_dot = vdb.config.parameter("vdb-asm-colors-jump-false-dot", "#ff0000", gdb_type = vdb.config.PARAM_COLOUR)
color_jump_true_dot  = vdb.config.parameter("vdb-asm-colors-jump-true-dot",  "#00ff00", gdb_type = vdb.config.PARAM_COLOUR)
color_jump_dot       = vdb.config.parameter("vdb-asm-colors-jump-dot",       "#000088", gdb_type = vdb.config.PARAM_COLOUR)
color_call_dot       = vdb.config.parameter("vdb-asm-colors-call-dot",       "#6600ff", gdb_type = vdb.config.PARAM_COLOUR)



nonfunc_bytes      = vdb.config.parameter("vdb-asm-nonfunction-bytes",16)
history_limit      = vdb.config.parameter("vdb-asm-history-limit",4)
tree_prefer_right  = vdb.config.parameter("vdb-asm-tree-prefer-right",False)
asm_showspec       = vdb.config.parameter("vdb-asm-showspec", "maodbnprTj" )
asm_showspec_dot   = vdb.config.parameter("vdb-asm-showspec-dot", "maobnprT" )
dot_fonts          = vdb.config.parameter("vdb-asm-font-dot", "Inconsolata,Source Code Pro,DejaVu Sans Mono,Lucida Console,Roboto Mono,Droid Sans Mono,OCR-A,Courier" )



color_list = vdb.config.parameter("vdb-asm-colors-jumps", "#f00;#0f0;#00f;#ff0;#f0f;#0ff" ,on_set = vdb.config.split_colors)

ix = -1
def next_index( ):
    global ix
    ix += 1
    return ix

class instruction( ):

    def __init__( self ):
        self.mnemonic = None
        self.args = None
        self.reference = None
        self.targets = set()
        self.conditional_jump = False
        self.call = False
        self.return_ = False
        self.target_name = None
#        self.target_offset = None
        self.target_of = set()
        self.address = None
        self.offset = None
        self.bytes = None
        self.marked = False
        self.prefix = ""
        self.infix = ""
        self.jumparrows = ""
        self.arrowwidth = 0
        self.bt = None
        self.history = None
        self.bt_idx = None

    def __str__( self ):
        ta = "None"
        if( len(self.targets) ):
            ta = ""
            for t in self.targets:
                ta += f"0x{t:x}"
        to = "("
        for target in self.target_of:
            to += f"0x{target:x}"
        to += ")"
        ret = f"INS @{self.address:x} => {ta} <={to}"
        return ret

class listing( ):

    def __init__( self ):
        self.function = None
        self.instructions = []
        # map from address to sources
        self.ins_map = {}
        self.by_addr = {}
        self.maxoffset = 0
        self.maxbytes = 0
        self.maxmnemoic = 0
        self.maxargs = 0
        self.start = 0
        self.end = 0
        self.finished = False
        self.current_branch = "a"
        self.bt_q = []

    def color_address( self, addr, marked ):
        mlen = vdb.arch.pointer_size // 4
        if( next_mark_ptr and marked ):
            return vdb.color.colorl(f"0x{addr:0{mlen}x}",color_marker.value)
        elif( len(color_addr.value) > 0 ):
            return vdb.color.colorl(f"0x{addr:0{mlen}x}",color_addr.value)
        else:
            return ( vdb.pointer.color(addr,vdb.arch.pointer_size)[0], mlen+2)

    # XXX generic enough for utils?
    def color_relist( self, s, l ):
        for r,c in l:
            if( re.match(r,s) ):
                return vdb.color.color(s,c)
        return s

    def color_mnemonic( self, mnemonic ):
        if( len(color_mnemonic.value) > 0 ):
            return vdb.color.color(mnemonic,color_mnemonic.value)
        else:
            return self.color_relist(mnemonic,asm_colors)

    def color_prefix( self, prefix ):
        if( len(color_prefix.value) > 0 ):
            return vdb.color.color(prefix,color_prefix.value)
        else:
            return self.color_relist(prefix,pre_colors)
    """
ascii mockup:
    For styles we should have special chars for every possible utf8 char and then replace them? or single variables that are filled by the style?

+---<   jmp A1
|
| +-<   jmp A2
| |
+--->   A1:
  |
+-+=>   A2: jmp A3
|
+--->   A3:


.
─
│
├
┤
┬
┴
┼
╭
╮
╯
╰
►
◄
◆

    UTF8 version mockup:
╭───◄   jmp A1
│
│ ╭─◄   jmp A2
│ │
╰───►   A1:
╰───→
  |
  ↑
╭─┴─◆   A2: jmp A3
  ▲
╭─┷─◆   A2: jmp A3
│
╰───►   A3:
"""
    def add_target( self,ins ):
#        print("add_target")
#        print("ins = '%s'" % ins )
        if( len(ins.targets) > 0  ):
            for tga in ins.targets:
                tgt = self.by_addr.get(tga,None)
                if( tgt is not None ):
                    tgt.target_of.add(ins.address)

    def finish( self ):
        global ix
        ix = -1

        def acolor( s, idx ):
            if( idx >= 0 ):
                return vdb.color.color(s,color_list.elements[idx % len(color_list.elements) ] )
            else:
                return s

        class arrow:
            def __init__( self, fr, to ):
                self.fr = fr
                self.to = to
                self.coloridx = next_index()
                self.lines = 0
                self.rows = 0
                self.done = False
                self.merger = None

            def __str__( self ):
                return f"0x{self.fr:x} -> 0x{self.to:x}, c={self.coloridx},l={self.lines},r={self.rows},d={self.done}"

        def find_next( cl, ar ):
            clen = len(cl)
            if( tree_prefer_right.value ):
                r = range(clen-1,-1,-1)
            else:
                r = range(0,clen)

            for i in r:
                if( cl[i] is None ):
                    cl[i] = ar
                    return i
                if( cl[i].done ):
                    old = cl[i]
                    ar.merger = old
                    cl[i] = ar
                    return i

            cl += [ None ]
            cl[clen] = ar
            return clen

        def to_arrows( ins, cl, ignore_target = False  ):
#            print("###################")
            ret = ""
            alen = 0
#            print("ins.address = '%x'" % ins.address )

#            print("current_lines = '%s'" % current_lines )
            ridx = 0
            doneleft = False
            leftarrow = None
            remove_indices = set()
            for cidx in range(0,len(cl)):
                ar = cl[cidx]
#                print("ar = '%s'" % ar )
                if( ar is None ):
                    # No vertical line expected here, lets see if we need some horizontal
                    if( leftarrow is not None ):
                        ret += acolor("-",leftarrow.coloridx)
                    else:
                        ret += " "
                else: # c is not None here
                    if( ar.done ):
                        remove_indices.add(cidx)
                    if( ar.rows == 0 ):
                        # arrow starts here, so goes down
                        # but what if there already was another?
                        if( leftarrow is not None ):
                            if( ar.merger ):
                                ret += acolor("+",leftarrow.coloridx)
                            else:
                                ret += acolor("T",leftarrow.coloridx)
                        else:
                            if( ar.merger ):
                                if( ar.to == ar.fr ):
                                    ret += acolor("^",ar.coloridx)
                                else:
                                    ret += acolor("#",ar.coloridx)
                            elif( ins.address in ins.targets ):
                                ret += " "
                            else:
                                ret += acolor("v",ar.coloridx)
                            leftarrow = ar
                    else:
                        if( ar.done ):
                            if( leftarrow is not None ):
                                ret += acolor("u",leftarrow.coloridx)
                            else:
                                ret += acolor("^",ar.coloridx)
                                leftarrow = ar
                        else:
                            # arrow already had a start
                            if( ar.lines == 0 ):
                                ret += acolor("|",ar.coloridx)
                            else:
                                ret += acolor("|",ar.coloridx)
                        ar.lines += 1
                    ar.rows += 1
                alen += 1
                # back to the current_line loop from here
            if( leftarrow is not None ):
                if( ins.address in ins.targets ):
                    ret += acolor("Q",leftarrow.coloridx)
                elif( leftarrow.to == ins.address ):
                    ret += acolor(">",leftarrow.coloridx)
                else:
                    ret += acolor("<",leftarrow.coloridx)
                alen += 1
            for i in remove_indices:
                cl[i] = None
            return ( ret, alen )

        self.do_backtrack()

        self.finished = True
        current_lines = []
        adict = {}

        for ins in self.instructions:
#            print("INS_----------------------------------")
#            print("ins = '%s'" % ins )
            self.add_target(ins)

            # Remove those arrows that end here, whiche are always from above. Those that start here are not yet in the
            # list
            for cl in current_lines:
                if( cl is not None ):
                    # One of the arrow ends targets this instruction
                    if( cl.to == ins.address or cl.fr == ins.address ):
                        cl.done = True
#                        print("DONE_01 cl = '%s'" % cl )


            # Now add the new ones
            for tgt in ins.targets:
                if( self.start <= tgt <= self.end ):
                    if( tgt == ins.address ):
                        ar = arrow(ins.address,tgt)
                        find_next( current_lines, ar )
                        ar.done = True
#                        print("ADD2 %s" % ar)
                    # Target is further down, add an arrow
                    elif( tgt > ins.address ):
                        ar = arrow(ins.address,tgt)
                        find_next( current_lines, ar )
#                        print("ADD1 %s" % ar)
            if( len(ins.target_of) > 0 ):
                # We are a target of something, lets have a look if those are further down
                for target in ins.target_of :
                    if( target > ins.address ):
                        # yep, further down, we need a new arrow
                        ar = arrow(target,ins.address)
                        find_next( current_lines, ar )
            (ins.jumparrows,ins.arrowwidth) = to_arrows(ins,current_lines)
        self.maxarrows = len(current_lines)+1

    def lazy_finish( self ):
        if( self.finished ):
            return
        self.finish()

    def next_backtrack( self ):
        ret = self.current_branch
        self.current_branch = chr(ord(ret)+1)
        return ret

    def q_backtrack_next( self, idx, bt, limit ):
        self.bt_q.append( (idx,bt,limit) )

    def backtrack_next( self, idx, bt, limit ):
        ins=self.instructions[idx]
        if( ins.bt is not None ):
            return
        ins.bt = "%s%s" % (bt[0],bt[1])
        if( limit == 0 ):
            return
        if( idx == 0 ):
            return
        for src in self.ins_map.get(ins.address,()):
            src=self.by_addr[src]
            nb = self.next_backtrack()
            ins.bt += nb
            self.q_backtrack_next( src.bt_idx , ( bt[0]+1, nb ), limit - 1 )

        self.q_backtrack_next( idx-1, (bt[0]+1,bt[1]), limit - 1 )


    def do_backtrack( self ):
        self.ins_map = {}
        idx = 0
        midx = None
        self.current_branch = "a"
#        if( any((c in showspec) for c in "hH" ) ):
        rec = gdb.current_recording()
#        else:
#            rec = None
        inh = {}
        if( rec is not None ):
            try:
                rins = rec.instruction_history
            except NotImplementedError:
                rins = None
#            print("rins = '%s'" % rins )
            if( rins is not None ):
                for h in rins:
#                    print("h = '%s'" % h )
#                    print("h.pc = '%s'" % h.pc )
                    print("h.decoded = '%s'" % h.decoded )
                    print("h.data = '%s'" % h.data.tolist() )
                    inh.setdefault(h.pc,[]).append(str(h.number))
        for i in self.instructions:
            if( rec is not None ):
                h = inh.get(i.address,None)
                if( h is not None ):
                    i.history = h[-history_limit.value:]
#                    print("h = '%s'" % h )
            i.bt_idx = idx
            i.bt = None
            for sr in i.target_of:
                self.ins_map.setdefault(i.address,set()).add(sr)
            for tgt in i.targets:
                self.ins_map.setdefault(tgt,set()).add(i.address)
            if( i.marked ):
                midx = idx
            idx += 1

#        print("midx = '%s'" % midx )
        # Just don't do anything if we have no marker
        if( midx is None ):
            return

        self.q_backtrack_next( midx, (0,""), 10 )

        while( len(self.bt_q) > 0 ):
            x_q = self.bt_q
            self.bt_q = []
            for x in x_q:
                self.backtrack_next( x[0], x[1], x[2] )


    def to_str( self, showspec = "maodbnprT", context = None ):
        self.lazy_finish()
        hf = self.function
        if( shorten_header.value ):
            hf = vdb.shorten.symbol(hf)

        marked_line = None
        cnt = 0
        context_start = None
        context_end = None

        otbl = []

        for i in self.instructions:
            line = []
            otbl.append(line)
            if( "m" in showspec ):
                if( i.marked ):
                    line.append( ( vdb.color.color(next_marker.value,color_marker.value), len(next_marker.value) ) )
                    marked_line = cnt
                    if( context is not None ):
                        if( context[0] is not None and context[1] is not None ):
                            # old behaviour
                            context_start = marked_line - context[0]
                            context_end = marked_line + context[1] + 1
                        elif( context[0] is not None ):
                            context_start = marked_line - context[0]
                            context_end = marked_line + 1
                        elif( context[1] is not None ):
                            context_start = marked_line 
                            context_end = marked_line + context[1] + 1

                else:
                    line.append( "" )
            if( "a" in showspec ):
                line.append( self.color_address( i.address, i.marked ))

            if( "j" in showspec ):
                line.append( i.bt )

            if( any((c in showspec) for c in "hH" ) ):
#                line.append("H")
                if( i.history is not None ):
                    if( "h" in showspec ):
                        line.append( i.history[0] )
                    else:
                        line.append( ",".join(i.history) )
                else:
                    line.append(None)

            if( "o" in showspec ):
                try:
                    io = vdb.util.xint(i.offset)
                    line.append( vdb.color.color(offset_fmt.value.format(offset = io, maxlen = self.maxoffset ),color_offset.value))
                except:
                    line.append( vdb.color.color(offset_txt_fmt.value.format(offset = i.offset, maxlen = self.maxoffset ),color_offset.value))

            if( "d" in showspec ):
#                mt=str.maketrans("v^-|<>+#Q~I","╭╰─│◄►┴├⥀◆↑" )
                mt=str.maketrans("v^-|<>u#Q~T+","╭╰─│◄►┴├⥀◆┬┼" )
                if( len(i.jumparrows) ):
                    ja=i.jumparrows.translate(mt)
                    fillup = " " * (self.maxarrows - i.arrowwidth)
                    line.append( (f"{ja}{fillup}", self.maxarrows) )
                else:
                    line.append( "" )

            if( "b" in showspec ):
                line.append( ( vdb.color.color(f"{' '.join(i.bytes)}",color_bytes.value),len(i.bytes)*3) )
            aslen = 0
#            xline = line + "123456789012345678901234567890"
#            print(xline)
            if( "n" in showspec ):
                pre = self.color_prefix(i.prefix)
                mne = self.color_mnemonic(i.mnemonic)
                mxe = pre + i.infix + mne
                mlen = len(i.prefix) + len(i.infix) + len(i.mnemonic)
#                aslen += mlen
#                if( i.args is not None ):
#                    mlen = self.maxmnemoic - mlen
#                else:
#                    mlen = 0
#                aslen += mlen + 1
#                print("mxe = '%s'" % mxe )
#                line.append( f" {mxe}{' '*mlen}")
                line.append( ( mxe, mlen ) )
#            line.append("%s = %s %s %s" % (mlen,len(i.prefix),len(i.infix),len(i.mnemonic)))
#            print("aslen = '%s'" % aslen )
#            print(line+"*")
            if( "p" in showspec ):
                if( i.args is not None ):
                    aslen += self.maxargs + 1
#                    line.append( vdb.color.color(f" {i.args:{self.maxargs}}",color_args.value))
                    line.append( (vdb.color.color(f"{i.args}",color_args.value),len(i.args)) )
#            maxlen = self.maxmnemoic+self.maxargs+2
#            print("maxlen = '%s'" % maxlen )
#            print("aslen = '%s'" % aslen )
#            print("self.maxmnemoic = '%s'" % self.maxmnemoic )
#            print("self.maxargs = '%s'" % self.maxargs )
#            print(line+"|")
#            if( aslen < maxlen ):
#                fillup = maxlen - aslen
#                print("fillup = '%s'" % fillup )
#                line.append( " " * fillup)

            if( "r" in showspec ):
                if( i.reference is not None ):
                    line.append( vdb.shorten.symbol(i.reference) )
            if( any((c in showspec) for c in "tT" ) ):
#                if( i.targets is not None ):
#                    line.append( i.targets)
                if( "T" in showspec ):
                    if( i.target_name is not None ):
                        line.append( vdb.shorten.symbol(i.target_name))


#            ret.append(line)
            cnt += 1
            if( context is not None and context_end is not None and context_end <= cnt ):
                break

        ret = otbl
        if( marked_line is not None and context is not None ):
            if( context_start < 0 ):
                context_start = 0
            ret = ret[context_start:context_end]


#        print("ret = '%s'" % ret )
        ret = vdb.util.format_table(ret,padbefore=" ",padafter="")
        return f"Instructions in range 0x{self.start:x} - 0x{self.end:x} of {hf}\n" + ret
#        return "\n".join(ret)

    def print( self, showspec = "maodbnprT", context = None ):
        print(self.to_str(showspec, context))

    def color_dot_relist( self, s, l ):
        for r,c in l:
            if( re.match(r,s) ):
                return vdb.dot.color(s,c)
        return s


    def ins_to_dot( self, i, node, showspec ):
#        if( "m" in showspec ):
#            if( i.marked ):
#                line = vdb.color.color(next_marker.value,color_marker.value)
#            else:
#                line = " " * len(next_marker.value)
        tr = vdb.dot.tr()
        tr["align"] = "left"
        node.table.add(tr)

        plen = vdb.arch.pointer_size // 4

        if( "m" in showspec ):
            if( i.marked ):
                tr.td_raw(vdb.dot.color(next_marker_dot.value,color_marker_dot.value))
            else:
                tr.td_raw("&nbsp;")

        if( "a" in showspec ):
            tr.td_raw(vdb.dot.color(f"0x{i.address:0{plen}x}",color_addr_dot.value))["port"] = str(i.address)

        if( "o" in showspec ):
            tr.td_raw(vdb.dot.color(offset_fmt_dot.value.format(offset = i.offset, maxlen = self.maxoffset),color_offset_dot.value))

        if( "b" in showspec ):
            tr.td_raw(vdb.dot.color(' '.join(i.bytes),color_bytes_dot.value))

        if( "n" in showspec ):
            tr.td_raw("&nbsp;")
            txt = ""
            if( len(i.prefix) > 0 ):
                if( len(color_prefix_dot.value) > 0 ):
                    pcol = vdb.dot.color(i.prefix,color_prefix_dot.value)
                else:
                    pcol = self.color_dot_relist(i.prefix,pre_colors_dot)
                txt += pcol
                txt += "&nbsp;"

            if( len(color_mnemonic_dot.value) > 0 ):
                mcol = vdb.dot.color(i.mnemonic,color_mnemonic_dot.value)
            else:
                mcol = self.color_dot_relist(i.mnemonic,asm_colors_dot)
            txt += mcol
            tr.td_raw(txt)

        if( "p" in showspec ):
            if( i.args is not None ):
                tr.td_raw(vdb.dot.color(i.args,color_args_dot.value))
            else:
                tr.td_raw("&nbsp;")

        if( "r" in showspec ):
            if( i.reference is not None ):
                tr.td_raw(vdb.dot.color(vdb.shorten.symbol(i.reference),color_function_dot.value))

        if( any((c in showspec) for c in "tT" ) ):
            if( "T" in showspec ):
                if( i.target_name is not None ):
                    tr.td_raw(vdb.dot.color(vdb.shorten.symbol(i.target_name),color_function_dot.value))

        for td in tr.tds:
            td["align"]="left"


    def to_dot( self,showspec ):
        self.lazy_finish()
        g = vdb.dot.graph("disassemble")
        g.node_attributes["fontname"] = dot_fonts.value

        node = None
        previous_node = None
        previous_instruction = None
        for ins in self.instructions:
            if( node is None or len(ins.target_of) > 0 ):
                node = g.node(ins.address)
                if( previous_node is not None ):
                    if( previous_instruction is not None and ( not previous_instruction.return_ ) ):
                        if( len(previous_instruction.targets) > 0  and not ( previous_instruction.conditional_jump or previous_instruction.call ) ):
                            pass
                        else:
                            e=previous_node.edge( ins.address )
                            if( previous_instruction and previous_instruction.conditional_jump ):
                                e["color"] = color_jump_false_dot.value
                            elif( previous_instruction and previous_instruction.call ):
                                e["color"] = color_call_dot.value
                    previous_node = None
                    previous_instruction = None
            if( node.table is None ):
                node.table = vdb.dot.table()
                node.table.attributes["border"] = "1"
                node.table.attributes["cellspacing"] = "0"
                node.table.attributes["cellborder"] = "0"
            self.ins_to_dot(ins,node,showspec)
            previous_node = node
            previous_instruction = ins
            if( len(ins.targets) > 0 and not ins.call ):
                for tgt in ins.targets:
                    port = None
                    if( tgt < ins.address ):
                        port = tgt
                    e=node.edge(tgt,port)
                    if( ins.conditional_jump ):
                        e["color"] = color_jump_true_dot.value
                    else:
                        e["color"] = color_jump_dot.value
                    if( prefer_linear_dot.value ):
                        e["constraint"] = "false"
                node = None
            if( ins.return_ ):
                node = None
        return g



    def add( self, ins ):
        self.finished = False
        self.instructions.append(ins)
        self.maxoffset = max(self.maxoffset,len(ins.offset))
        self.maxbytes = max(self.maxbytes,len(ins.bytes))
        if( ins.args is not None ):
            self.maxmnemoic = max(self.maxmnemoic,len(ins.prefix) + 1 + len(ins.mnemonic) )
            self.maxargs = max(self.maxargs,len(ins.args))
        if( len(ins.prefix) > 0 ):
            ins.infix = " "
        self.by_addr[ins.address] = ins
        # "up" jumping part of the target_of, the "down" jumping part is done in finish()
        self.add_target(ins)

x86_unconditional_jump_mnemonics = set([ "jmp", "jmpq" ] )
x86_return_mnemonics = set (["ret","retq","iret"])
x86_call_mnemonics = set(["call","callq","int"])
x86_prefixes = set([ "rep","repe","repz","repne","repnz", "lock", "bnd" ])

pc_list = [ "rip", "eip", "ip", "pc" ]
last_working_pc = ""

def fix_marker( ls, alt = None ):
#    mark = vdb.util.gint("$rip")
    try:
        mark = vdb.util.gint(f"${last_working_pc}")
    except:
        try:
            mark = vdb.util.gint(alt)
        except:
            mark = None

    for i in ls.instructions:
#            print("%s == %s ? %s " % (i.address,mark,(i.address == mark)))
        if( i.address == mark ):
            i.marked = True
        else:
            i.marked = False
    ls.do_backtrack()
    return ls

parse_cache = {}
def parse_from_gdb( arg, fakedata = None ):
#    print("fakedata = '%s'" % fakedata )
#    print("arg = '%s'" % arg )
#    print("len(arg) = '%s'" % len(arg) )
    global parse_cache

    key = arg

    if( len(arg) == 0 ):
        if( gdb.selected_thread() == None ):
            return listing()

#        gdb.execute(f"p $rip")
        global last_working_pc
        for pc in [ last_working_pc ] + pc_list:
            try:
#                key = gdb.execute(f"info symbol $rip",False,True)
                key = gdb.execute(f"info symbol ${pc}",False,True)
                last_working_pc = pc
                if( key.startswith("No symbol matches") ):
                    continue
#                print("pc = '%s'" % pc )
                break
            except:
                pass
#        print("key = '%s'" % key )
        key = re.sub(r" \+ [0-9]+","",key)

#    print("arg = '%s'" % arg )
#    print("key = '%s'" % key )

    ret = None
    ret = parse_cache.get(key,None)
#    print("ret = '%s'" % ret )
    if( ret is not None and fakedata is None ):
        return fix_marker(ret,arg)
    ret = listing()


    prefixes = x86_prefixes
    unconditional_jump_mnemonics = x86_unconditional_jump_mnemonics
    return_mnemonics = x86_return_mnemonics
    call_mnemonics = x86_call_mnemonics

#    print("arg = '%s'" % (arg,) )
    if( fakedata is None ):
        dis = gdb.execute(f'disassemble/r {arg}',False,True)
    else:
        dis = fakedata
#    print("dis = '%s'" % dis )
#    linere = re.compile("^(=>)*\s*(0x[0-9a-f]*)\s*<\+([0-9]*)>:\s*([^<]*)(<[^+]*(.*)>)*")
    linere = re.compile("^(=>)*\s*(0x[0-9a-f]*)(\s*<\+([0-9]*)>:)*\s*([^<]*)(<[^+]*(.*)>)*")
    funcre = re.compile("for function (.*):")
    rangere = re.compile("Dump of assembler code from (0x[0-9a-f]*) to (0x[0-9a-f]*):")
    bytere = re.compile("^[0-9a-fA-F][0-9a-fA-F]$")
    jmpre  = re.compile("^\*(0x[0-9a-fA-F]*)\(.*")
    cmpre  = re.compile("^\$(0x[0-9a-fA-F]*),.*")
    current_function=""
    last_cmp_immediate = 1

    markers = 0
#    print("dis = '%s'" % dis )
    for line in dis.splitlines():
#        print("line = '%s'" % line )
        ins = instruction()
        fm=re.search(funcre,line)
        if( fm ):
            ret.function = fm.group(1)
            current_function = "<" + fm.group(1)
            continue
        rr = re.search(rangere,line)
        if( rr ):
#            print("rr.group(0) = '%s'" % rr.group(0) )
#            print("rr.group(1) = '%s'" % rr.group(1) )
#            print("rr.group(2) = '%s'" % rr.group(2) )
            continue
        m=re.search(linere,line)
        if( m ):
            tokens = line.split()
            marker = m.group(1)
            if( marker is not None ):
                ins.marked = True
                markers += 1
                tokens = tokens[1:]
#            print("tokens = '%s'" % tokens )
            # the dissamble version without <line+>
            if( tokens[0][-1] == ":" ):
                tokens[0] = tokens[0][:-1]
            elif( tokens[1][-1] != ":" ):
                while( tokens[1][-1] != ":" ):
#                    print("tokens[1][-1] = '%s'" % tokens[1][-1] )
                    tokens[1] += tokens[2]
#                    print("tokens[1] = '%s'" % tokens[1] )
                    del tokens[2]

            xtokens = []
#            print("tokens = '%s'" % tokens )
            while len(tokens) > 0:
                tok = tokens[0]
                if( len(xtokens) > 0 and xtokens[-1].endswith(",") ):
                    xtokens[-1] += tok
                else:
                    xtokens.append(tok)
                tokens = tokens[1:]
#            print("xtokens = '%s'" % xtokens )
            tokens = xtokens

            ins.address = vdb.util.xint(tokens[0])
            if( ret.start == 0 ):
                ret.start = ins.address
            ret.end = max(ret.end,ins.address)
#            print("tokens[1] = '%s'" % tokens[1] )
            if( len(tokens[1]) < 2 or tokens[1][1] == "+" ):
                ins.offset = tokens[1][2:-2]
            else:
                ins.offset = tokens[1][1:-2]
#            print("ins.offset = '%s'" % ins.offset )
            tpos = 1
            ibytes = []
            while( tpos < len(tokens) ):
                tpos += 1
                tok = tokens[tpos]
                if( bytere.match(tok) ):
                    ibytes.append( tok )
                else:
                    break
            ins.bytes = ibytes
            tokens = tokens[tpos:]
            tpos = 0
            if( tokens[tpos] in prefixes ):
                ins.prefix = tokens[tpos]
                tpos += 1
            ins.mnemonic = tokens[tpos]
            tpos += 1
            if( ins.mnemonic in return_mnemonics ):
                ins.return_ = True
            if( len(tokens) > tpos ):
                ins.args = tokens[tpos]
                tpos += 1

            if( ins.mnemonic == "cmp" ):
                m = re.search(cmpre,ins.args)
#                print("m = '%s'" % m )
                if( m is not None ):
                    cmparg = m.group(1)
                    last_cmp_immediate = vdb.util.xint(cmparg)

            if( len(tokens) > tpos ):
#                print("tokens[tpos] = '%s'" % tokens[tpos] )
                if( tokens[tpos] == "#" ):
                    ins.reference = " ".join(tokens[tpos+1:])
#                    print("ins.reference = '%s'" % ins.reference )
                else:
                    if( ins.mnemonic not in unconditional_jump_mnemonics ):
                        ins.conditional_jump = True
#                    print("TARGET ADD %s",tokens[tpos-1])
                    try:
                        ins.targets.add(vdb.util.xint(tokens[tpos-1]))
                    except:
                        pass
                    ins.target_name = " ".join(tokens[tpos:])
            elif( ins.mnemonic in unconditional_jump_mnemonics ):
                m = re.search(jmpre,ins.args)
                if( m is not None ):
                    table = m.group(1)
                    cnt = 0
                    while True:
                        try:
                            jmpval = gdb.parse_and_eval(f"*((void**){table}+{cnt})")
#                        print("jmpval = '%s'" % jmpval )
                            if( jmpval == 0 ):
                                break
                        except gdb.MemoryError:
                            break
                        if( cnt > last_cmp_immediate ):
                            break
#                        print("last_cmp_immediate = '%s'" % last_cmp_immediate )
                        ins.targets.add(int(jmpval))
                        cnt += 1
                    ins.reference = f"{len(ins.targets)} computed jump targets " # + str(ins.targets)
#                    print("jmpval = '%s'" % jmpval )
#                    print("m = '%s'" % m )
#                    print("m.group(1) = '%s'" % m.group(1) )
#                    print("ins = '%s'" % ins )

            if( ins.mnemonic in call_mnemonics ):
                ins.call = True
                ins.conditional_jump = False
#            print("tokens = '%s'" % tokens[tpos:] )
            ret.add(ins)
            continue
        if( line in set(["End of assembler dump."]) ):
            continue
        if( len(line) == 0 ):
            continue
        print(f"Don't know what to do with '{line}'")
#			print("m = '%s'" % m )
    if( fakedata is None ):
        parse_cache[key] = ret
    if( markers == 0 ):
        ret = fix_marker(ret,arg)
#    print(f"Returning for {key}")
    return ret

def parse_from( arg, fakedata = None ):
    rng = arg.split(",")
    if( len(rng) == 2 ):
        try:
            fr=vdb.util.gint(rng[0])
            to=vdb.util.gint(rng[1])
#            print("fr = '%x'" % fr )
#            print("to = '%x'" % to )
            if( to < fr ):
                to = fr + to + 1
            arg = f"0x{fr:x},0x{to:x}"

        except:
#            print("rng = '%s'" % rng )
            pass
    # other disssembler options go here
    try:
#        print("arg = '%s'" % arg )
#        print("fakedata = '%s'" % fakedata )
        if( arg.startswith("000000") ): # really do some regex for a hex value and check that it starts with a digit
            ret = parse_from_gdb("0x" + arg,fakedata)
        else:
            ret = parse_from_gdb(arg,fakedata)
    except gdb.error as e:
        if( str(e) == "No function contains specified address." ):
            return parse_from(arg+","+str(nonfunc_bytes.value))
        elif( str(e) == "No function contains program counter for selected frame." ):
            return parse_from("$rip,"+str(nonfunc_bytes.value))
        else:
            print("e = '%s'" % e )
            traceback.print_exc()
            raise e

    return ret

def disassemble( argv ):
    dotty = False
    context = None
    fakedata = None

    if( len(argv) > 0 ):

        if( argv[0][0] == "/" ):
            if( argv[0][1] == "+" and argv[0][2:].isdigit() ):
                context = ( None, int(argv[0][2:]) )
                argv=argv[1:]
            elif( argv[0][1] == "-" and argv[0][2:].isdigit() ):
                context = ( int(argv[0][2:]), None )
                argv=argv[1:]
            elif( argv[0][1:].isdigit() ):
                context = int(argv[0][1:])
                context = ( context, context )
                argv=argv[1:]
            elif( argv[0].find(",") != -1 ):
                context = argv[0][1:].split(",")
                context = ( int(context[0]), int(context[1]) )
                argv=argv[1:]
            elif( argv[0] == "/d" ):
                dotty = True
                argv=argv[1:]
            elif( argv[0] == "/f" ):
                with open (argv[1], 'r') as fakefile:
                    fakedata = fakefile.read()
                argv=["fake"]
            elif( argv[0] == "/r" ):
                argv=argv[1:]
                gdb.execute("disassemble " + " ".join(argv))
                return


    listing = parse_from(" ".join(argv),fakedata)
    listing.print(asm_showspec.value, context)
    if( dotty ):
        g = listing.to_dot(asm_showspec_dot.value)
        g.write("dis.dot")
        os.system("nohup dot -Txlib dis.dot &")


def get_single( bpos ):
    ret="<??>"
    try:
        da=gdb.selected_frame().architecture().disassemble(int(bpos),count=1)
        da=da[0]
        fake = f"0x{da['addr']:x} <+0>: {da['asm']}"
        li = parse_from_gdb("",fake)
        ret = li.to_str(asm_showspec.value.replace("a","").replace("o",""))
        ret = ret.splitlines()
        ret = ret[1]
    except:
        pass
    return ret

class Dis (vdb.command.command):
    """Disassemble with bells and whistels"""

    def __init__ (self):
        super (Dis, self).__init__ ("dis", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):

        try:
            disassemble( argv )
        except gdb.error as e:
            print(e)
        except:
            traceback.print_exc()
            raise
            pass

Dis()


if __name__ == "__main__":
    try:
        disassemble( sys.argv[1:] )
    except:
        traceback.print_exc()
        pass



# vim: tabstop=4 shiftwidth=4 expandtab ft=python
