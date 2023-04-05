#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import contextlib
import wave
import random
import re
import copy
import time

import http.server
import socketserver

import azure.cognitiveservices.speech as speechsdk

from google.cloud import texttospeech

import openai
import random
import os

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "cryonite-fa5373079b4b.json"


SYSTEM_MESSAGE="""You are PodGPT, a podcast script writer for the
podcast "Byte Size". You write scripts that are funny and impersonates the
podcast presenters without being explicit about it. All scripts are returned
in the format "presenter name: text". The transcript will always start with
title: and one_liner:.

The podcast slogan is 'Your favourite robot podcast', and one of the
presenters is the lead, interviewing the other.

"""

class ByteSize:

    def __init__(self, model="text-davinci-003", temperature=0.5, maxtokens=3000):
        self.model = model
        self.temperature = temperature
        self.maxtokens = maxtokens
        self.presenters = ["Cora", "Tony"]
        self.target_dir = "./Episodes/"
        self._intro = "" 
        fesk = """
This is the podcast "Byte Size", having a welcome statement to "Byte Size,
your favourite robot podcast."
"""

    def _get_next_episode_nr(self):
        e = os.listdir(self.target_dir)
        for i in range(1, 999):
            if "ep_%02d.txt" % i not in e:
                break

        print("Next episode is", i)
        return i
    

    def replace_urls_with_text(self, text):
        """
        Replaces urls in a text with the text from the urls
        """
        from get_url import url_to_string

        https_pattern = re.compile(r'https://\S+')
        matches = https_pattern.findall(text)

        for url in matches:
            pagetext = url_to_string(url)
            text = text.replace(url, pagetext)
        return text

    def generate_episode(self, prompt):
        """
        Prompt should describe the content of the episode. The ByteSize bit is prepended
        """

        prompt = self.replace_urls_with_text(prompt)

        l = random.sample(range(len(self.presenters)), 1)[0]
        lead = self.presenters[l]
        guest = self.presenters[(l+1) % len(self.presenters)]

        p = self._intro + "Write a title, one liner and a full episode as a conversational transcript about this subject where %s is the lead and %s is the guest:\n" % \
            (lead, guest)
        p += prompt

        episode = self._get_next_episode_nr()
        path = os.path.join(self.target_dir, "ep_%02d.txt" % episode)
        print("Generating episode", path)

        print("Prompt:", p)
        res = self._send_to_gpt(p)

        with open(path, "w") as f:
            f.write(res)
        return path

    def _send_to_gpt(self, prompt, temperature=0.7, max_tokens=3800):
        """
        Returns a text by GPT, it's as a dictionary, you are likely looking for ["text"]
        """
        if temperature is None:
            temperature = self.temperature
        if max_tokens is None:
            max_tokens = self.max_tokens

        msgs = [
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt}
                ]

        # We estimate the number of tokens left (we're just guessing, but
        # based on info from gpt)
        avg_token_length = 3.3  # Pure guesswork I think
        # Already spent by the input
        spent_tokens = len(json.dumps(msgs)) / avg_token_length
        tokens_left = int(max_tokens - spent_tokens)
        # Estimated words left
        words_left = tokens_left * avg_token_length
        prompt.replace("__WORDCOUNT__", str(int(words_left)))
        print("prompt length", len(json.dumps(msgs)))
        print("Can generate", int(words_left), "words max")

        response = openai.ChatCompletion.create(
              model="gpt-3.5-turbo",
              messages=msgs,
              temperature=temperature,
              max_tokens=tokens_left
            )

        return response["choices"][0]['message']['content']
        texts = response['choices'][0]['message']['content'].split("\n")

        response = openai.Completion.create(
            model=self.model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens)
        return response["choices"][0]["text"]



# en-US-CoraNeural - female presenter
# en-US-TonyNeural - the enthusiast
# en-US-MichelleNeural - the introduction

