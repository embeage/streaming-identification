from posixpath import split
from itertools import islice
from sklearn.model_selection import GridSearchCV, cross_validate
from sklearn import svm
from collections import deque
from create_svm import SvmLearner
import svm_utils
import os
import csv
import pickle
from sklearn.utils.fixes import loguniform
from dataclasses import dataclass
from sklearn.utils.fixes import loguniform
import scipy
import numpy as np
"""
CS, GAMMAS, KERNELS are the parameters
modified in the gridsearch, change these parameters
to narrow or expand the search
"""

"""
Result from gridsearch:
Kernels: rbf
Gammas: [0.01, 0.02, 0.03, .., 1.00]
Cs: [1, 2, 3, .., 100]
result: SVC(C=72, gamma=0.03)

Training time:
    roughly 3s per iteration so in total
    100*100*3*3 = 90000s = 25 hours
    Could be decrased by reducing cross validation (Cv),
    Cs or Gammas
"""


NUM_FINGERPRINTS = 5000
CS = np.arange(1, 2, 1)
GAMMAS = np.arange(0.01, 0.02, 0.01)
KERNELS = ['rbf']

FINGERPRINT_START = 14
FINGERPRINT_END = 21
CAPTURED_RANGES = [(0,2),(0,3),(0,4),(0,5),(0,7),(0,8),(0,10),(0,12),(0,15)]

TRAINING_RANGES = [(14, 21),(14, 22),(14, 23),(14, 24),(14, 26),(14, 27),(14, 29),(14, 31),(14, 34)]


GRIDSEARCH_PARAMS = {'C': CS, 'gamma': GAMMAS,'kernel': KERNELS}






def run_gridsearch():

    # get segments from capt video streams (id as class)
    captured_segments=[]
    for (start, end) in CAPTURED_RANGES:
        captured_segments.append(svm_utils.get_capt_segments_id(start, end, 40))

    grid = GridSearchCV(
        svm.SVC(), 
        param_grid=GRIDSEARCH_PARAMS,
        refit=True,
        cv=3,
        verbose=2)
    
    print("Initializing Training Data")
    data = svm_utils.Training_Data()
    print("Finished initializing training data")
    
    print("Starting fit")
    grid.fit(data.X_train, data.Y_train)
    print("Finishing fit")
    print("Best Score: ")
    print(grid.best_score_)
    print("Best Params:")
    print(grid.best_params_)
    svm_utils.savedump("Parameters: {}, Score: {}".format(
        str(grid.best_params_),
        str(grid.best_score_)
    ), "gridsearch_result.csv")




if __name__ == "__main__":
    run_gridsearch()
