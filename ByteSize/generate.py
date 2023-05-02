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

import random
import os

from tts import BarkTTS as TTS

# If we use Google, provide a file with credentials
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

        import openai
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
    subprocess.call("./copy.sh")

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

