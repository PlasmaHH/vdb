#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vdb.shorten
import sys

vdb.shorten.add_foldable(
 [
	"feedconfig::condition_base",
	"dissected_message",
	"parser_base",
	"symbol_context",
	"intermediate_symbol",
	"buffered_write_device",
		] )

vdb.shorten.add_foldable("""

""")

#print("sys.path = '%s'" % sys.path )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
