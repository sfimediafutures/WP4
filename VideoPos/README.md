### Process a video

Examples processing an episode of "Vikingane" in "res/Vikingane/"

Encode video to proper format - lots of the ones I get have iframes every 5 seconds, not on scene changes. NRK are letterboxed to (at least the things I got), so run:
ffmpeg -i originalvideo -b:v 1500k -filter:v "crop=1280:640:0:40" thing_sXXeYY.mp4

Process audio too:
ffmpeg -i originalvideo -vn thing_sXXeYY.m4a

## Do some more AI processing
Create iframes (pngs + metadata.json):
video_to_iframe_dir.py -i <videofile> -o <destinationdir> -w <webroot> (e.g. /sfi/res/Vikingane/)

Analyze iframes (creates aux_ai.json):
AI/clarifai.py -i metadata.json -o ../bbt_s07e10_aux_ai.json

Extract faces (if wanted, creates pngs):
VideoPos/Tools/extract_people_from_iframes.py --iframes iframes_s07e10/metadata.json --aux bbt_s07e10_aux_ai.json -o /tmp/test/s07e10/

Create subtitle json:
VideoPos/Tools/nrk_dialogsub2json.py -s <srtfile> -d <transcript> -o <dest sub.json> -c <castfile (optional)> -u <weburl for cast files>

Try to ensure that positions are good based on detecting the cast (if trained AI)
srt+video2subs.py -i <videofile> --sub <subjson> --o <updatedsubfile> -a <updated aux.json> --workflow <workflow name - trained on this cast> --aux <inputauxfile>


## Sync subtitles

Detect voice track:

### Create index file of voices first (optional)
detect_voice.py -i <videofile.mp4/.wav> -o <voiceindex.json>

Index file is added to manifest as "voiceindex"

### Realign json subs (suggest using the chat_view using voiceindex as mentioned above, this will create a quite good result with little effort)

Chat view is loaded using chat_style.html?url=<manifest.json>?edit=true

detect_voice.py -i <videofile.mp4/.wav> --sub <UpdatedSubs.json> -o <sync_subs.json> 

