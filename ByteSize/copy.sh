#!/bin/bash
python3 merge_episodes.py
rsync Episodes/*json Episodes/*mp3 html/Episodes/
rsync -r html/* seer2.itek.norut.no:/var/www/html/ByteSize/
