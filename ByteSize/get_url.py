import re
import requests

def remove_text_with_number(input_string):


    pattern = r'\w*\*?\s*\[\d+\]\s*'
    # pattern matches any text of the form "  * [4] sometext"

    output_string = re.sub(pattern, '', input_string)
    # removes all matches of the pattern from the input string

    return output_string


def clean_text(text):
    # Remove lines that start with "* or ["
    pattern = r'\w*[\*\[].*'
    text = re.sub(pattern, '', text)

    # Remove short paragraphs
    pattern = r'^\S+[^\n]*\n\n(\s+\S+.*\n){,4}\n(?=^\S+)'
    text = re.sub(pattern, '', text, flags=re.MULTILINE)


    # Remove lines that are a "heading" and multiple blank lines
    pattern = r'^\S+\s*\n\n\n+'
    text = re.sub(pattern, '', text, flags=re.MULTILINE)

    # Remove super-short paragraphs - single indented lines
    # pattern = r'\n\s+\S+\n{2,}'
    pattern = r'\n(\s+\S+\n)+\n'
    text = re.sub(pattern, '\n', text, flags=re.MULTILINE)

    # Remove lines with only whitespaces
    text = re.sub("\s+\n", '\n', text, flags=re.MULTILINE)

    # Remove all the text before the first "header"
    pattern = r'^\s+.*\n(?=^\S)'
    text = re.sub(pattern, '', text, flags=re.MULTILINE)
    return text 

def remove_duplicate_lines(text):
    """
    If we find duplicate lines, remove all
    """
    lines = text.split("\n")
    different = {}
    for line in lines:
        if line not in different:
            different[line] = 0
        else:
            different[line] += 1
    newlines = [line for line in lines if different[line] == 0]

    return "\n".join(newlines)


def run_lynx(source):

    import subprocess
    cmd = ["lynx", "-dump", "-nolist", "-assume_charset=utf-8", "-display_charset=utf-8", "-pseudo_inlines"]
    cmd.append(source)
    print("Fetching", source)
    text = subprocess.getoutput(" ".join(cmd))
    print("Got page")
    return text

def read_url(url):
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception("Bad url '{}', code {}".format(url, r.status_code))
    return r.text


def read_file(filename):
    with open(filename, "rb") as f:
        text = f.read().decode("utf-8")
    return text


def url_to_string(url):
    text = run_lynx(url)
    text = clean_text(text)
    text = remove_duplicate_lines(text)
    return text

if __name__ == "__main__":
    import sys

    text = run_lynx(sys.argv[1])

    if 0:
        if sys.argv[1].startswith("http"):
            text = read_url(sys.argv[1])
        else:
            text = read_file(sys.argv[1])

    text = clean_text(text)
    text = remove_duplicate_lines(text)

    print(text)
