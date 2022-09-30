from collections import deque
import argparse
from utils import format, network
import requests
import db
from utils.console import console
#import traceback

HTTP_HEADERS = 801
TLS_OVERHEAD = 1.0018
SEGMENT_TIME_THRESHOLD = 2
MIN_SEGMENT_SIZE = 5000
MAX_SEGMENT_SIZE = 9000000

NB_BEST_MATCHES = 10
MAX_MATCHES_PER_STREAM = 100
INIT_PROBA = 0
ALPHA = 0.33
IDENTIFICATION_THRESHOLD = 0.75

def update_proba(old_proba, pearson):
    return (1-ALPHA)*old_proba + ALPHA*pearson

def run(interface, cli, window_width, k, pearson_threshold, full_cdn_search):

    identification_db = db.IdentificationDB(window_width, k)

    streams = {}
    if full_cdn_search:
        #console.log("Full CDN search running...")
        #capture_filter = ('src ' + ' or src '.join(network.get_svtplay_ips(full_cdn_search))
        #              + ' and greater 0')
        capture_filter = network.PRELOADED_CDN_FILTER
        #print(capture_filter)
    else:
        capture_filter = ('src net 185.102.0.0/16 and greater 0')
        
    packet_analyzer = network.get_packet_analyzer(capture_filter, interface)
    console.log("Packet analyzer up and running!")

    #with console.status("Identifier running (CTRL-C to quit)...", spinner='circle'):    
    if True:
        try:
            for packet in iter(packet_analyzer.stdout.readline, ''):
                src, dst, time, size, psrc, pdst = network.format_packet(packet)
                stream = (src, dst)

                if stream not in streams:
                    console.log(f"New SVT stream: {src}:{psrc} -> {dst}:{pdst}")
                    init_time = last_active = time
                    init_segment = size
                    window = deque(maxlen=window_width)
                    identified = {}
                    streams[stream] = [init_time, last_active, init_segment, window, identified]
                    continue
                
                init_time, last_active, segment, window, identified = streams[stream]

                # Real-time segmenting and matching when gap is detected
                if time - last_active > SEGMENT_TIME_THRESHOLD:

                    captured_segment = round(segment / TLS_OVERHEAD) - HTTP_HEADERS

                    if MIN_SEGMENT_SIZE < captured_segment < MAX_SEGMENT_SIZE: 
                        window.append(captured_segment)
                        time_elapsed = round(last_active-init_time, 1)
                        data = {'IP src': src, 'IP dst': dst, 
                            'Elapsed': time_elapsed,
                            'Captured segment': captured_segment,
                            'Match': [], 'Match2': [], 'Match3': [],
                            'Best match': [],
                            'Probability': 0}

                        # Update latest match

                        if len(window) == window_width:
                            #match_or_empty = identification_db.identify(window, pearson_threshold)
                            matches = identification_db.best_matches(window, NB_BEST_MATCHES)

                            for match, matched_window in matches:
                                title, pearson = match[0], match[-1]
                                pearson = max(0,pearson) # clip to [0,1]
                                if title not in identified:
                                    identified[title] = [INIT_PROBA, match, matched_window]
                                identified[title][0] = update_proba(identified[title][0],pearson)
                                identified[title][1] = match
                                identified[title][2] = matched_window

                        # For old matches, execute a pearson and also update their proba
                        # (OK to re-apply to all as pearson should be 0.999+ for newest ones)
                        for title in identified.keys():
                            match = identified[title][1]
                            matched_window = identified[title][2]
                            pearson = db.compute_pearson(window, matched_window)
                            pearson = max(0,pearson) # clip to [0,1]
                            identified[title][0] = update_proba(identified[title][0],pearson)

                        # Find the best video match overall
                        proba, best_title = None, None
                        all_matches = sorted([(identified[title][0],title,identified[title][1])
                                              for title in identified])
                        
                        if all_matches:
                            proba, best_title, best_match = all_matches[-1]

                            data['Match'] = best_match[:-1] + (round(100*proba,1),)
                            data['Best match'] = best_title
                            data['Probability'] = round(100*proba,1)

                            if len(all_matches) > 1:
                                match2 = all_matches[-2]
                                data['Match2'] = match2[2][:-1] + (round(100*match2[0],1),)

                            if len(all_matches) > 2:
                                match3 = all_matches[-3]
                                data['Match3'] = match3[2][:-1] + (round(100*match3[0],1),)

                            if proba >= IDENTIFICATION_THRESHOLD:
                                data['Match'] = best_match[:-1] + (round(100*proba,1),)

                        # Keep a bounded dictionary (keep only best matches over time)
                        identified = {}
                        for p,title,match in all_matches[:MAX_MATCHES_PER_STREAM]:
                            identified[title] = (p,match)

                        # Always also plot to cli & to web interface
                        stream_id = list(streams.keys()).index(stream)+1
                        format.cli_print(data, stream_id, proba and proba > 0.75, best_title, proba)
                        
                        try:
                            requests.post('http://localhost:5000', json=data)
                        except:
                            pass
                        
                        #if not identified:
                        #    if data['Match']:
                        #        streams[stream][4] = True
                        #requests.post('http://localhost:5000', json=data)

                    # Start building new segment
                    streams[stream][2] = 0

                # Update streams (last_active and current segment's size)
                streams[stream][1] = time
                streams[stream][2] += size

        except KeyboardInterrupt:
            console.log("Quitting identifier...")
        else:
            console.log("No packet captured on the interface...")
        finally:
            packet_analyzer.kill()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detects and identifies HTTPS encrypted videos from SVT Play.")
    parser.add_argument("-i", "--interface", required=True,
                        help="network interface to run identifier on")
    parser.add_argument('--full-cdn-search', action='store_true',  #default=True,
                        help="")
    parser.add_argument('--cli', action='store_true',
                        help="show output in the terminal instead of web interface")
    parser.add_argument('-w', "--window-width", default=12, type=int,
                        help="amount of segments in a window")
    parser.add_argument('-k', "--k-dimension", default=6, type=int,
                        help="dimension used for k-d tree")
    parser.add_argument('-p', "--pearson-threshold", default=0.99, type=float,
                        help="pearson's r threshold used when determining a match")
    args = parser.parse_args()
    interface = args.interface
    full_cdn_search = args.full_cdn_search
    cli = args.cli
    window_width = args.window_width
    k = args.k_dimension
    pearson_threshold = args.pearson_threshold
    run(interface, cli, window_width, k, pearson_threshold, full_cdn_search)
