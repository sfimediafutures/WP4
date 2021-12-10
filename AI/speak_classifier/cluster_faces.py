import os

from sklearn.cluster import DBSCAN
from imutils import build_montages
import numpy as np
import pickle
import cv2
import shutil
import time
import pickle
import json
import math

import face_recognition

from argparse import ArgumentParser

import queue
import threading


class FaceClusterer(queue.Queue):

    def __init__(self, image_list=[], jobs=6, img_dir=None, model="hog"):
        queue.Queue.__init__(self)
        self.jobs = jobs
        self.image_list = image_list
        self.data = []
        self.img_dir = img_dir
        self.detected_faces = {}
        self.model = model  # "hog" (CPU) or "cnn" on GPU
        self.added_images = []

        if 0:
            for i in range(jobs):
                t = threading.Thread(target=self._worker)
                t.daemon = True
                t.start()

    def add_task(self, task, *args, **kwargs):
        args = args or ()
        kwargs = kwargs or {}
        self.put((task, args, kwargs))

    def _worker(self):
        while True:
           item, args, kwargs = self.get()
           item(*args, **kwargs)
           self.task_done()

    def queued_add_image(self, *args, **kwargs):
        self.add_task(self._add_image, *args, **kwargs)

        print("Queued", self.qsize(), self.unfinished_tasks)

    def add_image(self, ts, image, min_faces=1, max_faces=1, save_dir=None, image_path=None, tunnel=None):
        """
        Try to add an image with a given timestamp. image needs to be a cv2 RGB image.

        If fewer or more than one face (or given values) is present it is ignored and None
        is returned, otherwise it is added to the list.
        If save_dir is given, the image is stored on disk too, otherwise image_path must be given

        Returns image path if added, None otherwise
        """
        if save_dir and image_path:
            raise Exception("Can't have both existing image file path and save directory")

        if not save_dir and not image_path:
            raise Exception("Need either image path or save dir")

        if save_dir:
            image_path = os.path.join(save_dir, "img_%.2f.jpg" % ts)

        # Did we already process this one?
        cache_file = image_path + ".encodings"
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                d = f.read()
                if len(d) == 0:
                    # No data in this file - it was wrong number of faces
                    return False
            info = pickle.loads(d)
            self.data.extend(info)

            self.detected_faces[info[0]["image_path"]] = [i["loc"] for i in info]
            self.added_images.append((tunnel, image_path))
            return image_path
            
        image.flags.writeable = False  # Apparently quicker

        print(time.time(), "Detecting faces in", image_path)
        # TODO: If we get things set up correctly we might use "cnn" as
        # detection method for better results, but it takes forever without
        # GPU acceleration
        boxes = face_recognition.face_locations(image)  # , model=detection_method)

        self.detected_faces[image_path] = boxes

        if len(boxes) > max_faces or len(boxes) < min_faces:
            # This image is no good, remember it
            with open(cache_file, "wb") as f:
                pass
            return None

        encodings = face_recognition.face_encodings(image, boxes)

        if save_dir:
            cv2.imwrite(image_path, image)

        d = [{"image_path": image_path, "loc": box, "encoding": enc}
             for (box, enc) in zip(boxes, encodings)]

        with open(cache_file, "wb") as f:
            f.write(pickle.dumps(d))

        self.data.extend(d)

        self.added_images.append((tunnel, image_path))
        return image_path


    def detect_faces(self, detection_method=None):

        for image_path in self.image_list:
            cache_file = image_path + ".encodings"
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    self.data.extend(pickle.loads(f.read()))
                continue

            image = cv2.imread(image_path)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False

            # We assume that the faces have been detected, this takes for EVER AND EVER
            if 1:
                print(time.time(), "Detecting faces in", image_path)
                boxes = face_recognition.face_locations(rgb)  # , model=detection_method)
                #if len(boxes) != 1:
                if len(boxes) == 0:
                   continue  # Ignore this one
                #print("   ", boxes)
            else:  # The whole image
                height, width, channels = image.shape
                boxes = [(0, width, 0, height)]
            encodings = face_recognition.face_encodings(rgb, boxes)
            d = [{"image_path": image_path, "loc": box, "encoding": enc}
                 for (box, enc) in zip(boxes, encodings)]

            with open(cache_file, "wb") as f:
                f.write(pickle.dumps(d))

            self.data.extend(d)

    def cluster_images(self, dst_dir=None, copy_files=True):
        """
        Cluster images in the dataset, returns the clusters in format
        {clusternr: [source_images]}

        If copy_files is given, they are copied into directories too
        """

        data = np.array(self.data)
        encodings = [d["encoding"] for d in data]

        # Try to cluster stuff
        print("Clustering %d images" % len(self.data))

        clt = DBSCAN(metric="euclidean", n_jobs=self.jobs)
        clt.fit(encodings)

        labelIDs = np.unique(clt.labels_)
        numUniqueFaces = len(np.where(labelIDs > -1)[0])
        print("[INFO] # unique faces: {}".format(numUniqueFaces))


        # Create a directory for each label for now (rather return this as a list)

        # loop over the unique face integers
        ret = {}
        for labelID in labelIDs:
            ret[int(labelID)] = []
            print("[INFO] faces for face ID: {}".format(labelID))
            idxs = np.where(clt.labels_ == labelID)[0]
            print(idxs)

            if dst_dir:
                path = os.path.join(dst_dir, str(labelID))
                print("SAVING TO '%s'" % path)
                if not os.path.exists(path):
                    os.makedirs(path)
                if copy_files:
                    shutil.copy(p, os.path.join(path, os.path.split(p)[1]))

            for idx in idxs:

                p = self.data[idx]["image_path"]
                ret[int(labelID)].append(p)


        self.clusters = ret
        return ret

    def parse_json(self, src_dir, jsonfile):

        skipped = 0
        with open(jsonfile, "r") as f:
            face_detections = json.load(f)

            for segment in face_detections:
                if "items" not in segment:
                    continue

                if len(segment["items"]) != 1:
                    skipped += 1
                    continue

                # Only one face, encode it
                image_path = os.path.join(src_dir, "img_%.2f.jpg" % segment["start"])

                if not os.path.exists(image_path):
                    raise Exception("Missing file '%s'" % image_path)

                image = cv2.imread(image_path)
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                height, width, channels = image.shape

                box = segment["items"][0]["box"]
                miny = math.floor(box["top"] * height)
                maxy = math.floor(box["bottom"] * height)
                minx = math.floor(box["left"] * width)
                maxx = math.floor(box["right"] * width)
                boxes = [[miny, maxx, maxy, minx]]
                print(segment["start"], "Boxes", boxes, box)
                encodings = face_recognition.face_encodings(rgb, boxes)
                d = [{"image_path": image_path, "loc": box, "encoding": enc}
                     for (box, enc) in zip(boxes, encodings)]

                self.data.extend(d)


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--src", dest="src", help="Source directory", required=True)
    parser.add_argument("--dst", dest="dst", help="Destination directory", required=True)
    parser.add_argument("-j", "--jobs", dest="jobs", help="Parallel jobs", default=1)
    parser.add_argument("--json", dest="json", help="JSON file with detections", default=None)


    options = parser.parse_args()


    if options.json is None:
        image_list = [os.path.join(options.src, x) for x in os.listdir(options.src) if x.endswith(".jpg")]
        clusterer = FaceClusterer(image_list, jobs=options.jobs)

        print(time.ctime(), "Detecting faces")
        clusterer.detect_faces()


        print(time.ctime(), "Clustering images")
        clusterer.cluster_images(options.dst)

    else:
        clusterer = FaceClusterer(jobs=options.jobs)
        clusterer.parse_json(options.src, options.json)
        clusterer.cluster_images(options.dst)

            
    print(time.ctime(), "All done")
