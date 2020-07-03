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
            f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\tFIP {get_entry_from_dict(title, 'webradio')}\t{get_entry_from_dict(title, 'artist')}\t{get_entry_from_dict(title, 'title')}\t{get_entry_from_dict(title, 'album')}\t{get_entry_from_dict(title, 'year')}\t{get_entry_from_dict(title, 'label')}\t{get_entry_from_dict(title, 'cover_url')}\n"
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


# def twitterconnect():
#    consumer_key = config["twitter"]["consumer_key"]
#    secret_key = config["twitter"]["secret_key"]
#    access_token = config["twitter"]["access_token"]
#    access_token_secret = config["twitter"]["access_token_secret"]
#
#    auth = tweepy.OAuthHandler(consumer_key, secret_key)
#    auth.set_access_token(access_token, access_token_secret)
#    return tweepy.API(auth)


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
    return BeautifulSoup(
        requests.get(url, headers={"Cache-Control": "no-cache"}).content, "lxml",
    )


def parse_fip_item(webradio, item):
    metadata = {}
    metadata["webradio"] = webradio
    metadata["title"] = item.find("span", {"class": "now-info-title"}).text.replace(
        "\t", ""
    )

    subtitle = item.find("span", {"class": "now-info-subtitle"}).text.replace("\t", "")
    # try:
    #     potential_year = (
    #         subtitle.rsplit(" ", 1)[1].replace("(", "").replace(")", "")
    #     )
    #     if potential_year.isdigit():
    #         metadata["year"] = potential_year
    #         metadata["artist"] = subtitle.rsplit(" ", 1)[0]
    #     else:
    #         metadata["artist"] = subtitle
    # except Exception as e:
    #     logger.error("potential_year : %s.", e)
    #     metadata["artist"] = subtitle
    metadata["artist"] = subtitle

    details = item.find("div", {"class": "now-info-details"})
    try:
        details_label = [
            x.text
            for x in details.find_all("span", {"class": "now-info-details-label"})
        ]
        logger.debug("details_label : %s.", details_label)
        details_value = [
            x.text.strip()
            for x in details.find_all("span", {"class": "now-info-details-value"})
        ]
        logger.debug("details_value : %s.", details_value)

        for index, label in enumerate(details_label):
            metadata[label.lower()] = details_value[index]
    except Exception as e:
        logger.error(e)

    if "album" in metadata:
        subtitle = metadata["album"].replace("\t", "")
        try:
            potential_year = (
                subtitle.rsplit(" ", 1)[1].replace("(", "").replace(")", "")
            )
            if potential_year.isdigit():
                metadata["year"] = potential_year
                metadata["album"] = subtitle.rsplit(" ", 1)[0]
            else:
                metadata["album"] = subtitle
        except Exception as e:
            logger.error("potential_year : %s.", e)
            metadata["album"] = subtitle

    # metadata["cover_url"] = item.find(
    #     "div", {"class": "now-cover playing-now-cover"}
    # ).find("img")["src"]
    metadata["cover_url"] = item.find("img")["src"].replace("\t", "")

    if not metadata["cover_url"].startswith("http"):
        metadata["cover_url"] = "https://fip.fr" + metadata["cover_url"]

    logger.debug(metadata)
    return metadata


