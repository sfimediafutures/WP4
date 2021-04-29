import json

data = open("svaltards.json", "r").read()
print(data[0])
source = json.loads(data)

dst = []

for item in source:
    if "subtitle" in item:
        dst.append( {
            "start": item["start"],
            "end": item["end"],
            "text": item["subtitle"]["no"],
            "who": item["subtitle"]["who"]
        })
    else:
        dst.append(item)

d = open("svaltards_subs.json", "w")
d.write(json.dumps(dst, indent="  "))