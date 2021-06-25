import json

from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('inputs', metavar='N', type=str, nargs='+',
                    help='Input files')
parser.add_argument("-o", "--output", dest="output", help="Output file", required=True)

options = parser.parse_args()


data = None

for i in options.inputs:
    with open(i, "r") as f:
        d = json.load(f)
        print("LOADED", d.__class__)
        if isinstance(d, list):
            if data is None:
                data = []
            data.extend(d)
        else:
            if data is None:
                data = {}
            for key in d:
                data[key] = d[key]


with open(options.output, "w") as f:
    json.dump(data, f, indent=" ")