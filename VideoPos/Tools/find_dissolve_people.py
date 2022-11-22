#!/usr/bin/env python3
import json
import os

def detectPeople(jsonfile):
    with open(jsonfile, "r") as f:
        data = json.load(f)

    # People
    people = []
    for item in data:
        if item["who"] and item["who"] not in people:
            people.append(item["who"])

    # Find mentions of people
    mentions = []
    for item in data:
        for person in people:
            if "text" in item and item["text"]:
                # full name
                if item["text"].lower().count(person.lower()) > 0:
                    mentions.append((item, person, person))
                    continue

                # first and last name
                if item["text"].lower().count(person.lower().split(" ")[0]) > 0:
                    mentions.append((item, person, person.split(" ")[0]))

                elif item["text"].lower().count(person.lower().split(" ")[-1]) > 0:
                    mentions.append((item, person, person.split(" ")[-1]))
                    continue
    return mentions

def mentions_to_info(mentions):
    """
    Convert mentions to positional info messages
    """
    infos = []
    for sub, target, nick in mentions:

        # Calculate time roughly - we take the time the sub is active, divide
        # on number of chars and figure out when it starts(ish)
        d = (sub["end"] - sub["start"]) / float(len(sub["text"]))
        start = sub["start"] + (d * sub["text"].lower().find(nick.lower()))
        print("STARTPOS", sub["text"].lower().find(target.lower()), sub["text"], )
        print("    ", sub["start"], "->", start)
        m = {
            "type": "infopos",
            "text": target,
            "start": start,
            "end": sub["end"],
            "speaker": sub["who"],
            "pos": [50, 50]
        }
        infos.append(m)

    return infos


if __name__ == "__main__":

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-s", "--source", dest="src", help="Source sub file", required=True)

    parser.add_argument("-d", "--destination", dest="dst",
                        help="Destination file (might already exist for merge)", required=True)

    options = parser.parse_args()

    if not os.path.exists(options.src):
        raise SystemExit("Missing source file '%s'" % options.src)

    mentions = detectPeople(options.src)
    info = mentions_to_info(mentions)

    if os.path.exists(options.dst):
        # Create backup
        BAKFILE = options.dst + ".BAK"
        for i in range(100):
            BAKFILE = options.dst + ".BAK%d" % i
            if not os.path.exists(BAKFILE):
                break

        print("Merging")
        with open(options.dst, "r") as f:
            originfo = json.load(f)
            originfo.extend(info)
            info = originfo

        os.rename(options.dst, BAKFILE)

    with open(options.dst, "w") as f:
        json.dump(info, f, indent=" ")

