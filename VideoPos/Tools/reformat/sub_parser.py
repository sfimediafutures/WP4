"""Parse subtitle file (srt, vtt) and convert to JSON."""
import re


class SubParser:
    """Parse VTT/SRT files."""

    def __init__(self):
        self.items = []

    @staticmethod
    def time2sec(t):
        ms = re.split("[,\.]", t)[1]
        t = t[:-len(ms) - 1]
        h, m, s = t.split(":")
        ts = int(h) * 3600 + int(m) * 60 + int(s) + (int(ms) / 1000.)
        return ts

    def sec2time(t):

        h = m = s = ms = 0
        s = ""

        ms = t - int(t)
        t = int(t)

        s = t % 60
        t = (t - s) % 60

        m = t % 60
        h = (t - m % 60)
        return "%02d:%02d:%02d.%03d" % (h, m, s, ms)

    def write_vtt(self, filename, entries, header="FILE"):
        with open(filename, "w") as f:
            f.write("WEBVTT %s\n\n" % header)

            counter = 1
            for entry in entries:
                f.write("%d\n" % counter)
                counter += 1
                f.write("%s --> %s\n" %
                        (SubParser.sec2time(entry["start"]), SubParser.sec2time(entry["end"])))

                for text in entry["text"].split("<br>"):
                    f.write("%s\n" % text)
                f.write("\n")

    def load_srt(self, filename, default_who=None):
        with open(filename, "rb") as f:

            start = end = None
            text = ""

            for line in f.readlines():
                line = line.decode("utf-8").strip()
                if text and line.startswith("-"):
                    # print("Continuation", line)
                    s = {
                        "start": SubParser.time2sec(start) + 0.01,
                        "end": SubParser.time2sec(end),
                        "text": line[1::].strip()}
                    if default_who:
                        s["who"] = default_who
                    self.items.append(s)
                    # text = ""
                    continue
                elif line.startswith("-"):
                    line = line[1:]

                if line.strip() == "":
                    # print("End of comment", text)
                    # End of comment
                    if text and start and end:
                        s = {
                            "start": SubParser.time2sec(start),
                            "end": SubParser.time2sec(end),
                            "text": text
                        }
                        if default_who:
                            s["who"] = default_who

                        self.items.append(s)
                    start = end = None
                    text = ""
                    continue
                if re.match("^\d+$", line):
                    # Just the index, we don't care
                    continue

                m = re.match("(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", line.replace(".", ","))
                if m:
                    start, end = m.groups()
                    continue

                # print("TEXT", text, "LINE", line)
                if text and text[-1] != "-":
                    text += "<br>"
                    text += line
                else:
                    text = text[:-1] + line  # word has been divided

        return self.items


if __name__ == "__main__":
    import sys
    parser = SubParser()
    parser.load_srt(sys.argv[1])
    print(parser.items)
