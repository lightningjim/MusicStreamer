"""AudioAddict network import backend.

Public API:
  fetch_channels(listen_key, quality) -> list[dict]
  import_stations(channels, repo, on_progress=None) -> (imported, skipped)
"""

import json
import urllib.error
import urllib.request


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
        for ch in data:
            pls_url = f"https://{net['domain']}/{tier}/{ch['key']}.pls?listen_key={listen_key}"
            stream_url = _resolve_pls(pls_url)
            results.append({
                "title": ch["name"],
                "url": stream_url,
                "provider": net["name"],
            })
    if not results:
        raise ValueError("no_channels")
    return results


def import_stations(channels: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Import a list of AudioAddict channel dicts into the station library via repo.

    Skips channels whose URL already exists (repo.station_exists_by_url).
    Calls on_progress(imported, skipped) after each channel if provided.

    Returns (imported_count, skipped_count).
    """
    imported = 0
    skipped = 0
    for ch in channels:
        url = ch["url"]
        if repo.station_exists_by_url(url):
            skipped += 1
        else:
            repo.insert_station(
                name=ch["title"],
                url=url,
                provider_name=ch["provider"],
                tags="",
            )
            imported += 1
        if on_progress:
            on_progress(imported, skipped)
    return imported, skipped
