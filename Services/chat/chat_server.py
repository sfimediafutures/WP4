from http.server import HTTPServer, SimpleHTTPRequestHandler

import openai
import json


SYSTEM_CONTEXT="""
You are CouchGPT, a helpful and playful couch companion
that replies to questions give a certain context. You will answer in a short
and conversational way, not elaborating if not particularly asked to do so.
If you don't know the answer or it's not in the given context, you could try
with a relevant witty remark or joke.
"""

def chat(message, context):

    response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=[
                {"role": "system", "content": SYSTEM_CONTEXT},
                {"role": "user", "content": "This is just context:\n" + context},
                {"role": "assistant", "content": "Ok, how can I help??"},
                {"role": "user", "content": message}
            ]
        )

    return response['choices'][0]['message']['content']


class RequestHandler(SimpleHTTPRequestHandler):

    def failed(self, code, message="Something went wrong"):
        self.send_error(code, message)

    def do_POST(self):
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)

        try:
            data = json.loads(post_body)

            if "message" not in data or "context" not in data:
                return self.send_error(400, "Bad request")

            response = {"message": chat(data["message"], data["context"])}
            response_json = json.dumps(response).encode("utf-8")

            print("Question:", data["message"])
            print("Response:", response)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json)

        except ValueError:
            self.send_error(400, 'Invalid JSON')

PORT = 8987

httpd = HTTPServer(("", PORT), RequestHandler)

print("Listening on port", PORT)

httpd.serve_forever()