import subprocess
import socket
import platform
from utils import format

def get_packet_analyzer(capture_filter, interface, 
        tshark_dir='C:\Program Files\Wireshark\\'):

    if platform.system() == 'Windows':
        tshark = subprocess.Popen(
            (
                tshark_dir + "tshark",
                "-i" + interface,
                "-f" + capture_filter,
                "-n",
                "-Tfields",
                "-eframe.time_relative",
                "-eip.src",
                "-eip.dst",
                "-etcp.len"
            ),
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            encoding = 'utf8'
        )
        return tshark
    else:
        tcpdump = subprocess.Popen(
            (
                "tcpdump",
                "-i" + interface,
                "-q",
                "-n", 
                "-ttttt",
                capture_filter
            ),
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            encoding = 'utf8'
        )
        return tcpdump

def _get_cdn_ips(name, start, end, char_start, char_end):
    cdn_ips = set()
    for i in range(start, end + 1):
        if char_end:
            for j in range(char_start, char_end + 1):
                for ip in socket.getaddrinfo(name.format(num=i, char=chr(j)),
                        443, family=socket.AF_INET):
                    cdn_ips.add(ip[4][0])
        else:
            for ip in socket.getaddrinfo(name.format(num=i), 
                    443, family=socket.AF_INET):
                cdn_ips.add(ip[4][0])
    return cdn_ips

def get_svtplay_ips(full_cdn_search=False):

    svtplay_ips = _get_cdn_ips('ed{num}.cdn.svt.se', 0, 9, 0, 0)
    if full_cdn_search:
        svtplay_ips |= (
            _get_cdn_ips('svt-vod-{num}.secure.footprint.net', 1, 10, 0, 0) |
            _get_cdn_ips('svt-vod-{num}{char}.akamaized.net', 1, 9, 97, 116))
    return svtplay_ips

def format_packet(packet):
    if platform.system() == "Windows":
        packet = packet.strip().split("\t")
        time = float(packet[0])
        src = packet[1]
        dst = packet[2]
    else:
        packet = packet.strip().split(" ")
        time = format.timestamp_to_sec(packet[0])
        src = '.'.join(packet[2].split('.')[:-1])
        dst = '.'.join(packet[4].split('.')[:-1])

    size = int(packet[-1])

    return src, dst, time, size