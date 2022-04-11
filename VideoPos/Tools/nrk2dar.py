#!/usr/bin/env python3

import subprocess
from argparse import ArgumentParser

from AI.mediapipe.analyze import Analyzer
import random
import json
import os
import re
import requests


# URL
# https://tv.nrk.no/serie/debatten/202202/NNFA51021522/avspiller

# INFO
# https://psapi.nrk.no/playback/metadata/program/NNFA51021522?eea-portability=true

# m3u8
# https://nrk-od-70.akamaized.net/world/1384470/0/hls/nnfa51021522/playlist.m3u8?bw_low=10&bw_high=6000&bw_start=1800&no_iframes&no_audio_only&no_subtitles
# https://nrk-od-70.akamaized.net/world/1384470/0/hls/nnfa51021522/1853524312-1203177498-prog_index.m3u8?version_hash=06241e27"


def resolve_urls(url_or_id):
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

    return res


def download_episode(url, destination):
    print("Downloading from '%s'" % url)
    cmd = 'ffmpeg -i "%s" -c copy %s' % (url, destination)

    res = subprocess.getoutput(cmd)
    # if res != 0:
    #    raise Exception("Download failed")

    print("Downloaded")


def analyze(src_video, dst_aux):

    class Options:
        def __init__(self):
            self.selfie = False
            self.startts = 0
            self.endts = None
            self.iframes = True
            self.tile = False
            self.show = False
            self.video = src_video
            self.cast = ""

    if os.path.exists(dst_aux):
        print("Already analyzed")
        return

    options = Options()
    analyzer = Analyzer(options)

    print("Processing", src_video)
    # Remove cached results if they are there
    if os.path.exists("/tmp/analysis.json"):
        os.remove("/tmp/analysis.json")
    options.cast = os.path.join(os.path.split(options.video)[0], "cast.json")
    res = analyzer.analyze_video(options.video, options)

    with open(dst_aux, "w") as f:
        json.dump(res, f, indent=" ")

    with open(options.cast, "w") as f:
        json.dump(analyzer.get_cast(), f, indent=" ")


def create_poster(src_video, dst_file):
    print("Generating poster")
    res = subprocess.getoutput("ffmpeg -y -ss 00:00:05 -i %s -frames:v 1 %s" % (src_video, dst_file))
    # res = subprocess.check_output(("ffmpeg -y -ss 00:01:00 -i %s -frames:v 1 %s" % (src_video, dst_file)).split(" "))


def create_manifest(options, video_file, aux_file, poster_file=None,
                    subsfile=None, info=None):

    # Actual folder we're using
    dst_folder = os.path.join(options.webroot, options.id)

    manifest = {"options": {"audioon": True, "auto_animate": True}}
    manifest["id"] = random.getrandbits(31)
    manifest["video"] = {"src": os.path.join(dst_folder, video_file)}
    if poster_file:
        manifest["poster"] = os.path.join(dst_folder, poster_file)

    if subsfile:
        manifest["subtitles"] = {"src": os.path.join(dst_folder, subsfile)}

    # Download poster and manifest from info
    if info:
        print("PREPLAY", json.dumps(info["info"]["preplay"], indent=" "))
        manifest["poster"] = info["info"]["preplay"]["poster"]["images"][-1]["url"]
        manifest["normalsubtitles"] = [{"src": info["manifest"]["playable"]["subtitles"][-1]["webVtt"]}]
        t = info["info"]["preplay"]["titles"]
        manifest["title"] = t["title"] + "\n" + t["subtitle"]
        manifest["desciption"] = info["info"]["preplay"]["description"]
        manifest["cast"] = os.path.join(dst_folder, "cast.json")

    manifest["aux"] = os.path.join(dst_folder, aux_file)

    manifest_file = os.path.join(options.dst, options.id + "/" + options.id + ".json")
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=" ")

    print("Created manifest", manifest_file)

if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-s", "--source", dest="src", help="Source url", required=True)

    parser.add_argument("-o", "--output", dest="dst",
                        help="Destination folder (new subfolder will be made)",
                        default="/var/www/html/sfi/res/")

    parser.add_argument("--id", dest="id", help="ID of resource (generated or taken from url if not given", required=False)

    parser.add_argument("--name", dest="name", help="Name of resource (ID used if not given)", default=None)

    parser.add_argument("--sub", "--subtitles", dest="suburl", help="URL of subtitles", default=None)
    parser.add_argument("--webroot", dest="webroot", default="/sfi/res/",
                        help="Relative position of dst folder for online (manifest)")

    parser.add_argument("--iframes", dest="iframes", help="Align to iframes (needs transcoding)",
                        action="store_true", default=False)
    parser.add_argument("-i", "--info", dest="infoonly", help="Only show info",
                        action="store_true", default=False)

    options = parser.parse_args()

    info = resolve_urls(options.src)

    if options.infoonly:
        print(json.dumps(info, indent=" "))
        raise SystemExit(0)

    options.id = info["id"]

    if not options.id:
        import re
        m = re.search("version_hash=([^&]*)", options.src)
        if m:
            options.id = m.groups()[0]
        else:
            m = re.search("hls/([^/]*)/", options.src)
            if m:
                options.id = m.groups()[0]

    if not options.id:
        options.id = str(random.getrandbits(31))

    print("ID is", options.id)
    dst_folder = os.path.join(options.dst, options.id)

    if not os.path.exists(dst_folder):
        os.makedirs(dst_folder)

    dst_video = os.path.join(dst_folder, options.id + ".mp4")
    dst_aux = os.path.join(dst_folder, options.id + "_aux.json")

    if not os.path.exists(dst_video):
        print("Downloading...")
        download_episode(info["m3u8"], dst_video)
    else:
        print("File already exists on disk, processing...")


    # Create poster
    # dst_poster = os.path.join(dst_folder, "poster.jpg")
    # create_poster(dst_video, dst_poster)

    # Download poster file for other things?

    # We now need to analyze it
    analyze(dst_video, dst_aux)

    # Create the manifest
    create_manifest(options, options.id + ".mp4", options.id + "_aux.json",
                    # poster_file="poster.jpg", 
                    info=info)

