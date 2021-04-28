#!/bin/env python3

import json
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument("-i", "--idx", dest="idx", help="New index file", required=True)
parser.add_argument("-a", "--aux", dest="aux", help="Aux file", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)
options = parser.parse_args()

idx = json.load(open(options.idx, "r"))
aux = json.load(open(options.aux, "r"))

iframes = sorted(idx["iframes"])
animated = 0

def find_closest(t, maxdiff=1.0):
    best = 10000000000
    for ti in iframes:
        if abs(t - ti) < abs(t - best):
            best =  ti
        if ti > t:
            break
    if abs(best - t) > maxdiff:
        return t, False
    return best, True


for item in aux:

    t, found = find_closest(item["start"])
    if not found:
        animated += 1
        item["animated"] = True
    else:
        item["start"] = t
    item["end"], _ = find_closest(item["end"])

# We now go through and ensure that ends and starts are in line
for i, item in enumerate(aux):
    if i < len(aux) - 1:
        item["end"] = aux[i+1]["start"]


json.dump(aux, open(options.output, "w"), indent=" ")

print("Animated", animated, "of", len(aux))