#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Converts manus to dialoglist
#
# Format:
# number SCENE number
# decsription/info*
# ROLE
# dialog
#
# info
# ROLE
# dialog
# ROLE2
# diaog
# ...


import sys
import re

data = open(sys.argv[1], "rb").read().decode("utf-8")
target = sys.argv[2]

text = ""
last_line = scene = person = None

items = []


def add_item(scene=None, person=None, text=None):
    # print("*** add_item", scene, person, text)
    if not scene and not person and not text:
        return

    if scene:
        i = {"who": "scene", "text": text.strip()}
    elif person:
        if not text:
            print("*** PERSON BUT NO TEXT", person.strip())
        i = {"who": person.strip(), "text": text.strip()}
    else:
        i = {"who": "info", "text": text.strip()}

    print(i)
    items.append(i)

data = data.replace(" *", "\n").replace("\r", "")
for idx, line in enumerate(data.split("\n")):

    line = line.strip()
    if line.startswith("#"):
        continue

    print("  %04d '%s'" % (idx, line))
    if line == "":
        if last_line != "empty":
            add_item(scene, person, text)
            scene = person = None
            text = ""
        last_line = "empty"
        continue

    m = re.match("\d+ (\W*)(.*)\d+", line)
    if m:
        if last_line != "empty":
            add_item(scene, person, text)
            scene = person = None
            text = ""
        last_line = "scene"
        where, scene = m.groups()
        print("NEW SCENE", scene)
        add_item(scene, text=scene)
        scene = None

        continue

    m = re.match("^(.[A-ZÆØÅ][A-Z ÆØÅ]+).*", line)
    if m:
        if last_line != "empty":
            add_item(scene, person, text)
            scene = person = None
            text = ""

        last_line = "person"
        person = m.groups()[0].strip()
        continue

    last_line = "dialogue"
    text = " ".join([text, line])


with open(target, "wb") as f:

    for item in items:
        if item["who"] not in []:
            f.write(("%s: %s\n\n" % (item["who"], item["text"])).encode("utf-8"))
        else:
            f.write(("(%s)\n\n" % item["text"]).encode("utf-8"))
print(items)





