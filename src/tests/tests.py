from utils import format
from collections import deque
import csv
import argparse
from tqdm import tqdm
from identifier import db
from timeit import default_timer as timer
import json
import ast
import sys
import tracemalloc

def identification_tests(window_widths, kd_dimensions, pearson_thresholds):

    test_videos = {}
    seen_ids = set()

    print("Reading database file...")
    csv_db = db.load_csv_db()

    print("Reading test data file...")
    with open('svtplay_test_data.csv', encoding='utf8') as test_file:
        reader = csv.reader(test_file)
        for row in reader:
            svt_id = row[1]
            first_segment_time = float(ast.literal_eval(row[3])[1])
            last_segment_time = float(ast.literal_eval(row[-1])[1])
            _, db_ids = csv_db
            if (svt_id not in db_ids or svt_id in seen_ids or 
                    first_segment_time > 15  or last_segment_time < 500):
                continue
            seen_ids.add(row[1])
            video = tuple(row[:3])
            segments_times = row[3:]
            test_videos[video] = segments_times

    for window_width in window_widths:
        for kd_dimension in kd_dimensions:
            print(f"Initializing database with window width {window_width} " +
                f"and k-dimension {kd_dimension}...")
            try:
                start = timer()
                tracemalloc.start()
                identification_db = db.IdentificationDB(window_width, 
                    kd_dimension, csv_db)
                mem, _ = tracemalloc.get_traced_memory()
            except ValueError as e:
                print("Error:", e, "Continuing...")
                continue
            finally:
                tracemalloc.stop()
                end = timer()
            print(f"Done in {round(end - start, 1)} seconds.")

            _identification_test(test_videos, identification_db, 
                window_width, kd_dimension, pearson_thresholds, mem)

def _identification_test(test_videos, identification_db, window_width, 
        kd_dimension, pearson_thresholds, mem):

    tested = {
        "Videos tested": len(test_videos),
        "Window width": window_width,
        "K-dimensions": kd_dimension,
        "Allocated memory": format.convert_size(mem)}

    pearson_thresholds_tests = {}
    query_times = []

    for pearson_threshold in (pbar := tqdm(pearson_thresholds)):
        pbar.set_description(f"Pearson's r threshold {pearson_threshold}")
  
        matches = {}
        false_matches = {}
        no_matches = {}
        match_times = []
        fastest_time = 600
        slowest_time = 0
        
        for video, segments_times in test_videos.items():

            title, svt_id, start_time = video
            tested_video = f"{title}, {svt_id}, {start_time} s"
            sliding_window = deque(maxlen=window_width)

            for segment_time in segments_times:
                captured_segment, time = ast.literal_eval(segment_time)
                time = float(time)
                segment = round((int(captured_segment) / 1.0018) - 801)
                sliding_window.append(segment)
                if len(sliding_window) == window_width:
                    start = timer()
                    match = identification_db.identify(sliding_window, pearson_threshold)
                    end = timer()
                    query_times.append(end - start)
                    if match:
                        matched_title, _, matched_id, _, matched_quality, \
                            matched_time, pearsons_r = match
                        matched_time = f'{matched_time[:-1]} s'
                        match = {
                            "Time to match": f'{time} s',
                            "Matched title": matched_title, 
                            "Matched SVT id": matched_id,
                            "Matched quality": matched_quality,
                            "Matched timestamp": matched_time,
                            "Pearson's r": pearsons_r}
                    
                        if svt_id == matched_id:
                            match_times.append(time)
                            if time > slowest_time:
                                slowest_time = time
                            if time < fastest_time:
                                fastest_time = time
                            matches[tested_video] = match
                        else:
                            false_matches[tested_video] = match
                        break
            else:
                no_matches[tested_video] = {
                    "No match after": f'{time} s'}

        match_percentage = f'{round((len(matches) / len(test_videos)) * 100, 1)}%' if len(test_videos) else None
        false_match_percentage = f'{round((len(false_matches) / len(test_videos)) * 100, 1)}%' if len(test_videos) else None
        no_match_percentage = f'{round((len(no_matches) / len(test_videos)) * 100, 1)}%' if len(test_videos) else None
        average_time = f'{round(sum(match_times) / len(match_times), 1)} s' if matches else None
        fastest_time = f'{fastest_time} s' if fastest_time < 600 else None
        slowest_time = f'{slowest_time} s' if slowest_time > 0 else None

        pearson_thresholds_tests[pearson_threshold] = {
            "Matches": len(matches),
            "Match percentage": match_percentage,
            "False matches": len(false_matches),
            "False match percentage": false_match_percentage,
            "No matches": len(no_matches),
            "No match percentage": no_match_percentage,
            "Average match time": average_time,
            "Fastest match": fastest_time,
            "Slowest match": slowest_time,
            "List of matches": matches,
            "List of false matches": false_matches,
            "List of no matches": no_matches}

    average_query_time = f'{round((sum(query_times) / len(query_times)) * 1000, 2)} ms' if query_times else None
    tested['Average query time'] = average_query_time
    tested["Pearson's r thresholds"] = pearson_thresholds_tests

    with (open(f'identification_test_{window_width}_{kd_dimension}.json', 
            'w', encoding='utf8') as json_file):
        json.dump(tested, json_file, indent=4)

