#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("Loading vdb core")

not_found = False

try:
    # in case the user has installed via setup.py
    # nothing more than an import vdb is necsesary
    import vdb
except ModuleNotFoundError:
    not_found = True

# Don't do it in the except clause since it may throw an exception which then gets chained which is confusing sometimes
if( not_found ):
    # otherwise we add the vdb dir to the python path
    import sys
    from os import path
    directory, file = path.split(__file__)
    directory       = path.expanduser(directory)
    directory       = path.abspath(directory)
    sys.path.append(directory)

    import vdb

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
