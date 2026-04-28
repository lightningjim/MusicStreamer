"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import urllib.parse

from musicstreamer.aa_import import NETWORKS


def _is_youtube_url(url: str) -> bool:
    """Return True if url is a YouTube URL."""
    return "youtube.com" in url or "youtu.be" in url


# AA stream domain patterns for URL detection (D-06)
_AA_STREAM_DOMAINS = {
    "di.fm", "radiotunes.com", "jazzradio.com",
    "rockradio.com", "classicalradio.com", "zenradio.com",
}

# Per-network URL key prefix that differs from the slug (e.g. ZenRadio uses "zr")
_NETWORK_URL_PREFIXES = {
    "zenradio": "zr",
}


def _is_aa_url(url: str) -> bool:
    """Return True if url is an AudioAddict stream URL (matches any of the 6 AA network domains)."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in _AA_STREAM_DOMAINS)


def _aa_channel_key_from_url(url: str, slug: str | None = None) -> str | None:
    """Extract channel key from an AudioAddict stream URL path segment.

    Stream URLs may include a quality-tier suffix (_hi/_med/_low) and some
    networks use a short URL prefix (ZenRadio: 'zr'). Both are stripped so
    the returned key matches the AA channels API image map.

    e.g. 'prem2.di.fm:80/ambient_hi'   -> 'ambient'
         'prem1.zenradio.com/zrambient' -> 'ambient'
    Returns None if the URL has no non-empty path segment.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lstrip("/")
        if not path:
            return None
        key = path.split("/")[0]
        if not key:
            return None
        # Strip quality-tier suffix added by PLS resolution
        for suffix in ("_hi", "_med", "_low"):
            if key.endswith(suffix):
                key = key[: -len(suffix)]
                break
        # Strip per-network URL prefix (e.g. 'zr' for zenradio)
        if slug:
            prefix = _NETWORK_URL_PREFIXES.get(slug, "")
            if prefix and key.startswith(prefix):
                key = key[len(prefix):]
        return key or None
    except Exception:
        return None


def _aa_slug_from_url(url: str) -> str | None:
    """Determine the AA network slug from a stream URL domain.

    e.g. 'http://prem2.di.fm:80/di_house' -> 'di'
    """
    url_lower = url.lower()
    for net in NETWORKS:
        # Match the domain part (e.g. di.fm matches prem2.di.fm)
        domain_base = net["domain"].replace("listen.", "")  # "di.fm"
        if domain_base in url_lower:
            return net["slug"]
    return None


def find_aa_siblings(
    stations: list,
    current_station_id: int,
    current_first_url: str,
) -> list[tuple[str, int, str]]:
    """Phase 51 / BUG-02: return AA stations on other networks sharing the same channel key.

    Returns a list of (network_slug, station_id, station_name) tuples.
    Excludes the current station by id. Excludes stations whose first stream
    URL is non-AA, has no slug, has no derivable channel key, or whose
    streams list is empty. Returns [] if the current URL is non-AA or has
    no channel key (D-04: callers may rely on emptiness as the "hide section"
    signal).

    Sort order: NETWORKS declaration order in aa_import.py
    (di -> radiotunes -> jazzradio -> rockradio -> classicalradio -> zenradio).

    Pure function — no Qt, no DB access, no logging. Match the
    url_helpers.py module convention.
    """
    # Gate: current station must itself be a parseable AA URL (D-04).
    if not _is_aa_url(current_first_url):
        return []
    current_slug = _aa_slug_from_url(current_first_url)
    if not current_slug:
        return []
    current_key = _aa_channel_key_from_url(current_first_url, slug=current_slug)
    if not current_key:
        return []

    # Sort-order index: NETWORKS declaration order is the canonical order.
    slug_order = {n["slug"]: i for i, n in enumerate(NETWORKS)}

    siblings: list[tuple[int, str, int, str]] = []  # (sort_index, slug, id, name)
    for st in stations:
        # Exclude self by id (D-03).
        if st.id == current_station_id:
            continue
        # Exclude stations with no streams (defensive — Repo always populates,
        # but tests construct Station(streams=[]) directly).
        if not st.streams:
            continue
        cand_url = st.streams[0].url
        # D-03: candidate must be AA, have a slug, and have a derivable key.
        if not _is_aa_url(cand_url):
            continue
        cand_slug = _aa_slug_from_url(cand_url)
        if not cand_slug:
            continue
        # Same-network siblings are not siblings (must be cross-network).
        if cand_slug == current_slug:
            continue
        cand_key = _aa_channel_key_from_url(cand_url, slug=cand_slug)
        if not cand_key:
            continue
        if cand_key != current_key:
            continue
        siblings.append((slug_order.get(cand_slug, 999), cand_slug, st.id, st.name))

    siblings.sort(key=lambda t: t[0])
    return [(slug, sid, sname) for _, slug, sid, sname in siblings]
