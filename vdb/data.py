#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.config
import vdb.color
import vdb.track
import vdb.command

import gdb

import re
import traceback


def do_histogram( ):
    td = vdb.track.tracking_data

# take this sorted version for indices when selecting 
#    for tk in sorted(trackings.keys()):
#        for tracking in trackings[tk]:
#            datakeys.append( tracking.expression )

    buckets = {}
    all_numeric = True
    for ts in sorted(td.keys()):
        tdata = td[ts]
        for _,v in tdata.items():
            try:
                v = int(v)
            except:
                try:
                    v = float(v)
                except:
                    all_numeric = False

            num=buckets.get(v,0)
            num += 1
            buckets[v] = num
    
#    print("all_numeric = '%s'" % all_numeric )
#    print("buckets = '%s'" % buckets )
    for b,n in sorted(buckets.items()):
        print("%s : %s" % (b,n) )


class cmd_data (vdb.command.command):
    """Take data and transform it into more useful views"""

    def __init__ (self):
        super (cmd_data, self).__init__ ("data", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv ):
        try:
            if( len(argv) > 0 ):
                if( argv[0] == "histogram" ):
                    do_histogram()

            else:
                raise Exception("data got %s arguments, expecting 1 or more" % len(argv) )



        except:
            traceback.print_exc()
            raise
            pass

cmd_data()




# vim: tabstop=4 shiftwidth=4 expandtab ft=python
