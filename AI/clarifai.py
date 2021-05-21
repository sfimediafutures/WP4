import os.path
import json
import sys
import operator

import re
import json
from argparse import ArgumentParser
from operator import attrgetter

from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_pb2, status_code_pb2

channel = ClarifaiChannel.get_grpc_channel()

# Note: You can also use a secure (encrypted) ClarifaiChannel.get_grpc_channel() however
# it is currently not possible to use it with the latest gRPC version

stub = service_pb2_grpc.V2Stub(channel)

# This will be used by every Clarifai endpoint call.
metadata = (('authorization', 'Key d5df25707e5a48ed8640a6b7d94947db'),)


models = {
    "general": "9f54c0342741574068ec696ddbebd699",
    "faces": "f76196b43bbd45c99b4f3cd8e8b40a8a"
}

def analyze(filelist, model):

    inputs = []
    for filename in filelist:
        # This is how you authenticate.
        if not filename.startswith("http"):
            with open(filename, "rb") as f:
                data = f.read()

        ext = os.path.splitext(filename)[1]
        if ext in [".png", ".jpg"]:
            file_type = "image"
            if filename.startswith("http"):
                print("HTTP link")
                data = resources_pb2.Data(image=resources_pb2.Image(url=filename))
            else:
                data = resources_pb2.Data(image=resources_pb2.Image(base64=data))
            inputs.append(resources_pb2.Input(data=data))
        else:
            raise Execption("Unknown file format %s" % ext)

    response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            model_id=models[model],
            inputs=inputs
        ),
        metadata=metadata
    )
    retval = []
    if response.status.code != status_code_pb2.SUCCESS:
        raise Exception("Post model outputs failed, status: " + response.status.description)

    for output in response.outputs:
        reply = {"items": [], "concepts": []}
        for concept in output.data.concepts:
            print('%12s: %.2f' % (concept.name, concept.value))
            reply["concepts"][concept.name] = concept.value
            print(dir(concept))

        for region in output.data.regions:
            name = region.data.concepts[0].name
            if model == "faces":
                name = "face"
            box = region.region_info
            reply["items"].append({
                "name": name,
                "box": {
                    "left": box.bounding_box.left_col,
                    "right": box.bounding_box.right_col,
                    "top": box.bounding_box.top_row,
                    "bottom": box.bounding_box.bottom_row
                },
                "value": region.value
            })
        print("Adding reply", reply)
        retval.append(reply)

    return retval


def analyze_image():
    request = service_pb2.PostModelOutputsRequest(
        # This is the model ID of a publicly available General model. You may use any other public or custom model ID.
        model_id=models[model],
        inputs=[
          #resources_pb2.Input(data=resources_pb2.Data(image=resources_pb2.Image(url='YOUR_IMAGE_URL')))
            resources_pb2.Input(data=resources_pb2.Data(image=resources_pb2.Image(url='YOUR_IMAGE_URL')))
        ])
    response = stub.PostModelOutputs(request, metadata=metadata)

    if response.status.code != status_code_pb2.SUCCESS:
        raise Exception("Request failed, status code: " + str(response.status.code))

    for concept in response.outputs[0].data.concepts:
        print('%12s: %.2f' % (concept.name, concept.value))



if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-b", "--base", dest="base", help="BaseURL", default="", required=False)
    parser.add_argument("-i", "--input", dest="input", help="Input file (timestamps)", required=True)
    parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)
    parser.add_argument("--start", dest="start", help="Start time", required=False, default=None)
    parser.add_argument("--end", dest="end", help="End time", required=False, default=None)
    parser.add_argument("--estimate", dest="estimate", help="Only estimate number of pictures", action="store_true", default=False)
    parser.add_argument("-m", "--model", dest="model", help="Model for analysis", default="faces")

    options = parser.parse_args()

#    analyze("/home/njaal/git/MediaFutures/res/Exit2/test/fragment_02.mp4", "general")

    #analyze("/home/njaal/git/MediaFutures/res/Exit2/test/img392.png", "faces")
    # a = analyze("/home/njaal/git/MediaFutures/res/Exit2/test/img392.png", "general")
    #open("output.json", "w").write(json.dumps(a, indent=" "))

    if os.path.exists(options.output):
        raise SystemExit("%s already exists" % options.output)

    with open(options.input, "r") as f:
        meta = json.loads(f.read())

    iframes = sorted(meta["iframes"], key=operator.itemgetter("ts"))
    for idx, frame in enumerate(iframes):
        if idx < len(iframes) - 1:
            frame["endts"] = iframes[idx + 1]["ts"]
        else:
            frame["endts"] = frame["ts"] + 100

    # If we have start/stop times, find the indexes and stop them there
    start_idx = end_idx = None
    if options.start:
        if not options.end:
            options.end = 1000000000000

        for idx, frame in enumerate(iframes):
            if start_idx is None and frame["ts"] > float(options.start):
                start_idx = idx

            if end_idx is None and frame["endts"] > float(options.end):
                end_idx = idx + 1
                break

    print("Will process between", start_idx, "and", end_idx)

    # We now have a list of iframes - rock on!
    files = [options.base + x["url"] for x in meta["iframes"]]
    if start_idx:
        if not end_idx:
            end_idx = -1
        files = files[start_idx:end_idx]
    else:
        start_idx = 0

    print("Analyze", len(files), "files")
    cache_file = "%s_temp_%s-%s.json" % (options.model, start_idx, end_idx)
    if options.estimate:
        raise SystemExit()
    if os.path.exists(cache_file):
        a = json.loads(open(cache_file, "r").read())
    else:
        a = analyze(files, options.model)
        open(cache_file,  "w").write(json.dumps(a, indent=" "))

    print("Written to", cache_file)

    # Go through results and hook them up
    aux_data = []
    for idx, res in enumerate(a):
        frame = iframes[start_idx + idx]


        # If we have multiple results, we're in a bit of a pickle - choose the largets one 
        # and store the alternative positions
        for item in res["items"]:
            item["size"] = (item["box"]["right"] - item["box"]["left"]) * \
                           (item["box"]["bottom"] - item["box"]["top"])
            item["posX"] = int(100 * (item["box"]["left"] + (item["box"]["right"] - item["box"]["left"]) / 2))
            item["posY"] = int(100 * (item["box"]["top"] + (item["box"]["bottom"] - item["box"]["top"]) / 2))

        by_size = sorted(res["items"], key=operator.itemgetter("size"), reverse=True)
        data = {
            "start": frame["ts"],
            "end": frame["endts"]
        }

        if len(by_size) > 0:
            data["pos"] = [by_size[0]["posX"], by_size[0]["posY"]]

        if options.model == "faces":
            if len(by_size) > 1:
                data["alt"] = by_size
        else:
            data["items"] = res["items"]

        aux_data.append(data)

    open(options.output, "w").write(json.dumps(aux_data, indent=" "))
