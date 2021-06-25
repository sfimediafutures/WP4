#!/bin/env python3
"""Create iframes from a video to use for automated indexing and loading."""

import re
import os.path
import json
from argparse import ArgumentParser
import subprocess
from PIL import Image
import operator


def time2sec(t):
    ms = t.split(",")[1]
    t = t[:-len(ms) - 1]
    h, m, s = t.split(":")
    ts = int(h) * 3600 + int(m) * 60 + int(s) + (int(ms)/1000.)
    return ts

def load_srt(filename):
    items = []
    with open(filename, "rb") as f:

        data = f.read()
        f.seek(0)

        start = end = None
        text = ""

        for line in f.readlines():
            line = line.decode("utf-8").strip()
            if text and line.startswith("-"):
                # print("Continuation", line)
                items.append({"start": time2sec(start) + 0.01 ,"end": time2sec(end), "text": line[1::].strip()})
                # text = ""
                continue
            elif line.startswith("-"):
                line = line[1:]

            if line.strip() == "":
                # print("End of comment", text)
                # End of comment
                if text and start and end:
                    items.append({"start": time2sec(start) ,"end": time2sec(end), "text": text})
                start = end = None
                text = ""
                continue
            if re.match("^\d+$", line):
                # Just the index, we don't care
                continue

            m = re.match("(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", line.replace(".", ","))
            if m:
                start, end = m.groups()
                continue

            if text and line[-1] != "-":
                text += "<br>"
                text += line
            else:
                text = text[:-1] + line  # word has been divided

    return items


"""
Use a processed aux file and extract the faces from each image from the 
correct iframes.

If sub is given, also run the thing through clarifai and update the subtitle
file with the guessed person(s)
"""
parser = ArgumentParser()
parser.add_argument("--iframes", dest="iframes", help="Iframe list of files", required=True)
parser.add_argument("--aux", dest="aux", help="Aux file (AI detections)", required=True)
parser.add_argument("--sub", dest="sub", help="Sub file (json)", required=False)
parser.add_argument("--workflow", dest="workflow", help="Workflow (for AI analysis)", required=False)

parser.add_argument("-o", "--output", dest="output", help="Output directory for files", required=True)
parser.add_argument("-p", "--prefix", dest="prefix", help="Prefix files with this", default="", required=False)
parser.add_argument("-r", "--root", dest="root", help="Root for image files",
                    required=False, default="/var/www/html")

options = parser.parse_args()

if os.path.exists(options.output):
    print(SystemExit("WARNING: Output %s dir exists" % options.output))
    # raise SystemExit("Output %s dir exists" % options.output)
else:
    os.makedirs(options.output)

with open(options.iframes, "r") as f:
    iframes = json.load(f)["iframes"]

print("Loaded %d iframes" % len(iframes))

index = {}
for iframe in iframes:
    iframe["path"] = os.path.join(options.root, iframe["url"][1:])
    if not os.path.exists(iframe["path"]):
        raise SystemExit("Missing file '%s'" % f)
    index[iframe["ts"]] = iframe

# Read aux data
with open(options.aux, "r") as f:
    aux = json.load(f)

subs = []
if options.sub:
    if not os.path.exists(options.sub):
        raise SystemExit("Missing sub file %s" % options.sub)

    if options.sub.endswith(".json"):
        with open(options.sub, "r") as f:
            subs = json.load(f)
        print("Loaded %d subs" % len(subs))
    else:
        subs = load_srt(options.sub)
        for s in subs[:10]:
            print(s)

def get_subs(startts, endts):
    # The the subs for this time (if any)
    r = [s for s in subs if s["start"] <= endts and s["end"] >= startts]
    return r

def makebox(pos, width, height, size=[65, 65]):
    """
    Make a box based on a point in percent
    """

    return {"left": ((pos[0] * width / 100.) - size[0]) / width,
            "right": ((pos[0] * width / 100.) + size[0]) / width,
            "top": ((pos[1] * height / 100.) - size[1]) / height,
            "bottom": ((pos[1] * height / 100.) + size[1]) / height}

def crop(iframe, box=None, dst=None, padding=25, pos=None):
    """
    Padding is in pixels
    """
    im = Image.open(iframe["path"])
    width, height = im.size

    if not box:
        box = makebox(pos, width, height)

    c = im.crop(((max(0, box["left"]) * width) - padding,
                 (max(0, box["top"]) * height) - padding,
                 (min(100, box["right"]) * width) + padding,
                 (min(100, box["bottom"]) * height) + padding))
    if c.histogram()[0] > 10000000:
        # Black
        print(" *** Black")
        return None

    if dst:
        c.save(dst)

    return iframe, dst, box

left = 10
# We now look for faces in the detections - if there is just one "pos", it's
# likely a face but we don't have the bounding box, so just make one
for idx, data in enumerate(aux):
    print("Processing", idx, "of", len(aux))
    if not data["start"] in index:
        raise Exception("Missing index for", data)

    nr = 0
    iframe = index[data["start"]]
    sub = get_subs(data["start"], data["end"])

    files = []

    if options.workflow and not subs:
        print("  - skipping, no subs for time", data["start"], data["end"])
        continue

    if "alt" in data:
        # Multiple things
        for item in data["alt"]:
            if item["name"] == "face":
                dst = os.path.join(options.output, "%sf%04d-%02d.png" % (options.prefix, idx, nr))
                nr += 1
                # print("We should extract face at", iframe, item["box"])
                files.append(crop(iframe, item["box"], dst))

    elif "pos" in data:
        # print("Is likely a face at", iframe, data["pos"], person)
        dst = os.path.join(options.output, "%sf%04d-%02d.png" % (options.prefix, idx, 0))
        files.append(crop(iframe, pos=data["pos"], dst=dst))

    # if we have some files for this frame, *and* we have a subtitle file,
    # figure out who it can be and update the subs!
    if sub and files and options.workflow:

        import clarifai
        f = [i[1] for i in files]
        results = clarifai.analyze(f, workflow=options.workflow)

        for idx, res in enumerate(results):

            if "concepts" in res:
                print("WHO is", [(k, res["concepts"][k]) for k in res["concepts"]])
                who = sorted([(k, res["concepts"][k]) for k in res["concepts"]], key=operator.itemgetter(1),
                             reverse=True)
                print("WHO", who)
                print("file", files[idx])
                for s in sub:
                    s["who"] = who[0][0]
                    s["alt"] = who
                    s["file"] = files[idx][1]
                    s["pos"] = files[idx][2]

                    print("Updated sub", s)
            left -= 1
            if left <= 0:
                raise SystemExit("REACHED MAX")

        open("/tmp/test_sub.json", "w").write(json.dumps(subs, indent=" "))
