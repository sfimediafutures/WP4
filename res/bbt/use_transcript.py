import sys
import re
import json
from fuzzywuzzy import fuzz
import string


DEBUG = True

items = []

def time2sec(t):
    ms = t.split(",")[1]
    t = t[:-len(ms) - 1]
    h, m, s = t.split(":")
    ts = int(h) * 3600 + int(m) * 60 + int(s) + (int(ms)/1000.)
    return ts

def load_srt(filename):
    with open(filename, "rb") as f:

        data = f.read()
        f.seek(0)

        start = end = None
        text = ""

        for line in f.readlines():
            line = line.decode("latin-1").strip()
            if line.startswith("- "):
                items.append({"start": time2sec(start) ,"end": time2sec(end), "text": line[2::]})
                text = None
                continue

            if line.strip() == "":
                # End of comment
                if text:
                    items.append({"start": time2sec(start) ,"end": time2sec(end), "text": text})
                start = end = None
                text = ""
                continue
            if re.match("^\d+$", line):
                # Just the index, we don't care
                continue

            m = re.match("(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", line)
            if m:
                start, end = m.groups()
                continue

            if text:
                text += "<br>"
            text += line

    return items


# Use json subs + transcript to build better subs

subfile = sys.argv[1]
transcript = sys.argv[2]
if len(sys.argv) > 3:
    outfile = sys.argv[3]
else:
    outfile = None

with open(sys.argv[1], "rb") as f:
    if sys.argv[1].endswith(".json"):
        subs = json.loads(f.read().decode("utf-8"))
    elif sys.argv[1].endswith(".srt"):
        subs = load_srt(sys.argv[1])
    else:
        raise SystemExit("Unknown subtitle file")


# Parse transcript
current_time = 0
hits = 0



