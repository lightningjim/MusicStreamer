"""AudioAddict network import backend.

Public API:
  fetch_channels(listen_key, quality) -> list[dict]
  import_stations(channels, repo, on_progress=None, on_logo_progress=None) -> (imported, skipped)
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

    Falls back to [pls_url] if resolution fails — keeps callers that take
    [0] working against the legacy fallback-on-error behavior.
    """
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            body = resp.read().decode()
        entries = []  # list of (int_index, url) for file-order preservation
        for line in body.splitlines():
            m = re.match(r"^File(\d+)=(.+)$", line.strip())
            if m:
                entries.append((int(m.group(1)), m.group(2).strip()))
        if not entries:
            return [pls_url]
        entries.sort(key=lambda t: t[0])
        return [url for _, url in entries]
    except Exception:
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
    """
    try:
        api_url = f"https://api.audioaddict.com/v1/{slug}/channels"
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read())
        out = {}
        for ch in data:
            img = ch.get("images") or {}
            raw = img.get("square") or img.get("default")
            if raw:
                out[ch["key"]] = _normalize_aa_image_url(raw)
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


def fetch_channels(listen_key: str, quality: str) -> list[dict]:
    """Fetch all channels across all 6 AudioAddict networks.

    Returns a list of dicts with keys: "title", "url", "provider".
    Raises ValueError("invalid_key") on 401/403.
    Raises ValueError("no_channels") when zero channels returned across all networks.
    Skips networks that return other HTTP errors (non-auth failures).
    """
    tier = QUALITY_TIERS[quality]
    results = []
    for net in NETWORKS:
        url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ValueError("invalid_key")
            continue  # skip this network on other HTTP errors (Pitfall 6)
        img_map = _fetch_image_map(net["slug"])
        for ch in data:
            pls_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
            urls = _resolve_pls(pls_url)  # gap-06: list, not str
            stream_url = urls[0] if urls else pls_url
            results.append({
                "title": ch["name"],
                "url": stream_url,
                "provider": net["name"],
                "image_url": img_map.get(ch["key"]),
            })
    if not results:
        raise ValueError("no_channels")
    return results


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
                        "codec": "AAC" if tier == "premium_high" else "MP3",
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


def import_stations(channels: list[dict], repo, on_progress=None, on_logo_progress=None) -> tuple[int, int]:
    """Import a list of AudioAddict channel dicts into the station library via repo.

    Skips channels whose URL already exists (repo.station_exists_by_url).
    Calls on_progress(imported, skipped) after each channel if provided.
    After station inserts, downloads logos in parallel and calls on_logo_progress(done, total).

    Returns (imported_count, skipped_count).
    """
    imported = 0
    skipped = 0
    logo_targets = []  # list of (station_id, image_url)
    for ch in channels:
        url = ch["url"]
        if repo.station_exists_by_url(url):
            skipped += 1
        else:
            station_id = repo.insert_station(
                name=ch["title"],
                url=url,
                provider_name=ch["provider"],
                tags="",
            )
            imported += 1
            image_url = ch.get("image_url")
            if image_url:
                logo_targets.append((station_id, image_url))
        if on_progress:
            on_progress(imported, skipped)

    # Phase 2: download logos in parallel
    if logo_targets:
        if on_logo_progress:
            on_logo_progress(0, len(logo_targets))

        def _download_logo(station_id: int, image_url: str) -> None:
            try:
                with urllib.request.urlopen(image_url, timeout=15) as resp:
                    data = resp.read()
                # Write to a temp file then copy into assets/
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
                pass  # Silent failure per D-03

        total = len(logo_targets)
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(_download_logo, sid, url): (sid, url)
                for sid, url in logo_targets
            }
            for future in as_completed(futures):
                future.result()  # exceptions already caught inside worker
                completed += 1
                if on_logo_progress:
                    on_logo_progress(completed, total)

    return imported, skipped
