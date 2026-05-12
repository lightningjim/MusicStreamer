"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import html
import logging
import random
import urllib.parse

from musicstreamer.aa_import import NETWORKS
from musicstreamer.filter_utils import normalize_tags
from musicstreamer.models import Station

_log = logging.getLogger(__name__)


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


def aa_normalize_stream_url(url: str) -> str:
    """Phase 56 / WIN-01 / D-04: rewrite DI.fm 'https://' URLs to 'http://'.

    DI.fm rejects HTTPS server-side (Phase 43 finding: TLS handshake
    succeeds, then souphttpsrc returns 'streaming stopped, reason error
    (-5)'). Workaround applied at the Player URI boundary so every
    set_uri call goes through normalization regardless of source.

    Idempotent (D-06):
    - Empty/None-ish input -> returns input unchanged
    - Non-https:// input -> returns input unchanged (already http://, file://, etc.)
    - Non-DI.fm input -> returns input unchanged
    - DI.fm https:// -> returns http:// equivalent

    Cross-platform (D-03): unconditional rewrite, no platform guard --
    DI.fm rejects HTTPS for everyone, not just Windows.
    """
    if not url:
        return url
    if not url.startswith("https://"):
        return url
    if _aa_slug_from_url(url) != "di":
        return url
    rewritten = "http://" + url[len("https://"):]
    _log.debug("aa_normalize_stream_url: DI.fm https->http: %s -> %s", url, rewritten)
    return rewritten


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


def find_manual_siblings(
    stations: list,
    current_station_id: int,
    link_ids: list[int],
) -> list[tuple[str, int, str]]:
    """Return (provider_name_or_empty, station_id, station_name) triples.

    link_ids: from Repo.list_sibling_links(current_station_id).
    Excludes current_station_id even if present in link_ids (defensive).
    Sort order: alphabetical by station_name (casefold).
    Pure function — no Qt, no DB access, no logging.
    """
    link_set = set(link_ids)
    result: list[tuple[str, int, str]] = []
    for st in stations:
        if st.id == current_station_id:
            continue
        if st.id not in link_set:
            continue
        result.append((st.provider_name or "", st.id, st.name))
    result.sort(key=lambda t: t[2].casefold())
    return result


def merge_siblings(
    aa_siblings: list[tuple[str, int, str]],
    manual_siblings: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Deduplicate by station_id; AA entries take precedence.

    Returns aa_siblings + non-duplicate manual_siblings.
    Pure function — no Qt, no DB access.
    """
    seen: set[int] = {sid for _, sid, _ in aa_siblings}
    merged = list(aa_siblings)
    for entry in manual_siblings:
        if entry[1] not in seen:
            merged.append(entry)
            seen.add(entry[1])
    return merged


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


def pick_similar_stations(
    stations: list[Station],
    current_station: Station,
    *,
    sample_size: int = 5,
    rng: random.Random | None = None,
) -> tuple[list[Station], list[Station]]:
    """Phase 67 / T-01..T-04, R-05, R-06: derive and sample two pools.

    Returns (same_provider_sample, same_tag_sample). Both lists are up to
    sample_size long; pools < sample_size return all candidates (no
    padding, no placeholder).

    Pool exclusions (both pools):
      - (a) self id (T-04a — mirrors find_aa_siblings self-exclusion).
      - (b) AA-sibling ids returned by find_aa_siblings (T-04b — avoids
            triple-listing across Phase 64's "Also on:" line and the
            Phase 67 sub-sections).
      - (c) Same-tag pool only: candidates whose normalize_tags(tags)
            returns an empty list (T-04c).
      - (d) Same-provider pool only: candidates whose provider_id is None
            when current's provider_id is set (T-04d).

    Cross-pool dedup is intentionally NOT performed (T-03) — a station
    qualifying under both pools appears in BOTH lists.

    Sampling primitive: random.sample (distinct picks within each pool).
    Empty current.streams: skip AA exclusion silently (RESEARCH Pitfall
    11 — friendlier than hiding the section just because the bound
    station happens to have no streams).

    rng: pass random.Random(seed) for deterministic tests. Defaults to
    the module-level random instance for production.

    Pure function — no Qt, no DB access, no logging. Mirrors
    find_aa_siblings placement convention.
    """
    rng = rng or random
    excluded_ids: set[int] = {current_station.id}

    # T-04b: exclude AA siblings already shown by Phase 64's "Also on:" line.
    # Skip silently when current has no streams (Pitfall 11 — defensive
    # against test doubles; production Repo always populates streams).
    if current_station.streams:
        aa = find_aa_siblings(
            stations,
            current_station_id=current_station.id,
            current_first_url=current_station.streams[0].url,
        )
        # find_aa_siblings returns list[tuple[network_slug, station_id, station_name]]
        excluded_ids.update(sid for _, sid, _ in aa)

    # Same-provider pool (T-04a/b/d).
    same_provider_pool: list[Station] = []
    if current_station.provider_id is not None:
        for s in stations:
            if s.id in excluded_ids:
                continue
            if s.provider_id is None:  # T-04d
                continue
            if s.provider_id == current_station.provider_id:
                same_provider_pool.append(s)

    # Same-tag pool (T-01 union semantics, T-04a/b/c).
    current_tags = set(t.casefold() for t in normalize_tags(current_station.tags))
    same_tag_pool: list[Station] = []
    if current_tags:
        for s in stations:
            if s.id in excluded_ids:
                continue
            cand_tags = set(t.casefold() for t in normalize_tags(s.tags))
            if not cand_tags:  # T-04c
                continue
            if current_tags & cand_tags:  # T-01 union
                same_tag_pool.append(s)

    # R-05/R-06: distinct picks; clamp k to avoid Pitfall 1 ValueError.
    same_provider_sample = rng.sample(
        same_provider_pool, k=min(sample_size, len(same_provider_pool))
    )
    same_tag_sample = rng.sample(
        same_tag_pool, k=min(sample_size, len(same_tag_pool))
    )
    return same_provider_sample, same_tag_sample


def render_similar_html(
    stations: list[Station],
    *,
    show_provider: bool,
    href_prefix: str = "similar://",
) -> str:
    """Phase 67 / D-03 / D-04: render a vertical link list with one <a> per row.

    show_provider=False (Same provider section)  -> rows render '{Name}'.
    show_provider=True  (Same tag section)       -> rows render '{Name} ({Provider})'.

    Rows joined with literal '<br>' (vertical, per D-03 — distinct from
    Phase 64 render_sibling_html which uses ' • ' bullet inline).

    Security (T-39-01 deviation mitigation, Pitfall 7):
      - Station.name AND Station.provider_name are user-controlled and
        pass through html.escape(..., quote=True). Phase 64's
        render_sibling_html only ever escapes name (network names come
        from compile-time NETWORKS); Phase 67 is the FIRST renderer to
        also escape provider_name.
      - href payload is integer-only ({prefix}{int_id}) — Station.id is
        int from SQLite. No string interpolation possible into href.

    Empty stations list returns "" (no leading/trailing <br>).

    Pure function — no Qt, no DB access, no logging.
    """
    parts: list[str] = []
    for s in stations:
        safe_name = html.escape(s.name, quote=True)
        if show_provider:
            safe_prov = html.escape(s.provider_name or "", quote=True)
            link_text = f"{safe_name} ({safe_prov})"
        else:
            link_text = safe_name
        parts.append(f'<a href="{href_prefix}{s.id}">{link_text}</a>')
    return "<br>".join(parts)
