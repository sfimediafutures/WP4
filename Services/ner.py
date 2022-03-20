from http.server import BaseHTTPRequestHandler, HTTPServer
from transformers import pipeline
import pandas as pd
import json
import gzip


class NER:
    def __init__(self, model="saattrupdan/nbailab-base-ner-scandi"):
        self.ner = pipeline(task='ner',
                            model=model,
                            aggregation_strategy='first')

    def evaluate(self, text):
        result = self.ner(text)
        return pd.DataFrame.from_records(result).to_json(orient='records')


class MyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            data_len = int(self.headers['Content-Length'])
            print("Got request", data_len, "bytes")

            request = json.loads(self.rfile.read(data_len).decode("utf-8"))

            # We expect "inputs" as a piece of text
            if "inputs" not in request:
                self.send_reply(500, "Bad arguments")
                return

            # Analyze
            res = self.server.ner.evaluate(request["inputs"])
            return self._send_text(res)

        except Exception as e:
            print("Bad data", e)

            self.send_response(500, 'Bad data')
            self.end_headers()
            return

    def _send_text(self, text, mimetype="application/json", response=200, content_range=None):
        encoding = None
        text = text.encode("utf-8")

        self.prepare_send(mimetype, len(text), encoding=encoding,
                          response=response, content_range=content_range, cache="no-cache")
        self.wfile.write(text)

    def prepare_send(self, type, size=None, response=200, encoding=None, content_range=None, cache=None):
        try:
            self.send_response(response)
        except Exception as e:
            print("Error sending response: %s" % e)
            # self.get_log().warning("Error sending response: %s"%e)
            return

        self.send_header("server", self.server_version)
        if type:
            self.send_header("Content-Type", type)

        self.send_header("Access-Control-Allow-Origin", "*")
        if content_range:
            self.send_header("Content-Range", "bytes %d-%d/%d" % content_range)

        self.send_header("Accept-Ranges", "bytes")
        if size:
            self.send_header("Content-Length", size)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()



def run(server_class=HTTPServer, handler_class=MyHandler):
    server_address = ('', 8765)
    httpd = server_class(server_address, handler_class)
    httpd.ner = NER()
    print("READY")
    httpd.serve_forever()


run()

