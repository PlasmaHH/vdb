#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.memory
import vdb.command

import gdb
import intervaltree

import re
import traceback
import shutil


color_executable   = vdb.config.parameter("vdb-vmmap-colors-executable",       "#e0e",        gdb_type = vdb.config.PARAM_COLOUR)
color_readonly     = vdb.config.parameter("vdb-vmmap-colors-readonly",         "#f03",        gdb_type = vdb.config.PARAM_COLOUR)
vmmap_max_size     = vdb.config.parameter("vdb-vmmap-visual-max-size", 64*128 )
vmmap_wrapat       = vdb.config.parameter("vdb-vmmap-wrapat", 0 )

#dpy_chars = vdb.config.parameter("vdb-vmmap-chars", "⠀⣿" )
#dpy_chars = vdb.config.parameter("vdb-vmmap-chars", " ░▒▓" )
dpy_chars = vdb.config.parameter("vdb-vmmap-chars", " ▂▃▄▅▆▇█" )
#dpy_chars = vdb.config.parameter("vdb-vmmap-chars", " #" )

def show_region( addr, colorspec ):
    ga = gdb.parse_and_eval(f"(void*){addr}")
    print(ga)
    ca,mm,_,_ = vdb.memory.mmap.color(addr,colorspec = colorspec)
    if( mm is None ):
        print(f"Nothing known about address {addr:#016x}")
        return None
    print( f"Address {ca} is in {str(mm)}" )

def fill_char( num, res ):
    ch = dpy_chars.value
    
    if( num == 0 ):
        return ch[0]
    if( num >= res ):
        return ch[-1]
    rb = res / (len(ch)-2)
    ri = int(num / rb)
#    print("num = '%s'" % (num,) )
#    print("res = '%s'" % (res,) )
#    print("ri = '%s'" % (ri,) )

    return ch[ri+1]



def visual( argv, regions = None ):

#    mingapsize = 128*1024
    mingapsize = 8*1024

    lastend = 0

    biggaps = []
    gapstartset = set()

    vdb.memory.print_legend(None)
    if( regions is None ):
        regions = vdb.memory.mmap.regions

    sorted_regions = sorted(regions)
#    print("len(sorted_regions) = '%s'" % (len(sorted_regions),) )
    for r in sorted_regions:
        r = r[2]
        if( r.start == 0 ):
            continue
        if( r.file == "[vsyscall]" ):
            continue
        if( lastend == 0 ):
            lastend = r.end
            continue
        gap = r.start - lastend
        if( gap < 0 ): # this should somewhat filter out overlaps 
            continue
        if( gap > 4096 ): # only count more than a page
            biggaps.append( ( gap, r.start ) )

        lastend = r.end
#    print("sorted(biggaps) = '%s'" % (sorted(biggaps,reverse=True),) )
    for bg in sorted(biggaps,reverse=True):
#        print("bg[0] = '%s'" % (bg[0],) )
        if( bg[0] >= mingapsize ):
            gapstartset.add( bg[1] )

    s = 0
    e = 0

    clusters = []

    memsum = 0
    for r in sorted_regions:
        r = r[2]
        if( r.start == 0 ):
            continue
        if( r.file == "[vsyscall]" ):
            continue
        if( s == 0 ):
            s = r.start
            continue
        if( r.start in gapstartset ):
#            print("e = '%s'" % (e,) )
#            print("r.start = '%s'" % (r.start,) )
#            print("(r.start-e) = '%s'" % ((r.start-e),) )
#            print(f"From 0x{s:08x} to 0x{e:08x} (size %{e-s})")
            if( (e-s) > (r.start-e) ):
                pass
            else:
                clusters.append( ( s, e ) )
                memsum += (e-s)
                s = r.start
        if( r.end  > e ):
            e = r.end
    clusters.append( ( s, e ) )
    memsum += (e-s)

    print(f"Found {len(clusters)} clusters")


    for s,e in clusters:
        res = 4096

        num,suf = vdb.util.num_suffix( e-s )
        maxl = vmmap_max_size.value

        while( (e-s)/res > maxl ):
            res *= 2
        rnum,rsuf = vdb.util.num_suffix( res )
