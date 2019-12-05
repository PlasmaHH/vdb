#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("Loading vdb core")

try:
    # in case the user has installed via setup.py 
    # nothing more than an import vdb is necsesary
    import vdb
except ModuleNotFoundError:
    # otherwise we add the vdb dir to the python path
    import sys
    from os import path,walk
    directory, file = path.split(__file__)
    directory       = path.expanduser(directory)
    directory       = path.abspath(directory)
    sys.path.append(directory)
    sys.path.append(path.join(directory, "vdb"))

    import vdb

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
