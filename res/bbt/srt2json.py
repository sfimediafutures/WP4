import re
import sys
import json

items = []

def time2sec(t):
    ms = t.split(",")[1]
    t = t[:-len(ms) - 1]
    h, m, s = t.split(":")
    ts = int(h) * 3600 + int(m) * 60 + int(s) + (int(ms)/1000.)
    return ts

with open(sys.argv[1], "rb") as f:

    data = f.read()
    f.seek(0)

    start = end = None
    text = ""

    for line in f.readlines():
        line = line.decode("latin-1").strip()
        if line.strip() == "":
            # End of comment
            items.append({"start": time2sec(start) ,"end": time2sec(end), "text": text, "who": ""})
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

print(json.dumps(items, indent="  "))
