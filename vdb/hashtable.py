#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.command
import vdb.config

import gdb

import traceback
import math
import re
import datetime
import os
from PIL import Image


raw_filename  = vdb.config.parameter("vdb-hashtable-filename","hashtable.png")
imgcommand    = vdb.config.parameter("vdb-hashtable-img-command", "gwenview {filename} &>/dev/null &" )

chains_buckets_number = [
        [ "_M_h", "_M_bucket_count" ],
        [ "data","bucket_traits_","buckets_len_" ]
        ]

chains_buckets_ptr = [
        [ "_M_h", "_M_buckets" ],
        [ "data","bucket_traits_","buckets_" ]
        ]

chains_next = [
        [ "_M_nxt" ],
        [ "data_","root_plus_size_","header_holder_","next_" ]
        ]

chains_ignore = [
        [ "_M_h", "_M_before_begin" ]
        ]

chain_skips = [
        ( "boost::intrusive::unordered.*", 1 )
        ]

def extract_member( val, chain ):
    for c in chain:
        try:
            xval = val
            for m in c:
#                print("m = '%s'" % m )
#                print("xval = '%s'" % xval )
                xval = xval[m]
#                print("xval = '%s'" % xval )
#            print("FINAL xval = '%s'" % xval )
            return xval
        except:
            pass
#    for f in val.type.fields():
#        print("f.name = '%s'" % f.name )
    return None


def extract_buckets_number(val):
    return extract_member( val, chains_buckets_number )

def extract_buckets_ptr(val):
    return extract_member( val, chains_buckets_ptr )

def extract_next( val ):
    return extract_member( val, chains_next )

def extract_ignore( val ):
    return extract_member( val, chains_ignore )


def get_probability( slots, entries, k ):
    m = entries
    n = slots

    ut = pow(((n-1)/n),m)

    cterm = 1.0
    for i in range( 1,k+1 ):
#    for( int i = 1; i <= k; ++i ):
        aterm = (m-i-1)
        aterm /= (i*(n-1))
        cterm *= aterm
    full = cterm * ut
    return full



pixel_colors = {
        0: (   0,   0,   0 ),
        1: ( 255, 255, 255 ),
        2: ( 255, 255,   0 ),
        3: ( 255, 128,   0 ),
        4: ( 255,   0,   0 ),
     None: ( 205,   0, 205 )
     }

def buckaddr( sbucket ):
    try:
        return int(sbucket)
    except:
        return int(sbucket.address)

def eval_hashtable( val ):
    num_buckets = extract_buckets_number(val)
    num_buckets = int(num_buckets)
    buckptr = extract_buckets_ptr(val)
    ignore_node = extract_ignore(val)
    ignore_nodes = set()
    ignore_nodes.add( 0x0 )
    if( ignore_node is not None ):
        ignore_nodes.add( int(ignore_node.address) )

#    print("val.type = '%s'" % val.type.strip_typedefs() )

    c_skips = 0
    for cs,n in chain_skips:
        m = re.match( cs,  str(val.type.strip_typedefs()) )
        if( m ):
            c_skips = n
            break

#    print("num_buckets = '%s'" % num_buckets )
#    print("buckptr = '%s'" % buckptr )
    chainlens = []
    first_nodes = set()
    for b in range(0,num_buckets):
        sbucket = buckptr[b]
#        print("sbucket = '%s'" % sbucket )
        first_nodes.add(buckaddr(sbucket))

    for b in range(0,num_buckets):
        clen = 0
        sbucket = buckptr[b]
#        if( sbucket != 0x0 ):
        if( buckaddr(sbucket) not in ignore_nodes ):
            xbucket = sbucket
            xbucket = extract_next(xbucket)
            clen += 1
            clen -= c_skips
#            print("xbucket = '%s'" % xbucket )
            while( xbucket is not None and buckaddr(xbucket) not in ignore_nodes and buckaddr(xbucket) not in first_nodes ):
                xbucket = extract_next(xbucket)
                clen += 1
#            print("sbucket = '%s'" % sbucket )
        chainlens.append(clen)
#    print("chainlens = '%s'" % chainlens )
    slotcounts = {}
    elements = 0
    maxchain = 0
    for ch in chainlens:
        elements += ch
        sc = slotcounts.get( ch, 0 )
        sc += 1
        slotcounts[ch] = sc
        maxchain = max(maxchain,ch)
#    print("maxchain = '%s'" % maxchain )
#    print("slotcounts = '%s'" % slotcounts )
#    print("elements = '%s'" % elements )
    load = elements / num_buckets
    print("load = '%.3f'" % load )
    tbl = [ ["Chainlen","Bucket%","Num", "Ideal","Ideal%" ] ]
#    for i in range(0,20):
    for i in range(0,maxchain+1):
        sc = slotcounts.get(i,None)
        if( sc is None ):
            continue
        buckpc = sc / num_buckets * 100.0
        p = get_probability( num_buckets, elements, i )
        ebuck = p * num_buckets
        p *= 100
#        print(f"{i: 2} {buckpc:.2f}% {sc} {ebuck:.1f} {p:.3f}%")
        tbl.append( [ f"{i: 2}",f"{buckpc:.2f}%",f"{sc}",f"{ebuck:.1f}",f"{p:.3f}%" ] )
    t = vdb.util.format_table(tbl)
    print(t)
    imgsz = math.ceil(math.sqrt(num_buckets))
#    print("imgsz = '%s'" % imgsz )
    img = Image.new("RGB",(imgsz,imgsz),"black")
    pixels = img.load()
    ix = 0
    iy = 0
    defcolor = pixel_colors.get(None)
    for ch in chainlens:
        ix += 1
        if( ix >= imgsz ):
            ix = 0
            iy += 1
        co = pixel_colors.get(ch,defcolor)
#        pixels[ix,iy] = (ch*30,ch*30,ch*30)
        pixels[ix,iy] = co

#    img.show()
    filename = raw_filename.value
    now=datetime.datetime.now()
    filename=now.strftime(filename)
#    img.save("hashtable.png")
    img.save("hashtable.png")

    if( len(imgcommand.value) > 0 ):
        cmd=imgcommand.value.format(filename=filename)
        print(f"Created '{filename}', starting {cmd}")
        os.system(cmd)

class cmd_hashtable (vdb.command.command):
    """Generate graphical information about the state of a hashtable (std:: and boost::)
hashtable <expression>

The expression must evaluate to a compatible object. Currently std::unordered and boost::instrusive::unordered are
supported. You can add support by filling the right chain lists above here. Until we are settled on a proper way and do
documentation you have to read the code on how to do that.

The output will be a png image with one pixel per bucket, filled black for empty, and then white,yellow,orange,red  for
chain lengths of 1,2,3,4 elements and pink for all bigger chains.

Additionally a table tells you details about the amount of chain lengths and how a "perfect" hash would perform in comparison
    """

    def __init__ (self):
        super (cmd_hashtable, self).__init__ ("hashtable", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.result = ""

    def do_invoke (self, argv ):
        if len(argv) > 1:
            raise gdb.GdbError('hashtable takes 1 arguments.')

        a0 = gdb.parse_and_eval(argv[0])

        try:
            eval_hashtable(a0)
        except Exception as e:
            traceback.print_exc()
        self.dont_repeat()

cmd_hashtable()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
