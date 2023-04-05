from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import re
import openai
import time


SYSTEM_CONTEXT=""" You are CouchGPT, a helpful and playful couch companion
that replies to questions give a certain context. You will answer in a short
and conversational way, not elaborating if not particularly asked to do so.
If you don't know the answer or it's not in the given context, you could try
with a relevant witty remark or joke. """

SYSTEM_CONFIG_CONTEXT="""You are ConfigGPT, a configuration bot that seeks to
assist users in selecting the correct configuration parameters.
"""

cache = {}

def clean_cache(max_time=3600):
    todel = []
    for key in cache:
        if cache[key]["ts"] < time.time() - max_time:
            todel.append(key)

    for key in todel:
        del cache[key]

def chat(message, context, chatmsgs):

    msgs = [
                {"role": "system", "content": SYSTEM_CONTEXT},
                {"role": "user", "content": "Respond in the same language as the user messages, or if you can't detect it, use the language of the context. This is the context:\n" + context},
                {"role": "assistant", "content": "Ok, how can I help??"}                
            ]
    for chat in chatmsgs:
        msgs.append({"role": chat["role"], "content": chat["text"]})

    msgs.append({"role": "user", "content": message})
    response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=msgs
        )

    text = response['choices'][0]['message']['content']
    return {"lang": "undefined", "response": text}


def configchat(message, config, chatmsgs):

    # Params should have a name, a range, a default value and if the name
    # isn't self descriptive, provide a description too.
    # JSON input should be acceptable, or JSONLines
    # clean_cache()  # We don't clean the cache for now

    key = json.dumps((message, config, chatmsgs))
    if key in cache:
        return cache[key]

    CFG = """These are the possible parameters:
__PARAMS__

You want to help the user adjust the GUI, and after each user message you will
print the updated config parameters in the format name: value, one line for
each parameter. Include your reason on a line starting with 'Reason:'. Always
respond in this format and don't ask the user what they want, just do it." 
"""
    msgs = [
                {"role": "system", "content": SYSTEM_CONFIG_CONTEXT},
                {"role": "user", "content": CFG.replace("__PARAMS__", config)},
                {"role": "assistant", "content": "Ok, how can I help??"}
            ]
    for chat in chatmsgs:
        msgs.append({"role": chat["role"], "content": chat["text"]})

    msgs.append({"role": "user", "content": message})

    response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=msgs
        )

    texts = response['choices'][0]['message']['content'].split("\n")

    print("\nThe response was:\n{}\n".format(response['choices'][0]['message']['content']))

    config = {}
    # Define the regular expression pattern to match the name-value pairs
    # pattern = r"([a-zA-Z]+)\s*:\s*([\w\s-]+)"
    pattern = r"([a-zA-Z]+)\s*:\s*([^\n]+)"

    other = []
    for text in texts:
        # Find all the matches in the string
        matches = re.findall(pattern, text)
        if matches:
            config.update(dict(matches))
        else:
            print("No match for line", text)
            other.append(text)

    # Convert the matches to a dictionary

    cache[key] = {"lang": "undefined", "response": config, "ts": time.time(), "text": "\n".join(other)}

    return cache[key]



class RequestHandler(SimpleHTTPRequestHandler):

    def failed(self, code, message="Something went wrong"):
        self.send_error(code, message)

    def do_POST(self):
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)

        try:
            data = json.loads(post_body)

            if ("config" not in data and "context" not in data) or "message" not in data:
                print(data)
                return self.send_error(400, "Bad request")

            if "chat" in data:
                chatmsgs = data["chat"]
            else:
                chatmsgs = None

            if "config" in data:
                # print("GOT DATA", post_body)
                # print("Parsed into", data)
                response = configchat(data["message"], data["config"], chatmsgs)
            else:
                response = chat(data["message"], data["context"], chatmsgs)

            response_json = json.dumps(response).encode("utf-8")

            print(data["message"])
            print("->")
            print(response_json)
            print("-------")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json)

        except ValueError as e:
            print("ERROR", e)
            self.send_error(400, '{"message": "Invalid JSON"}')


PORT = 8987

httpd = HTTPServer(("", PORT), RequestHandler)

print("Listening on port", PORT)

httpd.serve_forever()
