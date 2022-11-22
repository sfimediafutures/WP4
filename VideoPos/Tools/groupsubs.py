import json
import sys

with open(sys.argv[1], "r") as f:
    source = json.load(f)


summarized = []
for item in source:
    if len(summarized) == 0 or item["who"] != summarized[-1]["who"]:
        summarized.append(item)
        continue

    # Same user still
    summarized[-1]["text"] += " " + item["text"]


with open(sys.argv[2], "w") as f:
    json.dump(summarized, f, indent=" ")


for s in summarized:
    print()
    print(s["who"])
    print(s["text"])