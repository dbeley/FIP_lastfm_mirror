import logging
from youtube_dl import YoutubeDL

# import requests
# from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# def get_youtube_soup(name):
#     header = {
#         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0"
#     }
#     with requests.Session() as session:
#         session.headers.update = header
#         url = "https://www.youtube.com/results?search_query=" + name.replace(
#             " ", "+"
#         ).replace("&", "%26").replace("(", "%28").replace(")", "%29")
#         logger.debug("Youtube URL search : %s", url)
#         soup = BeautifulSoup(session.get(url).content, "lxml")
#     return soup
#
#
# def extract_url_from_soup(soup):
#     logger.debug(soup)
#     breakpoint()
#     titles = soup.find_all(
#         "a",
#         {
#             # "class": "yt-simple-endpoint style-scope ytd-video-renderer"
#             "id": "video-title"
#             # "class": "yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link"
#         },
#     )
#     logger.debug(titles)
#     href = [x["href"] for x in titles if x["href"]]
#     logger.debug(href)
#     # delete user channels url
#     href = [x for x in href if "channel" not in x and "user" not in x]
#     logger.debug(href)
#     id_video = href[0].split("?v=", 1)[-1]
#     if "&list" in id_video:
#         id_video = id_video.split("&list")[0]
#     logger.debug("href : %s.", href)
#     url = f"https://youtu.be/{id_video}"
#     return url
#
#
# def get_youtube_url(title):
#     # Extracting youtube urls
#     # Test if youtube is rate-limited
#     logger.debug("Extracting youtube url for %s.", title)
#     name = f"{title['artist']} - {title['title']}"
#     soup = get_youtube_soup(name)
#     if soup.find("form", {"id": "captcha-form"}):
#         logger.error("Rate-limit detected on Youtube. Exiting.")
#         return None
#     return extract_url_from_soup(soup)


def dict_is_song(info_dict):
    """ Determine if a dictionary returned by youtube_dl is from a song (and not an album for example). """
    if "full album" in info_dict["title"].lower():
        return False
    if int(info_dict["duration"]) > 7200:
        return False
    return True


def get_ydl_dict(search_term, position):
    ydl_opts = {"logger": MyLogger()}
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(
            f"ytsearch{position}:{search_term}", download=False
        )
    return info_dict["entries"][position - 1]


def get_youtube_url(search_term):
    """ Extract an url for a song. """
    position = 1
    while True:
        try:
            info_dict = get_ydl_dict(search_term, position)
            if dict_is_song(info_dict):
                break
        except Exception as e:
            logger.error(
                "Error extracting youtube search %s, position %s : %s.",
                search_term,
                position,
                e,
            )
            if position > 4:
                # Too many wrong results
                return None
        position += 1
    return info_dict["webpage_url"]


class MyLogger(object):  # pragma: no cover
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)
