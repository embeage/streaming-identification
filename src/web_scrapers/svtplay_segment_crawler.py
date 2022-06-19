from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import aiohttp
import asyncio
import tqdm
import csv
import random
import sys
import logging

logging.basicConfig(
    filename = 'segment_crawler.log',
    encoding = 'utf-8',
    level = logging.ERROR,
    format = '%(asctime)s %(levelname)s: %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)

DASH_FORMATS = (
    "dash-full",
    "dash",
    "dash-avc",
    "dash-avc-51",
    "dash-lb-full",
    "dash-lb",
    "dash-lb-avc",
    "dash-hb-avc",
    "dashhbbtv",
    "dash-hbbtv",
    "dash-hbbtv-avc",
    "dash-hbbtv-avc-51")

NEWS = (
    'Aktuellt', 
    'Kulturnyheterna', 
    'Lokala Nyheter', 
    'Morgonstudion', 
    'Rapport', 
    'Sportnytt', 
    'Väder')

def write_to_db(db_file, finalized_encodings):
    csv_writer = csv.writer(db_file)
    for encoding in finalized_encodings:
        metadata = next(iter(encoding))
        segments = encoding[metadata]
        csv_writer.writerow(metadata.rsplit(",", 4) + segments)

async def complete(session, svt_id, not_found=False, news=False, 
        long_video=False, no_dash=False):
    
    data = {'svt_id': svt_id}   
    if not_found:
        data['not_found'] = True
    elif news:
        data['news'] = True
    elif long_video:
        data['long_video'] = True
    elif no_dash:
        data['no_dash'] = True
    await session.post(
        'https://svtscraper.herokuapp.com/videos/complete',
        json=data,
        auth=aiohttp.BasicAuth('', ''))

async def fetch(session, url, json=False):
    async with session.get(url) as resp:
        if json: 
            return await resp.json()
        return await resp.read()

async def fetch_content_length(session, url):
    async with session.head(url) as resp:
        return resp.content_length

async def get_segment_sizes(session, base_url, rep, audio=False):

    segmentTemplate = rep.find('segmenttemplate')
    media_path = segmentTemplate['media'].replace('$Number$', '{}')
    media_url = urljoin(base_url, media_path)
    segment_timeline = segmentTemplate.find('segmenttimeline')
    n_segments = 0

    for segment in segment_timeline.find_all('s'):
        n_segments += 1
        subsequent_segments = segment.get('r')
        if subsequent_segments is None:
            continue
        for i in range(int(subsequent_segments)):
            n_segments += 1

    tasks = []
    for i in range(1, n_segments + 1):
        tasks.append(asyncio.create_task(
            fetch_content_length(session, media_url.format(i))))

    try:
        segment_sizes = await asyncio.gather(*tasks)
    except aiohttp.ClientError as e:
        # Cancel all remaining tasks if we encounter an error
        for t in tasks:
            t.cancel()
        raise e

    if audio:
        return segment_sizes
    
    # Encoding metadata
    bandwidth = rep['bandwidth']
    width = rep['width']
    height = rep['height']

    return {f"{bandwidth}bps,{width}x{height}p": segment_sizes}

async def scrape_video(session, svt_id):

    url = f'https://api.svt.se/video/{svt_id}'
    try:
        metadata = await fetch(session, url, json=True)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            await complete(session, svt_id, not_found=True)
            return []
        else:
            raise e

    if metadata is None:
        await complete(session, svt_id, not_found=True)
        return []

    try:
        title = metadata.get('programTitle')
        if title and title.startswith(NEWS):
            await complete(session, svt_id, news=True)
            return []
        episode_title = metadata['episodeTitle']
        if title and episode_title != title:
            title += f": {episode_title}"
        elif not title:
            title = episode_title
        content_duration = metadata['contentDuration']
        video_references = metadata['videoReferences']
    except KeyError as e:
        logging.error(f"ID: {svt_id}. {repr(e)}")
        return []

    if content_duration > 18000:
        await complete(session, svt_id, long_video=True)
        return []

    formats = {ref.get('format'): ref for ref in video_references}
    for dash_format in DASH_FORMATS:
        if dash_format in formats:
            ref = formats[dash_format]
            break
    else:
        await complete(session, svt_id, no_dash=True)
        return []
    
    # Exclude HEVC video codec and AC-3 audio codec. SVT does this
    # when watching from browser. Might be relevant on TV app.
    manifest_url = ref['url'] + '&excludeCodecs=hvc&excludeCodecs=ac-3'
    url = f'https://api.svt.se/ditto/api/V1/web?manifestUrl={manifest_url}'
    manifest_data = await fetch(session, url)

    soup = BeautifulSoup(manifest_data.decode('utf8'), 'lxml')
    base_url = soup.find('baseurl').text

    tasks = []
    for adaptation_set in soup.find_all('adaptationset'):
        if adaptation_set['contenttype'] == 'video':
            # Get all video representations (encodings)
            for rep in adaptation_set.find_all('representation'):
                tasks.append(asyncio.create_task(
                    get_segment_sizes(session, base_url, rep)))
        elif adaptation_set['contenttype'] == 'audio':
            # Get the main audio track
            if adaptation_set.find('role')['value'] == 'main':
                rep = adaptation_set.find('representation')
                tasks.append(asyncio.create_task(
                    get_segment_sizes(session, base_url, rep, audio=True)))
    
    all_video_encodings = []

    try:
        for coro in tqdm.tqdm(asyncio.as_completed(tasks),
                total=len(tasks), desc=title):
            result = await coro
            if isinstance(result, list):
                main_audio_segments = result
            else:
                all_video_encodings.append(result)
    except aiohttp.ClientError as e:
        # Cancel all remaining tasks if we encounter an error
        for t in tasks:
            t.cancel()
        raise e

    # SVT sends each corresponding video and audio segment together
    # so we add each audio segment to every corresponding video
    # segment from every single encoding.
    finalized_encodings = []
    for encoding in all_video_encodings:
        encoding_metadata = next(iter(encoding))
        encoding_segments = encoding[encoding_metadata]
        final_encoding_segments = [video_seg + audio_seg 
            for video_seg, audio_seg 
                in zip(encoding_segments, main_audio_segments)]
        
        finalized_encodings.append({
            f"{title},{content_duration}s,{svt_id},{encoding_metadata}":
                final_encoding_segments})

    await complete(session, svt_id)
    return finalized_encodings

async def scraper(db_file):

    # Server seems to limit the duration of a TCP connection
    # so we disable HTTP keep-alive so we don't lose a
    # connection before we are done with it.
    connector = aiohttp.TCPConnector(force_close=True)

    async with aiohttp.ClientSession(connector=connector, 
            raise_for_status=True) as session:

        while True:
            data = await fetch(session, 
                "https://svtscraper.herokuapp.com/videos/random", json=True)
            if data is None:
                print("All videos scraped")
                break
            svt_id = data['svt_id']
            video_encodings = await scrape_video(session, svt_id)
            if video_encodings:
                write_to_db(db_file, video_encodings)

def main():    
    with (open('svtplay_scraped.csv', 'a', newline='', 
            encoding='utf8') as db_file):
        try:
            asyncio.run(scraper(db_file))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logging.error(repr(e))
            min = random.randint(1,2)
            print(f"Error. Retrying in {min} min..")
            time.sleep(min*60)
            main()
        except KeyboardInterrupt:
            print("Interuppted")
            sys.exit()

if __name__ == "__main__":
    main()
