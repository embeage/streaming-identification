from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import argparse
import time
import os

def play_video(url, playback_time, exit_flag=None):

    os.environ['WDM_LOG'] = '0'
    options = webdriver.ChromeOptions()
    options.add_argument('--log-level=3')
    options.add_argument('start-maximized')
    driver = webdriver.Chrome(ChromeDriverManager().install(), 
        options=options)
    driver.get(url)

    # Click cookie pop-up
    try:
        WebDriverWait(driver, 2).until(
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

    # Play video
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//span[starts-with(@aria-label, 'Spela') " +
                    "and starts-with(text(), 'Spela')]"))
        ).click()
    except TimeoutException:
        if exit_flag is not None:
            exit_flag.set()
        else:
            driver.quit()
            return

    # Accept inappropriate content
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//span[text()='Jag förstår']"))
        ).click()
    except TimeoutException:
        pass
    else:
        driver.find_element_by_xpath(
            "//button[@data-rt='video-player-parental-splash-play']").click()

    if exit_flag is not None:
        while not exit_flag.is_set():
            exit_flag.wait(playback_time)
            exit_flag.set()
    else:
        time.sleep(playback_time)

    driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Opens a Chrome window and plays a SVT Play video.")
    parser.add_argument("--url", 
        help="SVT Play video to play.",
        required=True)
    parser.add_argument("--time",
        help="How long to play the video in seconds.",
        required=True)
    args = parser.parse_args()
    url = args.url
    playback_time = int(args.time)
    play_video(url, playback_time)