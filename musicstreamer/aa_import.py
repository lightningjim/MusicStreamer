"""AudioAddict network import backend.

Public API:
  fetch_channels_multi(listen_key) -> list[dict]
  import_stations_multi(channels, repo, on_progress=None, on_logo_progress=None) -> (imported, skipped)
"""

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import db_connect, Repo

_log = logging.getLogger(__name__)


def _resolve_pls(pls_url: str) -> list[str]:
    """Fetch a PLS playlist and return ALL stream URLs in file order.

    AA PLS files contain 2 server entries per tier (File1=primary, File2=fallback);
    both are needed for intra-tier failover redundancy (gap-06 fix for UAT gap 2).

    Phase 58 / D-10: thin wrapper around playlist_parser.parse_playlist.
    Preserves list[str] contract and [pls_url] fallback for callers at
    aa_import.py:135 and aa_import.py:177. File-order invariant (gap-06)
    is preserved by parse_playlist's numeric sorted(url_dict) traversal.

    Falls back to [pls_url] if resolution fails — keeps callers that take
    [0] working against the legacy fallback-on-error behavior.
    """
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        if entries:
            return [e["url"] for e in entries]
    except Exception:  # noqa: BLE001
        pass
    return [pls_url]


def _normalize_aa_image_url(raw: str) -> str:
    """Prepend https: and strip URI template from an AA CDN image URL."""
    url = re.sub(r'\{[^}]+\}', '', raw).strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def _fetch_image_map(slug: str) -> dict:
    """Return {channel_key: normalized_image_url} for a network. Empty dict on failure.

    IN-01: log 401/403 at WARNING (consistent with the rest of AA error handling,
    which raises invalid_key on auth failures). Other exceptions (network blips,
    JSON errors) are also logged but swallowed — image fetch is orthogonal to
    stream access, so we don't want to abort the whole import for an image miss.

    Image-key priority: prefer `default` over `square`. AudioAddict's `default`
    is the channel's canonical asset_url and is unique per channel; `square` is
    a curated variant that has been observed to collide upstream (jazzradio's
    `latenightjazz` and `trumpetjazz` share one `square` URL as of 2026-05).
    Falling back to `square` when `default` is absent preserves test fixtures
    that only set `square`.
    """
    try:
        api_url = f"https://api.audioaddict.com/v1/{slug}/channels"
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read())
        out = {}
        seen_urls: dict[str, str] = {}
        for ch in data:
            img = ch.get("images") or {}
            raw = img.get("default") or img.get("square")
            if raw:
                normalized = _normalize_aa_image_url(raw)
                key = ch["key"]
                prior = seen_urls.get(normalized)
                if prior is not None and prior != key:
                    _log.warning(
                        "AA image collision in %s: channels %r and %r share image %s",
                        slug, prior, key, normalized,
                    )
                seen_urls.setdefault(normalized, key)
                out[key] = normalized
        return out
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _log.warning("AA image map auth failure for %s: HTTP %s", slug, e.code)
        else:
            _log.warning("AA image map HTTP error for %s: %s", slug, e)
        return {}
    except Exception as e:
        _log.warning("AA image map fetch failed for %s: %s", slug, e)
        return {}


NETWORKS = [
    {"slug": "di",             "domain": "listen.di.fm",              "name": "DI.fm"},
    {"slug": "radiotunes",     "domain": "listen.radiotunes.com",     "name": "RadioTunes"},
    {"slug": "jazzradio",      "domain": "listen.jazzradio.com",      "name": "JazzRadio"},
    {"slug": "rockradio",      "domain": "listen.rockradio.com",      "name": "RockRadio"},
    {"slug": "classicalradio", "domain": "listen.classicalradio.com", "name": "ClassicalRadio"},
    {"slug": "zenradio",       "domain": "listen.zenradio.com",       "name": "ZenRadio"},
]

QUALITY_TIERS = {
    "hi":  "premium_high",
    "med": "premium",
    "low": "premium_medium",
}

# IN-02: module-scope constants for AA quality tier metadata
# (were redefined on every network × tier iteration).
_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}
_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}  # D-10: DI.fm tier -> kbps
# gap-07: ground-truth paid-AA codec mapping (user-verified from AA hardware-player
# settings UI — consistent across all paid AA networks): hi=MP3, med=AAC, low=AAC.
# Supersedes the previous inline 'AAC' if tier == 'premium_high' else 'MP3' ternary
# which produced the inverted mapping hi=AAC, med=MP3, low=MP3.
_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}


