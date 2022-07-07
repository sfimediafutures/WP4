import requests
import json
import re
import os
import subprocess
import time

"""
META: https://psapi.nrk.no/programs/PRHO04004903

Playlist:https://nrk-od-51.akamaized.net/world/23451/3/hls/prho04004903/playlist.m3u8?bw_low=262&bw_high=2399&bw_start=886&no_iframes&no_audio_only&no_subtitles






https://psapi.nrk.no/playback/metadata/program/PRHO04004903?eea-portability=true

"""


class NRKSucker():
    def resolve_urls(self, url_or_id):
        """
        Resolve NRK urls based on a url or an ID
        """

        if url_or_id.startswith("http"):
            r = re.match("https://.*/(.*)/avspiller", url_or_id)
            if r:
                id = r.groups()[0]
            else:
                raise Exception("Unknown URL, expect 'avspiller' URL")
        else:
            id = url_or_id

        res = {
            "id": id
        }

        # Fetch the info blob
        murl = "https://psapi.nrk.no/playback/metadata/program/%s?eea-portability=true" % id
        r = requests.get(murl)
        if r.status_code != 200:
            raise Exception("Failed to load metadata from '%s'" % murl)

        res["info"] = json.loads(r.text)

        if "playable" not in res["info"] or "resolve" not in res["info"]["playable"]:
            raise Exception("Bad info block from '%s'" % murl)

        murl = "https://psapi.nrk.no" + res["info"]["playable"]["resolve"]
        r = requests.get(murl)
        if r.status_code != 200:
            raise Exception("Failed to load manifest from '%s'" % murl)

        res["manifest"] = json.loads(r.text)

        # Now we find the core playlist URL
        purl = res["manifest"]["playable"]["assets"][0]["url"]
        r = requests.get(purl)
        if r.status_code != 200:
            raise Exception("Failed to get playlist from '%s'" % purl)

        spec = None  # We take the first valid line
        for line in r.text.split("\n"):
            if line.startswith("#"):
                continue
            spec = line
            break

        if not spec:
            raise Exception("Failed to find valid specification in core m3u8")

        # We now have the correct url for downloading
        res["m3u8"] = os.path.split(purl)[0] + "/" + spec

        # We need the subtitles too
        res["vtt"] = res["manifest"]["playable"]["subtitles"][0]["webVtt"]

        return res

    def extract_audio(self, info, target):

        if os.path.exists(target) and os.stat(target).st_size > 0:
            print("  Audio already present at '%s'" % target)
            return

        if "m3u8" not in info:
            print("No playlist in info", info)
            raise Exception("Missing HLS playlist for '%s'" % target)

        cmd = ["ffmpeg", "-y", "-i", info["m3u8"], "-vn", "-c:a", "copy", target]

        print("  Extracting audio to %s" % target)
        p = subprocess.run(cmd,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.STDOUT)

        if p.returncode != 0:
            raise Exception("Extraction failed '%s', code %s" % (cmd, p))

    def extract_vtt(self, info, target):

        if os.path.exists(target) and os.stat(target).st_size > 0:
            print("  Subtitle already present at '%s'" % target)
            return

        if "vtt" not in info:
            raise Exception("Missing VTT url for '%s'" % target)
        print("  Extracting subtitles to %s" % target)
        r = requests.get(info["vtt"])
        if r.status_code != 200:
            raise Exception("Failed to download vtt from '%s'" % info["vtt"])
        with open(target, "w") as f:
            f.write(r.text)

    def dump_at(self, id, target_dir):

        start_time = time.time()
        print("Processing", id)
        info = self.resolve_urls(id)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        target_audio = os.path.join(target_dir, "%s.m4a" % id)
        target_vtt = os.path.join(target_dir, "%s.vtt" % id)

        self.extract_audio(info, target_audio)
        self.extract_vtt(info, target_vtt)

        elapsed = time.time() - start_time
        print("  OK in ", NRKSucker.time_to_string(elapsed))

        info["audio"] = target_audio
        info["subtitles"] = target_vtt
        info["elapsed"] = elapsed
        return info

    @staticmethod
    def time_to_string(seconds):
        """
        Convert a number of minutes to days, hours, minutes, seconds
        """

        days = hours = minutes = secs = 0
        ret = ""

        if seconds == 0:
            return "0 seconds"

        secs = seconds % 60
        if secs:
            ret = "%d sec" % secs

        if seconds <= 60:
            return ret

        tmp = (seconds - secs) / 60
        minutes = tmp % 60

        if minutes > 0:
            ret = "%d min " % minutes + ret

        if tmp <= 60:
            return ret.strip()

        tmp = tmp / 60
        hours = tmp % 24
        if hours > 0:
            ret = "%d hours " % hours + ret

        if tmp <= 24:
            return ret.strip()

        days = tmp / 24

        return ("%d days " % days + ret).strip()

    def find_good_areas(self, subtitle):

        from VideoPos.Tools.sub_parser import SubParser
        p = SubParser()
        p.load_srt(subtitle)

        bad = 0
        playtime = 0
        for sub in p.items:
            # If sub is two lines and BOTH start with "-" it's two different
            # people and hence the timing is shit
            lines = sub["text"].split("<br>")
            if len(lines) > 1:
                if lines[0].strip().startswith("—") and \
                   lines[1].strip().startswith("—"):
                    # print("BAD SUB", sub)
                    bad += 1
                    continue

            playtime += sub["end"] - sub["start"]

        print("  -- %d subtitles, %d are bad" % (len(p.items), bad))
        print("  Playtime: %s" % NRKSucker.time_to_string(playtime))


def fetch_programme_info(id):

    url = "https://psapi.nrk.no/playback/metadata/program/%s?eea-portability=true" % id

    r = requests.get(url)
    if r.status_code != 200:
        print("Woops, status code", r.status_code)
        raise Exception("Bad shit went down getting '%s': %s" % (url, r.status_code))

    return json.loads(r.text)


def find_media_url(id):
    url = "https://psapi.nrk.no/playback/manifest/program/%s" % id

    r = requests.get(url)
    if r.status_code != 200:
        print("Woops, status code", r.status_code)
        raise Exception("Bad shit went down getting '%s': %s" % (url, r.status_code))

    return json.loads(r.text)


sucker = NRKSucker()


info = sucker.dump_at("PRHO04004903", "/tmp/norgerundt/")
sucker.find_good_areas(info["subtitles"])

next_id = info["info"]["_embedded"]["next"]["id"]
for i in range(2):
    info = sucker.dump_at(next_id, "/tmp/norgerundt/")
    sucker.find_good_areas(info["subtitles"])
    next_id = info["info"]["_embedded"]["next"]["id"]


#info = resolve_urls("PRHO04004903")
# print(json.dumps(info, indent=" "))

raise SystemExit()

info = fetch_programme_info("PRHO04004903")

print("INFO", json.dumps(info, indent=" "))

print("Next", info["_embedded"]["next"]["id"])


manifest = find_media_url("PRHO04004903")

print("media", json.dumps(manifest, indent=" "))


