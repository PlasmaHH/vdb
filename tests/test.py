#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import hashlib
import difflib
import sys
import re
import colors
import argparse
import shutil

sys.path.insert(0,'..')
import vdb.color
import vdb.util
import vdb.config

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
#    print("a = '%s'" % (a,) )
#    print("b = '%s'" % (b,) )
#	print ("re.match(%s,%s)") % (b,a)
    if a == b:
        return True
#	print a
    try:
        m = re.match(b,a) # b is the regexp
#        print("m = '%s'" % (m,) )
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
    cmdsx = [ "set confirm off", "dash null log", None ] + cmds + [ "q" ]
    gdb="/home/plasmahh/opt/bin/gdb"
    gdb = shutil.which("gdb")
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

# to "hijack" the config parser stuff
class fake_config:
    def __init__( self, v ):
        self.value = v
        self.elements = None

def run_tests( tests ):

    parser = argparse.ArgumentParser(description='run vdb tests.')
    parser.add_argument("-s","--show", action="store_true", help = "Show the list of active tests (and a bit of info)")
    parser.add_argument("-f","--filter", type=str, action="store", help = "Regex to filter tests for")
    parser.add_argument("-d","--debug", action="store_true", help = "enables test debugging mode")

    args = parser.parse_args(sys.argv[1:])

    if( args.filter ):
        cre = re.compile(args.filter)
        for test in tests:
            name = test.get("name",None)
            if( name is not None and cre.search(name) is not None ):
                pass
            else:
                test["enabled"] = False

    if( args.show ):
        otbl = []
        otbl.append(["Name","Enabled","Commands","Expect","Hash","File"])
        for test in tests:
            line=[]
            for kw in ["name","enabled","commands","expect","hash","file"]:
                var = test.get(kw,None)
                if( kw == "commands" ):
                    var = len(var)
                if( kw == "enabled" ):
                    if( var == True or var is None ):
                        var = "Y"
                    else:
                        var = "N"
                line.append( var )
            otbl.append(line)
        print(vdb.util.format_table(otbl))
        return None
    failset = set()
    failed = 0
    passed = 0
    skipped = 0
    for test in tests:
        f = test.get("file",None)
        c = test.get("commands",None)
        cl = test.get("enabled_commands",None)
        cmset = None
        if( cl is not None ):
            fc = fake_config(cl)
            vdb.config.set_array_elements(fc,d1="-")
#            print("fc.elements = '%s'" % (fc.elements,) )
            cmset = set(fc.elements)
            nc=[]
            for ci in range(0,len(c)):
                if( ci in cmset ):
                    nc.append(c[ci])
            c = nc

        n = test.get("name", "unnamed test" )
        en = test.get("enabled",None)
        op = test.get("output",args.debug)
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
                    failset.add( f"{n} hash")
        else:
            g,h = run_binary( None, c )
        e = test.get("expect",None)
        if( op ):
            print(g)
        if( args.debug ):
            continue
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
                failset.add( f"{n} expect")
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
    print(f"The following tests failed: {','.join(failset)}")



tests = [
            {
                "name" : "ftree backtrace",
                "file" : "ftree.cxx",
                "commands" : [ "r", None, "bt" ],
                "expect" : "ftree_backtrace.exp",
                "enabled" : True
            },
            {
                "name" : "varargs",
                "file" : "va.cxx",
                "commands" : [ "start", "set vdb-va-default-format S*", None, "b printf" ] + 9 * [ "c", "va wait", "va fp_offset=48" ],
                "expect" : "va.exp",
                "output" : True
            },
            {
                "name" : "pahole types",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "pahole/c morev", "pahole/c f3", "pahole/c u", "pahole/c oax", "pahole/c xv", "pahole/c bftest" ],
                "enabled" : True,
                "expect" : "pahole_types.exp"
            },
            {
                "name" : "pahole variables",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "pahole/c vm", "pahole/c fd", "pahole/c uu", "pahole/c xxx", "pahole/c x" ],
                "enabled" : True,
                "expect" : "pahole_variables.exp"

            },
            {
                "name" : "disassemble",
                "file" : "paholetest.cxx",
                "commands" : [ "start", None, "dis" ],
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
            {
                    "name": "hexdump",
                    "enabled": True,
                    "file" : "paholetest.cxx",
                    "expect" : "hexdump.exp",
                    "commands": [
                        "hexdump main"
                        ]
            },
            {
                "name": "shorten functions",
                "enabled": True,
#                "enabled_commands" : "0-4,45",
                "commands" : [ None,
                "vdb add foldable foldme",
                "vdb add shorten shorten<shorten> shorten",
                "vdb shorten shorten",
                "set vdb-shorten-debug on",
                "set vdb-shorten-debug off",
                None,
                "vdb shorten abort",
                "vdb shorten vdb::abort",
                "vdb shorten vdb::__detail::abort",
                "vdb shorten vdb::__detail::abort(__detail::x0)",
                "vdb shorten std::map<int, int, std::less<int> >",
                "vdb shorten abc::def<>::ghi()",
                "vdb shorten abort()",
                "vdb shorten abort(val)",
                "vdb shorten abort(val, vol)",
                "vdb shorten abort<>()",
                "vdb shorten abort<abc>()",
                "vdb shorten abort<abc>(v0, v1)",
                "vdb shorten abort<abc<def::ghi> >()",
                "vdb shorten abort<abc, def<xxx>, ghi>()",
                "vdb shorten abort<abc, def<xxx> >(unsigned)",
                "vdb shorten abort<abc, def<xxx> >()",
                "vdb shorten xxx::str0<int>::str1<long>::fx::fy",
                "vdb shorten x0<a1<b1>::x>::f0",
                "vdb shorten x0<a1<b1>::x<bar>::u>::f0",
                "vdb shorten mx<true>::cde<abc<abg>::xyz>",
                "vdb shorten mx<true>::cde<abc<abg>::xyz>()",
                "vdb shorten mx<true>::cde<abc<abg>::xyz>(int, int)",
                "vdb shorten std::function<void(void)>()",
                "vdb shorten foldme<true>()",
                "vdb shorten dontfold<foldme<true> >()",
                "vdb shorten shorten<shorten>",
                "vdb shorten shorten<shorten<shorten> >",
                "vdb shorten std::unique_ptr<char [], (anonymous namespace)::free_as_in_malloc>",
                "vdb shorten rabbit<node, std::map<int, int, std::less<int>, std::allocator<std::pair<int const, int> > > >",
                "vdb shorten main(int, char const**)",
                "vdb shorten hole<node, std::map<int, int, std::less<int>, std::allocator<std::pair<int const, int> > > >(node*, std::map<int, int, std::less<int>, std::allocator<std::pair<int const, int> > >*, int)",
                "vdb shorten std::remove_reference<std::pair<int const, int>&>",
                "vdb shorten std::pair<int const, int>&&",
                "vdb shorten std::pair<int const, int>&",
                "vdb shorten std::remove_reference<std::pair<int const, int> const&>",
                "vdb shorten std::remove_reference<void (std::thread::*)()>",
                "vdb shorten std::less<std::_Sp_counted_base<(__gnu_cxx::_Lock_policy)2>*>",
                "vdb shorten std::remove_reference<std::ios_base::<unnamed enum> >",
                "vdb shorten s0<(end)1, void>",
                "vdb shorten xtree::str::<union>::_M_allocated_capacity",
                "vdb shorten xtree::str::<union>::_M_local_buf"


                    ],
                "expect" : "shorten_function.exp",
#                "output" : True
            }

        ]

run_tests( tests )
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
