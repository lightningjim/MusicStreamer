"""Phase 68 / D-01a: AudioAddict events API + ICY-title live-show detection.

Pure Python — no Qt, no DB, no logging. Importable from any test or worker
thread. Plans 03 (panel/worker) and 04 (proxy) consume this module.

Public API:
    fetch_live_map(network_slug) -> dict[str, str]
    detect_live_from_icy(title) -> str | None
    get_di_channel_key(station) -> str | None

The internal _parse_live_map is exposed for testability (Plan 01 pins
deterministic `now` values via the keyword-only argument).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from musicstreamer.url_helpers import (
    _aa_channel_key_from_url,
    _aa_slug_from_url,
    _is_aa_url,
)

AA_EVENTS_URL = "https://api.audioaddict.com/v1/{slug}/events"
_REQUEST_TIMEOUT_S = 15
# P-01: regex matches LIVE: or LIVE - prefix (case-insensitive, optional surrounding ws).
# P-02: rejects substring matches like "Live and Let Die" — the [:|-] separator after LIVE
# is required.
_LIVE_ICY_RE = re.compile(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', re.IGNORECASE)


def detect_live_from_icy(title: Optional[str]) -> Optional[str]:
    """Return show name if title matches LIVE: or LIVE - prefix, else None.

    P-01: prefix-only match.
    P-02: substring matches like 'Live and Let Die' return None (no separator).
    P-03: stateless — caller re-evaluates on every title_changed.
    """
    if not title:
        return None
    m = _LIVE_ICY_RE.match(title)
    return m.group(1).strip() if m else None


def _parse_live_map(
    events: list[dict],
    *,
    now: Optional[datetime] = None,
) -> dict[str, str]:
    """Pure parser: extract {channel_key: show_name} for currently-live events.

    A show is live when start_at <= now < end_at. Multiple shows may be live
    simultaneously on different channels (one show may also broadcast to
    multiple channels). Malformed dates and missing fields are skipped.

    Args:
        events: list of event dicts from the AA events endpoint.
        now: timezone-aware datetime; defaults to datetime.now(timezone.utc).
             Tests pin this for determinism.

    Returns:
        dict mapping channel_key -> show_name for currently-live shows.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    live_map: dict[str, str] = {}
    for ev in events or []:
        start_raw = ev.get("start_at", "")
        end_raw = ev.get("end_at", "")
        if not start_raw or not end_raw:
            continue
        try:
            start = datetime.fromisoformat(start_raw)
            end = datetime.fromisoformat(end_raw)
        except (ValueError, TypeError):
            # Pitfall 2: malformed dates skipped silently.
            continue
        if start <= now < end:
            show = ev.get("show") or {}
            show_name = show.get("name", "") or ""
            for ch in show.get("channels") or []:
                key = ch.get("key", "")
                if key:
                    live_map[key] = show_name
    return live_map


def fetch_live_map(network_slug: str = "di") -> dict[str, str]:
    """Fetch currently-live shows for an AA network.

    D-02: network_slug parameterized so adding RockRadio/JazzGroove/etc. is
    a one-line caller change. Default 'di' covers Phase 68 v1 scope.

    A-04 silent failure contract: returns {} on any HTTPError, URLError,
    TimeoutError, JSON decode error, or generic Exception. No logging — the
    background poll cycle would amplify log noise on transient failures.
    Caller (Plan 03's _AaLiveWorker) re-attempts on next poll cycle.

    A-03: GET with no listen_key, no headers beyond the urllib defaults.
    """
    url = AA_EVENTS_URL.format(slug=network_slug)
    try:
        with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError:
        return {}
    except urllib.error.URLError:
        return {}
    except TimeoutError:
        return {}
    except (json.JSONDecodeError, ValueError):
        return {}
    except Exception:
        # A-04 belt-and-suspenders: never let a malformed response propagate
        # into the worker thread's run() — Pattern 7 / RESEARCH anti-patterns.
        return {}
    if not isinstance(data, list):
        return {}
    return _parse_live_map(data)


def get_di_channel_key(station) -> Optional[str]:
    """Extract DI.fm channel key from station's first stream URL.

    A-06: uses the existing _aa_channel_key_from_url contract from
    url_helpers.py (handles _hi/_med/_low quality suffix and the
    _AA_CHANNEL_KEY_ALIASES table for renamed channels — Pitfall 3).

    Returns None if:
      - station has no streams (defensive — Pitfall 6 cold-start guard).
      - station's first stream URL is not an AA URL.
      - station's network slug is not 'di' (D-02 v1 scope).
      - the channel key cannot be derived.
    """
    streams = getattr(station, "streams", None) or []
    if not streams:
        return None
    url = streams[0].url
    if not _is_aa_url(url):
        return None
    slug = _aa_slug_from_url(url)
    if slug != "di":
        return None
    return _aa_channel_key_from_url(url, slug="di")
