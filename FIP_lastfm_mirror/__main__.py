"""
Mirror the FIP webradios to lastfm.
"""
import json
import logging
import time
import argparse
import datetime
import configparser
import pylast
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

logger = logging.getLogger()
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)

TEMPS_DEBUT = time.time()
AUJ = datetime.datetime.now().strftime("%Y-%m-%d")
ENABLED_WEBRADIOS = [
    "FIP",
    "Rock",
    "Jazz",
    "Groove",
    "Monde",
    "Nouveautés",
    "Reggae",
    "Electro",
    "L'été Metal",
]


def get_soup(browser):
    return BeautifulSoup(browser.page_source, "lxml")


def get_FIP_metadata(browser):
    url = "https://www.fip.fr"
    new_titles = []
    browser.get(url)

    # click on cookie bar
    try:
        browser.find_element_by_xpath(
            "/html/body/div/div/div[2]/div[2]/button[2]/span"
        ).click()
        logger.debug("Cookie bar is now hidden.")
    except Exception as e:
        logger.debug("Cookie bar not found : %s.", e)

    # go to the bottom to load all the page
    browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    soup = get_soup(browser)

    for live_div in soup.find_all("div", {"class": "live-block"}):
        metadata = [
            x.text
            for x in live_div.find(
                "div", {"class": "live-block-info"}
            ).find_all("span")
        ]
        logger.debug(len(metadata))
        logger.debug(metadata)

        if (
            len(metadata) == 2
            and metadata[0] != "Écouter le direct"
            and metadata[0] in ENABLED_WEBRADIOS
        ):
            new_titles.append({"webradio": metadata[0], "title": metadata[1]})
    logger.debug("New titles : %s", new_titles)
    return new_titles


def get_lastfm_network(webradio_name):
    logger.debug("Getting lastfm network for %s.", webradio_name)
    config = configparser.RawConfigParser()
    config.read("config.ini")
    API_KEY = config[webradio_name]["API_KEY"]
    API_SECRET = config[webradio_name]["API_SECRET"]
    username = config[webradio_name]["username"]
    password = pylast.md5(str(config[webradio_name]["password"]))

    network = pylast.LastFMNetwork(
        api_key=API_KEY,
        api_secret=API_SECRET,
        username=username,
        password_hash=password,
    )
    return network


def post_title_to_lastfm(title):
    logger.debug(
        "Posting title %s to webradio %s.", title["title"], title["webradio"]
    )
    network = get_lastfm_network(title["webradio"])

    artist, track_name = title["title"].split(" - ", 1)
    unix_timestamp = int(time.mktime(datetime.datetime.now().timetuple()))

    network.scrobble(artist=artist, title=track_name, timestamp=unix_timestamp)

    return title["title"]


def main():
    args = parse_args()
    options = Options()
    options.headless = args.no_headless
    browser = webdriver.Firefox(options=options)

    last_posted_songs_file = "last_posted_songs"
    if Path(last_posted_songs_file).is_file():
        with open(last_posted_songs_file) as f:
            last_posted_songs = json.load(f)
    else:
        last_posted_songs = {}
    logger.debug("last_posted_songs file contains : %s", last_posted_songs)

    new_titles = get_FIP_metadata(browser)

    for title in new_titles:
        logger.debug(
            "Testing if %s for the %s webradio has been posted.",
            title["title"],
            title["webradio"],
        )
        # if key doesn't exist in dict (i.e. first iteration)
        if not title["webradio"] in last_posted_songs:
            last_posted_songs[title["webradio"]] = post_title_to_lastfm(title)
        # if title is already the last title posted
        if title["title"] != last_posted_songs[title["webradio"]]:
            last_posted_songs[title["webradio"]] = post_title_to_lastfm(title)
        else:
            logger.debug(
                "%s : %s already posted. Skipping.",
                title["webradio"],
                title["title"],
            )

    logger.debug("Exporting last_posted_songs.")
    with open(last_posted_songs_file, "w") as f:
        json.dump(last_posted_songs, f)

    logger.debug("Closing selenium browser.")
    browser.close()
    browser.quit()

    logger.info("Runtime : %.2f seconds." % (time.time() - TEMPS_DEBUT))


def parse_args():
    format = "%(levelname)s :: %(message)s"
    parser = argparse.ArgumentParser(
        description="Mirror the FIP webradios to lastfm."
    )
    parser.add_argument(
        "--debug",
        help="Display debugging information",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,
    )
    parser.add_argument(
        "positional_argument", nargs="?", type=str, help="Positional argument"
    )
    parser.add_argument(
        "--no_headless",
        help="Disable headless mode for the selenium browser.",
        dest="no_headless",
        action="store_false",
    )
    parser.set_defaults(no_headless=True)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format=format)
    return args


if __name__ == "__main__":
    main()
