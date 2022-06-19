from collections import deque
import os
import csv
from create_svm import SvmLearner
import pickle

# the different ranges of segments that are picked from the captured streams
captured_ranges = [(0,2),(0,3),(0,4),(0,5),(0,7),(0,8),(0,10),(0,12),(0,15)]
# the number of fingerprints to train the SVMs on
nr_fingerprints = 5000
# The values of the C parameter
Cs = [0.1,1,10,50,100]
# The values of the gamma parameter
gammas = [0.1,1,10,50,100]
# the start and end indices for the training fingerprints
training_ranges = [(14, 21),(14, 22),(14, 23),(14, 24),(14, 26),(14, 27),(14, 29),(14, 31),(14, 34)]


# HTTP headers account for both the received 
# video and audio segment
HTTP_HEADERS = 801
TLS_OVERHEAD = 1.0018


# Boundaries for allowed segment sizes. A very large
# captured segment is most likely a buffer initialization
# of several segments.
MIN_SEGMENT_SIZE = 5000
MAX_SEGMENT_SIZE = 9000000




def savedump(myobj, filename):
    with open(filename,'wb') as f:
        pickle.dump(myobj, f)
    print("svm saved in: ", filename)

def loaddump(filename):
    with open(filename,'rb') as f:
        print("svm loaded")
        return pickle.load(f)


def get_capt_segments_id(start, end, smallest_len):
    """Returns segments between *start* and *end* and video id for all test streams
    """
    video_segments = {}
    here = os.path.dirname(os.path.abspath(__file__))

    # Load data from captured file (starting from start of video)
    with open(os.path.join(here, "svtplay_test_data_start.csv"), encoding='utf8') as file:
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


def run_predictions(db, xs, ys):
    """Runs predictions using the svm nad the xs and ys provided
    """
    nr_matches=0                                           # the number of correctly predicted videos
    for window, vid_id in zip(xs, ys): # run predictions on every stream
        if db.predict(window) == vid_id: nr_matches+=1


def run(captured_ranges, nr_fingerprints, Cs, gammas, training_ranges):
    # the window widths of captured ranges
    window_widths = [end-start for (start,end) in captured_ranges]

    # get segments from capt video streams (id as class)
    captured_segments=[]
    for (start, end) in captured_ranges:
        captured_segments.append(get_capt_segments_id(start, end, 40))

    # get the ids of the videos in the svm
    svm_ids = get_svm_ids(nr_fingerprints)

    # all_Xs: list of all videos (first window) - each window width has its own list
    # all_Ys: list of all ids
    all_Xs, all_Ys = get_X_y(svm_ids, window_widths, captured_segments)

    # go through all different window widths for the database (i.e all different parameters)
    for ww_index, ranges in enumerate(training_ranges):
        fs, fe = ranges                 # get start and end of fingerprint for svm training
        ww = window_widths[ww_index]    # get the window width
        
        for c in Cs:                    # go through all different values for C
            for g in gammas:            # go through all different values for gamma
                print(ww_index, fs, fe, ww, nr_fingerprints, c, g)  # print parameters
                
                db = SvmLearner(fingerprint_start=fs, fingerprint_end=fe, window_length=ww, 
                    nr_fingerprints=nr_fingerprints, c_param=c, g_param=g)  # create and train SVM

                f_name = f"test_svm_{str(ww)}s_C{str(c)}_g{str(g)}"    # the filename where the svm is saved
                savedump(db.clf, f_name)                               # save svm

                correct_predictions = run_predictions(db, all_Xs[ww_index], all_Ys[ww_index])
                print("nr of videos tested: ", len(all_Xs[ww_index]))

                score = correct_predictions/len(all_Xs[ww_index])               # the score (correct/all) of the svm
                print("score: ", score)
                with (open('scores.csv', 'a', newline='', encoding='utf8') as csv_file): # save the results
                    writer = csv.writer(csv_file)
                    writer.writerow([f_name, fs, fe, ww, g, c, len(all_Xs[ww_index]), correct_predictions, score])
    
    



if __name__ == "__main__":
    run(captured_ranges, nr_fingerprints, Cs, gammas, training_ranges)
