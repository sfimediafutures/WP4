#!/bin/env python3

import re
import copy
import os.path
import json
from argparse import ArgumentParser
import random
from fuzzywuzzy import fuzz
from operator import itemgetter

"""
This is a parser for a very simple format (Exit2), with timestamp (sec accuracy),
the role name and the dialogs
"""
parser = ArgumentParser()
parser.add_argument("-d", "--dialog", dest="dialog", help="Dialog file", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)

parser.add_argument("-c", "--castfile", dest="cast", help="Output cast file", required=False)
parser.add_argument("-u", "--casturl", dest="cast_url", help="base url for cast", default=None, required=False)

options = parser.parse_args()


dst = open("/tmp/test.txt", "w")

def time2sec(t):
    m, s = t.split(":")
    ts = int(m) * 60 + int(s)
    return ts

subs = []

infos = ["PLAKAT", "SUPER", "SKJERM"]

lines = open(options.dialog, "r").readlines()
text = ""
who = ts = None
for line in lines:
    line = line.strip()
    if not line:
        if text and who:
            print(ts, who, text)

            dst.write("%s: %s\n\n" % (who, text))

            subs.append({
                "who": who,
                "start": ts,
                "end": ts + 10,
                "text": text
            })

        text = ""
        who = ts = None
        continue


    m = re.match("(\d\d:\d\d)\W+(\w.*)", line)
    if m:
        ts, who = m.groups()
        if who.find("(") > -1:
            who = who[:who.find("(")]
        for i in infos:
            if who.find(i) > -1:
                who = "INFO"
        ts = time2sec(ts)
        # print("Time", ts, who)
    else:
        # This is the text
        text += line + " "

# Save the output in a format we can use easily?
