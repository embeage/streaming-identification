import os
import csv
from collections import deque
import os
from timeit import default_timer as timer
from sklearn import svm
import pickle

def loaddump(filename):
    with open(filename,'rb') as f:
        print("svm loaded")
        return pickle.load(f)


def get_svt_segments(nr_fingerprints, start, end, database_name="svtplay_db.csv"):
    """ 
    Get the segments between start (incl.) and end (excl.) and the information of the video (name, id, encoding etc.)
    database should be located in ./database_name from the current directory
    """
    video_segments = {}
    here = os.path.dirname(os.path.abspath(__file__))

    # load all segments
    with open(os.path.join(here, database_name), encoding='utf8') as file:
        reader = csv.reader(file)
        nrRow = 0
        for row in reader:
            if end>0 and len(row[5:]) <=end:    # skip iteration if too few segments exist for video
                continue
            if nrRow >= nr_fingerprints:  # only load certain amount of videos
                break
            video = tuple(row[:5])
            segments = list(map(int, row[5:][start:end]))
            video_segments[video] = segments
            nrRow += 1
    return video_segments




def normalize_data(x0, minlength):
    """
    Normalizes a window of segments so that all values are in the range [-2,2] to
    get the weight of the segments to have the same influence on the SVM

    https://towardsai.net/p/data-science/how-when-and-why-should-you-normalize-standardize-rescale-your-data-3f083def38ff
    """
    xmin, xmax = min(x0), max(x0)
    return [-2 + 4 * (x - xmin) / (xmax - xmin) for x in x0] + [0] * max(0, minlength - len(x0))


def create_windows(stream, size, minwidth):
    """
    Creates, and normalizes, windows of size *size* from the given stream
    """
    ret_list = []
    window = deque(maxlen=size)
    for segment in stream:
        window.append(segment)
        if(len(window) == size):
            ret_list.append(normalize_data(window, minwidth))
    return ret_list


class SvmLearner:
    """
    Creates and traines an SVM with the given parameters

    C/c_param:      defaults to a value of 1, lower C means more regularization.
    gamma/g_param:  defines how much influence a single training example has
    For more info on C/gamma: https://scikit-learn.org/stable/modules/svm.html

    window_width:   determines the width of the windows populating the database
    """
    def __init__(self,fingerprint_start=0, fingerprint_end=-1, nr_fingerprints=15, window_width=15, c_param=1, g_param=1):
        self.clf = svm.SVC(gamma=g_param, C=c_param)
        self.window_start = fingerprint_start                # start index in fingerprints
        self.window_end = fingerprint_end                    # end index in fingerprints
        self.window_width = window_width
        video_segments = get_svt_segments(nr_fingerprints, fingerprint_start, fingerprint_end)

        self.db = self.load_svm_db(video_segments)  # format of db: video title + resolution (0), windows (>=1)
        self.learn(nr_fingerprints)

    def load_svm_db(self, video_segments):
        """
        Create list containing the video name and the associated start of the fingerprint
        """
        db = []
        min_windows = -1                            # only for printing
        max_windows = 0                             # only for printing
        # adds video title and sliding windows to db
        for video, stream in video_segments.items():
            windows = create_windows(stream, self.window_width, self.window_width)
            if len(windows)                  > max_windows: max_windows=len(windows)    # only for printing
            if min_windows<0 or len(windows) < min_windows: min_windows=len(windows)    # only for printing
            for window in windows:
                db.append([video[2], window])       # only use the id of the video

        t = [tuple(item[1]) for item in db]     # check if duplicates
        print("len as set: ", len(set(t)))
        print("Max number of windows for a fingerprint: ", max_windows)
        print("Min number of windows for a fingerprint: ", min_windows)
        return db

    def learn(self, videos_to_load):
        """
        Fit the SVM using the start of the fingerprints and the video ids as classes
        """
        self.generate_training_datasets()
        print("start fit")
        start = timer()
        self.clf.fit(self.X_train, self.Y_train)
        end = timer()
        print(f"svm with database of {videos_to_load} videos finished learning in {end - start} seconds.")

    def predict(self, window: deque) -> list:
        """
        Uses a window of segments to predict which video title it belongs to
        """
        return self.clf.predict([normalize_data(window, self.window_width)])[0]       # normalise the input data

    def generate_training_datasets(self):
        """
        Generates training data (windows) and target label (video title with resolution used)
        """
        self.X_train = [window[1] for window in self.db]            # all of the windows for training as individual points
        print("points in SVM: ", len(self.X_train))
        
        self.Y_train = [window[0] for window in self.db]            # all of the classes for the windows
        print("classes in SVM: ", len(set(self.Y_train)))




class PreloadedSVM:
    """ 
    Performs normalization before predictions on a preloaded SVM
    """
    def __init__(self, clf_filename, window_width=15):
        print("using SVM: ", clf_filename, " with window length: ", window_width)
        self.clf = loaddump(clf_filename)
        self.window_width = window_width


    def predict(self, window: deque) -> list:
        """
        Uses a window of segments to predict which video title it belongs to
        """
        return self.clf.predict([normalize_data(window, self.window_width)])[0]       # normalise the input data

    