def windows_uniqueness_tests(window_widths):

    print("Reading database file...")
    video_segments, _ = db.load_csv_db()
    for window_width in (pbar := tqdm(window_widths)):
        pbar.set_description(f"Window width {window_width}")
        _windows_uniqueness_test(video_segments, window_width)

def _windows_uniqueness_test(video_segments, window_width):

    windows = {}
    windows_tested = 0
    duplicate_windows = {}
    
    for video, segments in video_segments.items():
        title, _, svt_id, _, quality = video
        sliding_window = deque(maxlen=window_width)
        window_index = 0
        for segment in segments:
            sliding_window.append(segment)
            if len(sliding_window) == window_width:
                window = '[' +  ', '.join(map(str, sliding_window)) + ']'
                window_metadata = f'{title}, {svt_id}, {quality}, Window index: {window_index}'
                if window in windows:
                    if duplicate_windows.get(window) is None:
                        duplicate_windows[window] = [windows[window]]
                    duplicate_windows[window].append(window_metadata)
                else:
                    windows[window] = window_metadata

                window_index += 1
                windows_tested += 1

    unique_windows = windows_tested - len(duplicate_windows)
    unique_window_percentage = f'{((unique_windows / windows_tested) * 100):.20f}%' if windows_tested else None
    duplicate_window_percentage = f'{((len(duplicate_windows) / windows_tested) * 100):.20f}%' if windows_tested else None

    with (open(f'windows_uniqueness_test_{window_width}.json', 'w', 
            encoding='utf8') as json_file):
        tested = {
            "Windows tested": windows_tested,
            "Window width": window_width,
            "Unique windows": unique_windows,
            "Unique window percentage": unique_window_percentage,
            "Duplicate windows": len(duplicate_windows),
            "Duplicate window percentage": duplicate_window_percentage,
            "Duplicate windows list": duplicate_windows}
        json.dump(tested, json_file, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Runs specified test on the SVT Play test data.")
    parser.add_argument('--identification', 
        action=argparse.BooleanOptionalAction)
    parser.add_argument('--uniqueness',
        action=argparse.BooleanOptionalAction)
    parser.add_argument('-w', "--window-widths",
        type=int,
        nargs='+',
        required=True)
    parser.add_argument('-k', "--kd-dimensions",
        type=int,
        nargs='+',
        required='--identification' in sys.argv)
    parser.add_argument('-p', "--pearson-thresholds",
        type=float,
        nargs='+',
        required='--identification' in sys.argv)
    args = parser.parse_args()
    if args.identification:
        identification_tests(args.window_widths, args.kd_dimensions, 
            args.pearson_thresholds)
    elif args.uniqueness:
        windows_uniqueness_tests(args.window_widths)
    else:
        print("No tests specified...")