import os
import requests
import json
import sys
import tempfile
import re
import time

from sub_parser import SubParser


class Lookup:
    def __init__(self, manifest):
        try:
            self.manifest = json.load(open(manifest, "r"))
        except Exception as e:
            print("Couldn't read manifest '%s'" % manifest)
            print(e)

        if "normalsubtitles" in self.manifest:
            suburl = self.manifest["normalsubtitles"][0]["src"]
        else:
            suburl = self.manifest["subtitles"][0]["src"]

        self.subs = self._load_subs(suburl)

        self.stopwords = self._load_stopwords("/home/njaal/svn/motioncorp/web/live/t2/stopwords_combined.txt")

        self.keywords = []

        self.lookup_ai(self.subs)

    def save(self, filename):
        with open(filename, "wb") as f:
            f.write(json.dumps(self.keywords, indent=" ").encode("utf-8"))

    def _load_stopwords(self, filename):
        words = open(filename, "rb").read().decode("latin-1")
        return words.split("\n")

    def _load_subs(self, suburl):

        r = requests.get(suburl)
        if r.status_code != 200:
            raise Exception("Failed to load subs, status code", r.status_code)

        if suburl.endswith(".json"):
            return json.loads(r.content)

        f, fn = tempfile.mkstemp()
        os.write(f, r.content)
        os.sync()

        return SubParser().load_srt(fn)

    def build_card(self, item):

        if item["type"] == "LOC":
            key  = "AIzaSyAFI-Pk-PzIfjPGqmNO6qGQw_m0Cr3NV3I";
            print("Might want to check Google Maps")
            ursl = "https://www.google.com/maps/embed/v1/place?key=%s&q=" % key + " ".join(item["keywords"])
            # url = "https://www.google.com/maps/search/?api=1&query=" + " ".join(item["keywords"])
            return url

        keywords = item["keywords"]

        url = "https://no.wikipedia.org/w/index.php?search=" + \
              " ".join(keywords) + "&title=Spesial%3AS%C3%B8k&go=G%C3%A5&ns0=1"

        r = requests.get(url)
        if r.status_code < 300:
            m = re.search('\<link rel="canonical" href="([^\"]+)"', r.text)
            if m:
                new_url = m.groups()[0]

                if new_url.find("search") > -1:
                    return None

                return new_url

            if r.text.find("<title>Søkeresultater") > -1:
                return None

            return url

    def check_cards(self):
        """
        Go through all detections and check for "cards"
        """

        self.cards = {}  # Find these somewhere else?

        # Go through all detections and see if we might have one from before
        # If not, check if we can create a new card

        for item in self.keywords:

            if item["type"] not in self.cards:
                self.cards[item["type"]] = []

            found = False
            for keyword in item["keywords"][0].split(" "):
                for card in self.cards[item["type"]]:
                    for ckw in card["keywords"][0].split(" "):
                        if keyword.startswith(ckw) or ckw.startswith(keyword):
                            found = card
                            break
                    if found:
                        break
                if found:
                    break

            if not found:
                print("Must create a card for", item["keywords"])
                card = {
                    "keywords": item["keywords"],
                    "type": item["type"]
                }
                url = self.build_card(item)
                if (url):
                    card["url"] = url
                self.cards[item["type"]].append(card)

            else:
                print("Recycle:", found)

    def lookup(self, subs):
        for sub in subs:
            for line in sub["text"].split("<br>"):
                # print("-", line)
                interesting = []
                for word in re.split("\W", line)[1:]:
                    if len(word) == 0:
                        continue
                    if word.isdigit():
                        continue
                    if word.lower() in self.stopwords:
                        continue
                    if word.startswith(word[0].upper()):
                        interesting.append(word)

                if len(interesting) > 0:
                    print(sub["start"], " ".join(interesting))

                    self.keywords.append({
                        "start": sub["start"],
                        "end": sub["end"],
                        "keywords": interesting
                        })

    def lookup_ai(self, subs):

        for sub in subs:
            t = sub["text"].replace("<br>", " ").replace("-", " ")
            if t.count(" ") < 6:
                continue  # Need some words for the AI to work

            interesting = self._sat(t)
            for entry in interesting:
                print("Interesting entry", entry)
                self.keywords.append({
                    "start": sub["start"],
                    "end": sub["end"],
                    "keywords": [entry["word"]],
                    "type": entry["entity_group"],
                    "score": entry["score"]
                    })

    def _sat(self, text):
        # url = "https://api-inference.huggingface.co/models/saattrupdan/nbailab-base-ner-scandi"
        url = "https://seer2.itek.norut.no/sat"

        args = {"inputs": text, "parameters": {"aggregation_strategy": "first"}}

        r = requests.post(url, json.dumps(args).encode("utf-8"))
        try:
            res = json.loads(r.text)
        except Exception as e:
            print("BAD REPLY", r.text)
            raise e

        if "error" in res:
            print("Error", res)
            if "estimated_time" in res:
                time.sleep(res["estimated_time"] + 1.0)
                return self._sat(text)
            raise Exception("Failed: " + r.text)

        # If we have multiple names close to each other, we regard them as one?
        r = []
        if not isinstance(res, list):
            res = [res]
        for i, entity in enumerate(res):
            if entity == {}:
                continue

            if i == 0:
                r.append(entity)
                continue  # Can't group one

            if entity["entity_group"] == "PER" and res[i - 1]["entity_group"] == "PER":
                if entity["start"] - res[i - 1]["end"] <= 1:
                    r[-1]["word"] += " " + entity["word"]
                    r[-1]["end"] = entity["end"]
                    continue
            r.append(entity)

        return r


