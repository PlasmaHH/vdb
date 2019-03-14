#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from os import path,walk

import six

directory, file = path.split(__file__)
directory       = path.expanduser(directory)
directory       = path.abspath(directory)
sys.path.append(directory)

print("Loading vdb core")
import vdb

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
