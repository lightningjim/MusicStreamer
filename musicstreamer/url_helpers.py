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
