import re
import json
from argparse import ArgumentParser
from operator import attrgetter

from sub_parser import SubParser

parser = ArgumentParser()
parser.add_argument("-s", "--subtitle", dest="sub", help="Subtitle file", required=True)
parser.add_argument("-o", "--output", dest="output", help="Output file", required=False)
parser.add_argument("--who", dest="who", help="Default who (if any)", required=False, default=None)

parser.add_argument("-a", "--append_to", dest="append", help="JSON file to append to", required=False)

parser.add_argument("--sort", dest="sort", help="Sort if appending", default=False, required=False)

options = parser.parse_args()


parser = SubParser()

parser.load_srt(options.sub, default_who=options.who)

if options.append:
    items = json.load(open(options.append, "r"))

    # Merge
    items.extend(parser.items)

    if options.sort:
        items = sorted(items, key=attrgetter["start"])
else:
    items = parser.items

if options.output:
    json.dump(items, open(options.output, "w"), indent=" ")
else:
    print(json.dumps(items, indent=" "))
