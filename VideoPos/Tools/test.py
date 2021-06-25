#!/bin/env python3

import re
import copy
import json
from argparse import ArgumentParser
import random
from fuzzywuzzy import fuzz


parser = ArgumentParser()
parser.add_argument("-d", "--dialog", dest="dialog", help="Dialog file", required=True)
parser.add_argument("-s", "--subtitle", dest="sub", help="Subtitle file", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)
parser.add_argument("-c", "--castfile", dest="cast", help="Output cast file", required=False)
parser.add_argument("-l", "--limit", dest="limit", help="Percent match (higher = more false positives)", default=65, required=False)
parser.add_argument("-u", "--casturl", dest="cast_url", help="base url for cast", default=None, required=False)
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
subs =  load_srt(options.sub)


class LineChecker:
    def __init__(self, manuscript, subtitles):
        self.script_idx = 0
        self.sub_idx = 0
        self.cast = []

        self.word_importance = {}

        def load_manuscript(manuscript):
            """We load the manuscript and sort the words"""
            manus = []
            last_who = None
            for idx in range(len(manuscript)):

                try:
                    if manuscript[idx].startswith("(") or manuscript[idx].count(":") == 0:
                        who = "info"
                        text = manuscript[idx]
                    else:
                        who, text = manuscript[idx].split(":", 1)
                except:
                    print("Bad line %d: %s" % (idx, manuscript[idx]))
                    raise SystemExit()

                text = self._cleanup(text.lower())
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
        return s

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
        for subidx, sub in enumerate(self.subs):
            print("\n**************************** %d - %d\nCheck sub" % (subidx, midx), sub["text"])
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
            if len(line["words"]) > 0:
                if line["who"] not in ["info", "scene"]:
                    print("Something left", line)
                    if line["maxtime"] == 0:
                        print("   * Not touched")
                    start = self.manus[idx-1]["maxtime"]
                    if idx == len(self.manus) - 1:
                        end = start + 10
                    else:
                        end = self.manus[idx+1]["mintime"]
                    print("   - should be within", start, end)
                    start = max(start, end) - 1.6
                    print(line.keys())
                    # Add it after the lowest one, that will have to do

                    self.subs.append({
                        "start": start + 0.01,
                        "end": start + 1.5,
                        "text": line["text"],
                    })

    def save(self, filename):
        for sub in checker.subs:
            if "words" in sub:
                del sub["words"]

        open(filename, "w").write(json.dumps(checker.subs, indent=" "))

    def save_cast(self, filename, cast_url):

        def autocolor(idx):
            return "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) + "A6"

        characters = []
        for sub in subs:
            if sub["who"] not in characters:
                characters.append(sub["who"])            

        cast = {}
        for idx, c in enumerate(characters):
            # print(c, characters[c])
            cast[c] = {
                "name": characters[idx],
                "color": autocolor(idx),
                "src": cast_url + c.replace(" ", "_") + ".png"
            }

        open(filename, "w").write(json.dumps(cast, indent=" "))



checker = LineChecker(manuscript, subs)

print(len(manuscript), "lines of manuscript", len(subs), "subs")

for i in range(10):
    print(i)
    print("M:", checker.manus[i]["words"])
    print("S:", checker.subs[i]["words"])


checker.match(limit=float(options.limit)/100)

if options.cast:
    if not options.cast_url:
        raise SystemExit("Can't save cast without casturl")
    checker.save_cast(options.cast, options.cast_url)

print("Finding infos")
checker.find_infos()

checker.save(options.output)

