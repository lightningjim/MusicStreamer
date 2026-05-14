"""Cover art fetching via iTunes Search API and MusicBrainz + Cover Art Archive.

Phase 73 Plan 03: this module is now a source-aware ROUTER. The legacy iTunes
worker still lives here (as `_itunes_attempt`); MB+CAA lookups delegate to
`musicstreamer.cover_art_mb.fetch_mb_cover`. The public entry point
`fetch_cover_art(icy_string, callback, source='auto')` dispatches per D-01..D-04:

    - 'itunes_only' (D-03): legacy iTunes path; never call MB.
    - 'mb_only'    (D-04): never call iTunes (no side genre call per D-16).
    - 'auto'       (D-02): iTunes first; on miss, MB fallback (D-07 bare-title
                            gate prevents MB fallback for ICY without ' - ').

The `is_junk_title` gate runs FIRST regardless of source — empty / advert ICY
strings short-circuit to `callback(None)` before any dispatch.

The `source='auto'` default preserves backward compat with all existing
2-arg call sites (now_playing_panel.py:1187 today). Plan 04 widens the
panel to pass `source=` explicitly.
"""
import json
import logging
import tempfile
import threading
import urllib.parse
import urllib.request
from typing import Callable, Optional

import musicstreamer.cover_art_mb as _cover_art_mb

_log = logging.getLogger(__name__)

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


last_itunes_result: dict = {"artwork_url": None, "genre": ""}


def _parse_itunes_result(json_bytes: bytes) -> dict:
    """Return {'artwork_url': str|None, 'genre': str} from iTunes JSON."""
    data = json.loads(json_bytes)
    if not data.get("resultCount", 0) or not data.get("results"):
        return {"artwork_url": None, "genre": ""}
    result = data["results"][0]
    artwork_url = result.get("artworkUrl100")
    if artwork_url:
        artwork_url = artwork_url.replace("100x100", "160x160")
    genre = result.get("primaryGenreName", "")
    return {"artwork_url": artwork_url, "genre": genre}


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


def _itunes_attempt(
    icy_string: str,
    on_done: Callable[[Optional[str]], None],
) -> None:
    """Run the iTunes lookup worker; deliver result via on_done(path_or_None).

    Spawns the same daemon-thread worker as the historic single-source path.
    `on_done` is the router's internal continuation — in 'itunes_only' mode
    it equals the public callback; in 'auto' mode it's a wrapper that chains
    into the MB attempt on miss (D-02).

    All exception handling is intentionally inside the worker: per D-20 the
    worker NEVER raises out. On any failure (network / JSON / disk), on_done
    is invoked with None.
    """
    query_url = _build_itunes_query(icy_string)

    def _worker():
        import musicstreamer.cover_art as _self_module
        try:
            with urllib.request.urlopen(query_url, timeout=5) as resp:
                json_bytes = resp.read()
            result_dict = _parse_itunes_result(json_bytes)
            _self_module.last_itunes_result = result_dict
            artwork_url = result_dict["artwork_url"]
            if artwork_url is None:
                on_done(None)
                return
            with urllib.request.urlopen(artwork_url, timeout=5) as img_resp:
                image_bytes = img_resp.read()
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name
            on_done(temp_path)
        except Exception:
            on_done(None)

    threading.Thread(target=_worker, daemon=True).start()


def _split_artist_title(icy_string: str) -> Optional[tuple[str, str]]:
    """Split an ICY string on ' - ' into (artist, title); return None on bare title.

    D-07: ICY must contain ' - ' to qualify for MB. After split, both halves
    are stripped; if either is empty the result is None (treat as bare).
    """
    if " - " not in icy_string:
        return None
    artist, title = icy_string.split(" - ", 1)
    artist = artist.strip()
    title = title.strip()
    if not artist or not title:
        return None
    return artist, title


def fetch_cover_art(
    icy_string: str,
    callback: Callable[[Optional[str]], None],
    source: str = "auto",
) -> None:
    """Fetch cover art for the given ICY title and call callback(path_or_None).

    Phase 73 D-01..D-04 source-aware dispatch:

    - source='auto' (default; D-02): try iTunes first. On iTunes miss
      (callback(None) from the iTunes worker), fall through to MB+CAA. D-07
      gate: a bare-title ICY (no ' - ') tries iTunes only — no MB fallback,
      because MB requires artist+title.

    - source='itunes_only' (D-03): the legacy iTunes-only path. fetch_mb_cover
      is NEVER invoked. This is the historic behavior; preserved here for
      stations that have always worked well via iTunes.

    - source='mb_only' (D-04): iTunes is NEVER called (not even for genre
      handoff — D-16). Bare-title ICY short-circuits to callback(None)
      immediately without engaging fetch_mb_cover.

    The is_junk_title gate runs FIRST regardless of source.

    The callback is invoked from a background thread (the iTunes worker daemon
    thread, or Plan 02's MB worker daemon thread). Callers that update Qt
    widgets must marshal back to the main thread (the panel does this via
    the cover_art_ready Signal — queued connection at now_playing_panel.py:749).

    Unknown source values fall back to 'auto' with a WARNING log; never crashes
    (T-73-11 mitigation).
    """
    if is_junk_title(icy_string):
        callback(None)
        return

    if source == "itunes_only":
        # D-03: legacy path — iTunes only, never MB.
        _itunes_attempt(icy_string, callback)
        return

    if source == "mb_only":
        # D-04: strict MB-only. D-07 bare-title gate: if no ' - ' (or either
        # half is empty after split), short-circuit to callback(None) WITHOUT
        # engaging fetch_mb_cover — keeps MB's rate gate / queue state clean.
        split = _split_artist_title(icy_string)
        if split is None:
            callback(None)
            return
        artist, title = split
        _cover_art_mb.fetch_mb_cover(artist, title, callback)
        return

    if source != "auto":
        # T-73-11 mitigation: unknown source falls back to auto with a warning.
        _log.warning(
            "unknown cover_art source %r; falling back to 'auto'", source
        )
        # fall through to auto-mode dispatch below.

    # D-02: Auto mode — iTunes first, then MB on miss.
    # D-07 bare-title gate: even in Auto mode, a bare title does NOT fall
    # through to MB after an iTunes miss — MB requires artist+title.
    split = _split_artist_title(icy_string)

    def _on_itunes_done(path_or_none: Optional[str]) -> None:
        if path_or_none is not None:
            # iTunes hit — D-17: genre already written to last_itunes_result
            # by the iTunes worker. Don't call MB.
            callback(path_or_none)
            return
        # iTunes miss.
        if split is None:
            # D-07: bare title — no MB fallback even in Auto mode.
            callback(None)
            return
        artist, title = split
        _cover_art_mb.fetch_mb_cover(artist, title, callback)

    _itunes_attempt(icy_string, _on_itunes_done)
