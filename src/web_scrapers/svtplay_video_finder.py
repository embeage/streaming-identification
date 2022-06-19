from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import aiohttp
import asyncio
import re
import tqdm
import os
import requests
import logging

logging.basicConfig(
    filename = 'video_finder.log',
    encoding = 'utf-8',
    level = logging.ERROR,
    format = '%(asctime)s %(levelname)s: %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)

BASE_URL = 'https://www.svtplay.se/program'

def get_video_paths(soup):

    # Match against all paths that have an id at the end
    regex_str_id = ".*?id=\w*$"

    video_paths = []
    for a in soup.find_all('a', href=re.compile(regex_str_id)):
        video_paths.append(a['href'])

    return video_paths

def check_for_dom_buttons(soup, url, videos_with_dom):
    for button in soup.find_all('button'):
        aria_label = button.get('aria-label') 
        if aria_label == "Visa fler avsnitt":
            videos_with_dom.add(url)

def scrape_hidden_urls(videos_with_dom):
    """A few programs have videos only accessible by a clicking a 
    DOM button so we use a web driver to click it and access those
    videos.
    """
    os.environ['WDM_LOG'] = '0'
    options = webdriver.ChromeOptions()
    options.add_argument('--log-level=3')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(ChromeDriverManager().install(), 
        options=options)

    hidden_urls = set()

    for video_url in (pbar := tqdm.tqdm(videos_with_dom)):
        pbar.set_description(video_url)

        driver.get(video_url)

        try: # in case of cookie pop-up
            WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[text()='Acceptera alla']"))
            ).click()
        except TimeoutException:
            pass
        else:
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element(
                    (By.XPATH, "//div[@role='dialog' and contains(" +
                        "@aria-label, 'cookies')]")))

        try:
            dom_buttons = WebDriverWait(driver, 2).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//button[text()='Visa fler']"))
            )
            for dom_button in dom_buttons:
                dom_button.click()
        except TimeoutException:
            logging.info(f"Web driver timed out waiting for DOM buttons. " +
                f"URL: {video_url}")
            continue

        urls = (urljoin(BASE_URL, path) for path in get_video_paths(
            BeautifulSoup(driver.page_source, 'html.parser')))

        hidden_urls.update(urls)

    driver.quit()

    return hidden_urls

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def scrape_tab_paths(session, tab_path, videos_with_dom):
    tab_url = urljoin(BASE_URL, tab_path)
    response = await fetch(session, tab_url)
    soup = BeautifulSoup(response, 'html.parser')
    check_for_dom_buttons(soup, tab_url, videos_with_dom)
    return get_video_paths(soup)

async def scrape_program_urls(session, program_path, videos_with_dom):

    program_url = urljoin(BASE_URL, program_path)
    response = await fetch(session, program_url)
    soup = BeautifulSoup(response, 'html.parser')

    # Match against all tabs except accessibility (audio description
    # or sign language). Can be seasons, extra material etc.
    regex_str_tab = ".*?tab=(?!accessibility).*"

    tasks = []
    for a in soup.find_all('a', href=re.compile(regex_str_tab)):
        tab_path = a['href']
        tasks.append(asyncio.create_task(
            scrape_tab_paths(session, tab_path, videos_with_dom)))

    results = []
    try:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
    except aiohttp.ClientError as e:
        for t in tasks:
            t.cancel()
        raise e

    video_urls = [urljoin(BASE_URL, video_path) for tab_video_paths in results
        for video_path in tab_video_paths]

    # Also get all urls that are not in a tab
    video_urls += [urljoin(BASE_URL, video_path) 
        for video_path in get_video_paths(soup)]

    check_for_dom_buttons(soup, program_url, videos_with_dom)

    return video_urls

async def scrape_urls(videos_with_dom):
    
    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        response = await fetch(session, BASE_URL)
        soup = BeautifulSoup(response, 'html.parser')

        tasks = []
        
        for li in soup.find_all('li', attrs={'data-rt': 
                "alphabetic-list-item"}):
            a = li.find('a')
            program_path = a['href']
            tasks.append(asyncio.create_task(scrape_program_urls(
                session, program_path, videos_with_dom)))
        
        results = []
        try:
            for coro in tqdm.tqdm(asyncio.as_completed(tasks), 
                    total=len(tasks)):
                result = await coro
                results.append(result)
        except aiohttp.ClientError as e:
            for t in tasks:
                t.cancel()
            raise e

    return [video_url for program_video_urls in results 
        for video_url in program_video_urls]

def main():

    try:
        urls_with_dom = set()
        video_urls = set(asyncio.run(scrape_urls(urls_with_dom)))
        try:
            hidden_video_urls = scrape_hidden_urls(urls_with_dom)
        except Exception as e:
            logging.error(repr(e))

        video_urls |= hidden_video_urls
        
        videos = []
        for video_url in video_urls:
            svt_id = video_url[-7:]
            videos.append({'svt_id': svt_id, 'url': video_url})

        requests.post('https://svtscraper.herokuapp.com/videos/update', 
            json={'videos': videos},
            auth=('', ''))

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logging.error(repr(e))
        print("Error. Try again later.") 
        
if __name__ == "__main__":
    main()