class TTS:
    def __init__(self, config="config.json"):

        if not os.path.exists(config):
            raise Exception("Missing configuration file '%s'" % config)
        with open(config, "r") as f:
            self.config = json.load(f)

        if self.config.get("use_google", False):
            self.client = texttospeech.TextToSpeechClient()
        else:
            # Creates an instance of a speech config with specified subscription key and service region.
            speech_config = speechsdk.SpeechConfig(subscription=self.config["key"],
                                                   region=self.config["region"])

            # We want an MP3 file  - doesn't work
            # speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)

            # use the default speaker as audio output.
            self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
        self._last_mentions = {}  # Used for cleaning up annoying repetitions

    def speak(self, text):

        if self.config.get("use_google", False):
            input_text = texttospeech.SynthesisInput(ssml=text)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )
            # Why can't it just get this from the ssml?
            vname =  re.search('.*name="([\w-]*)"', text).groups()[0]
            vlang = vname[:5]
            voice = texttospeech.VoiceSelectionParams(
                language_code=vlang,
                name=vname
                # ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
                # name=vlang

            result = self.client.synthesize_speech(
                input=input_text, voice=voice, audio_config=audio_config
            )
            return result

        result = self.speech_synthesizer.speak_ssml_async(text).get()
        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            #print("Speech synthesized for text [{}]".format(text))
            pass
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))

        return result

    def toFile(self, text, filename):
        """
        We want this as MP3 but we get wav, transcode
        """
        if os.path.exists(filename):
            print("File '%s' already exists, returning" % filename)
            return

        result = self.speak(text)

        fd, name = tempfile.mkstemp()
        os.write(fd, result.audio_data)
        os.sync()

        # Now we transcode
        cmd = ["ffmpeg", "-y", "-i", name, filename]
        rv = subprocess.call(cmd)
        if rv != 0:
            raise Exception("ERROR TRANSCODING")

    def _cleanup(self, text):
        """
        We remove some annoying bits of text that ruins stuff for the TTS
        """
        if 0:
            # Remove the comma
            for name in self.config["people"].keys():
                text = re.sub(r'(, ' + name + ')', ' ' + name, text)
            return text

        # Remove the names all the time if we're not stopping on them
        # We ignore people we've already mentioned
        for name in self.config['people'].keys():
            if re.search(r'(, ' + name + ')', text):
                if name in self._last_mentions:
                    # Remove
                    text = re.sub(r'(, ' + name + ')', '', text)
                else:
                    self._last_mentions[name] = True
        return text

        # This just makes it sound stranger - find a way to not have a too long break here?

        for name in self.config["people"].keys():
            text = re.sub(r',(?= \b' + name + r'\b)', '', text)
        return text

    def speak_sentences(self, sentences, dstfile, tmpdir=None):
        """
        List of (who, text)

        This will create a number of sentences (as we otherwise loose all
        timing info...), and the files will be merged at the end
        """
        if not tmpdir:
            tmpdir = tempfile.mkdtemp()
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)

        audio_segments = []
        for idx, sentence in enumerate(sentences):
            temp = "{}/{}.wav".format(tmpdir, idx)
            if os.path.exists(temp):
                w = wave.open(temp, "r")
                duration =  w.getnframes() / w.getframerate()
            else:
                ssml = """<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US">"""
                p = self.config["people"][sentence["who"]]
                text = sentence["text"]
                for name in self.config["people"].keys():
                    text = text.replace(name, name.lower())

                t = '<voice name="{}"><prosody rate="{}%" pitch="{}%" style="{}">{}</prosody></voice>'\
                    .format(p["voice"], p.get("speed", 0),
                            p.get("pitch", 0), p.get("style", ""), sentence["text"])

                ssml += t
                ssml += "</speak>"""
                result = self.speak(ssml)
                # duration = result.audio_duration.total_seconds()

                if self.config.get("use_google", False):
                    with open(temp, "wb") as out:
                        # Write the response to the output file.
                        out.write(result.audio_content)
                else:
                    with open(temp, "wb") as f:
                        f.write(result.audio_data)

                # Read duration from file, it's not correct from MS service
                w = wave.open(temp, "r")
                duration =  w.getnframes() / w.getframerate()

            audio_segments.append({"path": temp,
                                   # "audio_data": result.audio_data,
                                   "type": "voice",
                                   "duration": duration,
                                   "sentence": sentence})
        # Convert to speech
        return self._merge_files_and_make_subs(audio_segments, dstfile)
        # self.toFile(ssml, dstfile)

    def _merge_files_and_make_subs(self, audio_segments, dstfile):
        """
        Merge audio files into one, create subtitles. Write audio to dstfile,
        return subs
        """

        subs = []
        last_start = 0
        # audio_data = b''
        cmd = ["sox"]
        for idx, segment in enumerate(audio_segments):
            # audio_data += segment["audio_data"]
            cmd.append(segment["path"])
            if segment["type"] != "voice":
                last_start += segment["duration"]
                continue
            segment["sentence"]["start"] = last_start + self.config.get("speechdelay", 0.2)
            segment["sentence"]["end"] = last_start + segment["duration"]
            last_start = segment["sentence"]["end"]
            subs.append(segment["sentence"])

        # Merge
        cmd.append("/tmp/merge.wav")
        print("CALLING", cmd)
        rv = subprocess.call(cmd, stderr=subprocess.PIPE)

        # Now we transcode and merge files
        cmd = ["ffmpeg", "-y", "-i", "/tmp/merge.wav", dstfile]
        rv = subprocess.call(cmd)
        if rv != 0:
            raise Exception("ERROR TRANSCODING")

        return subs

    def read_text_file(self, srcfile):
        """
        Format is: <person>: text\n
        Where person is defined in the fjson file
        """
        self.title = "Untitled"
        self.oneliner = ""
        sentences = []
        lastperson = None  # For alternative format
        with open(srcfile, "r") as f:
            lines = f.readlines()

            # If the end on a ":", merge with the next line
            newlines = []
            i = 0
            while i < len(lines):
                if lines[i].endswith(":"):
                    newlines.append(" ".join(lines[i], lines[i + 1]))
                    i += 2
                else:
                    newlines.append(lines[i])
                    i += 1

            for line in newlines:
                if line.strip() == "":
                    lastperson = None
                    continue

                if line.strip().startswith("----"):
                    break # We're done

                # GPT-3 has two formats - name: text ... and [name]\ntext, support both
                if line.strip().startswith("["):
                    who = re.match("\[(.*)\]", line).groups()[0]
                    if who in self.config["people"]:
                        lastperson = who
                    continue  # Likely stuff like [music]

                if lastperson:
                    who = lastperson
                    text = line
                else:
                    who, text = line.split(":", 1)
                if who.lower() == "prompt":
                    continue  # We ignore the prompt if given

                if who.lower() == "title":
                    self.title = text.strip()
                    continue

                if who.lower().find("transcript") > -1:
                    continue  # Ignore - it's likely just a meta thing

                if who.lower() == "one-liner" or who.lower() == "oneliner" or who.lower() == "one liner":
                    self.oneliner = text.strip()
                    continue

                text = self._cleanup(text)

                if who not in self.config["people"]:
                    raise Exception("Missing person: %s, known: %s" % \
                                    (who, str(self.config["people"])))

                sentences.append({"who": who, "text": text})

        return sentences

    def split_sentences(self, sentences, maxlen=240):
        """
        Split sentences into sensible bits for chat presentation
        """

        split = []
        def add(entry, text):
            if not text.strip():
                return
            entry = copy.copy(sentence)
            entry["text"] = text
            split.append(entry)

        for sentence in sentences:
            # We just split quick and easy on anything that gives us a long break.
            candidates = re.findall(r'[^\.\!\?:]+[\.\!\?:]*|[^\.\!\?:]+', sentence["text"])
            for candidate in candidates:
                add(sentence, candidate)
            continue


            candidates = re.findall(r'[^\.\!\?]+[\.\!\?]*|[^\.\!\?]+', sentence["text"])
            # candidates = re.findall(r'[^,\.\!\?:]+[,\.\!\?:]*|[^,\.\!\?:]+', sentence["text"])
            # Split into sensible bits
            current = ""
            for candidate in candidates:

                ml = maxlen if candidate[-1] in [".", "!", "?"] else maxlen * 0.8
                if len(current) + len(candidate) < ml:
                    current += candidate
                    continue

                # If this string is just too long, cut it (but keep at least 10 chars for next)
                toolong = False
                while len(current) > maxlen:
                    l = min(maxlen, len(current) - 10)
                    # Find last space within range
                    l = current.rfind(" ", 0, l)
                    add(sentence, current[:l])
                    current = current[l:]

                add(sentence, current)
                current = candidate

            add(sentence, current)

        return split

    def addSpeech(self, jsonfile, addToFile=True):
        """
        JSONfile must be formatted for SKMU thing,
        with "title", "intro", "short_text", and "texts".

        For "texts", the titles and image texts are not read.
        """

        with open(jsonfile, "r") as f:
            info = json.load(f)

        if "title" not in info:
            raise Exception("Format of this file seems wrong, missing title")

        # We create separate files
        basename = os.path.splitext(os.path.basename(jsonfile))[0]

        self.toFile(info["title"], basename + "-title.mp3")
        if addToFile:
            info["snd_title"] = basename + "-title.mp3"

        if "intro" in info and info["intro"]:
            self.toFile(info["intro"], basename + "-intro.mp3")
            if addToFile:
                info["snd_intro"] = basename + "-intro.mp3"

        if "short_text" in info and info["short_text"]:
            self.toFile(info["short_text"], basename + "-short_text.mp3")
            if addToFile:
                info["snd_short"] = basename + "-short_text.mp3"

        t = ""
        if "texts" in info:
            for textblock in info["texts"]:
                if "img" in textblock:
                    continue
                t += textblock["text"]
        if t:
            self.toFile(t, basename + "-long_text.mp3")
            if addToFile:
                info["snd_long"] = basename + "-long_text.mp3"

        if addToFile:
            with open(jsonfile, "w") as f:
                json.dump(info, f, indent=" ")

    def merge_trivial(self, intervals, sentences):
        """
        Trivial merge, just take one after the other (check for EXTREME stupidity)
        """
        if 1:
            too_slow = []
            for i, interval in enumerate(intervals):
                d = interval["end"] - interval["start"]
                chars = len(sentences[i]["text"])
                # Check extreme miss
                if chars/d < 6:
                    # This is rubbish, we should merge this sentence with the next
                    too_slow.append(i+1)
                    sentences[i]["text"] += sentences[i+1]["text"]

            while too_slow:  # Remove from the back
                print("Removing sentence", sentences[too_slow[-1]])
                sentences.pop(too_slow.pop())

        if len(intervals) != len(sentences):
            print("Warning - intervals and sentences are not equal, {} vs {}"\
                  .format(len(intervals), len(sentences)))

        for i in range(min(len(intervals), len(sentences))):
            sentences[i]["start"] = intervals[i]["start"]
            sentences[i]["end"] = intervals[i]["end"]

        return sentences

    def merge_smart(self, intervals, sentences):
        """
        Merge based on the average time pr char
        """
        intervals.sort(key=lambda x: x['start'])
        total_t = intervals[-1]["end"]
        # num chars:
        s = [len(x["text"]) for x in sentences]
        total_chars = sum(s)
        spd = total_t / total_chars
        print("Average speed", spd)

        # Go through each sentence and find segments that start/end sensibly
        new_sentences = []
        start = intervals[0]["start"]
        last_sentence = 0
        for idx, sentence in enumerate(sentences):
            person_speed = (100 + self.config["people"][sentence["who"]].get("speed", 0)) / 100.
                           # (100 + self.config.get("avg_speed", 0))
            est_end = (start + (len(sentence["text"]) * spd)) # / person_speed
            print("Estimated sentence", idx, sentence["who"],
                  len(sentence["text"]), start, "-", est_end)
            # Find the closest end point for this
            distances = [abs(i["end"] - est_end) for i in intervals[last_sentence + 1:]]
            if len(distances) == 0:
                print("RAN OUT OF BITS")
                break

            closest_index = idx + distances.index(min(distances))
            last_sentence = closest_index + 1
            # End point
            sentence["start"] = start
            sentence["end"] = intervals[closest_index]["end"]
            print("   Set end to", sentence["end"], min(distances))
            if sentence["end"] < sentence["start"]:
                raise SystemExit("Dafuq, set end to before start, should be impossible")
            if closest_index < len(intervals) - 1:
                start = intervals[closest_index + 1]["start"]
            else:
                print("AT END")

        return sentences


