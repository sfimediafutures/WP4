import os

from sklearn.cluster import DBSCAN
from imutils import build_montages
import numpy as np
import pickle
import cv2
import shutil
import time
import pickle

import face_recognition

from argparse import ArgumentParser




class FaceClusterer:

    def __init__(self, image_list=[], jobs=4, img_dir=None):
        self.jobs = jobs
        self.image_list = image_list
        self.data = []
        self.img_dir = img_dir
        self.detected_faces = {}

    def add_image(self, ts, image, min_faces=1, max_faces=1, save_dir=None, image_path=None):
        """
        Try to add an image with a given timestamp. image needs to be a cv2 RGB image.

        If fewer or more than one face (or given values) is present it is ignored and None
        is returned, otherwise it is added to the list.
        If save_dir is given, the image is stored on disk too, otherwise image_path must be given

        Returns image path if added, None otherwise
        """

        if save_dir and image_path:
            raise Exception("Can't have both existing image file path and save directory")

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
            self.data.extend(pickle.loads(d))
            return True
            
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
            return False

        encodings = face_recognition.face_encodings(image, boxes)

        if save_dir:
            cv2.imwrite(image_path, image)

        d = [{"image_path": image_path, "loc": box, "encoding": enc}
             for (box, enc) in zip(boxes, encodings)]

        with open(cache_file, "wb") as f:
            f.write(pickle.dumps(d))

        self.data.extend(d)

        return Trues


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
                if len(boxes) != 1:
                    continue  # Ignore this one
                print("   ", boxes)
            else:  # The whole image
                height, width, channels = image.shape
                boxes = [(0, width, 0, height)]
            encodings = face_recognition.face_encodings(rgb, boxes)
            d = [{"image_path": image_path, "loc": box, "encoding": enc}
                 for (box, enc) in zip(boxes, encodings)]

            with open(cache_file, "wb") as f:
                f.write(pickle.dumps(d))

            self.data.extend(d)

    def cluster_images(self, copy_files=True):
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
            ret[labelID] = []
            print("[INFO] faces for face ID: {}".format(labelID))
            idxs = np.where(clt.labels_ == labelID)[0]

            path = "/home/njaal/TEST_faces/%s" % labelID
            print("SAVING TO '%s'" % path)
            if not os.path.exists(path):
                os.makedirs(path)

            for idx in idxs:

                p = self.data[idx]["image_path"]
                ret[labelID].append(p)

                if copy_files:
                    shutil.copy(p, os.path.join(path, os.path.split(p)[1]))

        self.clusters = ret
        return ret


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--src", dest="src", help="Source directory", required=True)
    parser.add_argument("-j", "--jobs", dest="jobs", help="Parallel jobs", default=1)


    options = parser.parse_args()

    image_list = [os.path.join(options.src, x) for x in os.listdir(options.src) if x.endswith(".jpg")]
    clusterer = FaceClusterer(image_list, jobs=options.jobs)

    print(time.ctime(), "Detecting faces")
    clusterer.detect_faces()

    print(time.ctime(), "Clustering images")
    clusterer.cluster_images()

    print(time.ctime(), "All done")
