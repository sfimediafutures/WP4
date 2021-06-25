#!/bin/env python3
"""Create iframes from a video to use for automated indexing and loading."""
import copy
import re
import os.path
import json
from argparse import ArgumentParser
import subprocess
from PIL import Image
import operator

import clarifai
import tempfile


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



def get_subs(startts, endts):
    # The the subs for this time (if any)
    r = [s for s in subs if s["start"] <= endts and s["end"] >= startts]
    return r


# We go through subtitles, extract the image, run analysis on it.
# Then we make images of each of the faces, and send it to be marked


def extract_image(options, ts):

    tmpfile = os.path.join(options.tmp, "%f.png" % ts)
    if os.path.exists(tmpfile):
        return tmpfile

    ffmpeg="ffmpeg -loglevel quiet -y -ss %f -i %s -vframes 1 -q:v 2 %s" % (ts, options.video, tmpfile)
    import subprocess
    r = subprocess.call(ffmpeg.split(" "), stderr=None)

    # Add file for analysis
    return tmpfile


def extract_all_images(options, subs, idx):
    files = []

    # We extract iframes (scene shifts) inside of subtitles as well as subtitles
    for n, sub in enumerate(subs):
        shifts = [sub["start"]]
        # Are there any scene shifts inside this sub
        for i in idx:
            if i < sub["end"] and i > sub["start"]:
                shifts.append(i)

        if len(shifts) > 1:
            # Must split the sub (it's only for positions really)
            start = sub["start"]
            end = sub["end"]
            for x, shift in enumerate(shifts):
                s = copy.copy(sub)
                s["start"] = start
                if x < len(shifts) - 1:
                    s["end"] = shifts[x + 1]
                else:
                    s["end"] = end

                files.append({"sub": s,
                              "idx": n,
                              "img": extract_image(options, start + 0.015)})
                start = s["end"]
        else:
            files.append({"sub": sub,
                          "idx": n, 
                          "img": extract_image(options, min(sub["start"] + 0.033, sub["end"]))})

    return files


def crop(options, filename, box, dst=None, padding=25):
    """
    Padding is in pixels
    """

    if not dst:
        dst = tempfile.NamedTemporaryFile(dir=options.tmp, suffix=".png").name
    im = Image.open(filename)
    width, height = im.size

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

    return dst

def clean_up_name(name):
    name = name[:].lower()
    rmap = {" ": "_", "æ": "ae", "ø": "o", "å": "a"}
    for c in rmap:
        name = name.replace(c, rmap[c])
    return name


