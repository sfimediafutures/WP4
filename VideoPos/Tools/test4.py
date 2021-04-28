#!/bin/env python3

import re
import copy
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

        self.roles = {}
        self.role_lines = {}
        self.manuscript_ts = {}

        self.word_importance = {}
        self.current_time = 0

        def load_manuscript(manuscript):
            """We load the manuscript for each person"""

            manus = []
            last_who = None
            for idx in range(len(manuscript)):

                if manuscript[idx].startswith("("):
                    who = "info"
                    text = manuscript[idx]
                else:
                    who, text = manuscript[idx].split(":", 1)
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
        what = []  # copy.copy(self.manus)
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


    def timestamp_keywords(self, limit=0.4):
        # Here we go through the subtitles and put a time on each keyword (start of sub)

        self.keywords = {w:[] for w in self.word_importance.keys()}

        for sub in self.subs:
            for word in sub["words"]:
                if self.word_importance[word] > limit:
                    self.keywords[word].append((sub["start"], sub["end"]))

        # for word in self.keywords:
        #     print(word, ":", self.keywords[word])

    def match_sub(self, line):
        """
        Try to match a line in the manuscript with words in subs
        - we do this by picking the most important word in the text,
        then we return the next time of that word. Remove the word from
        the time list afterwords
        """

        if line["who"] in ["info", "scene"]:
            return

        words = [(word, self.word_importance[word]) for word in line["words"] if word in self.word_importance]
        words = sorted(words, key=itemgetter(1), reverse=True)
        if len(words) == 0:
            print("No important words...")
            return



        # We find the next time that hasn't been taken yet
        all_times = []
        print("Keywords")
        times = []
        for word, score in words[:6]:
            if len(self.keywords[word]) == 0:
                continue

            print("  %s: %.2f" % (word, score), self.keywords[word][0])
            for start, end in self.keywords[word]:

                if start > self.current_time:
                    # if start - self.current_time > 90:
                    #    print("   ----- too large gap, didn't find this one", start - self.current_time)
                    #    break
                    all_times.append((start, end))
                    print("  - found time", start)
                    times.append(start)

        line["times"] = sorted(all_times, key=itemgetter(0))

        new_time = self.current_time
        for t in sorted(times):
            if t > self.current_time:
                if t - self.current_time > 90:
                    print("   ----- too large gap, didn't find this one", t - self.current_time)
                    return

                new_time = t
                break

        if new_time == self.current_time:
            print("  - No luck")
            return

        self.current_time = new_time
        print("   Guessed time", self.current_time)
        return


    def not_good_match_sub(self, line, limit=0.2, line_limit=0.1):
        """
        Get a line from the manuscript and try to match it to subs.
        All subs that match it decently will be returned
        """
        if len(line["words"]) == 0:
            return 0

        line["subs"] = []
        matches = []

        line_ratio = 0
        ratio = 0

        max_line_points = 0
        for word in line["words"]:
            max_line_points += self.word_importance[word]

        for sub in self.subs:
            # What's the possible maximum score of this subtitle=?
            max_points = 0
            points = 0
            for word in sub["words"]:
                max_points += self.word_importance[word]

                # Score it
                if word in line["words"]:
                    points += self.word_importance[word]

            # How well did this sub match?
            ratio = points / max_points
            line_ratio = points / max_line_points
            # print(" - %.2f: %.2f/%.2f" %(points, ratio, line_ratio), sub["text"])

            if line_ratio > line_limit and ratio > limit or (line_ratio + ratio) > 0.6:
                print("*** Matched %.2f: %.2f/%.2f" %(points, ratio, line_ratio), sub)
                line["subs"].append(sub)

                # If this is a very near match for the whole line, we assume we're done
                if line_ratio > 0.85:
                    break

        print("*** found %d subs" % len(line["subs"]))
        return len(line["subs"])

    def old_match_sub(self, sub, mline, limit=0.8, dontremove=False):
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
        for subidx, line in enumerate(self.manus):
            print("\n**************************** %d - %d [%s]\nCheck line" % (subidx, midx, line["who"]), line["text"])

            hits = self.match_sub(line)

            continue
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

        # Go for only "info", and "scene"
        default_duration = 5.0  # we make them last 5 seconds (to be adjusted later)
        for subidx, line in enumerate(self.manus):
            if line["who"] in ["info", "scene"]:
                if subidx == 0:
                    # first one, starts on zero
                    line["start"] = 0
                    line["end"] = line["start"] + default_duration
                else:
                    line["start"] = self.manus[subidx - 1]["end"]
                    if subidx < len(self.manus) + 1 and "start" in self.manus[subidx + 1]:
                        line["end"] = min(line["start"] + default_duration, self.manus[subidx + 1]["start"])
                    else:
                        line["end"] = line["start"] + default_duration

                print("\n********   DESC  ************* %d - [%s] %s: %s\nCheck line" % (subidx, line["who"], line["start"], line["text"]))


        print("Mapped", found + good_guesses + guesses, "of", len(self.subs), "Certain:", found, "likely:", good_guesses, "guess:", guesses)


    def find_infos(self):
        for idx, line in enumerate(self.manus):
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


checker.timestamp_keywords(0.05)

checker.match(limit=float(options.limit)/100)

if options.cast:
    if not options.cast_url:
        raise SystemExit("Can't save cast without casturl")
    checker.save_cast(options.cast, options.cast_url)

# checker.find_infos()

print("Manuscript timestamps", len(checker.manuscript_ts.keys()))

checker.save(options.output)

