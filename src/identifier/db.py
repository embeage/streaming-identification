from utils.console import console
from collections import deque
import sklearn.neighbors
import scipy
import numpy as np
import csv
from os import path

class IdentificationDB:
    """Instantiation of this class loads the fingerprint db and creates
    the kd tree. Call the identify function with a captured window
    to determine a match.
    """
    def __init__(self, window_width=12, k_dimension=6, csv_db=None):

        self._window_width = window_width
        self._k = k_dimension
        self._videos = csv_db if csv_db is not None else load_csv_db()
        self._kd_tree = self._kd_tree_build()

    def _kd_tree_build(self):
        """Creates all k-d keys for all videos and their fingerprints, maps
        each tree index to its corresponding video id, fingerprint index and
        window index and builds the k-d tree with all keys.
        """
        with (console.status(f"Creating {self._k}-dimensional keys...")
              as status):

            self.tree_index_to_window = {}
            keys = []
            i = 0
            for video_id, video_data in self._videos.items():
                for f_i, fingerprint in enumerate(video_data['fingerprints']):
                    if len(fingerprint) < self._window_width:
                        continue
                    fingerprint_keys = get_kd_keys(
                        fingerprint, self._window_width, self._k)
                    for k_i, fingerprint_key in enumerate(fingerprint_keys):
                        keys.append(fingerprint_key)
                        self.tree_index_to_window[i] = (video_id, f_i, k_i)
                        i += 1

            console.log(f"{len(keys)} keys created")

            status.update("Building k-d tree, give this a moment...")
            kd_keys = np.zeros(shape=(len(keys), self._k))
            for i, key in enumerate(keys):
                kd_keys[i] = key
            kd_tree = sklearn.neighbors.KDTree(kd_keys, leaf_size=400)
            console.log("[bold green]K-d tree[/bold green] "
                        ":deciduous_tree: built successfully ")

        return kd_tree

    def _get_nearest_neighbors(self, key, neighbor_amount=5):
        """Returns nearest neighbors in the where each neighbor
        is on the form (video_id, fingerprint_index, window_index).
        """

        tree_indices = self._kd_tree.query([key], k=neighbor_amount,
            return_distance=False)[0]

        # Use tree_indices to get the neighbors
        return [self.tree_index_to_window[index] for index in tree_indices]

    def _determine_match(self, captured_window, nearest_neighbors,
            pearson_threshold):

        matches = []
        for neighbor in nearest_neighbors:
            video_id, fingerprint_index, window_index = neighbor

            fingerprint = (self._videos[video_id]['fingerprints']
                           [fingerprint_index])

            # Use index to extract window from segments
            neighbor_window = (fingerprint[window_index : window_index
                                           + self._window_width])

            pearsons_r, _ = scipy.stats.pearsonr(captured_window,
                                                 neighbor_window)

            if pearsons_r > pearson_threshold:
                name = self._videos[video_id]['name']
                duration = self._videos[video_id]['duration']
                segment_length = self._videos[video_id]['segment_length']
                time = video_time(window_index, len(fingerprint), duration,
                                      segment_length, self._window_width)
                matches.append({
                    'id': video_id,
                    'name': name,
                    'time': time,
                    'pearsons_r': pearsons_r
                    })

        return matches

    def identify(self, captured_window, pearson_threshold=0.99):
        kd_key = create_kd_key(captured_window, self._window_width, self._k)
        nearest_neighbors = self._get_nearest_neighbors(kd_key)
        match_or_empty = self._determine_match(captured_window,
            nearest_neighbors, pearson_threshold)
        return match_or_empty

    @property
    def videos(self):
        return self._videos

def video_time(window_index, fingerprint_length, video_duration,
                   segment_length, window_width, buffer_time=60):
    factor = window_index / fingerprint_length
    time = (round(factor * video_duration)
            + segment_length*window_width - buffer_time)
    return time

def create_kd_key(window: deque, window_width, k):

    if window_width == k:
        return np.array(window)

    slice_width = window_width // k
    kd_key = np.reshape(window, (k, slice_width)).sum(axis=1)
    return kd_key

def get_kd_keys(fingerprint, window_width, k):
    if window_width < k:
        raise ValueError("window width has to be larger or equal to the " +
            "specified dimension!")

    if window_width % k != 0:
        raise ValueError("window width has to be divisible by the " +
            "specified dimension!")

    sliding_window = deque(maxlen=window_width)
    keys = []
    for segment_size in fingerprint:
        sliding_window.append(segment_size)
        if len(sliding_window) == window_width:
            keys.append(create_kd_key(sliding_window, window_width, k))
    return keys

def load_csv_db():
    with console.status("Loading database..."):
        file_path = path.join(path.dirname(path.abspath(__file__)),
                              'svtplay_db.csv')
        if not path.exists(file_path):
            file_path = file_path.replace('.csv', '_intl.csv')
        with open(file_path, encoding='utf8') as file:
            videos = {}
            reader = csv.reader(file)
            for row in reader:
                video_id = row[0]
                name = row[1]
                duration = int(row[2])
                segment_length = float(row[3])
                fingerprints = tuple(tuple(map(int, row.split(',')))
                                     for row in row[4:])
                videos[video_id] = {
                    'name': name,
                    'duration': duration,
                    'segment_length': segment_length,
                    'fingerprints': fingerprints
                }
        console.log(f"{len(videos)} videos loaded")
        return videos