#        print("rng = '%s'" % (rng,) )
#        print("maxl = '%s'" % (maxl,) )

        print(f"From {s:#08x} to {e:#08x} (size {num:.02f} {suf}B) @{rnum:.01f} {rsuf}B" )
        rep = " " * ((e-s)//res)
        xr = regions[s:e]
        sp = s//res
        ep = (e+(res-1))//res
#        print("len(rep) = '%s'" % (len(rep),) )

        rep = ""
        cnt = 0

        mx = None
        lx = None
        wrapat = vmmap_wrapat.get()

        if( wrapat is None or wrapat == 0 ):
            wrapat=vdb.command.command.terminal_width

        if( wrapat is None ):
            wrapat = 80

#        xr = vdb.memory.mmap.regions[sp*res:ep*res]
#        print("len(xr) = '%s'" % (len(xr),) )
#        print("sp = '%s'" % (sp,) )
#        print("s = '%s'" % (s,) )
        psp = sp * res
        pep = ep * res
        pbytes = 0
        memsum = 0
        for x in sorted(xr):
            x = x[2]
            print("========")
            print("psp = '0x%x'" % (psp,) )
            print("(psp+res) = '0x%x'" % ((psp+res),) )
            print("x.start = '0x%x'" % (x.start,) )
            print("x.end = '0x%x'" % (x.end,) )
            print("(x.end-x.start) = '%s'" % ((x.end-x.start),) )
            print("len(rep) = '%s'" % (len(rep),) )

            if( (psp+res) < x.start ):
#                print(f"next page but partial bytes {pbytes}")
#                rep += "P"
#                rep += f"{{{pbytes}}}"
                rep += fill_char( pbytes, res )
                memsum += pbytes
                psp += res
                pbytes = 0

            while( (psp+res) <= x.start ):
                print(f"GAP {psp:#0x} - {psp+res:#0x}")
                psp += res
                rep += fill_char(0,res)
#                rep += "G"
#            print("psp = '0x%x'" % (psp,) )
#            print("(psp+res) = '0x%x'" % ((psp+res),) )
            # a subsection that is part of a bigger section we have seen already
            if( x.end <= psp ):
#                pass
                print(f"{x.start:#0x} - {x.end:#0x} IGNORED (within previous segment)")

            # The section started below or at our region of interest
            elif( x.start <= psp ):
                # mark all those pages that are completely filled due to this segment
                while( (psp + res) <= x.end ):
                    print(f"{psp:x} - {psp+res:x} FULL")
#                    rep += "F"
                    rep += fill_char( res, res )
                    psp += res
                    memsum += res
                    pbytes = 0
                # The rest gets into pbytes (maybe another segment will fill the rest of the page)
                else:
                    pbytes = x.end - psp
            # The section starts after our region of interest (there is a possibility for a gap)
            else:
                if( pbytes and (psp+res) < x.start ):
                    print(f"partial filled:  {pbytes}")
                    memsum += pbytes
#                    rep += "P"
#                    rep += f"{{{pbytes}}}"
                    rep += fill_char( pbytes, res )
                    pbytes = 0
#                print("x.start not at page start")
                # The end of our region is within the end of this segment
                if( (psp+res) <= x.end ):
                    pbytes += (psp+res)-x.start
                    print(f"partial {pbytes}")
                    psp += res
                    rep += fill_char( pbytes, res )
                while( (psp + res) <= x.end ):
                    print(f"{psp:x} - {psp+res:x} FULL")
#                    rep += "F"
                    rep += fill_char( res, res )
                    psp += res
                    memsum += res
                    pbytes = 0
                # The end (and start) are within the segment and more could follow
                else:
                    print(f"pbytes+= {x.end-x.start}")
                    pbytes += (x.end-x.start)
#            print("pbytes = '%s'" % (pbytes,) )
        if( pbytes > 0 ):
#            rep += f"{{{pbytes}}}"
            rep += fill_char( pbytes, res )
            memsum += pbytes


#            rep += "X"
        rep += "\n"

        rep += "CREP:\n"

        for ri in range(sp,ep):
            cnt+=1 
            rptr = ri * res
            ri -= sp
            eptr = rptr + res - 1
#            print("ri = '%s'" % (ri,) )
            memc,region = vdb.memory.mmap.get_mcolor( rptr )
#            print("region = '%s'" % (region,) )


            filled_char = dpy_chars.value[-1]
#            x = vdb.memory.mmap.regions[s:e]
#            print("memc = '%s'" % (memc,) )
#            print("region = '%s'" % (region,) )
            if( region is None ):
                rep += dpy_chars.value[0]
            else:
                ro_color = color_readonly.value
                try:
                    # This should throw if we are in a core file, where everything is readonly
                    if( gdb.selected_inferior().connection.type == "core" ):
                        ro_color = None
#                    else:
#                        gdb.inferiors()[0].threads()[0].handle()
                except:
#                    vdb.print_exc()
                    ro_color = None
                    pass
                if( region.atype == vdb.memory.access_type.ACCESS_EX ):
                    cs = vdb.color.color( filled_char,  [ memc, color_executable.value ] )
                elif( region.can_write is False ):
                    cs = vdb.color.color( filled_char,  [ memc, ro_color ] )
                else:
                    cs = vdb.color.color( filled_char,  memc )
                rep += cs
            if( cnt > 0 and (cnt % wrapat) == 0 ):
                print(rep)
                rep = ""
#        rep += vdb.color.color("XXX", "#f33,#3f3")

        print(rep)
        print()
#        break

        pages = memsum / res
        print(f"Total blocks occupied: {pages}")

#    print("x = '%s'" % (x,) )




class cmd_vmmap (vdb.command.command):
    """Module holding information about memory mappings

vmmap         - show information about the known memory maps (of the memory module), colored by types
vmmap/s       - short version of that information
vmmap refresh - re-read the information by triggering the memory module (happens at most stop events too)
vmmap <expr>  - Checks the expression/address memory map and displays all details we know about it
vmmap <cspec> - uses this colorspec
    """

    def __init__ (self):
        super (cmd_vmmap, self).__init__ ("vmmap", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            colorspec = None
            short = False
            if( len(argv) == 0 ):
                pass
            elif( len(argv) >= 1 ):
                try:
                    if( argv[0] == "/s" ):
                        short = True
                        argv = argv[1:]
                    if( len(argv) > 0 ):
                        if( argv[0] == "refresh" ):
                            vdb.memory.mmap.parse()
                            return
                        elif( argv[0] == "visual" ):
                            visual(argv[1:])
                            return

                        addr = None
                        try:
                            addr = gdb.parse_and_eval(argv[0])
                            addr = int(addr)
                            argv = argv[1:]
                        except:
#                            vdb.print_exc()
                            pass
                        if( len(argv) > 0 ):
                            colorspec = argv[0]
                            vdb.memory.check_colorspec(colorspec)
                        if( addr is not None ):
                            return show_region( addr, colorspec )
                except:
                    vdb.print_exc()
                    return
                    pass
            else:
                raise Exception("vmmap got %s arguments, expecting 0 or 1" % len(argv) )
            vdb.memory.check_colorspec(colorspec)
            vdb.memory.print_legend(colorspec)
            vdb.memory.mmap.print(colorspec,short)
        except:
            vdb.print_exc()
            raise
            pass
        self.dont_repeat()

cmd_vmmap()

if __name__ == "__main__":
    fr = [ (0x10,0x50), (0x100,0x200),(0x2000,0x3000),(0x2020,0x2800),(0x2a00,0x3100),(0x5000,0x5fff) ]
    regions = intervaltree.IntervalTree()
    for f in fr:
        mr = vdb.memory.memory_region(f[0],f[1],"?","?")
        regions[f[0]:f[1]+1] = mr

    visual([],regions)

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
