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
from youtube_dl import YoutubeDL

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
URLS_WEBRADIOS = [
    "https://www.fip.fr/titres-diffuses",
    "https://www.fip.fr/titres-diffuses?station=rock",
    "https://www.fip.fr/titres-diffuses?station=jazz",
    "https://www.fip.fr/titres-diffuses?station=groove",
    "https://www.fip.fr/titres-diffuses?station=musiques-du-monde",
    "https://www.fip.fr/titres-diffuses?station=tout-nouveau-tout-fip",
    "https://www.fip.fr/titres-diffuses?station=reggae",
    "https://www.fip.fr/titres-diffuses?station=electro",
    # "https://www.fip.fr/titres-diffuses?station=metal",
    # "https://www.fip.fr",
    # "https://www.fip.fr/rock/webradio",
    # "https://www.fip.fr/jazz/webradio",
    # "https://www.fip.fr/groove/webradio",
    # "https://www.fip.fr/musiques-du-monde/webradio",
    # "https://www.fip.fr/tout-nouveau-tout-fip/webradio",
    # "https://www.fip.fr/reggae/webradio",
    # "https://www.fip.fr/electro/webradio",
    # "https://www.fip.fr/fip-metal/webradio",
]
TIMELINE_FILE = "fip-timeline.csv"


def get_entry_from_dict(title, entry):
    if entry in title:
        return str(title[entry])
    else:
        return ""


def export_to_timeline(title):
    with open(TIMELINE_FILE, "a") as f:
        f.write(
            f"FIP {get_entry_from_dict(title, 'webradio')}\t{get_entry_from_dict(title, 'artist')}\t{get_entry_from_dict(title, 'title')}\t{get_entry_from_dict(title, 'album')}\t{get_entry_from_dict(title, 'year')}\t{get_entry_from_dict(title, 'label')}\t{get_entry_from_dict(title, 'cover_url')}\n"
        )


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


def get_soup(url):
    return BeautifulSoup(requests.get(url).content, "lxml")


def get_FIP_metadata():
    new_titles = []

    for url in URLS_WEBRADIOS:
        soup = get_soup(url)

        metadata = {}

        # Taking the last word
        # "En direct sur FIP" becomes FIP
        # "En direct sur FIP Rock" becomes Rock
        # "h1", {"class": "channel-header-title"}
        metadata["webradio"] = soup.find(
            "h1", {"class": "tracklist-content-title"}
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
                try:
                    tweet_image(
                        twitter_api, "cover.jpg", tweet_text, "twitter"
                    )
                except Exception as e:
                    logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    tweet_image(
                        mastodon_api, "cover.jpg", tweet_text, "mastodon"
                    )
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
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
                try:
                    tweet_image(
                        twitter_api, "cover.png", tweet_text, "twitter"
                    )
                except Exception as e:
                    logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    tweet_image(
                        mastodon_api, "cover.png", tweet_text, "mastodon"
                    )
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
            # Cover not found on lastfm
            else:
                try:
                    twitter_api.update_status(status=tweet_text)
                except Exception as e:
                    logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    mastodon_api.status_post(tweet_text)
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
        else:
            try:
                twitter_api.update_status(status=tweet_text)
            except Exception as e:
                logger.error("Error posting tweet to Twitter : %s.", e)
            try:
                mastodon_api.status_post(tweet_text)
            except Exception as e:
                logger.error("Error posting tweet to Mastodon : %s.", e)
    else:
        try:
            twitter_api.update_status(status=tweet_text)
        except Exception as e:
            logger.error("Error posting tweet to Twitter : %s.", e)
        try:
            mastodon_api.status_post(tweet_text)
        except Exception as e:
            logger.error("Error posting tweet to Mastodon : %s.", e)
        logger.info(
            "Twitter : Posting %s - %s. Tweet text : %s.",
            title["artist"],
            title["title"],
            tweet_text,
        )


class MyLogger(object):  # pragma: no cover
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


def get_youtube_url(search_term):
    try:
        ydl_opts = {"logger": MyLogger()}
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(
                f"ytsearch1:{search_term}", download=False
            )
            return "https://youtu.be/" + info_dict["entries"][0]["id"]
    except Exception as e:
        logger.error(e)
        return None


# def get_youtube_url(title):
#     # Extracting youtube urls
#     header = {
#         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0"
#     }
#     with requests.Session() as session:
#         session.headers.update = header
#         logger.debug("Extracting youtube url for %s.", title)
#         name = f"{title['artist']} - {title['title']}"
#         url = "https://www.youtube.com/results?search_query=" + name.replace(
#             " ", "+"
#         ).replace("&", "%26").replace("(", "%28").replace(")", "%29")
#         logger.info("Youtube URL search : %s", url)
#         soup = BeautifulSoup(session.get(url).content, "lxml")
#     # Test if youtube is rate-limited
#     if soup.find("form", {"id": "captcha-form"}):
#         logger.error("Rate-limit detected on Youtube. Exiting.")
#         return None
#     try:
#         titles = soup.find_all(
#             "a",
#             {
#                 "class": "yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link"
#             },
#         )
#         href = [x["href"] for x in titles if x["href"]]
#         # delete user channels url
#         href = [x for x in href if "channel" not in x and "user" not in x]
#         id_video = href[0].split("?v=", 1)[-1]
#         if "&list" in id_video:
#             id_video = id_video.split("&list")[0]
#         logger.debug("href : %s.", href)
#         url = f"https://youtu.be/{id_video}"
#     except Exception as e:
#         logger.error(e)
#         return None
#     return url


def main():
    args = parse_args()

    # Loading last posted songs
    last_posted_songs_filename = "last_posted_songs"
    if Path(last_posted_songs_filename).is_file():
        with open(last_posted_songs_filename) as f:
            last_posted_songs = json.load(f)
    else:
        last_posted_songs = {}
    logger.debug("last_posted_songs contains : %s", last_posted_songs)

    new_titles = get_FIP_metadata()

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

                    # add title to posted titles
                    last_posted_songs[
                        title["webradio"]
                    ] = f"{title['artist']} - {title['title']}"

                    export_to_timeline(title)

                    # post to lastfm (all webradios)
                    post_title_to_lastfm(title)

                    # post to twitter/mastodon (main webradio)
                    if title["webradio"] == "FIP":
                        post_tweet(title)
                # if title is not the last title posted
                if (
                    f"{title['artist']} - {title['title']}"
                    != last_posted_songs[title["webradio"]]
                ):

                    # add title to posted titles
                    last_posted_songs[
                        title["webradio"]
                    ] = f"{title['artist']} - {title['title']}"

                    export_to_timeline(title)

                    # post to lastfm (all webradios)
                    post_title_to_lastfm(title)

                    # post to twitter/mastodon (main webradio)
                    if title["webradio"] == "FIP":
                        post_tweet(title)
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
