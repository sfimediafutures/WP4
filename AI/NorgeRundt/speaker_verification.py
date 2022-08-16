
from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
from datasets import load_dataset
import librosa as lb
import torch
import os
import math

"""
Expects a json file with "start" and "end" segments. If not a common file is
given, it will use the "file" attribute of the entries.
"""


class VoiceCompare():
    def __init__(self):

        self.model = None
        self.feature_extractor = None
        self.last_model_id = None
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

    def _load_model(self, model_id='microsoft/wavlm-base-plus-sv'):

        if self.last_model_id != model_id:
            # Free existing?
            self.last_model_id = model_id
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_id)
            self.model = WavLMForXVector.from_pretrained(model_id).to(self.device)

    def compare_wav(self, file1, file2, model=None):
        """
        Compare the two files and see if the speaker is the same
        """

        if not os.path.exists(file1):
            raise Exception("Missing file '%s'" % file1)
        if not os.path.exists(file2):
            raise Exception("Missing file '%s'" % file2)
        waveform1, rate1 = lb.load(file1, sr=16000)
        waveform2, rate2 = lb.load(file2, sr=16000)

        return self.compare_raw(waveform1, waveform2, model)

    def compare_raw(self, data1, data2, model=None):

        if model:
            self._load_model(model)
        else:
            self._load_model()

        audio = [data1, data2]
        inputs = self.feature_extractor(audio, padding=True, return_tensors="pt", sampling_rate=16000)

        inputs.to(self.device)
        embeddings = self.model(**inputs).embeddings.to(self.device)
        embeddings = torch.nn.functional.normalize(embeddings, dim=-1)  # .cpu()

        # the resulting embeddings can be used for cosine similarity-based retrieval
        cosine_sim = torch.nn.CosineSimilarity(dim=-1)
        similarity = cosine_sim(embeddings[0], embeddings[1])
        return similarity

    @staticmethod
    def save_segment(source, start, end):
        """
        Create a temporary file  with the given segment
        """
        import wave
        import tempfile
        dst_file = tempfile.mktemp(suffix=".wav")
        dst = wave.open(dst_file, "w")
        src = wave.open(source, "r")

        # Skip to position
        rate = src.getframerate()
        # Sanity
        if start > src.getnframes() / rate:
            raise Exception("Segment starts after file end, %s, %s" % (start, source))

        src.setpos(math.floor(rate * start))
        data = src.readframes(rate * (end - start))
        dst.setsampwidth(src.getsampwidth())
        dst.setnchannels(src.getnchannels())
        dst.setframerate(rate)
        dst.writeframes(data)
        return dst_file

    def compare_wav_offset(self, file, meta1, meta2, model=None):
        """
        Meta in format {"start": x.x, "end": y.y}
        """

        # GPU runs out of memory on this one - is it that a large file fesses things up?

        fn1 = VoiceCompare.save_segment(file, meta1["start"], meta1["end"])
        fn2 = VoiceCompare.save_segment(file, meta2["start"], meta2["end"])

        c = self.compare_wav(fn1, fn2, model)
        os.remove(fn1)
        os.remove(fn2)
        return c

        print("Loading", (meta1["start"], meta1["end"]), (meta2["start"], meta2["end"]))
        waveform1, rate1 = lb.load(file, sr=16000,
                                   offset=meta1["start"],
                                   duration=meta1["end"] - meta1["start"])
        waveform2, rate2 = lb.load(file, sr=16000,
                                   offset=meta2["start"],
                                   duration=meta2["end"] - meta1["start"])
        return self.compare_raw(waveform1, waveform2, model)

    def process_json_subs(self, jsonfile, threshold=0.80, max_files_per_person=3):
        with open(what, "r") as f:
            entries = json.load(f)

        for entry in entries:
            try:
                # Sort list by most recently used
                cast.sort(key=operator.itemgetter("ts"), reverse=True)
                found = False
                for c in cast:

                    min_match = 100
                    for file in c["files"]:
                        similarity = vc.compare_wav(file, entry["file"])
                        print(" --- %s: score %.2f" % (c["name"], similarity), (file, entry["file"]))
                        min_match = min(min_match, similarity)
                        if similarity < threshold:
                            break

                    print(" * %s: score %.2f" % (c["name"], min_match), (entry["file"]))
                    if min_match >= threshold:
                        entry["who"] = c["name"]
                        c["ts"] = time.time()
                        if len(c["files"]) >= max_files_per_person:
                            c["files"].pop(0)
                        c["files"].append(entry["file"])
                        # c["file"] = entry["file"]  # Use the last file for this person (as opposed to the first)
                        found = True
                        break

                if not found:
                    # New cast memeber
                    print("New cast member", len(cast))
                    cast.append({
                        "name": "person_%d" % len(cast),
                        "files": [entry["file"]],
                        "ts": time.time()
                    })
                    entry["who"] = cast[-1]["name"]

                print(entry)
            except Exception as e:
                print("Failed", entry)
                print(e)

        return cast, entries


if __name__ == "__main__":
    # TEST
    import json
    import time
    import operator

    import sys
    what = sys.argv[1]

    if len(sys.argv) > 2:
        threshold = float(sys.argv[2])
    else:
        threshold = 0.89

    max_files_per_person = 3

    vc = VoiceCompare()

    # We check the files against each other
    cast = []
    if 0:  # for entry in entries:
        cast, entries = vc.process_json_subs(what, threshold, max_files_per_person)
    else:
        duration = lb.get_duration(filename=what)
        for i in range(0, int(duration - 3)):
            entry = {"start": i, "end": i + 3}
            # Check pr second
            # Sort list by most recently used
            cast.sort(key=operator.itemgetter("ts"), reverse=True)
            found = False
            for c in cast:
                min_match = 100
                for i2, cmeta in enumerate(c["meta"]):
                    similarity = vc.compare_wav_offset(what, cmeta, entry)
                    print(" --- %s: score %.2f" % (c["name"], similarity), i2)
                    min_match = min(min_match, similarity)
                    if similarity < threshold:
                        break

                print(" * %s: score %.2f" % (c["name"], min_match), i)
                if min_match >= threshold:
                    entry["who"] = c["name"]
                    c["ts"] = time.time()
                    if len(c["meta"]) >= max_files_per_person:
                        c["meta"].pop(0)
                    c["meta"].append(entry)
                    found = True
                    break

            if not found:
                # New cast memeber
                print("New cast member", len(cast))
                cast.append({
                    "name": "person_%d" % len(cast),
                    "meta": [entry],
                    "ts": time.time()
                })
                entry["who"] = cast[-1]["name"]
            print(entry)

    path = os.path.split(what)[0]
    base = os.path.splitext(os.path.basename(what))[0]
    fn = os.path.join(path, "new_" + base + ".json")
    with open(fn, "w") as f:
        f.write(json.dumps(entries, indent=" "))

    fn = os.path.join(path, "new_" + base + "_cast.json")
    with open(fn, "w") as f:
        f.write(json.dumps(cast, indent=" "))
