from utils.console import console
from collections import deque
import sklearn.neighbors
import scipy
import numpy as np
import csv
import os

class IdentificationDB:
    """Instantiation of this class loads the segments db and creates 
    the kd tree. Call the identify function with a captured window
    to determine a match.
    """
    def __init__(self, window_width=12, k_dimension=6, csv_db=None):

        self._window_width = window_width
        self._k = k_dimension

        self._video_segments, self._ids = (csv_db if csv_db is not None 
            else load_csv_db())

        self._kd_tree = self._kd_tree_build()

    def _kd_tree_build(self):
        """Creates all k-d keys for all videos and their segments, maps
        each tree index to its corresponding video name and window 
        index and builds the k-d tree with all keys.
        """
        with (console.status(f"Creating {self._k}-dimensional keys...") 
                as status):
            video_keys = get_kd_keys(self._video_segments, 
                self._window_width, self._k)
            
            self.tree_index_to_window = {}  

            all_keys = []  

            for video, keys in video_keys.items():
                for i in range(0, len(keys)):
                    window_index = i
                    tree_index = len(all_keys)
                    all_keys.append(keys[i])
                    self.tree_index_to_window[tree_index] = (video, 
                        window_index)

            console.log(f"{len(all_keys)} keys created")

            status.update(f"Building k-d tree, give this a moment...")
            kd_tree = sklearn.neighbors.KDTree(all_keys, leaf_size=400)
            console.log("[bold green]K-d tree[/bold green] " +
                f":deciduous_tree: built successfully ")

        return kd_tree

    def _get_nearest_neighbors(self, key, neighbor_amount=3):
        """Returns nearest neighbors in the where each neighbor 
        is on the form (video_metadata, window_index).
        """

        tree_indices = self._kd_tree.query([key], k=neighbor_amount, 
            return_distance=False)[0]

        # Use tree_indices to get the neighbors
        return [self.tree_index_to_window[index] for index in tree_indices]

    def _determine_match(self, captured_window, nearest_neighbors, 
            pearson_threshold):

        for neighbor in nearest_neighbors:
            neighbor_video, neighbor_window_index = neighbor

            neighbor_segments = self._video_segments[neighbor_video]

            # Use index to extract window from segments
            neighbor_window = (neighbor_segments[neighbor_window_index : 
                neighbor_window_index + self._window_width])

            pearsons_r, _ = scipy.stats.pearsonr(
                captured_window, neighbor_window)
            
            if pearsons_r > pearson_threshold:
                time = get_video_time(neighbor, len(neighbor_segments),
                    self._window_width)      
                match = neighbor_video + (time, pearsons_r)
                return match

        return []

    def identify(self, captured_window, pearson_threshold=0.99):
        kd_key = create_kd_key(captured_window, self._window_width, self._k)
        nearest_neighbors = self._get_nearest_neighbors(kd_key)

        match_or_empty = self._determine_match(captured_window, 
            nearest_neighbors, pearson_threshold)
        return match_or_empty

    @property
    def ids(self):
        return self._ids

    @property
    def video_segments(self):
        return self._video_segments

def get_video_time(video_window: int, n_segments: int, window_width: int, 
        segment_time: int=4, buffer_time: int=60) -> str:
    video_metadata, video_window_index = video_window
    total_time = int(video_metadata[1][:-1])
    factor = video_window_index / n_segments
    time = (round(factor * total_time) + 
        segment_time*window_width - buffer_time) 
    return f'{time}s'

def create_kd_key(window, window_width, k):

    if window_width == k:
        return np.array(window)

    slice_width = window_width // k
    kd_key = np.reshape(window, (k, slice_width)).sum(axis=1)
    return kd_key

def get_kd_keys(video_segments: dict, window_width: int, 
        k: int) -> dict:

    if window_width < k:
        raise ValueError("window width has to be larger or equal to the " +
            "specified dimension!")

    if window_width % k != 0:
        raise ValueError("window width has to be divisible by the " +
            "specified dimension!")

    video_keys = {}
    for video, segments in video_segments.items():
        if window_width > len(segments):
            continue
        keys = []
        sliding_window = deque(maxlen=window_width)
        for segment in segments:
            sliding_window.append(segment)
            if len(sliding_window) == window_width:
                keys.append(create_kd_key(sliding_window, 
                    window_width, k))
        video_keys[video] = keys
    return video_keys

def load_csv_db():
    with console.status("Loading database..."):
        here = os.path.dirname(os.path.abspath(__file__))
        video_segments, ids = {}, set()
        with open(os.path.join(here, 'svtplay_db.csv'), 
            encoding='utf8') as file:
            reader = csv.reader(file)
            for row in reader:
                ids.add(row[2])
                video = tuple(row[:5])
                segments = list(map(int, row[5:]))
                video_segments[video] = segments
        console.log(f"{len(video_segments)} videos loaded")
        return video_segments, ids