if __name__ == "__main__":

    """
    Use a processed aux file and extract the faces from each image from the 
    correct iframes.

    If sub is given, also run the thing through clarifai and update the subtitle
    file with the guessed person(s)
    """
    parser = ArgumentParser()
    parser.add_argument("-i", "--video", dest="video", help="Video file", required=True)
    parser.add_argument("--sub", dest="sub", help="Sub file (srt) or json (if already guessed who)", required=False)
    parser.add_argument("--aux", dest="aux", help="Aux json file with positions", required=False)
    parser.add_argument("--idx", dest="idx", help="Idx json file with iframes", required=True)
    parser.add_argument("--workflow", dest="workflow", help="Workflow (for AI analysis)", required=False)
    parser.add_argument("--tmp", dest="tmp", help="Temp dir", required=False, default="/tmp/mediafutures")

    parser.add_argument("-o", "--output", dest="output", help="Output subtitle.json", required=True)
    parser.add_argument("-a", "--auxoutput", dest="auxoutput", help="Output auxilary info (positions)", required=False)

    options = parser.parse_args()


    if not os.path.exists(options.tmp):
        os.makedirs(options.tmp)

    index = json.load(open(options.idx, "r"))["iframes"]

    subs = []
    if options.sub:
        print("Loading subs from", options.sub)
        if not os.path.exists(options.sub):
            raise SystemExit("Missing sub file %s" % options.sub)

        if options.sub.endswith(".json"):
            with open(options.sub, "r") as f:
                subs = json.load(f)
            print("Loaded %d subs" % len(subs))
        else:
            subs = load_srt(options.sub)

    # FOR TESTING
    # subs = subs[:10]
    # Extract images

    cache_file_video = "temp_video_%s.json" % (options.video)
    if os.path.exists(cache_file_video):
        files = json.loads(open(cache_file_video, "r").read())
    else:
        print("Analyzing %d subs" % len(subs))
        files = extract_all_images(options, subs, index)
        open(cache_file_video, "w").write(json.dumps(files, indent=" "))

    # We now do AI analysis of faces
    cache_file = "temp_%s.json" % (options.video)
    cache_file_face = "temp_face_%s.json" % (options.video)
    if os.path.exists(cache_file):
        a = json.loads(open(cache_file, "r").read())
    else:
        print("AI Finding positions")
        fl = [f["img"] for f in files]
        a = clarifai.bulk_analyze(fl, "faces")
        open(cache_file, "w").write(json.dumps(a, indent=" "))
        print("Written to", cache_file)

    # Put info together
    for idx, f in enumerate(files):
        if idx >= len(files) or idx >= len(a):
            break
        files[idx]["ai"] = a[idx]

    json.dump(files, open("temp_coll_%s.json" % options.video, "w"), indent=" ")

    # print("Files are now")
    # for f in files:
    #    print(f)

    # Extract the faces from each file
    stat_face = stat_noface = 0
    faces = []
    for f in files:
        if not "ai" in f:
            stat_noface += 1
            continue
        stat_face += 1
        for items in f["ai"]["items"]:
            if os.path.exists(cache_file_face):
                tf = None
            else:
                tf = crop(options, f["img"], items["box"])
            faces.append((tf, items))

    # Now we can process faces
    print("Found %d subs with faces, %d without" % (stat_face, stat_noface))
    # print("FACES", [f[0] for f in faces])

    # We now do bulk processing of the faces
    f = [i[0] for i in faces]
    if os.path.exists(cache_file_face):
        results = json.loads(open(cache_file_face, "r").read())
    else:
        print("AI Identifying people")
        results = clarifai.bulk_analyze(f, workflow=options.workflow)
        open(cache_file_face, "w").write(json.dumps(results, indent=" "))

    for idx, res in enumerate(results):

        if "concepts" in res:
            print("WHO %d is" % idx, [(k, res["concepts"][k]) for k in res["concepts"]])
            who = sorted([(k, res["concepts"][k]) for k in res["concepts"]], key=operator.itemgetter(1),
                         reverse=True)
            # print("WHO", who)
            faces[idx][1]["who"] = who

            if 0:
                sub = subs[idx]
                sub["who"] = who[0][0]
                sub["alt"] = who
                if idx < len(files):
                    sub["ai"] = files[idx]["ai"]

            if 0:
                print("file", files[idx])
                for s in sub:
                    s["who"] = who[0][0]
                    s["alt"] = who
                    s["file"] = files[idx][1]
                    s["pos"] = files[idx][2]

                    print("Updated sub", s)


    # print("AFTER")
    # for f in files:
    #    print(f)

    # Update subs
    if not options.sub.endswith(".json"):
        """
        We don't have much information from before, so just add stuff
        """
        subs = []
        for idx, f in enumerate(files):
            print("*** Checking", idx, f)
            sub = sub[f["idx"]]  # f["sub"]

            # Who is either a string or a list of names We select the most likely
            # candidate for *Each face* we can see (but no dupes)

            candidates = []
            alternatives = []
            if "items" in f["ai"]:
                for item in f["ai"]["items"]:
                    if "who" in item:
                        w = item["who"][0][0]
                        if w not in candidates:
                            candidates.append(w)
                        for w in item["who"]:
                            alternatives.append(w)
                if len(candidates) == 1:
                    sub["who"] = candidates[0]
                elif len(candidates) > 1:
                    sub["who"] = candidates
                if len(alternatives) > len(candidates):
                    sub["who_alt"] = alternatives

            # sub["ai"] = f["ai"]
            if "who" in f:
                sub["who"] = faces[idx]["who"]
            subs.append(sub)
    else:
        # We already had some info, possibly who is speaking.
        # If the speaker is there, we want to update the aux data
        # to focus on that person
        for idx, f in enumerate(files):
            sub = subs[f["idx"]] # subs[idx]  # f["sub"]
            if "who" in sub:
                # Clean up name
                speaker = clean_up_name(sub["who"])
                print("S:", idx, speaker, sub["text"])
                bestmatch = 0       
                # Make a list of all the persons, value, position for all faces
                # print("Already have who", sub["who"], "(%s)" % speaker)

                l = {}
                if "items" in f["ai"]:
                    for item in f["ai"]["items"]:
                        if "who" in item:
                            for person, value in item["who"]:
                                print("Checking", person, value, item["posX"])
                                print(l)
                                if person in l:
                                    print("Multi", person, value, l[person]["value"])
                                    if value < l[person]["value"]:
                                        continue
                                l[person] = {"value": value, "pos": (item["posX"], item["posY"])}
                                if clean_up_name(person) == speaker:  #  and "pos" not in sub:
                                    sub["pos"] = l[person]["pos"]
                                    print(" **** Found", idx, sub["start"], speaker, "pos", l[person]["pos"])

                # l = sorted(l, key=operator.itemgetter(1), reverse=True)

    # Save subs
    open(options.output, "w").write(json.dumps(subs, indent=" "))

    # We also make a bit of AUX data, having cast positions for each time
    if options.auxoutput:
        if not options.aux:
            print("Generating AUX data too")
            aux = []
            for f in files:
                sub = f["sub"]
                if "ai" not in f:
                    continue
                ai = f["ai"]
                for item in ai["items"]:
                    # print("ITEM", item)
                    if "who" in item:
                        entry = {
                            "type": "cast",
                            "alt": item["who"],
                            "pos": (item["posX"], item["posY"]),
                            "value": item["value"],
                            "size": item["size"],
                            "box": item["box"],
                            "start": sub["start"],
                            "end": sub["end"]
                        }
                        if len(item["who"]) > 0:
                            entry["who"] = item["who"][0][0]
                        else:
                            entry["who"] = "unknown"
                        aux.append(entry)
        elif 0:
            # We already have aux data, load and merge!
            aux = json.load(open(options.aux, "r"))

            # We must now go through it and look for which subs are within this
            # frame
            for idx, entry in enumerate(aux):
                people = []
                for s in get_subs(entry["start"], entry["end"]):
                    if "who" in s and "pos" in s:
                        people.append((s["who"], s["pos"], len(s["text"]), s["end"] - s["start"]))

                # We know who is speaking and where they are 
                if len(people) > 0:
                    # Sort by duration
                    use = sorted(people, key=operator.itemgetter(2), reverse=True)
                    print("%.2f -> %.2f:" % (entry["start"], entry["end"]), people)
                    print ("  pos", entry["pos"], use[0][1])
                    entry["pos"] = use[0][1]
                if not "pos" in entry:
                    entry["pos"] = (50, 50)

                if entry["start"] == 173.52:
                    print("ENTRY", entry)
                    print(get_subs(entry["start"], entry["end"]))
        else:
            # We use z-index style positions and just add these to the existing
            # positioning
            aux = json.load(open(options.aux, "r"))

            for i, f in enumerate(files):
                print("")
                print("-------------------")
                print("F", f)
                print("FACES", faces[i])
                if "pos" in f:
                    entry = {"start": start, "end": end, "pos": s["pos"], "people":[]}
                    for f in faces[i]:
                        pass
                    aux.append(entry)
    
        open(options.auxoutput, "w").write(json.dumps(aux, indent=" "))
