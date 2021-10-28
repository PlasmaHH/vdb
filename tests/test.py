#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import hashlib
import difflib
import sys
import re
import colors

sys.path.insert(0,'..')
import vdb.color

goodcolor = "#080"
failcolor = "#f00"
skipcolor = "#ff0"

def color( msg, col ):
    print(vdb.color.color(msg,col))

def good( msg ):
    color(msg,goodcolor)

def skip( msg ):
    color(msg,skipcolor)

def fail( msg ):
    color(msg,failcolor)

def same(a,b):
#	print ("re.match(%s,%s)") % (b,a)
	if a == b:
		return True
#	print a
	try:
		m = re.match(b,a)
		if(m):
			return True
	except Exception:
		return False

def my_find_longest_match(self, alo, ahi, blo, bhi):
	"""Find longest matching block in a[alo:ahi] and b[blo:bhi].

	If isjunk is not defined:

	Return (i,j,k) such that a[i:i+k] is equal to b[j:j+k], where
	alo <= i <= i+k <= ahi
	blo <= j <= j+k <= bhi
	and for all (i',j',k') meeting those conditions,
	k >= k'
	i <= i'
	and if i == i', j <= j'

	In other words, of all maximal matching blocks, return one that
	starts earliest in a, and of all those maximal matching blocks that
	start earliest in a, return the one that starts earliest in b.

	>>> s = SequenceMatcher(None, " abcd", "abcd abcd")
	>>> s.find_longest_match(0, 5, 0, 9)
	Match(a=0, b=4, size=5)

	If isjunk is defined, first the longest matching block is
	determined as above, but with the additional restriction that no
	junk element appears in the block.  Then that block is extended as
	far as possible by matching (only) junk elements on both sides.  So
	the resulting block never matches on junk except as identical junk
	happens to be adjacent to an "interesting" match.

	Here's the same example as before, but considering blanks to be
	junk.  That prevents " abcd" from matching the " abcd" at the tail
	end of the second sequence directly.  Instead only the "abcd" can
	match, and matches the leftmost "abcd" in the second sequence:

	>>> s = SequenceMatcher(lambda x: x==" ", " abcd", "abcd abcd")
	>>> s.find_longest_match(0, 5, 0, 9)
	Match(a=1, b=0, size=4)

	If no blocks match, return (alo, blo, 0).

	>>> s = SequenceMatcher(None, "ab", "c")
	>>> s.find_longest_match(0, 2, 0, 1)
	Match(a=0, b=0, size=0)
	"""

	# CAUTION:  stripping common prefix or suffix would be incorrect.
	# E.g.,
	#	ab
	#	acab
	# Longest matching block is "ab", but if common prefix is
	# stripped, it's "a" (tied with "b").  UNIX(tm) diff does so
	# strip, so ends up claiming that ab is changed to acab by
	# inserting "ca" in the middle.  That's minimal but unintuitive:
	# "it's obvious" that someone inserted "ac" at the front.
	# Windiff ends up at the same place as diff, but by pairing up
	# the unique 'b's and then matching the first two 'a's.

	a, b, b2j, isbjunk = self.a, self.b, self.b2j, self.bjunk.__contains__
	besti, bestj, bestsize = alo, blo, 0
	# find longest junk-free match
	# during an iteration of the loop, j2len[j] = length of longest
	# junk-free match ending with a[i-1] and b[j]
	j2len = {}
	nothing = []
	for i in range(alo, ahi):
	# look at all instances of a[i] in b; note that because
	# b2j has no junk keys, the loop is skipped if a[i] is junk
		j2lenget = j2len.get
		newj2len = {}
		for j in b2j.get(a[i], nothing):
			# a[i] matches b[j]
			if j < blo:
				continue
			if j >= bhi:
				break
			k = newj2len[j] = j2lenget(j-1, 0) + 1
			if k > bestsize:
				besti, bestj, bestsize = i-k+1, j-k+1, k
		j2len = newj2len

	# Extend the best by non-junk elements on each end.  In particular,
	# "popular" non-junk elements aren't in b2j, which greatly speeds
	# the inner loop above, but also means "the best" match so far
	# doesn't contain any junk *or* popular non-junk elements.
	while besti > alo and bestj > blo and \
			not isbjunk(b[bestj-1]) and \
			same(a[besti-1] , b[bestj-1]):
#		print( "same(%s,%s)" % (a[besti-1],b[bestj-1]) )
		besti, bestj, bestsize = besti-1, bestj-1, bestsize+1
	while besti+bestsize < ahi and bestj+bestsize < bhi and \
			not isbjunk(b[bestj+bestsize]) and \
			same(a[besti+bestsize] , b[bestj+bestsize]):
#		print( "same(%s,%s)" % (a[besti+bestsize],b[bestj+bestsize]) )
		bestsize += 1

	# Now that we have a wholly interesting match (albeit possibly
	# empty!), we may as well suck up the matching junk on each
	# side of it too.  Can't think of a good reason not to, and it
	# saves post-processing the (possibly considerable) expense of
	# figuring out what to do with it.  In the case of an empty
	# interesting match, this is clearly the right thing to do,
	# because no other kind of match is possible in the regions.
	while besti > alo and bestj > blo and \
			isbjunk(b[bestj-1]) and \
			same(a[besti-1] , b[bestj-1]):
#		print( "same(%s,%s)" % (a[besti-1],b[bestj-1]) )
		besti, bestj, bestsize = besti-1, bestj-1, bestsize+1
	while besti+bestsize < ahi and bestj+bestsize < bhi and \
			isbjunk(b[bestj+bestsize]) and \
			same(a[besti+bestsize] , b[bestj+bestsize]):
