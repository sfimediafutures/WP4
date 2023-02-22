import json
import os

srcdir = "Episodes"
dst = "html/episodes.json"
episodes = []

for filename in os.listdir(srcdir):
    if filename.endswith("_subs.json"):
        continue

    if not filename.endswith(".json"):
        continue

    with open(os.path.join(srcdir, filename), "r") as f:
        episode = json.load(f)
        if "manifest" not in episode:
            episode["manifest"] = "https://seer2.itek.norut.no/ByteSize/Episodes/" + filename

        if "published" not in episode:
            created = os.stat(os.path.join(srcdir, filename.replace(".json", "_subs.json"))).st_ctime
            episode["published"] = created

        episodes.append(episode)


    # Sort by published time
    import operator
    episodes.sort(key=operator.itemgetter("published"))

    with open(dst, "w") as f:
        json.dump(episodes, f, indent=2)



