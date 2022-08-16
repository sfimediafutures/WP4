#!/usr/bin/env python3

"""
Convert voice detection json to CSV suitable for w2vtransthingy
"""

import json
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument("-s", "--source", dest="src", help="Source file", required=True)

parser.add_argument("-d", "--destination", dest="dst",
                    help="Destination file",
                    default=None)

parser.add_argument("-a", "--audiofile", dest="audiofile",
                    help="Audio file that is to be transcribed (the whole thing)",
                    required=True)

options = parser.parse_args()

with open(options.src, "r") as f:
    source = json.load(f)

if options.dst:
    destination = options.dst
else:
    destination = options.src.replace(".json", ".csv")

with open(destination, "w") as f:
    f.write("speaker,start,end,duration,audio_path\n")
    for item in source:
        if "who" not in item:
            print("Missing 'WHO'", item)
            item["who"] = "unknown"
        f.write("%s,%f,%f,%f,%s\n" % (item["who"],
                                    item["start"],
                                    item["end"],
                                    item["end"] - item["start"],
                                    options.audiofile))

print("OK")