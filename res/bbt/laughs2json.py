import re
import sys
import json

items = []

baseurl = "/sfi/res/emotions/"
cutoff = 2

with open(sys.argv[1], "rb")as f:
    for line in f.readlines():
        line = line.decode("utf-8").replace("'", '"')
        try:
            l = json.loads(line)
        except Exception as e:
            print("Bad line", line)
            print(e)
            raise e
        startts = l["start"]
        endts = l["end"]
        if endts - startts > cutoff:
            emotion = "laugh_hard"
        else:
            emotion = "laugh"

        item = {
            "type": "emotion",
            "emotion": emotion,
            "start": startts,
            "end": endts,
            "url": baseurl + emotion + ".png"
        }
        items.append(item)

print(json.dumps(items, indent=4))



