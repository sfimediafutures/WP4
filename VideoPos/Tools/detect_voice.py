#!/bin/env python3
import contextlib
import sys
import wave
import json
import webrtcvad
import operator
from argparse import ArgumentParser
import tempfile
import os


def read_wave(path):
    """Reads a .wav file.

    Takes the path, and returns (PCM audio data, sample rate).
    """
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000, 48000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate


class Frame(object):
    """Represents a "frame" of audio data."""
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
    """Generates audio frames from PCM audio data.

    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.

    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def vad_collector(sample_rate, frame_duration_ms,
                  padding_frames, vad, frames):
    triggered = False
    segments = []
    voiced_frames = []
    frames_speech = 0
    frames_audio = 0
    padding = start = end = 0
    for idx, frame in enumerate(frames):
        is_speech = vad.is_speech(frame.bytes, sample_rate)
        if is_speech:
            frames_speech += 1
        else:
            frames_audio += 1

        if not triggered and is_speech:
            triggered = True
            start = idx * frame_duration_ms
        elif triggered and not is_speech:
            if padding < padding_frames:
                padding += 1
                continue
            triggered = False
            end = idx * frame_duration_ms
            segments.append({"type": "voice", "start": start / 1000., "end": end / 1000.})
            start = end = padding = 0
        elif triggered and is_speech:
            padding = 0

    return segments

def convert(mp3file):

    import subprocess
    fd, tmpfile = tempfile.mkstemp(suffix=".wav")
    print("Extracting audio to", tmpfile)
    cmd = ["ffmpeg", "-i", mp3file, "-vn", "-ac", "1", "-y", tmpfile]
    print(" ".join(cmd))
    s = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    s.wait()
    print(s.poll())

    print("Analyzing")
    return tmpfile


if __name__ == '__main__':


    parser = ArgumentParser()
    parser.add_argument("-i", "--input", dest="src", help="Source audio/video file", required=True)
    parser.add_argument("-a", "--aggressive", dest="aggressive", help="How aggressive (0-3, 3 is most agressive)", default=2)
    parser.add_argument("-s", "--sub", dest="sub", help="Subtitle file (json), if given it will be realigned and written to output file", required=False)
    parser.add_argument("-o", "--output", dest="dst", help="Output file", required=False)

    parser.add_argument("--min_cps", dest="min_cps", help="Minimum CPS", default=12)
    parser.add_argument("--max_cps", dest="max_cps", help="Maximum CPS", default=18)
    parser.add_argument("--max_adjust", dest="max_adjust", help="Maximum adjustment (s)", default=0.7)
    parser.add_argument("--min_time", dest="min_time", help="Minimium time for a sub (s)", default=1.2)


    options = parser.parse_args()

    options.min_cps = float(options.min_cps)
    options.max_cps = float(options.max_cps)
    options.max_adjust = float(options.max_adjust)
    options.min_time = float(options.min_time)

    is_tmp = False
    if not options.src.endswith(".wav"):
        is_tmp = True
        options.src = convert(options.src)

    audio, sample_rate = read_wave(options.src)
    vad = webrtcvad.Vad(int(options.aggressive))
    frames = frame_generator(30, audio, sample_rate)
    frames = list(frames)
    segments = vad_collector(sample_rate, 30, 3, vad, frames)

    updated = kept = 0    

    if not options.sub:
        if options.dst:
            with open(options.dst, "w") as f:
                json.dump(segments, f, indent=" ")
        else:
            print(json.dumps(segments, indent=" "))

    # Read the sub file and try to align
    if options.sub:
        print("Aligning with subs from", options.sub)
        with open(options.sub, "r") as f:
            subs = json.load(f)

            subs = sorted(subs, key=operator.itemgetter("start"))

        for sub in subs:
            found = False
            # Find a start in the segments that is very close, and if found, re-align
            for segment in segments:
                if abs(segment["start"] - sub["start"]) < options.max_adjust:

                    # Calculate cps
                    orig = (sub["start"], sub["end"])

                    sub["start"] = segment["start"]
                    sub["end"] = max(sub["start"] + options.min_time, segment["end"])

                    found = True
                    updated += 1
                    # print("ADJUST", orig, "->", (sub["start"], sub["end"]), cps, newcps, sub["text"])
                    break
            if not found:
                # print("Keeping", (sub["start"], sub["end"]), sub["text"])
                kept += 1

            cps = len(sub["text"]) / (sub["end"] - sub["start"])
            if options.max_cps and cps > options.max_cps:
                # print("** Too fast")
                sub["end"] = sub["start"] + len(sub["text"]) / float(options.max_cps)
            if options.min_cps and cps < options.min_cps:
                # print("** Too slow", (sub["start"], sub["end"]), (len(sub["text"]) / float(options.min_cps)))
                sub["end"] = sub["start"] + max(options.min_time,  (len(sub["text"]) / float(options.min_cps)))
            newcps = len(sub["text"]) / (sub["end"] - sub["start"])


        # Do some additional checking - if two subs close very close to each other, bundle them
        threshold = 0.4
        # If some overlap with a tiny bit, shorten down the first
        for idx, sub in enumerate(subs):
            if idx > 0:
                if abs(sub["end"] - subs[idx-1]["end"]) < threshold:
                    print("Aligning ends", subs[idx-1], sub)
                    subs[idx-1]["end"] = sub["end"]
                if subs[idx-1]["end"] - sub["start"]  < threshold * 2 and subs[idx-1]["end"] - sub["start"] > 0:
                    print("Overlapping\n", subs[idx-1],"\n", sub)
                    subs[idx-1]["end"] = sub["start"] - 0.001

        # Sanity
        for sub in subs:
            if sub["end"] < sub["start"]:
                raise SystemExit("Super-wrong, end is before start", sub)

        if options.dst:
            print("Saving to", options.dst)
            with open(options.dst, "w") as f:
                json.dump(subs, f, indent=" ")
        else:
            print("Not saving updated file")


        print("Updated", updated, "kept", kept)

    if is_tmp:
        os.remove(options.src)