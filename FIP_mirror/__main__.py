"""
Mirror the FIP webradios to several services.
"""
import requests
import json
import logging
import time
import argparse
import datetime
import configparser
import pylast
import tweepy
from mastodon import Mastodon
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

logger = logging.getLogger()
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("tweepy").setLevel(logging.WARNING)
logging.getLogger("chardet.charsetprober").setLevel(logging.WARNING)

config = configparser.RawConfigParser()
config.read("config.ini")

BEGIN_TIME = time.time()
ENABLED_WEBRADIOS = [
    "FIP",
    "Rock",
    "Jazz",
    "Groove",
    "Monde",
    "Nouveautés",
    "Reggae",
    "Electro",
    "Metal",
]


def lastfmconnect(webradio_name):
    logger.debug("Getting lastfm network for %s.", webradio_name)
    API_KEY = config[f"lastfm-{webradio_name}"]["API_KEY"]
    API_SECRET = config[f"lastfm-{webradio_name}"]["API_SECRET"]
    username = config[f"lastfm-{webradio_name}"]["username"]
    password = pylast.md5(str(config[f"lastfm-{webradio_name}"]["password"]))

    network = pylast.LastFMNetwork(
        api_key=API_KEY,
        api_secret=API_SECRET,
        username=username,
        password_hash=password,
    )
    return network


def twitterconnect():
    consumer_key = config["twitter"]["consumer_key"]
    secret_key = config["twitter"]["secret_key"]
    access_token = config["twitter"]["access_token"]
    access_token_secret = config["twitter"]["access_token_secret"]

    auth = tweepy.OAuthHandler(consumer_key, secret_key)
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)


def mastodonconnect():
    if not Path("mastodon_clientcred.secret").is_file():
        Mastodon.create_app(
            "mastodon_bot_lastfm_cg",
            api_base_url=config["mastodon"]["api_base_url"],
            to_file="mastodon_clientcred.secret",
        )

    if not Path("mastodon_usercred.secret").is_file():
        mastodon = Mastodon(
            client_id="mastodon_clientcred.secret",
            api_base_url=config["mastodon"]["api_base_url"],
        )
        mastodon.log_in(
            config["mastodon"]["login_email"],
            config["mastodon"]["password"],
            to_file="mastodon_usercred.secret",
        )

    mastodon = Mastodon(
        access_token="mastodon_usercred.secret",
        api_base_url=config["mastodon"]["api_base_url"],
    )
    return mastodon


def get_soup(browser):
    return BeautifulSoup(browser.page_source, "lxml")


def get_FIP_metadata(browser):
    urls_webradios = [
        "https://www.fip.fr",
        "https://www.fip.fr/rock/webradio",
        "https://www.fip.fr/jazz/webradio",
        "https://www.fip.fr/groove/webradio",
        "https://www.fip.fr/musiques-du-monde/webradio",
        "https://www.fip.fr/tout-nouveau-tout-fip/webradio",
        "https://www.fip.fr/reggae/webradio",
        "https://www.fip.fr/electro/webradio",
        "https://www.fip.fr/fip-metal/webradio",
    ]
    new_titles = []

    for url in urls_webradios:
        browser.get(url)
        # Click on cookie bar if found.
        try:
            browser.find_element_by_xpath(
                "/html/body/div/div/div[2]/div[2]/button[2]/span"
            ).click()
            logger.debug("Cookie bar is now hidden.")
        except Exception as e:
            logger.debug("Cookie bar not found : %s.", e)

        # Go to the bottom to load all the page.
        # browser.execute_script(
        #     "window.scrollTo(0, document.body.scrollHeight);"
        # )
        logger.debug("Waiting for 1 second.")
        time.sleep(1)

        soup = get_soup(browser)

        metadata = {}

        # Taking the last word
        # "En direct sur FIP" becomes FIP
        # "En direct sur FIP Rock" becomes Rock
        metadata["webradio"] = soup.find(
            "h1", {"class": "channel-header-title"}
        ).text.split()[-1]

        metadata["title"] = soup.find("span", {"class": "now-info-title"}).text

        subtitle = soup.find("span", {"class": "now-info-subtitle"}).text
        try:
            potential_year = (
                subtitle.rsplit(" ", 1)[1].replace("(", "").replace(")", "")
            )
            if potential_year.isdigit():
                metadata["year"] = potential_year
                metadata["artist"] = subtitle.rsplit(" ", 1)[0]
            else:
                metadata["artist"] = subtitle
        except Exception as e:
            logger.error(e)
            metadata["artist"] = subtitle

        details_label = [
            x.text
            for x in soup.find_all("span", {"class": "now-info-details-label"})
        ]
        logger.debug(details_label)
        details_value = [
            x.text.strip()
            for x in soup.find_all("span", {"class": "now-info-details-value"})
        ]
        logger.debug(details_value)

        for index, label in enumerate(details_label):
            metadata[label.lower()] = details_value[index]

        metadata["cover_url"] = soup.find(
            "div", {"class": "now-cover playing-now-cover"}
        ).find("img")["src"]

        if not metadata["cover_url"].startswith("http"):
            metadata["cover_url"] = "https://fip.fr" + metadata["cover_url"]

        logger.debug(metadata)

        if (
            # At least webradio, artist, title in dict.
            {"webradio", "artist", "title"} <= set(metadata)
            and metadata["webradio"] in ENABLED_WEBRADIOS
            and metadata["title"] != ""
            and metadata["artist"] != ""
        ):
            new_titles.append(metadata)
        else:
            logger.info(
                "Metadata %s didn't fullfill the requirements.", metadata
            )
    logger.debug("New titles : %s", new_titles)
    return new_titles


