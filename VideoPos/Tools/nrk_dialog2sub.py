import re
import sys
import os
import random
import json


class NRKParser:

    info_chars = ["skilt", "supertext", "sign", "on-screen text"]
    scene_chars = ["scene"]

    def __init__(self, filename, offset_sec=0):
        """
        Offset_sec is the offset of the video (seems like they don't start on zero but on total content time?)
        """
        self._filename = filename
        self._offset_sec = offset_sec


    def parse(self):

        dialog = open("test_dialog.txt", "wb")
        def _string2time(_s):
            m = re.match("(\d\d):(\d\d):(\d\d):(\d\d)", _s)
            if m:
                h, m, s, ms = m.groups()
                return int(h) * 3600 + int(m) * 60 + int(s) + (float(ms)/1000.) - self._offset_sec
            return None

        def autocolor(idx):
            return "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) + "A6"

        subs = []
        characters = {}

        for line in open(self._filename, "r").readlines():
            line = line.strip()

            if not re.match("\d\d:", line):
                continue

            if len(line.split("\t")) < 6:

                print("Too short line", len(line.split("\t")))
                print("   ", line)
                continue

            aux = None
            startts, endts, role, character, norwegian, english = line.split("\t")[:6]

            start = _string2time(startts)
            end = _string2time(endts)
            if end and end < start:
                # Reversed timestamps
                e = end
                end = start
                start = e
            if not end:
                end = start + 5
            #    print("Open ended", line)

            # Clean up the character for any descriptions
            s = re.search("([^\(]*)(\(.*\))", character)
            if s:
                character = s.groups()[0].strip()
                aux = s.groups()[1]

            if character.lower() in self.info_chars:
                character = "info"
                if not role.lower().startswith("super"):
                    norwegian = role + ": " + norwegian
            if character.lower() in self.scene_chars:
                character = "scene"

            if character not in characters:
                characters[character] = []

            if role not in characters[character]:
                characters[character].append(role)

            # print(startts, endts, role, character, norwegian, english, subs)

            sub = {
                "start": start,
                "end": end,
                "who": character,
                "text": norwegian,
                "role": role
            }
            if aux:
                sub["aux"] = aux
            subs.append(sub)

            if character != "info":
                dialog.write(("%s: %s\n\n" % (character, norwegian)).encode("utf-8"))
            else:
                dialog.write(("(%s)\n\n" % (norwegian)).encode("utf-8"))

        print("Chars", characters.keys())
        cast = {}
        for idx, c in enumerate(characters):
            # print(c, characters[c])
            cast[c] = {
                "name": characters[c][0],
                "color": autocolor(idx),
                "src": "/sfi/res/Valkyrien/cast/" + c.replace(" ", "_") + ".png"
            }

        open("test_cast.json", "wb").write(json.dumps(cast, indent=" ").encode("utf-8"))
        open("test_subs_full.json", "wb").write(json.dumps(subs, indent=" ").encode("utf-8"))



if __name__ == "__main__":

    parser = NRKParser("../../res/Valkyrien/VALKYRIEN Dialoglister NO-ENG S01EP01-08.xlsx - EP01.tsv", 3600)
    parser.parse()




