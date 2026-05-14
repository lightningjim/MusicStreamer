"""SomaFM network import backend.

Public API:
  fetch_channels(timeout) -> list[dict]
  import_stations(channels, repo, on_progress=None) -> (imported, skipped)

Each channel dict has:
  {"id": str, "title": str, "description": str, "image_url": str|None,
   "streams": [{"url": str, "quality": str, "position": int,
                "codec": str, "bitrate_kbps": int}]}

Phase 74 DEVIATIONS from aa_import.py:
  1. No listen_key / no _fetch_image_map (SomaFM API is public).
  2. fetch_channels expands inline playlists from the channels.json response
     rather than fetching per-network URLs.
  3. import_stations wraps each channel loop body in try/except (D-15 / RESEARCH
     Pitfall 2) — AA does NOT have this wrapper; Phase 74 adds it.
  4. _resolve_pls returns ALL File= entries (5 ICE relays), not just the first.
"""

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.metadata import version as _pkg_version
from urllib.parse import urlparse

from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import db_connect, Repo

_log = logging.getLogger(__name__)

# SomaFM public catalog endpoint (RESEARCH Open Question 5 LOCKED 2026-05-13).
_API_URL = "https://api.somafm.com/channels.json"

# AA convention: 15-second timeout for catalog fetches (cover_art uses 5; we use 15).
_TIMEOUT_S = 15

# Phase 74 D-18 / SOMA-13/14: UA literal must contain both substrings for source-grep
# gate (test_user_agent_literal_present_in_source / SOMA-14). Mirror cover_art_mb.py:68-83.
# IN-05: tolerate PackageNotFoundError so import never fails on stripped-metadata builds.
try:
    _MS_VERSION = _pkg_version("musicstreamer")
except Exception:
    _MS_VERSION = "0.0.0"
_USER_AGENT = (
    f"MusicStreamer/{_MS_VERSION} "
    f"(https://github.com/lightningjim/MusicStreamer)"
)

# Phase 74 D-03 LOCKED 2026-05-13: 4-tier × 5-relay = 20 streams per channel.
# Tier→quality mapping (tier_base drives position ordering):
#   (mp3,  highest) → quality="hi",  tier_base=1, codec="MP3", bitrate=128
#   (aac,  highest) → quality="hi2", tier_base=2, codec="AAC", bitrate=128
#   (aacp, high)    → quality="med", tier_base=3, codec="AAC", bitrate=64
#   (aacp, low)     → quality="low", tier_base=4, codec="AAC", bitrate=32
# Position formula: position = tier_base * 10 + relay_index (relay_index 1..5).
# Codec for 'aacp' (HE-AAC) is "AAC" — Phase 69 WIN-05 verified it decodes via
# aacparse + avdec_aac chain. "AAC+" is intentionally absent (SOMA-15 / T-74-02).
_TIER_BY_FORMAT_QUALITY: dict[tuple[str, str], dict] = {
    ("mp3",  "highest"): {"quality": "hi",  "tier_base": 1, "codec": "MP3", "bitrate_kbps": 128},
    ("aac",  "highest"): {"quality": "hi2", "tier_base": 2, "codec": "AAC", "bitrate_kbps": 128},
    ("aacp", "high"):    {"quality": "med", "tier_base": 3, "codec": "AAC", "bitrate_kbps": 64},
    ("aacp", "low"):     {"quality": "low", "tier_base": 4, "codec": "AAC", "bitrate_kbps": 32},
}


# Phase 74 REVIEW CR-02: SSRF / local-file-read mitigation.
# urllib.request.urlopen accepts file://, ftp://, jar://, etc. A compromised
# api.somafm.com (or any MitM that survives TLS) could return
# {"image": "file:///etc/passwd"} and the import would read local files into
# the station-art directory. Restrict to HTTP(S) — 'http' is retained for
# legacy SomaFM ICE relays on port 80.
_ALLOWED_SCHEMES = frozenset({"https", "http"})