class Test:
    def __init__(self, filename):
        self.keywords = json.loads(open(filename, "r").read())

    def build_card(self, item):

        if item["type"] == "LOC":
            print("Might want to check Google Maps")
            url = "https://www.google.com/maps/search/?api=1&query=" + " ".join(item["keywords"])
            return url

        keywords = item["keywords"]

        url = "https://no.wikipedia.org/w/index.php?search=" + \
              " ".join(keywords) + "&title=Spesial%3AS%C3%B8k&go=G%C3%A5&ns0=1"

        r = requests.get(url)
        if r.status_code < 300:
            m = re.search('\<link rel="canonical" href="([^\"]+)"', r.text)
            if m:
                new_url = m.groups()[0]

                if new_url.find("search") > -1:
                    return None

                return new_url

            if r.text.find("<title>Søkeresultater") > -1:
                return None

            return url

    def check_cards(self):
        """
        Go through all detections and check for "cards"
        """

        self.cards = {}  # Find these somewhere else?

        # Go through all detections and see if we might have one from before
        # If not, check if we can create a new card

        for item in self.keywords:

            if item["type"] not in self.cards:
                self.cards[item["type"]] = []

            found = False
            for keyword in item["keywords"][0].split(" "):
                for card in self.cards[item["type"]]:
                    for ckw in card["keywords"][0].split(" "):
                        if keyword.startswith(ckw) or ckw.startswith(keyword):
                            found = card
                            break
                    if found:
                        break
                if found:
                    break

            if not found:
                print("Must create a card for", item["keywords"])
                card = {
                    "keywords": item["keywords"],
                    "type": item["type"]
                }
                url = self.build_card(item)
                if (url):
                    card["url"] = url
                self.cards[item["type"]].append(card)
                item["url"] = card
            else:
                print("Recycle:", found)
                item["url"] = found

    def save(self, filename):
        with open(filename, "wb") as f:
            f.write(json.dumps(self.keywords, indent=" ").encode("utf-8"))


if __name__ == "__main__":
    if 0:
        l = Lookup(sys.argv[1])
        l.check_cards()
        l.save(sys.argv[2])
    else:
        l = Test(sys.argv[2])
        l.check_cards()
        l.save(sys.argv[2])
