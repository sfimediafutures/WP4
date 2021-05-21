#!/bin/env python3

import re
import copy
import os.path
import json
from argparse import ArgumentParser
import subprocess


"""
This is a parser for a very simple format (Exit2), with timestamp (sec accuracy),
the role name and the dialogs
"""
parser = ArgumentParser()
parser.add_argument("-i", "--input", dest="input", help="Video file to parse", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output directory", required=True)
parser.add_argument("-w", "--webroot", dest="webroot", help="URL of images on web", required=False, default="")

options = parser.parse_args()
if options.webroot and options.webroot[-1] != "/":
    options.webroot += "/"

iframes = []
iframes.append({
    "url": options.webroot + "img%03d.png" % 1,
    "ts": 0,
    "nr": 0
})

def extract(options):
    CMD = ["ffmpeg", "-i"]
    CMD.append(options.input)
    CMD.extend(["-filter_complex", "select='eq(pict_type,PICT_TYPE_I)',showinfo", "-vsync", "vfr", os.path.join(options.output, "img%03d.png")])

    res = subprocess.check_output(CMD, stderr=subprocess.STDOUT)
    return res.decode("utf-8").split("\n")

def parseLine(line):

    m = re.search("n:\W+(\d+) .*pts_time:(\d+\.\d+)", line)
    if m:
        idx, ts = m.groups()
        idx = int(idx)
        ts = float(ts)

        iframes.append({
            "url": options.webroot + "img%03d.png" % (idx + 1),
            "ts": ts,
            "nr": idx
        })

os.makedirs(options.output)

if 1:
    lines = extract(options)
else:
    lines = open("output.txt", "r").readlines()

for line in lines:
    parseLine(line)

dst = os.path.join(options.output, "metadata.json")
open(dst, "w").write(json.dumps({"iframes": iframes}, indent=" "))
