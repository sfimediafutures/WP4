#!/bin/env python3

"""AI analysis of iframes from a video."""
import os.path
import json
import operator

from argparse import ArgumentParser

from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2



channel = ClarifaiChannel.get_grpc_channel()

# Note: You can also use a secure (encrypted) ClarifaiChannel.get_grpc_channel() however
# it is currently not possible to use it with the latest gRPC version

stub = service_pb2_grpc.V2Stub(channel)

# This will be used by every Clarifai endpoint call.
# BBT
metadata = (('authorization', 'Key ...'),)

# NRK
# metadata = (('authorization', 'Key ....'),)


models = {
    "general": "9f54c0342741574068ec696ddbebd699",
    "faces": "f76196b43bbd45c99b4f3cd8e8b40a8a",
    "text": "75a5b92a0dec436a891b5ad224ac9170"
}

workflows = {
    "bbt": "bbt_tag_cast",
    "vikingane": "vikingane_tag_cast"
}

metadatas = {
    "bbt": (('authorization', 'Key d5df25707e5a48ed8640a6b7d94947db'),),
    "vikingane": (('authorization', 'Key 48c95749d90b474db1e4890786be3492'),)
}

def bulk_analyze(filelist, model=None, workflow=None, batch_size=24):
    """
    Analyze any number of files, but process them in batches.
    """
    ret = []
    idx = 0
    while idx < len(filelist):
        l = filelist[idx:idx + int(batch_size)]
        idx += len(l)

        r = analyze(l, model, workflow)
        ret.extend(r)
    return ret

def analyze(filelist, model=None, workflow=None):
    """
    Analyze a list of files with the given model or workflow.
    Need ONE

    Uses Clarifai and requires analysis with video_to_iframe_dir.py.
    """
    if workflow:
        metadata = metadatas[workflow]
    else:
        metadata = metadatas["bbt"]  # Default

    if model and not model in models:
        raise Exception("Unknown model '%s', have %s" % (model, models.keys()))
    if workflow and not workflow in workflows:
        raise Exception("Unknown workflow '%s', have %s" % (workflow, workflows.keys()))
    if not model and not workflow:
        raise Exception("Missing model or workflow")

    inputs = []
    for filename in filelist:
        # This is how you authenticate.
        if not filename.startswith("http"):
            with open(filename, "rb") as f:
                data = f.read()

        ext = os.path.splitext(filename)[1]
        if ext in [".png", ".jpg"]:
            if filename.startswith("http"):
                print("HTTP link")
                data = resources_pb2.Data(image=resources_pb2.Image(url=filename))
            else:
                data = resources_pb2.Data(image=resources_pb2.Image(base64=data))
            inputs.append(resources_pb2.Input(data=data))
        else:
            raise Exception("Unknown file format %s" % ext)

    if model:
        response = stub.PostModelOutputs(
            service_pb2.PostModelOutputsRequest(
                model_id=models[model],
                inputs=inputs
            ),
            metadata=metadata
        )
        if response.status.code != status_code_pb2.SUCCESS:
            raise Exception("Post model outputs failed, status: " + response.status.description)
        results = response.outputs
    else:
        print("Using workflow", workflow, workflows[workflow])
        response = stub.PostWorkflowResults(
            service_pb2.PostWorkflowResultsRequest(
                workflow_id=workflows[workflow],
                inputs=inputs
            ),
            metadata=metadata
        )

        if response.status.code != status_code_pb2.SUCCESS:
            raise Exception("Workflow failed, status: " + response.status.description)

        results = [r.outputs[1] for r in response.results]

        print("RESPONSE")
        # print(results[0].outputs[1].data)

    retval = []

    for output in results:
        reply = {"items": [], "concepts": {}}
        for concept in output.data.concepts:
            if concept.value < 0.01:
                continue
            print('%12s: %.2f' % (concept.name, concept.value))
            reply["concepts"][concept.name] = concept.value

        for region in output.data.regions:
            name = region.data.concepts[0].name
            if model == "faces":
                name = "face"
            box = region.region_info
            item = {
                "name": name,
                "box": {
                    "left": box.bounding_box.left_col,
                    "right": box.bounding_box.right_col,
                    "top": box.bounding_box.top_row,
                    "bottom": box.bounding_box.bottom_row
                },
                "value": region.value
            }
            item["size"] = (item["box"]["right"] - item["box"]["left"]) * \
                           (item["box"]["bottom"] - item["box"]["top"])
            item["posX"] = int(100 * (item["box"]["left"] +
                               (item["box"]["right"] - item["box"]["left"]) / 2))
            item["posY"] = int(100 * (item["box"]["top"] + (item["box"]["bottom"] -
                               item["box"]["top"]) / 2))
            reply["items"].append(item)

        print("Adding reply", reply)
        retval.append(reply)

    return retval


