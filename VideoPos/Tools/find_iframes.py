#!/bin/env python3
import re
import subprocess
import json
import sys
import os.path

FFPROBE="ffprobe -v error -skip_frame nokey -show_entries frame=pkt_pts_time -select_streams v -of csv=p=0 "

def analyze(filename, directory=None):
    index = {}
    cmd = FFPROBE + filename
    res = subprocess.getoutput(cmd)

    index["iframes"] = [float(x) for x in res.split("\n")]

    target = os.path.splitext(filename)[0] + ".idx"

    with open(target, "w") as f:
        f.write(json.dumps(index))

    print("Saved to", len(index["iframes"]), "timecodes to",  target)
    return index
 
def extract(filename, directory):
    index = {"images": []}
    EXTRACT="ffmpeg -i " + filename + \
        " -f image2 -vf \"select='eq(pict_type,PICT_TYPE_I)'\" -vsync vfr " + \
        directory + "i%03d.png"

    res = subprocess.getoutput(EXTRACT)
    # res = open("/tmp/testoutput", "r").read()
    print("Wrote images to", directory)
    print(res)
    # open("/tmp/testoutput", "w").write(res)

    i = 1
    def tosec(ts):
        main, ms = ts.split(".")
        hh, mm, ss = main.split(":")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + (int(ms) / 1000.)

    for line in res.split("\n"):
        m = re.search("frame=\W+(\d+) .*time=(\d\d:\d\d:\d\d\.\d+) ", line)
        if m:
            print(m.groups())
            frame, ts = m.groups()
            index["images"].append({"ts": tosec(ts), "img": os.path.join(directory, "i%03d.png" % int(frame))})
        i += 1

    target = os.path.splitext(filename)[0] + "_imgs.json"

    with open(target, "w") as f:
        f.write(json.dumps(index, indent=" "))

    print("Saved to", len(index["images"]), "timecodes to",  target)
    return index



if len(sys.argv) > 2:
    # os.makedirs(sys.argv[2])
    imgs = extract(sys.argv[1], sys.argv[2])

#    analyze(sys.argv[1], sys.argv[2])
else:
    analyze(sys.argv[1])