def get_FIP_metadata():
    new_titles = []

    for url in URLS_WEBRADIOS:
        soup = get_soup(url)

        # Taking the last word
        # "En direct sur FIP" becomes FIP
        # "En direct sur FIP Rock" becomes Rock
        # "h1", {"class": "channel-header-title"}
        webradio = soup.find("h1", {"class": "tracklist-content-title"}).text.split()[
            -1
        ]
        list_dict_tracks = []

        # First item : now playing
        now_playing = soup.find("div", {"class": "playing-now"})
        # If something is playing, otherwise just extract the old tracks
        if now_playing.find("span", {"class": "now-info-title"}).text != "":
            metadata = parse_fip_item(webradio, now_playing)
            if (
                # At least webradio, artist, title in dict.
                {"webradio", "artist", "title"} <= set(metadata)
                and metadata["webradio"] in ENABLED_WEBRADIOS
                and metadata["title"] != ""
                and metadata["artist"] != ""
            ):
                list_dict_tracks.append(metadata)

        # Other items : broadcasted tracks
        list_tracks = soup.find_all("li", {"class": "list-item timeline-item"})
        for i in list_tracks:
            metadata = parse_fip_item(webradio, i)
            if (
                # At least webradio, artist, title in dict.
                {"webradio", "artist", "title"} <= set(metadata)
                and metadata["webradio"] in ENABLED_WEBRADIOS
                and metadata["title"] != ""
                and metadata["artist"] != ""
            ):
                list_dict_tracks.append(metadata)
        new_titles.append(list_dict_tracks)

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
            artist=title["artist"], title=title["title"], timestamp=unix_timestamp,
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
    # twitter_api = twitterconnect()
    mastodon_api = mastodonconnect()
    lastfm_api = lastfmconnect(title["webradio"])

    # Search youtube video
    youtube_url = get_youtube_url(title)
    logger.debug(
        "Youtube url for %s - %s : %s.", title["artist"], title["title"], youtube_url,
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

    tweet_text = (
        f"{title['artist']} - {title['title']}{additional_infos} #fipradio #nowplaying"
    )
    # tweet_text = f"#fipradio #nowplaying {title['artist']} - {title['title']}{additional_infos}"
    if "album" in title:
        logger.info(
            "Mastodon : Posting %s - %s (%s). Tweet text : %s.",
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
                # try:
                #     tweet_image(
                #         twitter_api, "cover.jpg", tweet_text, "twitter"
                #     )
                # except Exception as e:
                #     logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    tweet_image(mastodon_api, "cover.jpg", tweet_text, "mastodon")
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
            # Problem with the cover download
            else:
                # twitter_api.update_status(status=tweet_text)
                mastodon_api.status_post(tweet_text)
        # Cover is the placeholder, searching on lastfm
        elif "cover_url" in title and "placeholder" in title["cover_url"]:
            cover = get_lastfm_cover(lastfm_api, title)
            # Cover found on lastfm and successfully downloaded
            if cover and cover.status_code == 200:
                with open("cover.png", "wb") as f:
                    f.write(cover.content)
                # try:
                #     tweet_image(
                #         twitter_api, "cover.png", tweet_text, "twitter"
                #     )
                # except Exception as e:
                #     logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    tweet_image(mastodon_api, "cover.png", tweet_text, "mastodon")
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
            # Cover not found on lastfm
            else:
                # try:
                #     twitter_api.update_status(status=tweet_text)
                # except Exception as e:
                #     logger.error("Error posting tweet to Twitter : %s.", e)
                try:
                    mastodon_api.status_post(tweet_text)
                except Exception as e:
                    logger.error("Error posting tweet to Mastodon : %s.", e)
        else:
            # try:
            #     twitter_api.update_status(status=tweet_text)
            # except Exception as e:
            #     logger.error("Error posting tweet to Twitter : %s.", e)
            try:
                mastodon_api.status_post(tweet_text)
            except Exception as e:
                logger.error("Error posting tweet to Mastodon : %s.", e)
    else:
        # try:
        #     twitter_api.update_status(status=tweet_text)
        # except Exception as e:
        #     logger.error("Error posting tweet to Twitter : %s.", e)
        try:
            mastodon_api.status_post(tweet_text)
        except Exception as e:
            logger.error("Error posting tweet to Mastodon : %s.", e)
        logger.info(
            "Mastodon : Posting %s - %s. Tweet text : %s.",
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
        logger.debug("Youtube URL search : %s", url)
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
        id_video = href[0].split("?v=", 1)[-1]
        if "&list" in id_video:
            id_video = id_video.split("&list")[0]
        logger.debug("href : %s.", href)
        url = f"https://youtu.be/{id_video}"
    except Exception as e:
        logger.error("get_youtube_url : %s.", e)
        return None
    return url


def post_title(args, title):
    export_to_timeline(title)

    if not args.no_posting:
        # post to lastfm (all webradios)
        post_title_to_lastfm(title)

        # post to twitter/mastodon (main webradio)
        if title["webradio"] == "FIP":
            post_tweet(title)


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

    # list of list
    for webradio_titles in new_titles:
        formatted_titles = [f"{x['artist']} - {x['title']}" for x in webradio_titles]
        current_webradio = webradio_titles[0]["webradio"]
        # webradio not in dict, i.e. first iteration.
        if current_webradio not in last_posted_songs:
            logger.debug(
                "%s - %s posted to %s.",
                webradio_titles[0]["artist"],
                webradio_titles[0]["title"],
                webradio_titles[0]["webradio"],
            )
            last_posted_songs[current_webradio] = formatted_titles[0]
            post_title(
                args, webradio_titles[0],
            )
        # posting next song if last_posted_song exists in formatted_titles
        elif last_posted_songs[current_webradio] in formatted_titles:
            index = formatted_titles.index(last_posted_songs[current_webradio]) - 1
            # if last_played_song is not the current one playing.
            if index != -1:
                logger.debug(
                    "%s - %s posted to %s.",
                    webradio_titles[index]["artist"],
                    webradio_titles[index]["title"],
                    webradio_titles[index]["webradio"],
                )
                last_posted_songs[current_webradio] = formatted_titles[index]
                post_title(
                    args, webradio_titles[index],
                )
        # if last_posted_song is too outdated, posting the current track playing.
        else:
            logger.debug(
                "%s - %s posted to %s.",
                webradio_titles[0]["artist"],
                webradio_titles[0]["title"],
                webradio_titles[0]["webradio"],
            )
            last_posted_songs[current_webradio] = formatted_titles[0]
            post_title(
                args, webradio_titles[0],
            )

        # Exporting json each time
        logger.debug("Exporting last_posted_songs.")
        with open(last_posted_songs_filename, "w") as f:
            json.dump(last_posted_songs, f)

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
        "--no_posting", help="Disable posting.", dest="no_posting", action="store_true",
    )
    parser.set_defaults(no_headless=True, no_posting=False)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format=format)
    return args


if __name__ == "__main__":
    main()