def general_positioning(filelist, cached_faces=None):
    """
    Try to position all the iframes - this is done by first looking for people
    in the frames. If people are detected, the largest face is used, the
    others made available as alternatives. For frames with *no* faces
    detected, a general analysis is performed, and analyzed for possibly
    important stuff. Alternatives are highly likely in that case.
    """

    if cached_faces:
        res = cached_faces
    else:
        res = analyze(filelist, "faces")

    # Go through the results and find frames that have *no* faces
    reprocess = []
    missing = 0
    ok = 0
    for idx, frame in enumerate(res):
        if "items" not in frame or frame["items"] == []:
            reprocess.append(filelist[idx])
            frame["idx"] = idx
            frame["missingidx"] = missing
            missing += 1
        else:
            ok += 1

    print("%d ok, %d missing positioning" % (ok, missing))

    tmp_file = "/tmp/tmpanalysis2.json"

    if os.path.exists(tmp_file):
        generic_analysis = json.loads(open(tmp_file, "r").read())
    else:
        generic_analysis = bulk_analyze(reprocess, model="general")

    print(generic_analysis)
    try:
        open(tmp_file, "w").write(json.dumps(generic_analysis, indent=" "))
    except Exception as e:
        print("Exception writing results", e)

    # We now analyze the indexes
    for frame in generic_analysis:
        analyze_generic_frame(frame)

        print("Analyzed to", frame)

    # Merge
    for idx, frame in enumerate(res):
        if "missingidx" in frame:
            print("Merging", frame)
            res[frame["idx"]] = generic_analysis[frame["missingidx"]]

    return res


def analyze_generic_frame(frame):
    """
    Amalyse a generic frame
    """

    items = frame["items"]

    concepts = {}
    for item in items:
        if item["name"] not in concepts:
            concepts[item["name"]] = 0
        concepts[item["name"]] += 1

    print("FRAME CONCEPTS", concepts)

    # Now we calculate a sort of "importance" metric - if we're unsure, we
    # will regard things as less important and things that are present
    # many places is of less interest
    for item in items:
        if item["value"] < 0.5:
            item["importance"] = 0
            continue

        item["importance"] = (item["value"] * 5 * item["size"] / (
                              float(concepts[item["name"]])))

    # Sort by importance
    frame["focus"] = sorted(items, key=operator.itemgetter("importance"), reverse=True)

    # Set the position to the most important one
    if len(frame["focus"]) > 0:
        frame["posX"] = frame["focus"][0]["posX"]
        frame["posY"] = frame["focus"][0]["posY"]

if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-b", "--base", dest="base", help="BaseURL", default="/var/www/html/", required=False)
    parser.add_argument("-i", "--input", dest="input", help="Input file (timestamps)",
                        required=True)
    parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)
    parser.add_argument("--start", dest="start", help="Start time", required=False, default=None)
    parser.add_argument("--end", dest="end", help="End time", required=False, default=None)
    parser.add_argument("--estimate", dest="estimate", help="Only estimate number of pictures",
                        action="store_true", default=False)
    parser.add_argument("-m", "--model", dest="model", help="Model for analysis", default="full")
    parser.add_argument("-w", "--workflow", dest="workflow", help="Workflow for analysis", default="")

    options = parser.parse_args()

    if options.workflow:
        options.model = None

    # analyze("/home/njaal/git/MediaFutures/res/Exit2/test/img392.png", "faces")
    # a = analyze("/home/njaal/git/MediaFutures/res/Exit2/test/img392.png", "general")
    # open("output.json", "w").write(json.dumps(a, indent=" "))

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

    if options.model == "full":

        if os.path.exists(cache_file):
            a = json.loads(open(cache_file, "r").read())
            a = general_positioning(files, cached_faces=a)
        else:
            a = bulk_analyze(files, "faces")
            open(cache_file, "w").write(json.dumps(a, indent=" "))
            print("Written to", cache_file)

            # Now we do the general positioning too
            a = general_positioning(files, cached_faces=a)

    else:
        # Just run a single model
        a = bulk_analyze(files, options.model, options.workflow)

    # Go through results and hook them up
    aux_data = []
    for idx, res in enumerate(a):
        frame = iframes[start_idx + idx]

        # If we have multiple results, we're in a bit of a pickle - choose the largets one
        # and store the alternative positions
        for item in res["items"]:
            item["size"] = (item["box"]["right"] - item["box"]["left"]) * \
                           (item["box"]["bottom"] - item["box"]["top"])
            item["posX"] = int(100 * (item["box"]["left"] +
                               (item["box"]["right"] - item["box"]["left"]) / 2))
            item["posY"] = int(100 * (item["box"]["top"] + (item["box"]["bottom"] -
                               item["box"]["top"]) / 2))

        data = {
            "start": frame["ts"],
            "end": frame["endts"]
        }

        if "focus" not in frame:
            by_size = sorted(res["items"], key=operator.itemgetter("size"), reverse=True)

            if len(by_size) > 0:
                data["pos"] = [by_size[0]["posX"], by_size[0]["posY"]]

            if options.model == "faces":
                if len(by_size) > 1:
                    data["alt"] = by_size
            else:
                if "items" in res:
                    data["items"] = res["items"]
                if "concepts" in res:
                    data["contepts"] = res["concepts"]
        else:
            data["pos"] = [frame["posX"], frame["posY"]]
            if len(frame["focus"]) > 1:
                data["alt"] = frame["focus"]

        aux_data.append(data)

    open(options.output, "w").write(json.dumps(aux_data, indent=" "))
