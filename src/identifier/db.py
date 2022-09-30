from utils.console import console, console_progress
from collections import deque
import sklearn.neighbors
import scipy
import numpy as np
import csv
import os

DEFAULT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(DEFAULT_DIR, 'svtplay_db.csv')
DEFAULT_DB_BIN = os.path.join(DEFAULT_DIR, 'svtplay_db.bin')
DEFAULT_PEARSON_THRESHOLD = 0.999999999

### pickle utils
import pickle

def savedump(myobj, filename):
    with open(filename,'wb') as f:
        pickle.dump(myobj, f)
        
def loaddump(filename):
    with open(filename,'rb') as f:
        return pickle.load(f)    
###

class IdentificationDB:
    """Instantiation of this class loads the segments db and creates 
    the kd tree. Call the identify function with a captured window
    to determine a match.
    """
    def __init__(self, window_width=12, k_dimension=6,
                 db_filename=DEFAULT_DB, bin_filename=DEFAULT_DB_BIN):
        self._w = window_width
        self._k = k_dimension
        self._load_database(db_filename, bin_filename)
        self._kd_tree_build()

    def _load_database(self, db_filename, bin_filename):
        ## Loading from csv file ##
        if not os.path.exists(bin_filename):
            with console.status("Loading CSV database..."):  
                self._video_infos, self._segments, self._ids = [], [], set()
                with open(db_filename, encoding='utf8') as file:
                    for row in csv.reader(file):
                        self._ids.add(row[2])
                        self._video_infos.append(tuple(row[:5]))
                        self._segments.append(list(map(int, row[5:])))
            savedump((self._video_infos,self._segments,self._ids), bin_filename)
        else:
            ## Loading from pickled binary ##
            self._video_infos, self._segments, self._ids = loaddump(bin_filename)
            
        console.log(f"{len(self._video_infos)} videos loaded")

    def _create_kd_key(self, window):
        if self._w == self._k:
            return np.array(window)
        # Weird enough but there was a bug here!
        return np.reshape(window, (self._k, self._w // self._k)).sum(axis=1)

    def _compute_kd_keys(self):        
        if self._w < self._k:
            raise ValueError("window width has to be larger or equal to the specified dimension!")

        if self._w % self._k != 0:
            raise ValueError("window width has to be divisible by the specified dimension!")

        ## First pass: pre-calculate total number of keys ##
        total_keys = sum(max(0,len(fingerprint)-self._w+1) for fingerprint in self._segments)

        ## Allocate 'C_CONTIGUOUS' data (no extra copy for building the kdtree if doubles!) ##
        self._all_keys = np.empty((total_keys, self._k), dtype=np.uint32)
        self._video_indexes = np.empty(total_keys, dtype=np.uint32)
        self._window_indexes = np.empty(total_keys, dtype=np.uint32)

        ## Second pass: compute all keys ##
        console.log(f"Computing {total_keys} keys...")

        key_index = 0
        for video_index in range(len(self._segments)):
            fingerprint = self._segments[video_index]
            if self._w > len(fingerprint):
                continue
            sliding_window = deque(maxlen=self._w)
            for window_index in range(len(fingerprint)):
                sliding_window.append(fingerprint[window_index])
                if len(sliding_window) == self._w:
                    self._all_keys[key_index] = self._create_kd_key(sliding_window)
                    self._video_indexes[key_index] = video_index
                    self._window_indexes[key_index] = window_index+1-self._w
                    key_index += 1
            console_progress(key_index, total_keys)

    def _kd_tree_build(self, output_dir=DEFAULT_DIR, N=103531):
        """Creates all k-d keys for all videos and their segments, maps
        each tree index to its corresponding video name and window 
        index and builds the k-d tree with all keys.
        """
        video_keys_filename = os.path.join(output_dir, f"keys_db-{self._w}-{self._k}.bin")
        kdtree_filename = os.path.join(output_dir, f"kdtree-{self._w}-{self._k}.bin")

        ## Keys: pickle binary dump if possible
        if os.path.exists(video_keys_filename):
            self._all_keys,self._video_indexes,self._window_indexes = loaddump(video_keys_filename)
        else:
            self._compute_kd_keys()
            savedump((self._all_keys,self._video_indexes,self._window_indexes), video_keys_filename)
        console.log(f"{len(self._all_keys)} keys loaded")

        ## Kdtree: pickle binary dump if possible
        if not os.path.exists(kdtree_filename):
            with console.status(f"Creating {self._k}-dimensional keys...") as status:
                status.update(f"Building k-d tree, give this a moment...")        
                self._kd_tree = sklearn.neighbors.KDTree(self._all_keys, leaf_size=400)
            savedump(self._kd_tree, kdtree_filename)
        else:
            self._kd_tree = loaddump(kdtree_filename)

        console.log(f"[bold green]K-d tree[/bold green] :deciduous_tree: built successfully ")

    def _get_nearest_neighbors(self, key, neighbor_amount=3):
        """Returns nearest neighbors in the where each neighbor 
        is on the form (video_metadata, window_index).
        """

        neighbors = self._kd_tree.query([key], k=neighbor_amount, return_distance=False)[0]

        # Use tree_indices to get the neighbors
        return [(self._video_indexes[index], self._window_indexes[index]) for index in neighbors]

    def _get_video_time(self, video_index, window_index, n_segments,
                   segment_time=4, buffer_time=60):
        total_time = int(self._video_infos[video_index][1][:-1])
        factor = window_index / n_segments
        time = round(factor * total_time) + segment_time*self._w - buffer_time
        return f'{time}s'
    
    def _determine_match(self, captured_window, nearest_neighbors, pearson_threshold):
        for neighbor in nearest_neighbors:
            video_index, window_index = neighbor
            neighbor_segments = self._segments[video_index]

            # Use index to extract window from segments
            neighbor_window = neighbor_segments[window_index: window_index+self._w]
            if len(neighbor_window) == self._w:
                pearsons_r, _ = scipy.stats.pearsonr(captured_window, neighbor_window)

                if pearsons_r > pearson_threshold:
                    time = self._get_video_time(video_index, window_index, len(neighbor_segments))      
                    match = self._video_infos[video_index] + (time, pearsons_r)
                    return match

        return []

    def identify(self, captured_window, pearson_threshold=DEFAULT_PEARSON_THRESHOLD):
        kd_key = self._create_kd_key(captured_window)
        nearest_neighbors = self._get_nearest_neighbors(kd_key)
        return self._determine_match(captured_window, nearest_neighbors, pearson_threshold)

    def best_matches(self, captured_window, nb_neighbors=10):
        kd_key = self._create_kd_key(captured_window)
        nearest_neighbors = self._get_nearest_neighbors(kd_key, neighbor_amount=nb_neighbors)
        matches = []
        for neighbor in nearest_neighbors:
            video_index, window_index = neighbor
            neighbor_segments = self._segments[video_index]

            # Use index to extract window from segments
            neighbor_window = neighbor_segments[window_index: window_index+self._w]
            if len(neighbor_window) == self._w:
                pearsons_r, _ = scipy.stats.pearsonr(captured_window, neighbor_window)
                time = self._get_video_time(video_index, window_index, len(neighbor_segments))      
                matches.append((self._video_infos[video_index] + (time, pearsons_r),
                                neighbor_window))
        return matches
            

    @property
    def ids(self):
        return self._ids

    @property
    def video_segments(self):
        return self._segments


def compute_pearson(captured_window, neighbor_window):
    return scipy.stats.pearsonr(captured_window, neighbor_window)[0]
