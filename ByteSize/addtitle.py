import shutil

import os
import json
import re

import openai


def generate_info(data):

    prompt = "Generate a title and a oneliner for the given podcast episode:\n" + data
    print(prompt)
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=300)
    return response["choices"][0]["text"]


for filename in os.listdir("Episodes"):

    if not filename.endswith(".txt"):
        continue

    path = "Episodes/" + filename
    manifest = path.replace(".txt", ".json")

    if not os.path.exists(manifest):
        print("Missing manifest for text file", filename)
        continue

    with open(manifest, "r") as f:
        m = json.load(f)

    if "oneliner" in m:
        print(filename, "already has a oneliner")
        continue

    # Find title in the text file
    with open(path, "r") as f:
        lastperson = None
        title = None
        oneliner = None
        for line in f.readlines():

            if not line.strip():
                continue    
            if line.startswith("---"):
                break

            # GPT-3 has two formats - name: text ... and [name]\ntext, support both
            if line.strip().startswith("["):
                who = re.match("\[(.*)\]", line).groups()[0]
                lastperson = who
                continue  # Likely stuff like [music]

            if lastperson and not line.find(":") > -1:
                who = lastperson
                text = line
            else:
                who, text = line.split(":", 1)

            if who.lower() == "prompt":
                continue  # We ignore the prompt if given

            if who.lower() == "title":
                title = text.strip()
                continue

            if who.lower() == "one-liner" or who.lower() == "oneliner":
                oneliner = text.strip()
                continue

        if not oneliner or not title:
            print("Missing data", filename)
            with open(path, "r") as f2:
                data = f2.read()
                x = data.find("---")
                if x > -1:
                    ep_data = data[:x]
                else:
                    ep_data = data
            d = generate_info(ep_data)
            print("Got result:", d)
            shutil.copy(path, path + ".BAK")
            with open(path, "w") as f:
                f.write(d + "\n")
                f.write(data)
            raise SystemExit(0)
        else:
            print(filename, title, oneliner)

            m["title"] = title
            m["oneliner"] = oneliner
            shutil.copy(manifest, manifest + ".BAK")
            with open(manifest, "w") as f:
                json.dump(m, f, indent=2)