import os
import json
import re
import copy
import wave
import subprocess
import tempfile


class BaseTTS:
    def __init__(self, config="config.json"):
        if not os.path.exists(config):
            raise Exception("Missing configuration file '%s'" % config)
        with open(config, "r") as f:
            self.config = json.load(f)
        self.client = None
        self.use_ssml = False
        self._last_mentions = {}  # Used for cleaning up annoying repetitions

    def speak(self, text):
        raise Exception("Not implemented, use a specialized version")

    def write_results(self, result, filename):
        raise Exception("Not implemented!")

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
                print("File '{}' already exists".format(temp))
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

                if self.use_ssml:
                    result = self.speak(ssml)
                    # duration = result.audio_duration.total_seconds()
                else:
                    result = self.speak(sentence)

                self.write_results(result, temp)
                w = wave.open(temp, "r")
                duration =  w.getnframes() / w.getframerate()

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



class GoogleTTS(BaseTTS):

    def __init__(self, config="config.json"):
        from google.cloud import texttospeech

        super().__init__(config)
        self.client = texttospeech.TextToSpeechClient()
        self.use_ssml = True

    def speak(self, text):
        from google.cloud import texttospeech
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

    def write_results(self, result, filename):
        with open(filename, "wb") as out:
            # Write the response to the output file.
            out.write(result.audio_content)



class MicrosoftTTS(BaseTTS):
    def __init__(self, config="config.json"):
        import azure.cognitiveservices.speech as speechsdk

        super().__init__(config)
        self.use_ssml = True

        self.client = texttospeech.TextToSpeechClient()
        # Creates an instance of a speech config with specified subscription key and service region.
        speech_config = speechsdk.SpeechConfig(subscription=self.config["key"],
                                               region=self.config["region"])

        # We want an MP3 file  - doesn't work
        # speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)

        # use the default speaker as audio output.
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)


    def speak(self, text):
        import azure.cognitiveservices.speech as speechsdk
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

    def write_results(self, result, filename):
        with open(filename, "wb") as f:
            f.write(result.audio_data)


class BarkTTS(BaseTTS):
    def __init__(self, config="config.json"):
        super().__init__(config)

        # from bark import preload_models
        # preload_models()

    def speak(self, text):

        print("Should speak text", text)

        if text["who"] not in self.config["people"]:
            print("Missing person '{}', using 'default'".format(text["who"]))

            if "default" not in self.config["people"]:
                raise Exception("No default user")

        from bark import generate_audio
        voice = self.config["people"][text["who"]]["voice"]
        audio_array = generate_audio(text["text"], history_prompt=voice)
        return audio_array


    def write_results(self, audio_data, filename):
        from bark import SAMPLE_RATE
        from scipy.io.wavfile import write as write_wav
        import numpy as np
        print("**** WRITING TO '{}'".format(filename))
        scaled_audio = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)
        write_wav(filename, SAMPLE_RATE, result)
        # write_wav(filename, SAMPLE_RATE, result.astype(np.int16))

