"""
Mirror the FIP webradios to several services.
"""
import requests
import re
import json
import logging
import time
import argparse
import datetime
import configparser
import pylast
from pathlib import Path
from bs4 import BeautifulSoup

logger = logging.getLogger()
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("chardet.charsetprober").setLevel(logging.WARNING)
logging.getLogger("pylast").setLevel(logging.WARNING)

config = configparser.RawConfigParser()
config.read("config.ini")

BEGIN_TIME = time.time()
ENABLED_WEBRADIOS = [
    "FIP",
    "Rock",
    "Jazz",
    "Groove",
    "Pop",
    "Electro",
    "Monde",
    "Reggae",
    "Nouveautés",
    "Metal",
]
URL_WEBRADIOS = "https://www.radiofrance.fr/api/v1.7/stations/fip/webradios/"


def get_entry_from_dict(title, entry):
    if entry in title:
        return str(title[entry])
    else:
        return ""


def export_to_timeline(timeline_filename, title):
    with open(timeline_filename, "a") as f:
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


def get_webradio_name_from_tag(webradio: str) -> str:
    if webradio == "fip":
        return "FIP"
    elif webradio == "fip_rock":
        return "Rock"
    elif webradio == "fip_jazz":
        return "Jazz"
    elif webradio == "fip_groove":
        return "Groove"
    elif webradio == "fip_pop":
        return "Pop"
    elif webradio == "fip_electro":
        return "Electro"
    elif webradio == "fip_world":
        return "Monde"
    elif webradio == "fip_reggae":
        return "Reggae"
    elif webradio == "fip_nouveautes":
        return "Nouveautés"
    elif webradio == "fip_metal":
        return "Metal"
    elif webradio == "fip_hiphop":
        return "Hip-Hop"
    else:
        raise ValueError(f"webradio {webradio} not supported.")


def get_FIP_metadata():
    new_titles = []

    content = requests.get(URL_WEBRADIOS).json()
    for webradio_content in content:
        webradio = get_webradio_name_from_tag(webradio_content["slug"])

        album = None
        label = None
        year = None
        if "song" in webradio_content["now"]:
            year = webradio_content["now"]["song"].get("year")
            if "release" in webradio_content["now"]["song"]:
                album = webradio_content["now"]["song"]["release"].get("title")
                label = webradio_content["now"]["song"]["release"].get("label")
        title = webradio_content["now"]["firstLine"]
        if title.lower() != "le direct" and webradio in ENABLED_WEBRADIOS:
            new_titles.append(
                [
                    {
                        "webradio": webradio,
                        "title": title,
                        "artist": webradio_content["now"]["secondLine"],
                        "year": year,
                        "album": album,
                        "label": label,
                    }
                ]
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


def post_title(args, title):
    timeline_path = "fip-timeline.csv"
    export_to_timeline(timeline_path, title)

    if not args.no_posting:
        # post to lastfm (all webradios)
        post_title_to_lastfm(title)


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
    logger.debug(new_titles)

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
                args,
                webradio_titles[0],
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
                    args,
                    webradio_titles[index],
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
                args,
                webradio_titles[0],
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
        "--no_posting",
        help="Disable posting.",
        dest="no_posting",
        action="store_true",
    )
    parser.set_defaults(no_posting=False)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format=format)
    return args


if __name__ == "__main__":
    main()
