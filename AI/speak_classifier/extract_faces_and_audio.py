#!/bin/env python3
import os
import math
import subprocess
import cv2
import json
import random

from argparse import ArgumentParser

from VideoPos.Tools.detect_voice import VoiceDetector
# from AI.mediapipe import analyze
from AI.speak_classifier.cluster_faces import FaceClusterer



class Extractor:

    def __init__(self, src, dst, options):
        self.src = src
        self.dst = dst
        self.aggressive = options.aggressive
        self.segments = []
        self.options = options

        self.clusterer = FaceClusterer()

    def extract_audio(self):
        detector = VoiceDetector(self.src, output_dir=self.dst)
        return detector.analyze(aggressive=self.aggressive, max_segment_length=10)


    def _to_timestamp(self, ts):
        s = ""
        # hours
        if ts > 3600:
            h = math.floor(ts/3600)
            ts -= h * 3600
            s += "%02d:" % h
        else:
            s += "00:"

        if ts > 60:
            m = math.floor(ts/60)
            ts -= m * 60
            s += "%02d:" % m
        else:
            s += "00:"
        s += "%02f" % ts
        return s


    def extract_faces(self, save_dir):
        """
        Use face_detector
        """

        cap = cv2.VideoCapture(self.src)

        ret = []
        segment_idx = 0
        last_ts = 0
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.

            # We only want to extract some faces in each segment

            if ts > self.segments[segment_idx]["end"]:
                # We're at the end of this segment
                segment_idx += 1
                print(" - SEGMENT", segment_idx, "of", len(self.segments), " %.2f" % self.segments[segment_idx-1]["start"])

            if segment_idx > len(self.segments) - 1:
                print("Done with all segments")
                # Extracted for all segments
                break

            if ts < self.segments[segment_idx]["start"]:
                continue

            # At most 1hz
            if ts - last_ts < 1.0:
                continue

            if 1:
                facepath = os.path.join(self.dst, "img_%.02f.jpg" % ts)
                cv2.imwrite(facepath, image)
                last_ts = ts

            image_path = self.clusterer.add_image(ts, image, save_dir=save_dir, tunnel=segment_idx)
            if image_path:
                    if "faceimg" not in self.segments[segment_idx]:
                        self.segments[segment_idx]["faceimg"] = []
                    self.segments[segment_idx]["faceimg"].append(image_path)

        if 0:
            # Wait for processing to end

            print("Waiting for jobs to complete")
            self.clusterer.join()

            print("Clustering done, rebuilding return values")
            for segment_idx, image_path in self.clusterer.added_images:
                if image_path:
                    if "faceimg" not in self.segments[segment_idx]:
                        self.segments[segment_idx]["faceimg"] = []
                    self.segments[segment_idx]["faceimg"].append(image_path)


    def old_extract_faces(self, crop=True):
        """
        Uses mediapipes to extract faces directly from the video        
        """
        self.options.selfie = False
        self.options.tile = False
        self.options.show = False

        face_analyzer = analyze.Analyzer(self.options)
        cap = cv2.VideoCapture(self.src)

        ret = []
        segment_idx = 0
        last_ts = 0
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.

            # We only want to extract some faces in each segment

            if ts > self.segments[segment_idx]["end"]:
                # We're at the end of this segment
                segment_idx += 1
                print(" - SEGMENT", segment_idx, "of", len(self.segments))

            if segment_idx > len(self.segments) - 1:
                print("Done with all segments")
                # Extracted for all segments
                break

            if ts < self.segments[segment_idx]["start"]:
                continue

            # At most 1hz
            if ts - last_ts < 1.0:
                continue

            if 1:
                facepath = os.path.join(self.dst, "img_%.02f.jpg" % ts)
                cv2.imwrite(facepath, image)
                last_ts = ts
                continue

                if "faceimg" not in self.segments[segment_idx]:
                    self.segments[segment_idx]["faceimg"] = []
                self.segments[segment_idx]["faceimg"].append(facepath)
            analysis = face_analyzer.analyze(image, ts, options)
            if not analysis:
                continue

            # If anything is detected lower than 70% secure, dismiss it
            for face in analysis["faces"]:
                if face["value"] < 0.7:
                    analysis["faces"].remove(face)

            if len(analysis["faces"]) == 1:
                face = analysis["faces"][0]
                if face["heading"] == "sideview":
                    # print(" ** ignoring sideview")
                    continue
                last_ts = ts
                if face["value"] < 0.7:
                    print("WTF, got a good face apparently, but it's shit!")
                    continue

                if crop:
                    # print("  %.2f" % ts, "Got ONE good face, extracting it", face["value"], face)

                    # Extract this image - we want them all in 196x196 tiles, but
                    # first we need to extract the bounding box, which is relative
                    height, width, channels = image.shape
                    miny = int(face["box"]["bottom"] * height / 100)
                    maxy = int(face["box"]["top"] * height / 100)
                    minx = int(face["box"]["left"] * width / 100)
                    maxx = int(face["box"]["right"] * width / 100)

                    # We want the box square, so make the shortest side longer( it
                    # might already be square but it might not really do anything wrong?
                    if 1:
                        x = maxx - minx
                        y = maxy - miny
                        if x < y:
                            maxx += (y/x) / 2
                            minx -= (y/x) / 2
                        elif y < x:
                            maxy += (x/y) / 2
                            miny -= (x/y) / 2

                    subimg = image[int(miny):int(maxy), int(minx):int(maxx)]
                    # subimg = np.asarray(subimg, order='C')

                    # Resize
                    faceimg = cv2.resize(subimg, (196, 196))
                else:
                    faceimg = image

                facepath = os.path.join(self.dst, "face_%.02f.png" % ts)
                cv2.imwrite(facepath, faceimg)

                if "faceimg" not in self.segments[segment_idx]:
                    self.segments[segment_idx]["faceimg"] = []
                self.segments[segment_idx]["faceimg"].append(facepath)

                if 0:
                    cv2.imshow("Resized", faceimg)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()



    def extract_images(self):

        print("Extracting files...")
        numfiles = 0
        # Extract images and add to the segments
        for idx, segment in enumerate(self.segments):
            print("   %d of %d" % (idx, len(self.segments)))
            segment["images"] = []
            ts = segment["start"]
            while ts < segment["end"]:
                start = self._to_timestamp(ts)
                ts += 1
                img_name = "img_%05.2f.png" % ts
                cmd = "ffmpeg -accurate_seek -ss %s -i %s -frames:v 1 %s" % \
                      (start, self.src, os.path.join(self.dst, img_name))
                subprocess.getoutput(cmd)  # Might throw exception, but if that's the case, it's correct

                segment["images"].append(os.path.join(self.dst, img_name))

                numfiles += 1

                # We'll add these files to the segment

        print("Extracted %d files" % numfiles)

    def _clean_segments(self):
        """
        Remove ones we don't want
        """
        cleaned = 0
        for segment in self.segments:
            if "faceimg" not in segment:
                self.segments.remove(segment)
                continue

            if len(segment["faceimg"]) <= 1:
                self.segments.remove(segment)
                # Remove the files too
                for filename in segment["faceimg"]:
                    cleaned += 1
                    print("Should remove filename", filename)
                    os.remove(filename)
                continue

        print("Cleaned %d image files" % cleaned)

    def _update_segments(self, clusters):
        """
        Expects clusters as {clusterid: [filename1, filename2, ...]}
        """

        # Reverse index
        idx = {}
        for cluster in clusters:
            for fn in clusters[cluster]:
                idx[fn] = cluster

        for segment in self.segments:
            face_id = None
            if "faceimg" in segment:
                for f in segment["faceimg"]:
                    if f not in idx:
                        print(" *** Woops, segment image is not in index???", f)
                        print(" --- Segment was:", segment)
                        face_id = None
                        break

                    if face_id is None:
                        face_id = idx[f]
                    elif face_id != idx[f]:
                        print(" *** Different faces in this segment, we should ignore it", segment)
                        self.segments.remove(segment)
                        face_id = None
                        break

            if face_id is not None:
                segment["castid"] = int(face_id)

    def _define_cast(self, cast_dir, clusters, detected_faces):
        if not os.path.exists(cast_dir):
            os.makedirs(cast_dir)

        # Pick some faces for each cast memeber
        for cluster in clusters:
            # For now we pick a few random face images

            person_dir = os.path.join(cast_dir, str(cluster))

            if not os.path.exists(person_dir):
                os.makedirs(person_dir)


            all_faces = clusters[cluster]

            # print("Checking cluster", cluster, "with", len(all_faces), "faces")
            for idx, f in enumerate(random.sample(all_faces, min(10, len(all_faces)))):
                if f not in detected_faces:
                    raise Exception("Missing face detection for image '%s'" % f)
                box = detected_faces[f][0]

                # The box is just the actual face, we need it to be more like
                # twice the size to be useful
                miny,maxx, maxy,minx = box

                height = maxy - miny
                width = maxx - minx

                # Target is bigger than just the faces
                image = cv2.imread(f)
                orig_height, orig_width, _ = image.shape
                miny = max(0, miny - math.floor(height/2.))
                maxy = min(orig_height, maxy + math.floor(height/2.))
                minx = max(0, minx - math.floor(width/2.))
                maxx = min(orig_width, maxx + math.floor(width/2.))

                # Open the image and crop it
                subimg = image[int(miny):int(maxy), int(minx):int(maxx)]

                # Resize?
                faceimg = cv2.resize(subimg, (196, 196))
                cv2.imwrite(os.path.join(person_dir, "%s_%d.jpg" % (cluster, idx)), faceimg)


    def run(self):

        self.segments = self.extract_audio()

        print("Got audio %d segments and files" % len(self.segments))

        self.extract_faces(self.options.dst)

        # self.extract_images()

        # We don't clean now, let the process run first
        # self._clean_segments()

        # We should now cluster the images
        clusters = self.clusterer.cluster_images()
        print("CLUSTERS", json.dumps(clusters, indent=" "))


        input("Press enter to continue")
        # Update segments with the clustered images
        self._update_segments(clusters)

        # Select some faces for each person?
        self._define_cast(os.path.join(self.options.dst, "cast"), clusters, self.clusterer.detected_faces)

        print("CLUSTERS", json.dumps(clusters, indent=" "))


    def get_stats(self):
        """
        Provide stats to check if there is enough data
        """

        cast = {"unclassified": 0}

        for segment in self.segments:
            if "castid" in segment:
                if segment["castid"] not in cast:
                    cast[segment["castid"]] = 0
                cast[segment["castid"]] += segment["end"] - segment["start"]
            else:
                cast["unclassified"] += segment["end"] - segment["start"]

        return cast



    def save_json(self, destination):

        with open(destination, "w") as f:
            json.dump(self.segments, f, indent=" ")


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-i", "--input", dest="src", help="Source audio/video file", required=True)
    parser.add_argument("-o", "--output", dest="dst", help="Output directory", required=True)

    parser.add_argument("-a", "--aggressive", dest="aggressive", help="How aggressive (0-3, 3 is most aggressive)", default=2)


    options = parser.parse_args()

    if not os.path.exists(options.dst):
        os.makedirs(options.dst)

    extractor = Extractor(options.src, options.dst, options)

    extractor.run()

    extractor.save_json(os.path.join(options.dst, "segments.json"))

    cast = extractor.get_stats()
    print("CAST")
    print(json.dumps(cast, indent=" "))
