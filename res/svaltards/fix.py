import json

from operator import itemgetter

source = json.load(open("svaltards_data.json", "r"))

# First we don't want the subtitles here
items = [s for s in source if "subtitle" not in s and "start" in s]

def by_start(a, b):
    print("A", a, "B", b)
    return a["start"] - b["start"]

sorted(items, key=itemgetter("start"))

aux = []
for idx, item in enumerate(items):

    print("START", item["start"])

    if "content" in item:
        if "video" in item["content"]:
            item["content"]["video"] = "https://mcorp.no/examples/p3dok/" + item["content"]["video"]

        if "img" in item["content"]:
            item["content"]["img"] = "https://mcorp.no/examples/p3dok/" + item["content"]["img"]

    if idx < len(items) - 1:
        item["end"] = items[idx + 1]["start"]
    else:
        # Last item
        item["end"] = 100000

    print("  End", item["end"])
    aux.append(item)

with open("svaltards_aux.json", "w") as f:
    f.write(json.dumps(aux, indent=" "))
