import sys
import re
import json
import string

encoding = "utf-8"
who = "info"
items = []

def time2sec(t):
    h, m, s, ms = t.split(":")
    ts = int(h) * 3600 + int(m) * 60 + int(s) + (int(ms)/1000.)
    return ts

def load_file(filename):
    with open(filename, "rb") as f:

        start = end = None
        text = ""

        for line in f.readlines():
            line = line.decode(encoding).strip()
            if line.startswith("- "):
                items.append({"start": time2sec(start) ,"end": time2sec(end), "text": line[2::], "who": who})
                text = ""
                continue

            if line.strip() == "":
                # End of comment
                if text and start and end:
                    items.append({"start": time2sec(start) ,"end": time2sec(end), "text": text, "who": who})
                start = end = None
                text = ""
                continue
            if re.match("^\d+$", line):
                # Just the index, we don't care
                continue

            m = re.match("(\d+:\d+:\d+:\d+) +(\d+:\d+:\d+:\d+)", line.replace(".", ","))
            if m:
                start, end = m.groups()
                continue

            if text:
                text += "<br>"
            text += line

    return items


load_file(sys.argv[1])
print(json.dumps(items, indent=" "))