# Server

class JSONHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        try:
            request = json.loads(body)
        except Exception as e:
            print("Exception in request:", e)
            print("Request was", body)
            send.send_response(400, "Invalid request")
            self.end_headers()
            return

        # Create a new episode?
        result = None
        if "cmd" in request and request["cmd"] == "generate":
            if "prompt" in request:
                prompt = request["prompt"]
                print("Should generate for prompt '%s'" % prompt)
                # Check for maximum length?

                result = {"will_process": True}
        if result is None:
            send.send_response(400, "Incomplete request")
            self.end_headers()
            return

        self.send_response(200)
        # do something with the data
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

        # Actually do the processing - we could do it here but also we could
        # spawn it off and provide progress?
        print("Generating episode")
        generator = ByteSize()
        src = generator.generate_episode(prompt)
        print("Creating episode")
        create_episode(src)
        print("Publishing")
        publish_episodes()


def publish_episodes():
    import subprocess
    subprocess.call("copy.sh")

def create_episode(src):
    tts = TTS()
    dst = os.path.splitext(src)[0] + ".mp3"
    times = os.path.splitext(src)[0] + "_segments.json"
    subfile = os.path.splitext(src)[0] + "_subs.json"
    manifestfile = os.path.splitext(src)[0] + ".json"

    sentences = tts.read_text_file(src)

    sentences = tts.split_sentences(sentences, maxlen=180)
    subs = tts.speak_sentences(sentences, dst, "/tmp/{}".format(os.path.basename(dst)))

    with open(subfile, "w") as f:
        json.dump(subs, f, indent=" ")

    # Write manifest
    manifest = {
     "id": random.getrandbits(48),
     "subtitles": [
      {
       "src": "/ByteSize/Episodes/" + os.path.basename(subfile)
      }
     ],
     "title": tts.title,
     "oneliner": tts.oneliner,
     "cast": "/ByteSize/bytesize_people.json",
     "poster": "https://seer2.itek.norut.no/ByteSize/gfx/poster.jpg",
     "audio": {
      "src": "/ByteSize/Episodes/" + os.path.basename(dst)
     },
     "duration": subs[-1]["end"],
     "published": time.time()
    }

    with open(manifestfile, "w") as f:
        json.dump(manifest, f, indent=" ")


if __name__ == "__main__":

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-t", "--temperature", dest="temperature",
                        help="Temperature, default 0.7", default=0.7)
    parser.add_argument("--maxtokens", dest="maxtokens",
                        help="Max tokens, default 3800", default=3800)
    parser.add_argument("-p", "--prompt", dest="prompt",
                        help="Prompt if given")
    parser.add_argument("-s", "--src", dest="src",
                        help="Source file if generating from an existing file")

    parser.add_argument("--port", dest="port",
                        help="Port for web server, if not given, it will not be run as a server")

    options = parser.parse_args()

    if options.port:
        httpd = socketserver.TCPServer(("", int(options.port)), JSONHandler)
        print("Server running on port", options.port)
        try:
            httpd.serve_forever()
        finally:
            httpd.shutdown()
            httpd.server_close()

    if options.prompt:
        generator = ByteSize(temperature=float(options.temperature), maxtokens=int(options.maxtokens))
        src = generator.generate_episode(options.prompt)
    else:
        src = options.src

    create_episode(src)

    print("Done")

