from collections import deque
import os
import csv
from create_svm import SvmLearner
import pickle
from dataclasses import dataclass


HTTP_HEADERS = 801
TLS_OVERHEAD = 1.0018


# Boundaries for allowed segment sizes. A very large
# captured segment is most likely a buffer initialization
# of several segments.
MIN_SEGMENT_SIZE = 5000
MAX_SEGMENT_SIZE = 9000000

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


def get_capt_segments_id(start, end, smallest_len):
    """Returns segments between *start* and *end* and video id for all test streams
    """
    video_segments = {}
    here = os.path.dirname(os.path.abspath(__file__))

    # Load data from captured file (starting from start of video)
    # with open(os.path.join(here, "svtplay_test_data_start.csv"), encoding='utf8') as file:
    with open(os.path.join(here, "svm_database", "svtplay_test_data_599_start0.csv"), encoding='utf8') as file:
        reader = csv.reader(file)
        nrRow = 0
        for row in reader:
            if len(row[3:]) <=smallest_len:     # don't bother with to short streams
                continue
            video = tuple(row[1:2])
            if(nrRow%2==0): segments = list(map(int, row[3:][start:end])) # only take segments
            video_segments[video] = segments
            nrRow += 1
    return video_segments



def get_svm_ids(nr_fingerprints):
    """ Get the ids of the videos used when training the svm
        (the first nr_fingerprints fingerprints)
    """
    video_ids = []
    here = os.path.dirname(os.path.abspath(__file__))

    # load all segments
    with open(os.path.join(here, "svtplay_db.csv"), encoding='utf8') as file:
        reader = csv.reader(file)
        nrRow = 0
        for row in reader:
            if nrRow >= nr_fingerprints:  # only load certain amount of videos
                break
            video = tuple(row[2:3])
            video_ids.append(video[0])
            nrRow += 1
    return video_ids


def get_X_y(svm_ids, window_widths, captured_segments):
    """ Go through the captured segments as if the identifier was run
    """
    all_Xs, all_Ys=[], []
    for i in range(len(captured_segments)):
        x, y = [], []
        for video, segs in captured_segments[i].items():
            window = deque(maxlen=window_widths[i])     # recreate the deque for every video
            found = ""
            if(video[0] in svm_ids):          # check if the video is in the training data
                for current_segment in segs:            # go through the segments of the video
                    captured_segment = (round(current_segment / TLS_OVERHEAD) 
                                    - HTTP_HEADERS)

                    if MIN_SEGMENT_SIZE < captured_segment < MAX_SEGMENT_SIZE:
                        window.append(captured_segment)
                        if len(window) == window_widths[i]: # Only query DB with full windows
                            x.append(window)
                            y.append(video[0])
                            break
        all_Xs.append(x)
        all_Ys.append(y)
    
    return (all_Xs, all_Ys)


def savedump(myobj, filename):
    with open(filename,'wb') as f:
        pickle.dump(myobj, f)
    print("svm saved in: ", filename)

def loaddump(filename):
    with open(filename,'rb') as f:
        print("svm loaded")
        return pickle.load(f)

def run_predictions(db, xs, ys):
    """Runs predictions using the svm nad the xs and ys provided
    """
    nr_matches=0                                           # the number of correctly predicted videos
    for window, vid_id in zip(xs, ys): # run predictions on every stream
        if db.predict(window) == vid_id: nr_matches+=1


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


def get_db(window_width, video_segments):
        """
        Create list containing the video name and the associated start of the fingerprint
        """
        db = []
        min_windows = -1                            # only for printing
        max_windows = 0                             # only for printing
        # adds video title and sliding windows to db
        for video, stream in video_segments.items():
            windows = create_windows(stream, window_width, window_width)
            if len(windows)                  > max_windows: max_windows=len(windows)    # only for printing
            if min_windows<0 or len(windows) < min_windows: min_windows=len(windows)    # only for printing
            for window in windows:
                db.append([video[2], window])       # only use the id of the video

        t = [tuple(item[1]) for item in db]     # check if duplicates
        print("len as set: ", len(set(t)))
        print("Max number of windows for a fingerprint: ", max_windows)
        print("Min number of windows for a fingerprint: ", min_windows)
        return db

@dataclass
class Training_Data():
    nr_fingerprints : int = 3000
    window_width: int = 15
    fing_end : int = 29
    fing_start : int = 14
    video_segments = get_svt_segments(
        nr_fingerprints=nr_fingerprints,
        start=fing_start,
        end=fing_end
    )
    database = get_db(
        window_width=window_width,
        video_segments=video_segments
    )
    X_train, Y_train = [window[1] for window in database], [window[0] for window in database]



