#!/usr/bin/env python3

import sys
import json
from operator import itemgetter


from sub_parser import SubParser

if len(sys.argv) < 3:
    raise SystemExit("Need source and target")


def balance(lines):
    """
    Ensure that the lines are of similar length
    """
    if not lines:
        return lines

    if len(lines) <= 1:
        return lines

    if len(lines) > 2:
        raise Exception("Must have at most two lines", len(lines))

    if lines[0][-1] == ".":
        return lines

    text = lines[0] + " " + lines[1]
    text = text.replace("  ", " ")

    mid_point = int(len(text) / 2.0)
    # Find the space before the mid point
    pos = text.rfind(" ", 0, mid_point)
    if pos > -1:
        lines[0] = trim(text[:pos])
        lines[1] = trim(text[pos:])
    return lines


def calculate_new_endts(item, position):
    txt = item["text"].replace("<br>", " ")
    time_pr_char = (item["end"] - item["start"]) / float(len(txt))
    return item["start"] + (position * time_pr_char)


def trim(s):
    # Remove additional spaces, also spaces in front of punctuation
    import re

    while True:
        m = re.search("(\s[\W\s])", s)
        if not m:
            break
        s = s[:m.span()[0]] + s[m.span()[0] + 1:]
    return s.strip()


def reformat(items):

    max_length = 42
    max_additional = 5  # If this is what we have left of a sub, let it go over max length.
    max_next_line = 10  # How far into the next line do we look for a "."

    new_subs = []

    # Need to have items sorted by start time
    items.sort(key=itemgetter("start"))

    for idx, item in enumerate(items):
        sstart = 0
        send = max_length

        if idx < len(items) - 1:
            next_item = items[idx + 1]

        else:
            next_item = None

        txt = trim(item["text"].replace("<br>", " ") + " ")
        # print(item["text"].replace("<br>", "\n") + "\n---")
        # If we've got a "." early in the next sub, merge them.
        if idx < len(items) - 1:
            i2 = next_item["text"].find(".", 0, max_next_line)

            if i2 > -1:
                txt += " " + next_item["text"][0:i2]
                next_item["text"] = next_item["text"][i2:]

        # print(item["text"].replace("<br>", "\n"))
        # split at
        lines = []
        while sstart < len(txt):
            split_at = txt.find(".", sstart, send) + 1
            if split_at <= 0:
                split_at = txt.rfind(",", sstart, send) + 1
            if split_at <= 0:
                split_at = txt.rfind(" ", sstart, send)
            if split_at <= 0:
                split_at = len(txt)

            if len(txt) - split_at < max_additional and txt[-1] not in [".", ",", "!", "?"]:
                split_at = len(txt)

            lines.append(txt[sstart:split_at])
            sstart = split_at + 1
            send = sstart + max_length

        if len(lines) > 2:
            pos = len(lines[0]) + len(lines[1]) + 1
            old_end = item["end"]
            item["end"] = calculate_new_endts(item, pos)

            # Is the next item soon?
            if next_item and next_item["start"] - old_end < 2.0:
                next_item["start"] = item["end"]
                next_item["text"] = trim("<br>".join(lines[2:])) + " " + next_item["text"]
            else:
                new_item = {"start": item["end"], "end": old_end, "text": trim("<br>".join(lines[2:]))}
                items.insert(idx + 1, new_item)
            lines = lines[:2]

        item["text"] = "<br>".join(balance(lines))
        # Fake
        item["who"] = "1"
        new_subs.append(item)

        # print("\n".join(balance(lines[:2])) + "\n")

    # Sanity
    for s in new_subs:
        if s["end"] < s["start"]:
            print("BAD SUB - Ends before start", s)

    return new_subs


parser = SubParser()
parser.load_srt(sys.argv[1])
items = parser.items

items = reformat(items)

target = sys.argv[2]
if target.endswith(".json"):
    with open(target, "w") as f:
        json.dump(items, f, indent=" ")
else:
    parser.write_vtt(target, items)
