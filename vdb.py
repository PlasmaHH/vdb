#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("Loading vdb core")

try:
    import vdb
except ModuleNotFoundError:
    import sys
    from os import path,walk
    directory, file = path.split(__file__)
    directory       = path.expanduser(directory)
    directory       = path.abspath(directory)
    sys.path.append(directory)
    sys.path.append(path.join(directory, "vdb"))

    import vdb

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
