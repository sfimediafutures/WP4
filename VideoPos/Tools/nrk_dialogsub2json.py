#!/bin/env python3

import re
import copy
import os.path
import json
from argparse import ArgumentParser
import random
from fuzzywuzzy import fuzz
from operator import itemgetter

DEBUG = False
# DEBUG = "dostangsystemet"

parser = ArgumentParser()
parser.add_argument("-d", "--dialog", dest="dialog", help="Dialog file", required=True)
parser.add_argument("-s", "--subtitle", dest="sub", help="Subtitle file", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)

parser.add_argument("-l", "--limit", dest="limit",
                    help="Percent match (higher = more false positives)",
                    default=65, required=False)

parser.add_argument("-c", "--castfile", dest="cast", help="Output cast file", required=False)
parser.add_argument("-u", "--casturl", dest="cast_url", help="base url for cast", default=None, required=False)

parser.add_argument("-a", "--analyze", action="store_true", dest="analyze", help="Only analyze",
                    default=False, required=False)

options = parser.parse_args()


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


manuscript = [l for l in open(options.dialog, "r").readlines() if l.strip()]
if os.path.splitext(options.sub)[1] in [".vtt", ".srt"]:
    subs =  load_srt(options.sub)
else:
    subs = json.load(open(options.sub, "r"))

