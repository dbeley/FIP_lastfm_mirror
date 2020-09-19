import pytest
from FIP_mirror.ydl_utils import get_youtube_url


def test_youtube(FIP_title):
    search = "Rick Astley - Never Gonna Give You Up"
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    youtube_url = get_youtube_url(FIP_title)
    print(youtube_url)

    if not youtube_url.startswith("http"):
        raise AssertionError()

    if not youtube_url == url:
        raise AssertionError()
