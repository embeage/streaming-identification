"""Gathers test data by playing SVT Play videos in 
svtplay_video_paths.txt and stores the segments as well 
as the received times in svtplay_test_data.csv.
"""

import argparse
from utils import network
import requests
import random
import csv
import video_player
from threading import Thread, Timer, Event

PLAYBACK_TIME = 600
BUFFER_TIME = 60
SEGMENT_TIME_THRESHOLD = 2

def run(interface):
    
    try:
        with open('svtplay_video_paths.txt', 'r') as file:
            video_urls = ['https://www.svtplay.se' + path.strip() 
                for path in file.readlines()]
    except FileNotFoundError:
        videos = requests.get(
            'https://svtscraper.herokuapp.com/videos/all').json()
        video_urls = [video['url'] for video in videos]
    
    capture_filter = ('src ' + ' or src '.join(network.get_svtplay_ips()) 
        + ' and greater 0')
    
    for url in video_urls:
        svt_id = url[-7:]
        metadata = requests.get(f'https://api.svt.se/video/{svt_id}').json()
        try:
            title = metadata['programTitle']
            episode_title = metadata['episodeTitle']
            if episode_title != title:
                title += f": {episode_title}" 
            duration = int(metadata['contentDuration'])
        except (TypeError, KeyError):
            continue

        if duration < PLAYBACK_TIME + BUFFER_TIME:
            continue

        start_time = random.randint(0, duration - PLAYBACK_TIME - BUFFER_TIME)
        url += f'&position={start_time}'

        stream = ()
        segments = []
        segment_times = []
        current_segment = 0

        packet_analyzer = network.get_packet_analyzer(capture_filter, 
            interface)
        exit_flag = Event()
        interuppted = False
        player = Thread(target=video_player.play_video, 
            args=(url, PLAYBACK_TIME, exit_flag))
        player.start()
        
        while player.is_alive(): 
            try:
                timer = Timer(10, packet_analyzer.terminate)
                timer.start()
                packet = packet_analyzer.stdout.readline()
                
                try:
                    src, dst, time, size = network.format_packet(packet)
                except Exception:
                    break
                
                if not stream:
                    stream = (src, dst)
                    init_time = last_active = time
                    current_segment = size
                    continue

                time_elapsed = round(last_active-init_time, 1)
            
                if time - last_active > SEGMENT_TIME_THRESHOLD:
                    segments.append(current_segment)
                    segment_times.append(time_elapsed)
                    current_segment = 0

                last_active = time
                current_segment += size

            except KeyboardInterrupt:
                exit_flag.set()
                interuppted = True
                print("Interuppted. Quitting testing...")
                break

            finally:
                timer.cancel()

        exit_flag.set()
        packet_analyzer.kill()
        with (open('svtplay_test_data.csv', 'a', newline='', encoding='utf8')
                as csv_file):
            writer = csv.writer(csv_file)
            segment_data = list(zip(segments, segment_times))
            writer.writerow([title, svt_id, start_time] + segment_data)

        if interuppted:
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plays videos and gathers segment test data from" +
            " SVT Play in real-time.")
    parser.add_argument("-i", "--interface", 
        help="Network interface to run the test data gatherer on.",
        required=True)
    args = parser.parse_args()
    interface = args.interface
    run(interface)