#!/usr/bin/env python3
from argparse import ArgumentParser
import json
import pickle
import math

import os
import pandas as pd
import librosa
import glob 
import librosa.display
import random

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from tensorflow.keras.utils import to_categorical

import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation, Flatten
from tensorflow.keras.layers import Convolution2D, MaxPooling2D
from tensorflow.keras.optimizers import Adam
from sklearn import metrics 

from sklearn.datasets import make_regression
from sklearn.preprocessing import StandardScaler
from sklearn import metrics
from sklearn.model_selection import train_test_split, GridSearchCV

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout 
from tensorflow.keras.wrappers.scikit_learn import KerasRegressor

from tensorflow.keras.callbacks import EarlyStopping

from tensorflow.keras import regularizers

from sklearn.preprocessing import LabelEncoder

from datetime import datetime

import os



class SpeechTrainer:
    def __init__(self, dir):
        """
        Requires a directory with one subdirectory for each voice containing
        wav files
        """
        self.dir = dir

        self.frac_train = 0.70
        self.frac_validate = 0.20
        self.frac_test = 0.10

        if os.path.isfile(dir):
            self._build_filelist_from_json(dir)

            dir = os.path.split(dir)[0]

        else:
            self._build_filelist(self.dir)


        self._voice_id_file = os.path.join(dir, "voices.json")
        if os.path.exists(self._voice_id_file):
            self.voice_ids = json.load(open(self._voice_id_file, "r"))
        else:
            self.voice_ids = {}


        print("Loaded", len(self.voice_files), "voices")

    def _build_filelist_from_json(self, jsonfile):
        """
        Expect a json with mapping {voice: [item1, item2...]} where item is
        {"start":, "end":, "file"} etc
        """

        self.voice_files = []
        self.speaker_list = []
        self.features = []

        with open(jsonfile, "r") as f:
            mapping = json.load(f)

        for speaker in mapping:
            for item in mapping[speaker]:
                self.speaker_list.append(speaker)
                self.voice_files.append(item["file"])

        json.dump(mapping.keys(), open(self._voice_id_file, "w"))


    def _build_filelist(self, dir):
        """
        Expect a directory with one subdir for each voice and wav files inside.
        Returns a map {voice:[files]}
        """
        # We need these two sets as different bits for the training
        self.voice_files = []
        self.speaker_list = [] 
        self.features = []

        for voice in os.listdir(dir):

            if voice not in self.voice_ids:
                self.voice_ids[voice] = len(self.voice_ids) + 1

            voicedir = os.path.join(dir, voice)

            if not os.path.isdir(voicedir):
                continue

            # This is a voice directy, add all the wav files within
            files = os.listdir(voicedir)
            size = 0
            for f in files:
                size += os.stat(os.path.join(voicedir, f)).st_size

            print(voicedir, len(files), size)
            if size < 1000000:  # Need at LEAST one mb with data
                continue  # Ignore - not enough data

            for soundfile in files:
                if soundfile.endswith(".wav"):
                    self.voice_files.append(os.path.join(voicedir, soundfile))
                    self.speaker_list.append(self.voice_ids[voice])

        # Update voice ids
        json.dump(self.voice_ids, open(self._voice_id_file, "w"))

    def _extract_features_from_file(self, file_name):
        """
        This bit is from <>
        """

        cache_file = file_name + ".features"
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        # Loads the audio file as a floating point time series and assigns the default sample rate
        # Sample rate is set to 22050 by default, librosa will resample automatically
        X, sample_rate = librosa.load(file_name, res_type='kaiser_fast') 
        print("Sample rate", sample_rate)

        # Generate Mel-frequency cepstral coefficients (MFCCs) from a time series 
        mfccs = np.mean(librosa.feature.mfcc(y=X, sr=sample_rate, n_mfcc=40).T,axis=0)

        # Generates a Short-time Fourier transform (STFT) to use in the chroma_stft
        stft = np.abs(librosa.stft(X))

        # Computes a chromagram from a waveform or power spectrogram.
        chroma = np.mean(librosa.feature.chroma_stft(S=stft, sr=sample_rate).T,axis=0)

        # Computes a mel-scaled spectrogram.
        mel = np.mean(librosa.feature.melspectrogram(X, sr=sample_rate).T,axis=0)

        # Computes spectral contrast
        contrast = np.mean(librosa.feature.spectral_contrast(S=stft, sr=sample_rate).T,axis=0)

        # Computes the tonal centroid features (tonnetz)
        tonnetz = np.mean(librosa.feature.tonnetz(y=librosa.effects.harmonic(X),
        sr=sample_rate).T,axis=0)
            
        
        with open(cache_file, "wb") as f:
            pickle.dump((mfccs, chroma, mel, contrast, tonnetz), f)

        return mfccs, chroma, mel, contrast, tonnetz

    def extract_features(self):

        for soundfile in self.voice_files:

            r = self._extract_features_from_file(soundfile)
            mfccs, chroma, mel, contrast, tonnetz = r

            self.features.append(np.concatenate((mfccs, chroma, mel, contrast, tonnetz), axis=0))

    def get_dataframe(self):
        """
        We want a pandas dataframe that has this format:
        |   | filename | label (the speaker ID) |
        """

        # Filenames are already in the self.voice_files list, the speaker id is in self.voice_ids

        # col1 = [fn for ]
        pass


    def train(self):

        # We have two lists - one is the features concatenated, the other is an array
        # |   | filename | label (the speaker ID) |


        data = {"filename": self.voice_files, "label": self.speaker_list}
        labels = pd.DataFrame(data=data)

        print("labels")
        print(labels.shape)

        print("Unique speakers", labels["label"].nunique())

        print("features")
        print(len(self.features))

        X = np.array(self.features)
        Y = np.array(self.speaker_list)

        # Hot encoding y
        lb = LabelEncoder()
        Y = to_categorical(lb.fit_transform(Y))

        print("Shapes", X.shape, Y.shape)

        num_classes = Y.shape[1]

        # Split
        train = math.floor(X.shape[0] * self.frac_train)
        val = train + math.floor(X.shape[0] * self.frac_validate)
        print("TOTAL", Y.shape[0])
        print("Training on", train, "validating on", Y.shape[0] - val, "saved for testing", Y.shape[0] - val)

        X_train = X[:train]
        X_val = X[train:val]
        X_test = X[val:]

        Y_train = Y[:train]
        Y_val = Y[train:val]
        Y_test = Y[val:]

        ss = StandardScaler()
        X_train = ss.fit_transform(X_train)
        X_val = ss.transform(X_val)
        X_test = ss.transform(X_test)


        # Build a simple dense model with early stopping with softmax for categorical classification
        # We have 115 classes 

        model = Sequential()

        model.add(Dense(193, input_shape=(193,), activation = 'relu'))
        model.add(Dropout(0.1))

        model.add(Dense(128, activation = 'relu'))
        model.add(Dropout(0.25))  

        model.add(Dense(128, activation = 'relu'))
        model.add(Dropout(0.5))    

        model.add(Dense(num_classes, activation = 'softmax'))

        model.compile(loss='categorical_crossentropy', metrics=['accuracy'], optimizer='adam')

        early_stop = EarlyStopping(monitor='val_loss', min_delta=0, patience=100, verbose=1, mode='auto')

        history = model.fit(X_train, Y_train, batch_size=256, epochs=1000, 
                            validation_data=(X_val, Y_val),
                            callbacks=[early_stop])


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-i", "--src", dest="src", help="Directory with voice subdirs (or JSON)", required=True)
    parser.add_argument("-o", "--output", dest="dst", help="Output file", default=None)

    parser.add_argument("--train", dest="train", action="store_true", default=False, help="Train network")

    options = parser.parse_args()


    if options.train:
        if not options.dst:
            options.dst = os.path.join(options.src, "trainingdata.json")  # Rather a model or something?
        trainer = SpeechTrainer(options.src)
        print("Extracting features")
        
        trainer.extract_features()
        trainer.train()

        print("Done")


