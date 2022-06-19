from collections import deque
import argparse
from utils import format, network
import requests
import db
from utils.console import console

HTTP_HEADERS = 801
TLS_OVERHEAD = 1.0018
SEGMENT_TIME_THRESHOLD = 2
MIN_SEGMENT_SIZE = 5000
MAX_SEGMENT_SIZE = 9000000

def run(interface, cli, window_width, k, pearson_threshold, full_cdn_search):

    identification_db = db.IdentificationDB(window_width, k)

    with console.status("Identifier running (CTRL-C to quit)...", 
            spinner='circle'):

        streams = {}
        capture_filter = ('src ' + ' or src '.join(network.get_svtplay_ips(
            full_cdn_search)) + ' and greater 0')
        packet_analyzer = network.get_packet_analyzer(capture_filter, 
            interface)
        
        try:
            for packet in iter(packet_analyzer.stdout.readline, ''):
                src, dst, time, size = network.format_packet(packet)
                stream = (src, dst)

                if stream not in streams:
                    init_time = last_active = time
                    init_segment = size
                    window = deque(maxlen=window_width)
                    identified = False
                    streams[stream] = [init_time, last_active, 
                        init_segment, window, identified]
                    continue
                
                init_time, last_active, segment, window, \
                    identified = streams[stream]

                # Real-time segmenting and matching
                if time - last_active > SEGMENT_TIME_THRESHOLD:

                    captured_segment = (round(segment / TLS_OVERHEAD) 
                        - HTTP_HEADERS)

                    if MIN_SEGMENT_SIZE < captured_segment < MAX_SEGMENT_SIZE:
                        
                        window.append(captured_segment)
                        time_elapsed = round(last_active-init_time, 1)
                        data = {'IP src': src, 'IP dst': dst, 
                            'Elapsed': time_elapsed,
                            'Captured segment': captured_segment,
                            'Match': []}

                        if len(window) == window_width:
                            match_or_empty = identification_db.identify(
                                window, pearson_threshold)
                            data['Match'] = match_or_empty

                        if cli:
                            format.cli_print(data, 
                                list(streams.keys()).index(stream)+1)
                        elif not identified:
                            if data['Match']:
                                streams[stream][4] = True
                            requests.post('http://localhost:5000', json=data)                

                    # Start building new segment
                    streams[stream][2] = 0

                streams[stream][1] = time
                streams[stream][2] += size

        except KeyboardInterrupt:
            print("Quitting identifier...")
        finally:
            packet_analyzer.kill()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detects and identifies HTTPS " +
            "encrypted videos from SVT Play.")
    parser.add_argument("-i", "--interface", 
        help="network interface to run identifier on",
        required=True)
    parser.add_argument('--full-cdn-search',
        action=argparse.BooleanOptionalAction,
        help="")
    parser.add_argument('--cli', 
        action=argparse.BooleanOptionalAction,
        help="show output in the terminal instead of web interface")
    parser.add_argument('-w', "--window-width",
        help="amount of segments in a window",
        type=int,
        default=4)
    parser.add_argument('-k', "--k-dimension",
        help="dimension used for k-d tree",
        type=int,
        default=4)
    parser.add_argument('-p', "--pearson-threshold",
        help="pearson's r threshold used when determining a match",
        type=float,
        default=0.99999999)
    args = parser.parse_args()
    interface = args.interface
    full_cdn_search = args.full_cdn_search
    cli = args.cli
    window_width = args.window_width
    k = args.k_dimension
    pearson_threshold = args.pearson_threshold
    run(interface, cli, window_width, k, pearson_threshold, full_cdn_search)
