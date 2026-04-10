"""Radio-Browser.info API client.

All three functions are intended to be called from daemon threads only.
Never call from the GTK main thread — all network I/O blocks.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://all.api.radio-browser.info/json"


def search_stations(
    name: str,
    tag: str = "",
    countrycode: str = "",
    limit: int = 100,
) -> list[dict]:
    """Search Radio-Browser.info stations by name.

    Args:
        name: Station name search term.
        tag: Optional genre/tag filter (omitted from URL when empty).
        countrycode: Optional ISO 3166-1 alpha-2 country filter.
        limit: Maximum results to return (default 100).

    Returns:
        List of station dicts with keys: name, url, tags, countrycode,
        bitrate, homepage, network (plus others from the API).

    Raises:
        urllib.error.URLError: On network failure.
    """
    params: dict[str, str] = {
        "name": name,
        "limit": str(limit),
        "hidebroken": "true",
        "order": "votes",
        "reverse": "true",
    }
    if tag:
        params["tag"] = tag
    if countrycode:
        params["countrycode"] = countrycode
    url = f"{BASE}/stations/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def fetch_tags(limit: int = 200) -> list[str]:
    """Fetch available tags/genres ordered by station count descending.

    Args:
        limit: Maximum tags to return (default 200).

    Returns:
        List of tag name strings.
    """
    url = f"{BASE}/tags?order=stationcount&reverse=true&limit={limit}&hidebroken=true"
    with urllib.request.urlopen(url, timeout=10) as r:
        return [t["name"] for t in json.load(r)]


def fetch_countries() -> list[tuple[str, str]]:
    """Fetch countries with Radio-Browser stations, ordered by station count.

    Returns:
        List of (iso_3166_1, name) tuples. Entries with empty iso_3166_1
        are skipped.
    """
    url = f"{BASE}/countries?order=stationcount&reverse=true"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)
    return [(c["iso_3166_1"], c["name"]) for c in data if c.get("iso_3166_1")]