def fetch_channels_multi(listen_key: str) -> list[dict]:
    """Fetch all channels across all 6 AA networks with hi/med/low quality streams.

    Returns list of dicts:
      {"title": str, "provider": str, "image_url": str|None,
       "streams": [{"url": str, "quality": str, "position": int, "codec": str}]}
    Raises ValueError("invalid_key") on 401/403.
    Raises ValueError("no_channels") when zero channels returned.
    """
    channels_by_net_key = {}  # (network_slug, channel_key) -> channel dict

    for net in NETWORKS:
        img_map = _fetch_image_map(net["slug"])

        for quality, tier in QUALITY_TIERS.items():
            url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise ValueError("invalid_key")
                continue
            except Exception:
                continue

            for ch in data:
                key = (net["slug"], ch["key"])
                pls_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
                stream_urls = _resolve_pls(pls_url)  # gap-06: list, not str

                if key not in channels_by_net_key:
                    channels_by_net_key[key] = {
                        "title": ch["name"],
                        "provider": net["name"],
                        "image_url": img_map.get(ch["key"]),
                        "streams": [],
                    }
                # gap-06 fix for UAT gap 2: emit one stream dict per PLS File= entry
                # (primary + fallback). Position preserves PLS order within the tier
                # (tier_base * 10 + pls_index), so primary sorts before fallback when
                # order_streams uses position as the tiebreaker.
                tier_base = _POSITION_MAP[quality]
                for pls_index, url in enumerate(stream_urls, start=1):
                    channels_by_net_key[key]["streams"].append({
                        "url": url,
                        "quality": quality,
                        "position": tier_base * 10 + pls_index,
                        "codec": _CODEC_MAP[quality],
                        "bitrate_kbps": _BITRATE_MAP[quality],
                    })

    results = list(channels_by_net_key.values())
    if not results:
        raise ValueError("no_channels")
    return results


def import_stations_multi(channels: list[dict], repo, on_progress=None, on_logo_progress=None) -> tuple[int, int]:
    """Import multi-quality AA channels. Creates one station per channel with multiple streams.

    Each channel dict has "streams" list with {url, quality, position, codec}.
    Skips channel if ANY of its stream URLs already exist in library.
    """
    imported = 0
    skipped = 0
    logo_targets = []

    for ch in channels:
        # WR-02: skip channels with no streams. insert_station short-circuits on
        # empty url (repo.py:415-416), which would yield an orphan station with
        # zero stream rows counted as "imported". fetch_channels_multi never
        # emits empty streams today; this guards future callers that might.
        if not ch.get("streams"):
            skipped += 1
            _log.warning(
                "Skipping AA channel with no streams: %s",
                ch.get("title", "<unnamed>"),
            )
            if on_progress:
                on_progress(imported, skipped)
            continue
        # Check if any stream URL already exists
        any_exists = any(repo.station_exists_by_url(s["url"]) for s in ch["streams"])
        if any_exists:
            skipped += 1
        else:
            # Insert station (with first stream URL for backward compat)
            first_url = ch["streams"][0]["url"]
            station_id = repo.insert_station(
                name=ch["title"],
                url=first_url,
                provider_name=ch["provider"],
                tags="",
            )
            # insert_station already created a stream for first_url at position=1
            # Update the auto-created stream with quality/codec metadata, then insert remaining
            for s in ch["streams"]:
                if s["url"] == first_url:
                    streams = repo.list_streams(station_id)
                    if streams:
                        repo.update_stream(
                            streams[0].id, s["url"], s.get("label", ""),
                            s["quality"], s["position"],
                            "shoutcast", s.get("codec", ""),
                            bitrate_kbps=s.get("bitrate_kbps", 0),
                        )
                else:
                    repo.insert_stream(
                        station_id, s["url"], label="",
                        quality=s["quality"], position=s["position"],
                        stream_type="shoutcast", codec=s.get("codec", ""),
                        bitrate_kbps=s.get("bitrate_kbps", 0),
                    )
            imported += 1
            image_url = ch.get("image_url")
            if image_url:
                logo_targets.append((station_id, image_url))
        if on_progress:
            on_progress(imported, skipped)

    # Logo download phase (reuse existing pattern)
    if logo_targets:
        if on_logo_progress:
            on_logo_progress(0, len(logo_targets))

        def _download_logo(station_id: int, image_url: str) -> None:
            try:
                with urllib.request.urlopen(image_url, timeout=15) as resp:
                    data = resp.read()
                suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
                try:
                    art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
                    thread_repo = Repo(db_connect())
                    thread_repo.update_station_art(station_id, art_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except Exception:
                pass

        total = len(logo_targets)
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(_download_logo, sid, url): (sid, url)
                for sid, url in logo_targets
            }
            for future in as_completed(futures):
                future.result()
                completed += 1
                if on_logo_progress:
                    on_logo_progress(completed, total)

    return imported, skipped