def _safe_urlopen_request(url: str) -> urllib.request.Request:
    """Build a urllib Request after validating the URL scheme + netloc.

    Raises ValueError for non-HTTP(S) schemes (file://, ftp://, jar://) or
    URLs with an empty netloc. Callers feed the returned Request to
    urllib.request.urlopen.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Refusing non-HTTP(S) URL scheme: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValueError(f"Refusing URL with empty netloc: {url!r}")
    return urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})


# Phase 74.1 / G-02 / SOMA-02 / CR-01: SomaFM relay URL slugs encode the
# actual stream bitrate (e.g. ice2.somafm.com/synphaera-256-mp3 -> 256 kbps).
# The _TIER_BY_FORMAT_QUALITY table is only a fallback for unparseable slugs.
_BITRATE_FROM_URL_RE = re.compile(r"-(\d+)-(?:mp3|aac|aacp)\b")


def _bitrate_from_url(url: str, default: int) -> int:
    """Extract bitrate from SomaFM ICE URL slug like ice2.somafm.com/foo-256-mp3.

    Falls back to ``default`` when the slug is missing or non-numeric.
    """
    m = _BITRATE_FROM_URL_RE.search(url)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return default


def _resolve_pls(pls_url: str, timeout: int = 10) -> list[str]:
    """Fetch a PLS playlist and return ALL stream URLs in file order.

    SomaFM PLS files contain 5 ICE relay entries per tier (ice1..ice5.somafm.com);
    all 5 are needed to give the player per-channel relay failover.

    Phase 74 D-03 LOCKED: return ALL File= entries (not just the first — this is
    the sole behavioural deviation from the old aa_import._resolve_pls which took [0]).
    T-74-03: returned URLs are direct ice*.somafm.com URLs, NOT the .pls input URL.

    Phase 74 REVIEW CR-01: returns [] on fetch failure or empty parse. The
    caller's ``if not streams: continue`` (fetch_channels) already drops a
    channel that produces zero recognisable tiers — that is the correct
    behaviour. Returning [pls_url] on error (the old AA-legacy fallback
    contract) would persist a `.pls` URL as a `station_streams.url` row that
    the player cannot decode, and dedup-by-URL would then prevent any
    subsequent re-import from repairing it (silent permanent data corruption).
    """
    try:
        req = _safe_urlopen_request(pls_url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        return [e["url"] for e in entries if e.get("url")]
    except Exception as exc:  # noqa: BLE001
        _log.warning("SomaFM PLS fetch failed for %s: %s", pls_url, exc)
        return []


def fetch_channels(timeout: int = _TIMEOUT_S) -> list[dict]:
    """Fetch all SomaFM channels and expand each channel's 4 PLS tiers to streams.

    Returns list of channel dicts; each dict contains the expanded stream list
    (up to 4 tiers × 5 ICE relays = 20 streams per channel).

    Raises ValueError("no_channels") if catalog returns zero channels (D-14).
    Raises urllib / json exceptions on network / parse failure — they propagate
    to the caller (worker layer) without wrapping.

    Per-channel exceptions during stream extraction skip that channel and continue
    (D-15 / RESEARCH Pitfall 2 mitigation).
    """
    req = _safe_urlopen_request(_API_URL)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())

    raw_channels = data.get("channels", [])
    if not raw_channels:
        raise ValueError("no_channels")

    out: list[dict] = []

    for ch in raw_channels:
        try:
            streams: list[dict] = []
            for pl in ch.get("playlists", []):
                tier_meta = _TIER_BY_FORMAT_QUALITY.get(
                    (pl.get("format"), pl.get("quality"))
                )
                if tier_meta is None:
                    # Unknown tier — skip silently (RESEARCH Pitfall 6)
                    continue
                relay_urls = _resolve_pls(pl["url"])
                for relay_index, relay_url in enumerate(relay_urls, start=1):
                    parsed_bitrate = _bitrate_from_url(relay_url, tier_meta["bitrate_kbps"])
                    streams.append({
                        "url": relay_url,
                        "quality": tier_meta["quality"],
                        "position": tier_meta["tier_base"] * 10 + relay_index,
                        "codec": tier_meta["codec"],
                        "bitrate_kbps": parsed_bitrate,
                    })
            if not streams:
                # Channel produced no recognisable tiers — drop it
                continue
            out.append({
                "id": ch["id"],
                "title": ch["title"],
                "description": ch.get("description", ""),
                # Use "image" (120 px) to match AA logo dimensionality
                # (RESEARCH "Alternatives Considered" — NOT "xlimage" / 512 px)
                "image_url": ch.get("image"),
                "streams": streams,
            })
        except Exception as exc:  # noqa: BLE001
            _log.warning("Skipping SomaFM channel %s: %s", ch.get("id"), exc)
            continue

    return out


def import_stations(channels: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Import SomaFM channels. Creates one station per channel with multiple streams.

    Each channel dict must have a "streams" list as returned by fetch_channels.
    Skips channel if ANY of its stream URLs already exist in library (D-05/D-09).

    Phase 74 D-15 / RESEARCH Pitfall 2: the loop body is wrapped in try/except so
    a malformed channel dict only increments `skipped` and the import continues.
    This is the SOLE structural deviation from aa_import.import_stations_multi,
    which lacks the per-channel try/except wrapper.

    Returns (imported, skipped).
    """
    imported = 0
    skipped = 0
    logo_targets: list[tuple[int, str]] = []

    for ch in channels:
        try:
            if not ch.get("streams"):
                skipped += 1
                _log.warning(
                    "Skipping SomaFM channel with no streams: %s",
                    ch.get("title", "<unnamed>"),
                )
            else:
                # D-05/D-09: skip if ANY stream URL already exists in the library
                any_exists = any(
                    repo.station_exists_by_url(s["url"]) for s in ch["streams"]
                )
                if any_exists:
                    skipped += 1
                else:
                    first_url = ch["streams"][0]["url"]
                    # D-02: provider_name literal is "SomaFM" (CamelCase, no space, no period)
                    station_id = repo.insert_station(
                        name=ch["title"],
                        url=first_url,
                        provider_name="SomaFM",
                        tags="",
                    )
                    # D-10: insert_station auto-creates ONE stream row at position=1.
                    # Backfill codec/quality/bitrate on the auto-created row, then
                    # insert_stream for each remaining stream.
                    for s in ch["streams"]:
                        if s["url"] == first_url:
                            streams = repo.list_streams(station_id)
                            if streams:
                                repo.update_stream(
                                    streams[0].id,
                                    s["url"],
                                    "",
                                    s["quality"],
                                    s["position"],
                                    "shoutcast",
                                    s["codec"],
                                    bitrate_kbps=s["bitrate_kbps"],
                                )
                        else:
                            repo.insert_stream(
                                station_id,
                                s["url"],
                                label="",
                                quality=s["quality"],
                                position=s["position"],
                                stream_type="shoutcast",
                                codec=s["codec"],
                                bitrate_kbps=s["bitrate_kbps"],
                            )
                    imported += 1
                    if ch.get("image_url"):
                        logo_targets.append((station_id, ch["image_url"]))
        except Exception as exc:  # noqa: BLE001
            # D-15: bad channel increments skipped; import continues with rest
            _log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
            skipped += 1

        if on_progress:
            on_progress(imported, skipped)

    # D-11: logo download is best-effort; station + streams survive logo failure
    _download_logos(logo_targets)
    return imported, skipped


def _download_logos(logo_targets: list[tuple[int, str]]) -> None:
    """Download station logos concurrently (best-effort; failures are silently swallowed).

    D-11: logo failure is non-fatal — station + streams remain inserted.
    D-08: no progress bar; toast-only feedback.
    Uses ThreadPoolExecutor(max_workers=8) (RESEARCH "Alternatives Considered").
    """
    if not logo_targets:
        return

    def _download_logo(station_id: int, image_url: str) -> None:
        try:
            req = _safe_urlopen_request(image_url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
                # Phase 74 REVIEW CR-03: own the sqlite3.Connection lifetime
                # explicitly. Relying on refcount GC under ThreadPoolExecutor
                # leaves dozens of WAL-locked connections open for the
                # executor's lifetime; on Windows that has been observed to
                # hold journal locks
                # (MEMORY: reference_musicstreamer_db_schema).
                con = db_connect()
                try:
                    Repo(con).update_station_art(station_id, art_path)
                finally:
                    con.close()
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception:  # noqa: BLE001
            pass

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_download_logo, sid, url): (sid, url)
            for sid, url in logo_targets
        }
        for future in as_completed(futures):
            future.result()