with open(sys.argv[2], "rb") as f:

    def _simple_clean(s):
        s = re.sub(r'\</?\w+\>', ' ', s)
        # s = s.replace("<br>", " ", s)
        s = re.sub(r'\([^)]*\)', '', s)
        s = re.sub(r'  ', ' ', s)

        if s.find("<") > -1:
            print("FAILED", s)
        return s.strip()

    def _cleanup(s):
        s = re.sub(r'\</?\w+\>', ' ', s)
        s = re.sub(r'[^\w\s]', ' ', s.lower()).strip()
        s = re.sub(r'  ', ' ', s)
        return s

    def _check_strings(what, sub):
        _what = _cleanup(what)
        _sub = _cleanup(sub.replace("<br>", " ").strip().replace("  ", " "))

        if not _what or not _sub:
            return False, 0, 0

        ratio = 0
        # We need to cut the strings - see if we can find a common starting point
        # We typically assume that the shorter string is within the bigger
        newhit = False
        if len(_what) > len(_sub):
            for i in range(0, len(_what), 10):
                ratio = fuzz.ratio(_what[i:i+len(_sub)], _sub)
                if ratio > 80:
                    return True, ratio, abs(len(_what) - len(_sub))
        else:
            for i in range(0, len(_sub), 10):
                ratio = fuzz.ratio(_sub[i:i+len(_what)], _what)
                if ratio > 80:
                    return True, ratio, abs(len(_what) - len(_sub))
        return False, ratio, 0

    def _update_sub(sub, who):
        if DEBUG:
            print("-----> [%s]: %s" % (who, sub["text"]))
        who = who.lower()
        # if is more than one name, just use the first
        who = who.split(" ")[0]
        # We update this sub with the person - if it already has a person, add another
        if "who" not in sub:
            sub["who"] = who
        else:
            # Already have one - make a list if it isn't
            if isinstance(sub["who"], str):
                if sub["who"] == who:
                    return
                sub["who"] = [sub["who"], who]
            else:
                if sub["who"][-1] == who:
                    return
                sub["who"].append(who)

    last_idx = 0
    last_who = "unknown"
    for line in f.readlines():
        description = info = prev = None
        text = ""
        emotion = None
        orig_line = line.decode("utf-8").strip()
        line = _simple_clean(orig_line)  # Strips off some descriptions
        if len(line) < len(orig_line) - 10:
            print("Suspicious of cleaning '%s' -> '%s'" % (orig_line, line))
        found = False
        if not line.strip():
            if orig_line:
                m = re.search("\(([^\)]*)\)", orig_line)
                if m:
                    info = m.groups()[0]    
                    subs.append({"start": current_time + 0.1,"end": current_time + 4, "text": info, "who": "info"})
                    if DEBUG: print("INFO %s: %s" % (current_time, info))
                    info = None
                else:
                    print("NO INFO: '%s'" % orig_line)
            continue
        print("Line:", line)
        print("olne:", orig_line)

        m = re.match("(.*): (.*)", line)
        if m:
            found = True
            who, what = m.groups()
            print("WHO", who, "What:", what)
            m2 = re.search("\((.*)\)", who)
            if m2:
                person_desc = m2.groups()[0] 
                if who and who != "unknown":
                    print("Emotion?: ", who, person_desc)
                else:
                    print("Person emotion but no person?", person_desc)

            if who.lower() == "scene":
                if DEBUG: print("Scene description", current_time + 1, what)
                subs.append({"start": current_time + 1,"end": current_time + 4, "text": what, "who": "scene"})
                continue
        else:
            who = "unknown"

        m = re.search("(.*)\(([^\)]*)\)(:?)", orig_line)
        if m:
            found = True
            # if there is a ":" at the end, it's an emotion or description, ignore here
            pre, description, ignore = m.groups()
            if not ignore:
                print("DESC", description)
                if pre:
                    prev = _cleanup(pre).split(" ")[-1]
                else:
                    prev = None
                if 0:
                    if who and who != "unknown":
                        description = who + ": " + description
                if DEBUG: print("Description", current_time, description)
                # subs.append({"start": current_time + 0.1 ,"end": current_time + 4, "text": description, "who": "info"})
            else:
                description = None

        if not found and line:
            if DEBUG: print("INFO %s, (%s)" % (current_time, line))
            subs.append({"start": current_time + 0.1,"end": current_time + 4, "text": line, "who": "info"})
            # info = line
            # subs.append({"start": current_time + 1,"end": current_time + 4, "text": line, "who": "info"})
            continue

        # Try to determine the time of this bit based on subtitles
        hit = False
        if DEBUG: print("Looking for %s from index %d" % (what, last_idx))
        if DEBUG: print(last_idx, ": ", subs[last_idx]["text"])
        sub_index = 0
        for sub in subs[last_idx:]:
            idx = subs.index(sub)

            # We split subs into sentences and check them all
            newhit = False
            ratio = 0
            lendiff = 0
            # if DEBUG: print("- Sub is", sub["text"])
            for s in _simple_clean(sub["text"]).replace(",", ".").split("."):
                if s == "":
                    continue

                if DEBUG: print("Checking sub: '%s'" % s)
                h, ratio, lendiff = _check_strings(what[sub_index:], s)
                if DEBUG: print("  what: %s, s: %s, h: %s, %s, %d" % (what[sub_index:], s, h, ratio, lendiff))
                if h:
                    _update_sub(sub, who)
                    newhit = True
                    current_time = sub["end"]

                    # Guess the end of the match
                    last_word = s.split(" ")[-1]
                    sub_index = what.find(last_word, sub_index) + len(last_word)
                    # sub_index += len(s) + 1  # ,. spaces, that kind of thing
                    # break

                # Check if description fits in here
                if description:
                    s = _cleanup(sub["text"])
                    print("D:", description, "prev:", prev, "idx:", s.find(prev), s)
                    if prev:
                        if s.find(prev) > -1:
                            subs.append({"start": sub["end"] + 0.1 ,"end": sub["end"] + 4, "text": description, "who": "info"})
                            description = None
                    else:
                        subs.append({"start": sub["end"] + 0.1 ,"end": sub["end"] + 4, "text": description, "who": "info"})
                        description = None

            if newhit and lendiff < 3:
                hit = True
                if DEBUG: print("Completed index", idx)
                # Full hit, don't analyze this again
                last_idx = idx + 1
                # break
            if hit and not newhit:
                break
            if not newhit:
                # We search *at most* 10 ahead, then we abort
                if idx > last_idx + 10:
                    if DEBUG: print(" ** Gave up")
                    break
                # print("NOT A HIT %d: %s" % (idx, sub))
                continue  # Not a hit

            if DEBUG: print("  *** GOT IT", what, ratio, idx, sub["text"])
            hit = True
            hits += 1
            current_time = sub["end"]
            if lendiff < 3:
                last_idx = idx + 1
            else:
                last_idx = idx # in case a sub is multiple people 

        print("Checking stuff", hit, newhit)
        if description:
            print("D: AT END", description)
            subs.append({"start": current_time + 0.1 ,"end": current_time + 4, "text": description, "who": "info"})
        if info:
            subs.append({"start": current_time + 0.1,"end": current_time + 4, "text": line, "who": "info"})

        if not hit:
            print("<<< [%s] No hit :-(" % what, "likely", who)
        else:
            print(">>> [%s] Hit" % what, current_time)

    print(hits, "of", len(subs), "subtitles matched")

    # Go through all subs and add "unknown" as who for those that are empty
    # last_who = "unknown"
    for sub in subs:
        if "who" not in sub:
            # _update_sub(sub, last_who)
            _update_sub(sub, "unknown")
        # else:
        #    last_who = sub["who"]

        # We also check if there are any likely two-person items that have only one person
        # and add the second as "unknown"
        c = sub["text"].count("<br>-")
        if c > 0 and (isinstance(sub["who"], str) or len(sub["who"]) < c + 1):
            _update_sub(sub, "unknown")

if outfile:
    with open(outfile, "wb") as f:
        f.write(json.dumps(subs, indent=4).encode("utf-8"))
else:
    print(json.dumps(subs, indent=4))

