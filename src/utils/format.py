from utils.console import console
import datetime
import math

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

def timestamp_to_sec(timestamp: str) -> float:
    h, m, s = timestamp.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def format_sse(data: str) -> str:
    sse_msg = f'data: {data}\n\n'
    return sse_msg

def cli_print(data, stream_num):

    src = data['IP src']
    dst = data['IP dst']
    segment = data['Captured segment']
    elapsed = data['Elapsed']
    color = f"[color({stream_num+2})]>[/color({stream_num+2})]"
    format_str = (f"{color} [bold white]#{stream_num}[/bold white] " +
        f"[bold blue]{elapsed}s[/bold blue] {src} " +
        f":right_arrow: {segment} [b]B[/b] :right_arrow: {dst} ")

    if data['Match']:
        format_str += (f":white_heavy_check_mark: " +
            f"[green]{data['Match'][0]} [/green] :watch: " +
            f"{datetime.timedelta(seconds=int(data['Match'][5][:-1]))}")
    else:
        format_str += f":magnifying_glass_tilted_left:"

    console.print(format_str)
