"""Cover art fetching via iTunes Search API."""
import json
import tempfile
import threading
import urllib.parse
import urllib.request

JUNK_TITLES: frozenset[str] = frozenset({
    "",
    "advertisement",
    "advert",
    "commercial",
    "commercial break",
})


def is_junk_title(icy_string: str) -> bool:
    """Return True if the ICY title string is junk (empty, whitespace, ad marker)."""
    return icy_string.strip().casefold() in JUNK_TITLES


def _build_itunes_query(icy_string: str) -> str:
    """Build an iTunes Search API URL from an ICY title string.

    If the string contains ' - ', split into artist/title for a more precise query.
    Otherwise use the full string as the search term.
    """
    if " - " in icy_string:
        artist, title = icy_string.split(" - ", 1)
        term = f"{artist} {title}"
    else:
        term = icy_string
    params = urllib.parse.urlencode({"term": term, "media": "music", "limit": "1"})
    return f"https://itunes.apple.com/search?{params}"


def _parse_artwork_url(json_bytes: bytes) -> str | None:
    """Parse iTunes Search API JSON and return the 160x160 artwork URL, or None."""
    data = json.loads(json_bytes)
    if not data.get("resultCount", 0):
        return None
    results = data.get("results", [])
    if not results:
        return None
    artwork_url = results[0].get("artworkUrl100")
    if not artwork_url:
        return None
    return artwork_url.replace("100x100", "160x160")


def fetch_cover_art(icy_string: str, callback: callable) -> None:
    """Fetch cover art for the given ICY title string and call callback(path_or_None).

    The callback is invoked from a background thread. Callers that update GTK
    widgets must wrap the callback body with GLib.idle_add.

    If the title is junk or the fetch fails, callback(None) is called.
    """
    if is_junk_title(icy_string):
        callback(None)
        return

    query_url = _build_itunes_query(icy_string)

    def _worker():
        try:
            with urllib.request.urlopen(query_url, timeout=5) as resp:
                json_bytes = resp.read()
            artwork_url = _parse_artwork_url(json_bytes)
            if artwork_url is None:
                callback(None)
                return
            with urllib.request.urlopen(artwork_url, timeout=5) as img_resp:
                image_bytes = img_resp.read()
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name
            callback(temp_path)
        except Exception:
            callback(None)

    threading.Thread(target=_worker, daemon=True).start()