def post_title_to_lastfm(title):
    network = lastfmconnect(title["webradio"])

    unix_timestamp = int(time.mktime(datetime.datetime.now().timetuple()))

    if "album" in title:
        logger.info(
            "Lastfm : Posting %s - %s (%s) to webradio %s.",
            title["artist"],
            title["title"],
            title["album"],
            title["webradio"],
        )
        network.scrobble(
            artist=title["artist"],
            title=title["title"],
            timestamp=unix_timestamp,
            album=title["album"],
        )
    else:
        logger.info(
            "Lastfm : Posting %s - %s to webradio %s.",
            title["artist"],
            title["title"],
            title["webradio"],
        )
        network.scrobble(
            artist=title["artist"],
            title=title["title"],
            timestamp=unix_timestamp,
        )


def tweet_image(api, filename, title, social_media):
    if social_media == "twitter":
        pic = api.media_upload(str(filename))
        api.update_status(status=title, media_ids=[pic.media_id_string])
    elif social_media == "mastodon":
        id_media = api.media_post(str(filename), "image/png")
        api.status_post(title, media_ids=[id_media])


def get_fip_cover(title):
    try:
        return requests.get(title["cover_url"])
    except Exception as e:
        logger.error("Error : %s.", e)
        return None


def get_lastfm_cover(network, title):
    logger.debug(f"Searching image for {title}.")
    try:
        picture_url = network.get_album(
            title["artist"], title["album"]
        ).get_cover_image()
    except Exception as e:
        logger.error("Error in lastfm cover extraction : %s.", e)
        picture_url = None

    if picture_url:
        picture = requests.get(picture_url)
    else:
        picture = None
    return picture


def post_tweet(title):
    twitter_api = twitterconnect()
    mastodon_api = mastodonconnect()
    lastfm_api = lastfmconnect(title["webradio"])

    # Search youtube video
    youtube_url = get_youtube_url(title)
    logger.info(
        "Youtube url for %s - %s : %s.",
        title["artist"],
        title["title"],
        youtube_url,
    )

    # Four cases :
    # 1) album present, cover found on fip
    # 2) album present, cover found on lastfm
    # 3) album present, cover not found on lastfm nor on fip
    # 4) no album
    # also year
    additional_infos = ""
    if "album" in title:
        if "year" in title:
            additional_infos += f" ({title['album']} - {title['year']})"
        else:
            additional_infos += f" ({title['album']})"
    if youtube_url:
        additional_infos += f" {youtube_url}"

    tweet_text = f"#fipradio #nowplaying {title['artist']} - {title['title']}{additional_infos}"
    if "album" in title:
        logger.info(
            "Twitter : Posting %s - %s (%s). Tweet text : %s.",
            title["artist"],
            title["title"],
            title["album"],
            tweet_text,
        )
        # Cover is not the placeholder on fip
        if "cover_url" in title and "placeholder" not in title["cover_url"]:
            cover = get_fip_cover(title)
            # Cover successfully downloaded
            if cover and cover.status_code == 200:
                with open("cover.jpg", "wb") as f:
                    f.write(cover.content)
                tweet_image(twitter_api, "cover.jpg", tweet_text, "twitter")
                tweet_image(mastodon_api, "cover.jpg", tweet_text, "mastodon")
            # Problem with the cover download
            else:
                twitter_api.update_status(status=tweet_text)
                mastodon_api.status_post(tweet_text)
        # Cover is the placeholder, searching on lastfm
        elif "cover_url" in title and "placeholder" in title["cover_url"]:
            cover = get_lastfm_cover(lastfm_api, title)
            # Cover found on lastfm and successfully downloaded
            if cover and cover.status_code == 200:
                with open("cover.png", "wb") as f:
                    f.write(cover.content)
                tweet_image(twitter_api, "cover.png", tweet_text, "twitter")
                tweet_image(mastodon_api, "cover.png", tweet_text, "mastodon")
            # Cover not found on lastfm
            else:
                twitter_api.update_status(status=tweet_text)
                mastodon_api.status_post(tweet_text)
        else:
            twitter_api.update_status(status=tweet_text)
            mastodon_api.status_post(tweet_text)
    else:
        twitter_api.update_status(status=tweet_text)
        mastodon_api.status_post(tweet_text)
        logger.info(
            "Twitter : Posting %s - %s. Tweet text : %s.",
            title["artist"],
            title["title"],
            tweet_text,
        )


