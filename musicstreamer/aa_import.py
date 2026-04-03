"""AudioAddict network import backend.

Public API:
  fetch_channels(listen_key, quality) -> list[dict]
  import_stations(channels, repo, on_progress=None, on_logo_progress=None) -> (imported, skipped)
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import db_connect, Repo


def _resolve_pls(pls_url: str) -> str:
    """Fetch a PLS playlist and return the first stream URL (File1 entry).

    Falls back to the PLS URL itself if resolution fails.
    """
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            for line in resp.read().decode().splitlines():
                if line.startswith("File1="):
                    return line[len("File1="):].strip()
    except Exception:
        pass
    return pls_url


def _normalize_aa_image_url(raw: str) -> str:
    """Prepend https: and strip URI template from an AA CDN image URL."""
    url = re.sub(r'\{[^}]+\}', '', raw).strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def _fetch_image_map(slug: str) -> dict:
    """Return {channel_key: normalized_image_url} for a network. Empty dict on failure."""
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
    except Exception:
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
            stream_url = _resolve_pls(pls_url)
            results.append({
                "title": ch["name"],
                "url": stream_url,
                "provider": net["name"],
                "image_url": img_map.get(ch["key"]),
            })
    if not results:
        raise ValueError("no_channels")
    return results


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
