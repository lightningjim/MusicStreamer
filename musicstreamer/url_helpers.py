"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import html
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

# Per-network URL key prefix that differs from the slug.
# DI.fm stream URLs use a 'di_' path prefix (e.g. /di_house, /di_trance_hi).
# RadioTunes uses 'rt' (e.g. /rtambient, /rtchillout).
# ZenRadio uses 'zr' (e.g. /zrambient).
# All must be stripped to recover the bare channel key that matches the AA API.
_NETWORK_URL_PREFIXES = {
    "di": "di_",
    "radiotunes": "rt",
    "zenradio": "zr",
}

# Channel key aliases: some DI.fm channels have a URL path segment that no longer
# matches the current API key (renamed channels, or legacy alternate URL slugs).
# Applied after prefix stripping, so keys here are already prefix-stripped values.
# Note: public-PLS stream URLs and premium stream URLs sometimes carry DIFFERENT
# legacy slugs for the same channel (e.g. classictechno is `oldschoolelectronica`
# on public infra and `classicelectronica` on premium). Both must be aliased.
# Verified against the AA channels API and the user station DB 2026-05-01.
_AA_CHANNEL_KEY_ALIASES: dict[str, str] = {
    # URL path segment (after stripping di_) -> current API channel key
    "electrohouse": "electro",       # Electro House: URL uses electrohouse, API key is electro
    "mainstage": "edmfestival",      # EDM Festival: URL uses mainstage (legacy), API key is edmfestival
    "clubsounds": "club",            # Club Sounds: URL uses clubsounds, API key is club
    "oldschoolelectronica": "classictechno",  # Oldschool Techno & Trance (public): URL uses oldschoolelectronica
    "classicelectronica": "classictechno",    # Oldschool Techno & Trance (premium): URL uses classicelectronica
}

# Cross-network sibling identity: per-network API keys that represent the SAME
# channel concept on different networks despite the keys themselves differing.
# Used ONLY by find_aa_siblings to decide whether two stations on different
# networks are siblings — does NOT affect per-network image-map lookups (each
# network's image fetch keeps using its own API key).
# Keyed by (network_slug, per_network_api_key) -> canonical sibling identity.
# Verified against the AA channels API and the user station DB 2026-05-01.
_AA_CROSS_NETWORK_KEYS: dict[tuple[str, str], str] = {
    ("di", "spacemusic"): "spacedreams",         # DI.fm "Space Dreams" key=spacemusic; ZR/canonical=spacedreams
    ("radiotunes", "altrock"): "alternativerock",  # RadioTunes key=altrock; RockRadio/canonical=alternativerock
    ("classicalradio", "baroqueperiod"): "baroque",  # ClassicalRadio key=baroqueperiod; RT/canonical=baroque
    ("classicalradio", "romanticperiod"): "romantic",  # ClassicalRadio key=romanticperiod; RT/canonical=romantic
}


def _aa_sibling_identity(slug: str, key: str) -> str:
    """Canonical cross-network sibling identity for (network_slug, api_key).

    Defaults to the input key when no cross-network alias is registered.
    Used by find_aa_siblings to compare stations across networks that share
    the same channel concept but have different per-network API keys.
    """
    return _AA_CROSS_NETWORK_KEYS.get((slug, key), key)


def _is_aa_url(url: str) -> bool:
    """Return True if url is an AudioAddict stream URL (matches any of the 6 AA network domains)."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in _AA_STREAM_DOMAINS)


def _aa_channel_key_from_url(url: str, slug: str | None = None) -> str | None:
    """Extract channel key from an AudioAddict stream URL path segment.

    Stream URLs may include a quality-tier suffix (_hi/_med/_low) and some
    networks use a path prefix (DI.fm: 'di_', ZenRadio: 'zr'). Both are
    stripped so the returned key matches the AA channels API image map.
    Renamed/aliased channels are resolved via _AA_CHANNEL_KEY_ALIASES.

    e.g. 'prem2.di.fm:80/di_ambient_hi' -> 'ambient'
         'prem2.di.fm:80/di_electrohouse_hi' -> 'electro'
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
        # Strip per-network URL prefix (e.g. 'di_' for DI.fm, 'zr' for zenradio)
        if slug:
            prefix = _NETWORK_URL_PREFIXES.get(slug, "")
            if prefix and key.startswith(prefix):
                key = key[len(prefix):]
        # Resolve channel key aliases (renamed/legacy URL slugs -> current API key)
        key = _AA_CHANNEL_KEY_ALIASES.get(key, key)
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
    # Cross-network identity: e.g. DI.fm "spacemusic" and ZenRadio "spacedreams"
    # both normalize to "spacedreams" so they match as siblings.
    current_identity = _aa_sibling_identity(current_slug, current_key)

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
        if _aa_sibling_identity(cand_slug, cand_key) != current_identity:
            continue
        siblings.append((slug_order.get(cand_slug, 999), cand_slug, st.id, st.name))

    siblings.sort(key=lambda t: t[0])
    return [(slug, sid, sname) for _, slug, sid, sname in siblings]


def render_sibling_html(
    siblings: list[tuple[str, int, str]],
    current_name: str,
) -> str:
    """Phase 51 / D-07, D-08 (promoted in Phase 64 / D-03 from
    EditStationDialog._render_sibling_html). Render the 'Also on: ...' HTML
    for an AA cross-network sibling label.

    siblings: from find_aa_siblings — already sorted in NETWORKS order.
    current_name: the bound station's display name. Drives D-08 link-text
                  format: same name -> network-only; different -> "Network — Name".
    Returns: 'Also on: <a href="sibling://{id}">{label}</a> • <a ...>...'

    Security: every interpolated station_name passes through
    html.escape(name, quote=True) (T-39-01 deviation mitigation). Network
    display names come from the NETWORKS compile-time constant and need no
    escape. The href payload is integer-only ('sibling://{id}') so it cannot
    carry injectable content.
    """
    name_for_slug = {n["slug"]: n["name"] for n in NETWORKS}
    parts: list[str] = []
    for slug, station_id, station_name in siblings:
        network_display = name_for_slug.get(slug, slug)
        if station_name == current_name:
            link_text = network_display
        else:
            safe_name = html.escape(station_name, quote=True)
            link_text = f"{network_display} — {safe_name}"  # U+2014 EM DASH
        parts.append(f'<a href="sibling://{station_id}">{link_text}</a>')
    return "Also on: " + " • ".join(parts)  # U+2022 BULLET