def get_youtube_url(title):
    # Extracting youtube urls
    header = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0"
    }
    with requests.Session() as session:
        session.headers.update = header
        logger.debug("Extracting youtube url for %s.", title)
        name = f"{title['artist']} - {title['title']}"
        url = "https://www.youtube.com/results?search_query=" + name.replace(
            " ", "+"
        ).replace("&", "%26").replace("(", "%28").replace(")", "%29")
        logger.info("Youtube URL search : %s", url)
        soup = BeautifulSoup(session.get(url).content, "lxml")
    # Test if youtube is rate-limited
    if soup.find("form", {"id": "captcha-form"}):
        logger.error("Rate-limit detected on Youtube. Exiting.")
        return None
    try:
        titles = soup.find_all(
            "a",
            {
                "class": "yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link"
            },
        )
        href = [x["href"] for x in titles if x["href"]]
        # delete user channels url
        href = [x for x in href if "channel" not in x and "user" not in x]
        logger.debug("href : %s.", href)
        url = f"https://youtu.be/{href[0].split('?v=', 1)[-1]}"
        # logger.info(url)
        # url = "https://www.youtube.com" + href[0]
    except Exception as e:
        logger.error(e)
        return None
    return url


def main():
    args = parse_args()
    options = Options()
    options.headless = args.no_headless
    browser = webdriver.Firefox(options=options)

    # Loading last posted songs
    last_posted_songs_filename = "last_posted_songs"
    if Path(last_posted_songs_filename).is_file():
        with open(last_posted_songs_filename) as f:
            last_posted_songs = json.load(f)
    else:
        last_posted_songs = {}
    logger.debug("last_posted_songs contains : %s", last_posted_songs)

    new_titles = get_FIP_metadata(browser)

    for title in new_titles:
        try:
            logger.debug(
                "Testing if %s - %s for the %s webradio has been posted.",
                title["artist"],
                title["title"],
                title["webradio"],
            )
            if not args.no_posting:
                # if key doesn't exist in dict (i.e. first iteration)
                if not title["webradio"] in last_posted_songs:
                    # post to lastfm (all webradios)
                    post_title_to_lastfm(title)
                    # post to twitter/mastodon (main webradio)
                    if title["webradio"] == "FIP":
                        post_tweet(title)
                    # add title to posted titles
                    last_posted_songs[
                        title["webradio"]
                    ] = f"{title['artist']} - {title['title']}"
                # if title is not the last title posted
                if (
                    f"{title['artist']} - {title['title']}"
                    != last_posted_songs[title["webradio"]]
                ):
                    # post to lastfm (all webradios)
                    post_title_to_lastfm(title)
                    # post to twitter/mastodon (main webradio)
                    if title["webradio"] == "FIP":
                        post_tweet(title)
                    # add title to posted titles
                    last_posted_songs[
                        title["webradio"]
                    ] = f"{title['artist']} - {title['title']}"
                else:
                    logger.debug(
                        "%s : %s already posted. Skipping.",
                        title["webradio"],
                        title["title"],
                    )

                # Exporting each time
                logger.debug("Exporting last_posted_songs.")
                with open(last_posted_songs_filename, "w") as f:
                    json.dump(last_posted_songs, f)
            else:
                logger.debug("No-posting mode activated.")
        except Exception as e:
            logger.error("Error for title %s : %s.", title, e)

    logger.debug("Closing selenium browser.")
    browser.close()
    browser.quit()

    logger.info("Runtime : %.2f seconds." % (time.time() - BEGIN_TIME))


def parse_args():
    format = "%(levelname)s :: %(message)s"
    parser = argparse.ArgumentParser(
        description="Mirror the FIP webradios to several services."
    )
    parser.add_argument(
        "--debug",
        help="Display debugging information.",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,
    )
    parser.add_argument(
        "--no_headless",
        help="Disable headless mode for the selenium browser.",
        dest="no_headless",
        action="store_false",
    )
    parser.add_argument(
        "--no_posting",
        help="Disable posting.",
        dest="no_posting",
        action="store_true",
    )
    parser.set_defaults(no_headless=True, no_posting=False)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format=format)
    return args


if __name__ == "__main__":
    main()
