#!/bin/bash

# ffmpeg -f lavfi -i color=c=black \
#       -i $1 \
#       -filter_complex  \
#            "[1:v]chromakey=0x70de77:0.1:0.3[ckout]; \
#            [0:v][ckout]overlay[out]"  \
#       -map "[out]"  output.webm


ffmpeg \
  -i $1 \
  -b:v 1M \
  -vf chromakey=0x81da66:0.15:0.025\
  -c:v libvpx \
  -pix_fmt yuva420p \
  -metadata:s:v:0 alpha_mode="1" \
  -auto-alt-ref 0 \
  output.webm

#-filter:v "crop=360:360:220:0" \
  #-vf chromakey=0x70de77:0.1:0.3\