#		print( "same(%s,%s)" % (a[besti+bestsize],b[bestj+bestsize]) )
		bestsize = bestsize + 1

	return difflib.Match(besti, bestj, bestsize)

difflib.SequenceMatcher.find_longest_match = my_find_longest_match


def diff( fromlines, tolines ):
    res=[line for line in difflib.unified_diff(fromlines,tolines,"A","B")]
#    print(''.join(res))
    return res

compilecache = {}

def compile( fn ):
    global compilecache
    ofn = compilecache.get(fn,None)
    if( ofn is not None ):
        return ofn
    ofn = os.path.splitext(fn)[0]
    print("Compiling %s ..." % fn )
    gcc = subprocess.check_output( [ "g++", "-w", "-ggdb3", "-std=gnu++2b", fn, "-o", ofn ] ).decode("utf-8")
    compilecache[fn] = ofn
    return ofn


def run_binary( binary, cmds ):
    cmdsx = [ "set confirm off", "echo ONLY_USE_OUT_AFTER_THIS" ] + cmds + [ "q" ]
    gdb="/home/plasmahh/opt/gdb/bin/gdb"
    if( binary is not None ):
        cmdlist = [ gdb, binary ]
    else:
        cmdlist = [ gdb ]
    for cmd in cmdsx:
        if( cmd is None ):
            cmd = "echo ONLY_USE_OUT_AFTER_THIS"
        cmdlist += [ "-ex", cmd ]
#        print("cmd = '%s'" % (cmd,) )

#    print("cmdlist = '%s'" % (cmdlist,) )
    print('" "'.join(cmdlist))
    gdb = subprocess.check_output( cmdlist, stderr = subprocess.STDOUT, input=None ).decode("utf-8")
    gdb = gdb.split("ONLY_USE_OUT_AFTER_THIS")[-1]
#    print("gdb = '%s'" % (gdb,) )
    hash = hashlib.md5( gdb.encode("utf-8") ).hexdigest()
#    print("gdb = '%s'" % (gdb,) )
#    print("hash = '%s'" % (hash,) )
    return ( gdb, hash )


def run_tests( tests ):
    failed = 0
    passed = 0
    skipped = 0
    for test in tests:
        f = test.get("file",None)
        c = test.get("commands",None)
        n = test.get("name", "unnamed test" )
        en = test.get("enabled",None)
        print("Test '%s' :" % n)
        if( en is not None and en == False ):
            skip("Skipping, not enabled")
            skipped += 1
            continue
        if( f is not None and c is not None ):
            b = compile(f)
            g,h = run_binary( b, c )
            h0 = test.get("hash",None)
            if( h0 is not None ):
                if( h == h0 ):
                    good("hash passed")
                    passed += 1
                else:
                    fail("hash failed")
                    print("Expected: %s, result %s" % (h0,h) )
                    failed += 1
        else:
            g,h = run_binary( None, c )
        e = test.get("expect",None)
        if( e is not None ):
            tolines = open(e, 'r').readlines()
            g=colors.strip_color(g)
            r = diff(g.splitlines(keepends=True),tolines)
            if( len(r) > 0 ):
                fail("Failed:")
                print("".join(r))
                ofn = os.path.splitext(e)[0]
                ofn += ".out"
                with open(ofn,"w") as o:
                    o.write(g)
                failed += 1
            else:
                good("expect passed")
                passed += 1
#            print("r = '%s'" % (r,) )

    fc = failcolor
    sk = skipcolor
    if( failed == 0 ):
        fc = goodcolor
    if( skipped == 0 ):
        sk = goodcolor
    print(vdb.color.color(f"Passed: {passed}",goodcolor),end="")
    print(vdb.color.color(f", Failed: {failed}",fc),end="")
    print(vdb.color.color(f", Skipped: {skipped}",sk))



tests = [
            {
                "name" : "ftree backtrace",
                "file" : "ftree.cxx",
                "commands" : [ "r", None, "bt" ],
                "hash" : "4bb6e33ddf91a27fa15a3d6818b8a007",
                "expect" : "ftree_backtrace.exp",
                "enabled" : True
            },
            {
                "name" : "pahole types",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "pahole/c morev", "pahole/c f3", "pahole/c u", "pahole/c oax", "pahole/c xv" ],
                "hash" : "18c39b3d99a413f7eb008ed0bf69e2a4",
                "enabled" : True
            },
            {
                "name" : "pahole variables",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "pahole/c vm", "pahole/c fd", "pahole/c uu", "pahole/c xxx", "pahole/c x" ],
                "hash" : "6ff35e9faa4ff294ee8bf10eebb3047c",
                "enabled" : True
            },
            {
                "name" : "disassemble",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "dis" ],
                "hash" : "5ed9eeaff6ea320f66756334445d3e13",
                "expect" : "pahole_disassemble.exp",
                "enabled" : True
            },
            {
                "name" : "mock disassemble",
                "commands" : [ None,
                    "dis/f mock0.txt",
                    "dis/f mock1.txt",
                    "dis/f mock2.txt",
                    "dis/f mock3.txt",
                    "dis/f mock4.txt",
                    "dis/f mock5.txt",
                    "dis/f mock6.txt",
                    "dis/f mock7.txt",
                    "dis/f mock8.txt",
                    ],
                "hash" : "f3b0222bf815ec12765f06a1fa14c646",
                "expect" : "mock_disassemble.exp",
                "enabled" : True
            },

        ]

run_tests( tests )
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
