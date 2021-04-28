#!/bin/env python3

import subprocess
import json
import sys
import os.path

FFPROBE="ffprobe -v error -skip_frame nokey -show_entries frame=pkt_pts_time -select_streams v -of csv=p=0 "

def analyze(filename):
    index = {}
    cmd = FFPROBE + filename
    res = subprocess.getoutput(cmd)

    index["iframes"] = [float(x) for x in res.split("\n")]

    target = os.path.splitext(filename)[0] + ".idx"

    with open(target, "w") as f:
        f.write(json.dumps(index))

    print("Saved to", len(index["iframes"]), "timecodes to",  target)
    return index
 

analyze(sys.argv[1])