class LineChecker:
    def __init__(self, manuscript, subtitles):
        self.script_idx = 0
        self.sub_idx = 0
        self.cast = []

        self.roles = {}
        self.role_lines = {}
        self.manuscript_ts = {}

        self.word_importance = {}

        def load_manuscript(manuscript):
            """We load the manuscript for each person"""

            manus = []
            last_who = None
            for idx in range(len(manuscript)):

                if manuscript[idx].startswith("(") or manuscript[idx].count(":") == 0:
                    who = "info"
                    text = manuscript[idx]
                else:
                    who, text = manuscript[idx].split(":", 1)
                    who = who.strip()
                text = self._cleanup(text.lower())

                if who not in self.roles:
                    self.roles[who] = []
                    self.role_lines[who] = []

                if who not in ["info", "scene"]:
                    self.role_lines[who].append({"text": text, "idx": idx})

                for x in sorted(text.split(" ")):
                    if not x:
                        continue
                    if x not in self.roles[who]:
                        self.roles[who].append(x)

                # If the *last* person to speak is the same, merge them
                if last_who == who:
                    l = manus[-1]["words"]
                    l.extend([x for x in sorted(text.split(" ")) if x])
                    l.sort()
                    manus[-1]["words"] = l
                    manus[-1]["text"] += " " + text.strip()
                else:
                    manus.append({"who": who.strip(), "words": [x for x in sorted(text.split(" ")) if x], "mintime": 10000000, "maxtime": 0, "text": text.strip()})
                last_who = who
            return manus

        self.manus = load_manuscript(manuscript)
        self.subs = subtitles

        if 0:
            for idx, sub in enumerate(self.subs):
                # If we have a sub with multiple people, we'll split it in two
                if sub["text"].find("<br>") > -1 or sub["text"].find("\n") > -1:
                    if sub["text"].find("<br>") > -1:
                        # HTML
                        items = sub["text"].split("<br>")
                    else:
                        items = sub["text"].split("\n")
                    sub["text"] = items[0].strip()
                    sub2 = copy.copy(sub)
                    sub2["text"] = items[1]

        for sub in self.subs:
            sub["words"] = [x for x in sorted(self._cleanup(sub["text"].lower()).split(" ")) if x]


        self._count()


    def _count(self):
        import copy
        what = copy.copy(self.manus)
        what.extend(self.subs)

        from operator import itemgetter
        words = {}
        max_reps = 0
        for item in what:
            for word in item["words"]:
                if not word in words:
                    words[word] = 1
                else:
                    words[word] += 1
                    max_reps = max(max_reps, words[word])

        # Max "points" is the number of words, as it will be divided by 1 occurrance
        # Normalize based on this - max points should be 1, so divide the "score" by the
        # maximum value

        # words = [(w, float(len(words))/words[w]) for w in words]
        self.word_importance = {w:(len(words) / float(words[w])) / float(len(words)) for w in words}


    def _simple_clean(self, s):
        s = re.sub(r'\</?\w+\>', ' ', s)
        # s = s.replace("<br>", " ", s)
        s = re.sub(r'\([^)]*\)', '', s)
        s = re.sub(r'  ', ' ', s)
        return s.strip()

    def _cleanup(self, s):
        s = re.sub(r'\</?\w+\>', ' ', s)
        # s = re.sub(r'[^\w\s]', ' ', s.lower()).strip()
        s = re.sub(r'[^\w\s]', ' ', s.strip())
        s = re.sub(r'  ', ' ', s)
        return s.strip()


    def _find_order(self, what, ignore_info=False):
        # Find order of something
        order = []
        last_who = None
        for w in what:
            if ignore_info and w["who"] in ["info", "scene"]:
                continue

            if w["who"] != last_who:
                order.append(w["who"])
            last_who = w["who"]

        return order

    def match_role(self, sub):
        """
        Look through role words, calculate the points and return it
        """

        points = {}
        lpoints = {}
        max_points = 0

        dbg_line = None
        for word in sub["words"]:
            max_points += self.word_importance[word]

        if DEBUG and DEBUG in sub["words"]:
                print(DEBUG, "max points:", max_points)

        for role in self.roles:
            points[role] = 0
            lpoints[role] = 0
            if role in ["info", "scene"]:
                continue

            for word in sub["words"]:
                if word in self.roles[role]:
                    points[role] += self.word_importance[word]

                if DEBUG:
                        print(role, word, points[role])

            # Also check for each line of this role
            for line, _idx in self.role_lines[role]:
                if line.find(self._cleanup(sub["text"]).lower()) > -1:
                    lpoints[role] = 1.1
                    self.manuscript_ts[idx] = sub["start"]

        # Normalize
        for role in points:
            points[role] /= max_points


        r = [(role, points[role]) for role in points if points[role] > 0]
        r2 = [(role, lpoints[role]) for role in lpoints if lpoints[role] > 0]
        r.extend(r2)
        ret = sorted(r, key=itemgetter(1), reverse=True)

        # ret = sorted([(role, points[role]) for role in points if points[role] > 0], key=itemgetter(1), reverse=True)
        # lret = sorted([(role, lpoints[role]) for role in lpoints if lpoints[role] > 0], key=itemgetter(1), reverse=True)
        print("ROLE HITS", ret[:4])
        return ret



    def match_sub(self, sub, mline, limit=0.8, dontremove=False):
        """
        How much of the sub is here?
        """
        if mline["who"] in ["info", "scene"]:
            return 0, {}

        if len(mline["words"]) == 0:
            return False, {"ratio": 0, "isPerfect": False, "ratio_m": 0}

        print("----\nChecking sub\ns:%s\nm:%s\n" % (" ".join(sub["words"]), " ".join(mline["words"])))
        hits = 0
        points = 0
        max_points = 0
        orig_words = copy.copy(mline["words"])

        subwords = copy.copy(sub["words"])  # copy - we're removing as we go along

        print([(w, self.word_importance[w]) for w in subwords] )

        remove = []
        for word in subwords:
            max_points += self.word_importance[word]

            max_ratio = 0
            for m in mline["words"]:
                max_ratio = max(max_ratio, fuzz.ratio(word, m))

            print("RATIO", word, max_ratio)
            if max_ratio >= 75:
            #if mline["words"].count(word) > 0:
                hits += len(word)
                points += self.word_importance[word]
                # remove.append(word)
                if max_ratio == 1:
                    mline["words"].remove(word)
                # We save the times too
                mline["mintime"] = min(mline["mintime"], sub["start"])
                mline["maxtime"] = max(mline["maxtime"], sub["end"])

        if 0:
            for r in remove:
                subwords.remove(r)

            for word in subwords:
                if not word:
                    continue

                for idx, mword in enumerate(mline["words"]):
                    if not mword:
                        continue

                    if word < mword[:len(word)]:
                        break
                    if word == mword:
                        hits += len(word)
                        mline["words"].remove(word)
                        break

                    # Partial?
                    continue
                    partial = False
                    for i in range(min(len(word), len(mword))):
                        if word[i] != mword[i]:
                            if i > 3:
                                partial = True
                            break
                        hits += 1

                        # Remove word if we're close?
                    if partial:
                        # Found a partial hit, go on
                        break

        total = len("".join(sub["words"]))
        ratio = points/max_points
        # ratio = float(hits) / total
        ratio_m = float(hits) / len("".join(orig_words))
        isPerfect = len(mline["words"]) == 0
        if 0 and not isPerfect:
            print("Not perfect\ns:%s\nm:%s\n" % (sub["words"], orig_words))
            print("Left:", mline["words"])

        if ratio < limit or (dontremove and len(orig_words) < 3) :
            # Undelete
            #print("***UNDELETE***", ratio, limit)
            mline["words"] = orig_words
        print("R", ratio, "H", hits, "of", total, 100. * hits / total, "points:", points, "max points", max_points)
        return ratio > limit, {"ratio": ratio, "isPerfect": isPerfect, "ratio_m": ratio_m}

    def match(self, limit=0.65):
        midx = 0
        found = 0
        guesses = 0
        good_guesses = 0
        last_end_time = 0

        for subidx, sub in enumerate(self.subs):
            print("\n**************************** %d - %d\nCheck sub" % (subidx, midx), sub["text"])

            hits = self.match_role(sub)

            sub["who"] = "Unknown"
            if len(hits) > 0:
                if len(hits) == 1 or hits[0][1] > 0.4:
                    sub["who"] = hits[0][0]
                elif hits[0][1] / hits[1][1] > 2:
                    sub["who"] = hits[0][0]
                sub["who_alt"] = hits
                if hits[0][1] > 0.9:
                    found += 1
                elif hits[0][1] > 0.7:
                    good_guesses += 1
                else:
                    guesses += 1

            continue

            i = 0
            while True:
                if midx + i >= len(self.manus):
                    break

                hit, info = self.match_sub(sub, self.manus[midx + i], limit=limit, dontremove=i>1)
                if not hit:
                    if i == 0:
                        hit, info = self.match_sub(sub, self.manus[midx - 1], limit=limit, dontremove=i>1)
                        if hit:
                            print("  **** Hit on last", hit, info)
                    i += 1
                    if i > 40:
                        print("  *** Gave up", sub)
                        sub["who"] = "Unknown"
                        break
                    continue

                # We got it!
                if i == 0:
                    sub["who"] = self.manus[midx]["who"]
                    print("  Found", sub["who"], "at index", midx, info)
                    found += 1
                    if info["ratio_m"] > limit:  #  or (len(sub["words"]) > 3 and info["ratio"] == 1.0):
                        midx += 1
                else:
                    sub["who"] = self.manus[midx + i]["who"]
                    print("  Guessed", sub["who"], "at index", midx, info)
                    
                    if len(sub["words"]) > 3 and info["ratio_m"] > 0.7:
                        sub["guesswho"] = "good"
                        print("      ----- good enough")
                        midx += 1 + i
                        good_guesses += 1
                    else:
                        guesses += 1
                        sub["guesswho"] = "pure"


                # We don't add "i" here yet, as we might be guessing
                break

        print("Mapped", found + good_guesses + guesses, "of", len(self.subs), "Certain:", found, "likely:", good_guesses, "guess:", guesses)


    def find_infos(self):

        for idx, line in enumerate(self.manus):

            if line["who"] not in ["scene", "info"]:
                continue

            # We try to find the timestamps of this - look for the sub before or after
            



            if len(line["words"]) > 0:
                if line["who"] not in ["info", "scene"]:
                    print("Something left", line)
                    if line["maxtime"] == 0:
                        print("   * Not touched")
                    start = self.manus[idx-1]["maxtime"]
                    end = self.manus[idx+1]["mintime"]
                    print("   - should be within", start, end)
                    start = max(start, end) - 1.6
                    print(line.keys())
                    # Add it after the lowest one, that will have to do

                    self.subs.append({
                        "start": start + 0.01,
                        "end": start + 1.5,
                        "text": line["text"]
                    })

    def save(self, filename):
        for sub in checker.subs:
            if "words" in sub:
                del sub["words"]

        open(filename, "w").write(json.dumps(checker.subs, indent=" "))

    def _cleanup_who(self, who):
        """
        We don't want cast members to have spaces and paranthesis and stuff
        """
        if who.find("(") > -1:
            who = who[:who.find("(")]
        who = who.replace(" ", "_")
        if who[-1] == "_":
            return who[:-1]
        return who


    def save_cast(self, filename, cast_url):

        def autocolor(idx):
            return "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) + "A6"

        characters = []
        for sub in subs:
            who = self._cleanup_who(sub["who"])
            if who not in characters:
                characters.append(who)

        cast = {}
        for idx, c in enumerate(characters):
            # print(c, characters[c])
            cast[c] = {
                "name": characters[idx],
                "color": autocolor(idx),
                "src": cast_url + c.replace(" ", "_") + ".png"
            }

        open(filename, "w").write(json.dumps(cast, indent=" "))

    def analyze(self):
        suborder = self._find_order(self.subs)
        manorder = self._find_order(self.manus)

        sidx = 0
        midx = 0

        def resync(midx, sidx):

            def remove_dupes(l):
                r = []
                for x in l:
                    if not r:
                        r.append(x)
                    if x != r[-1]:
                        r.append(x)
                return r

            # We get the pattern first
            mpattern = [x["who"] for x in self.manus[midx:midx+10] if x["who"] not in ["info", "scene"]]
            spattern = [x["who"] for x in self.subs[sidx:sidx+20] if x["who"] not in ["info", "scene"]]

            print("RESYNC", midx, sidx)
            print("m", mpattern)
            print("r", remove_dupes(spattern))
            print("s", spattern)

            # Is this a missing sub or manuscript line (do we match the pattern?)
            for i in range(3):
                if mpattern[i:i+3] == remove_dupes(spattern)[0:3]:
                    print("RESYNC1", i)
                    return midx + i, sidx

                if remove_dupes(spattern)[i:i+3] == mpattern[0:3]:
                    print("RESYNC2", i, "to", remove_dupes(spattern)[i])
                    for i2 in range(10):
                        if spattern[i + i2] == mpattern[0]:
                            print("Guessing", i + i2)
                            return midx, sidx + i + i2
                    # Now we have a slight issue, as spattern has been modified - find out where we are
                    #return midx, sidx + i
                    break

            print("Resync failed")
            print(self.manus[midx])
            print(self.subs[sidx])
            raise SystemExit()
            return midx, sidx

        last = None
        last_time = 0
        while True:
            if midx >= len(self.manus) or sidx >= len(self.subs):
                break

            if self.manus[midx]["who"] in ["info", "scene"]:

                print("GOT", self.manus[midx]["who"], "between", self.manus[midx-1]["who"], "and", self.manus[midx+1]["who"])
                midx += 1

                continue
                midx += 1
            last = self.manus[midx]["who"]
            continue


            # Try to align
            if self.manus[midx]["who"] == self.subs[sidx]["who"]:
                midx += 1
                sidx += 1
                continue
            else:
                print("Not equal '%s', '%s'" % (self.manus[midx]["who"], self.subs[sidx]["who"]))

            # Out of sync
            midx, sidx = resync(midx, sidx)
            continue

            # We're not correct, try various permutations?
            permutations = [(1,0), (0,1), (2,0), (0,2), (2,1), (1,2)]
            found = False
            for m, s in permutations:
                try:
                    if manorder[midx + m] == suborder[sidx + s]:
                        found = True
                        print("Found", m, s, midx+m, sidx+s)
                        midx += m
                        sidx += s
                        break
                except:
                    print("Exception - went beyond end")
                    break
            if found:
                continue

            print("Failed", self.manus[midx])
            print("man:", manorder[midx:midx+4])
            print("sub:", suborder[sidx:sidx+4])
            midx += 1

checker = LineChecker(manuscript, subs)

print(len(manuscript), "lines of manuscript", len(subs), "subs")

if not options.analyze:
    checker.match(limit=float(options.limit)/100)

    if options.cast:
        if not options.cast_url:
            raise SystemExit("Can't save cast without casturl")
        checker.save_cast(options.cast, options.cast_url)
else:
    checker.analyze()


# checker.find_infos()

print("Manuscript timestamps", len(checker.manuscript_ts.keys()))

checker.save(options.output)

