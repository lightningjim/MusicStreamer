"""Phase 68 / TD-01: pure-helper RED tests for aa_live.

Modeled on tests/test_aa_siblings.py — no Qt, no live network calls, one assertion
per test. Tests assert the contract of:

    fetch_live_map(network_slug) -> dict[str, str]
    _parse_live_map(events, *, now=None) -> dict[str, str]
    detect_live_from_icy(title) -> str | None
    get_di_channel_key(station) -> str | None

All tests in this file FAIL with ImportError on the import below until Plan 02
creates musicstreamer/aa_live.py. That ImportError IS the RED state for Wave 0 —
a single collection-time failure that blocks all 20+ test functions simultaneously.
"""
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.aa_live import (  # noqa: E402  ← PRODUCES ImportError until Plan 02
    _parse_live_map,
    detect_live_from_icy,
    fetch_live_map,
    get_di_channel_key,
)


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures" / "aa_live"


def _load(name: str) -> list:
    """Load a JSON fixture file from tests/fixtures/aa_live/."""
    return json.loads((_FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# Station factory (mirrors test_aa_siblings.py:12-23)
# ---------------------------------------------------------------------------

def _mk_di(id_: int, name: str, url: str) -> Station:
    """Factory: DI.fm Station with one StationStream at `url`."""
    return Station(
        id=id_,
        name=name,
        provider_id=1,
        provider_name="DI.fm",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=id_ * 10,
                station_id=id_,
                url=url,
                position=1,
            )
        ],
    )


# ---------------------------------------------------------------------------
# ICY pattern tests (P-01, P-02, P-03)
# ---------------------------------------------------------------------------

def test_icy_live_prefix_colon():
    """Phase 68 / P-01: detect_live_from_icy matches LIVE: prefix."""
    assert detect_live_from_icy("LIVE: DJ Set") == "DJ Set"


def test_icy_live_prefix_dash():
    """Phase 68 / P-01: detect_live_from_icy matches LIVE - prefix."""
    assert detect_live_from_icy("LIVE - DJ Set") == "DJ Set"


def test_icy_case_insensitive():
    """Phase 68 / P-01: detect_live_from_icy is case-insensitive."""
    assert detect_live_from_icy("live: Set") == "Set"


def test_icy_no_false_positive_substring():
    """Phase 68 / P-02: 'Live and Let Die' must NOT match (no separator after LIVE)."""
    assert detect_live_from_icy("Live and Let Die") is None


def test_icy_no_false_positive_at_wembley():
    """Phase 68 / P-02: 'Live at Wembley' must NOT match (no colon or dash separator)."""
    assert detect_live_from_icy("Live at Wembley") is None


def test_icy_returns_none_for_empty_and_none():
    """Phase 68 / P-01: empty string and None both return None."""
    assert detect_live_from_icy("") is None and detect_live_from_icy(None) is None


def test_icy_strips_surrounding_whitespace():
    """Phase 68 / P-01: optional surrounding whitespace stripped from title and group."""
    assert detect_live_from_icy("  LIVE: My Show  ") == "My Show"


# ---------------------------------------------------------------------------
# Events parser tests (A-02)
# ---------------------------------------------------------------------------

def test_parse_live_map_event_in_window():
    """Phase 68 / A-02: _parse_live_map detects event whose window covers now."""
    events = _load("events_with_live.json")
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert result == {"house": "Deeper Shades of House", "lounge": "Deeper Shades of House"}


def test_parse_live_map_no_live():
    """Phase 68 / A-02: _parse_live_map returns empty dict when no event covers now."""
    events = _load("events_no_live.json")
    now = datetime(2026, 5, 9, 0, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert result == {}


def test_parse_live_map_multi_channel_one_show():
    """Phase 68 / A-02: multi-channel show maps all channel keys to same show name."""
    events = _load("events_with_live.json")
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert "house" in result and "lounge" in result
    assert result["house"] == result["lounge"] == "Deeper Shades of House"


def test_parse_live_map_multiple_concurrent_events():
    """Phase 68 / A-02: multiple concurrent events on distinct channels → multiple entries."""
    events = _load("events_multiple_live.json")
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert len(result) >= 2
    assert "trance" in result
    assert "house" in result or "progressive" in result


def test_parse_live_map_skips_malformed_dates():
    """Phase 68 / A-02 / Pitfall 2: malformed start_at skipped silently; valid event still present."""
    events = [
        {
            "id": 1,
            "start_at": "not-a-date",
            "end_at": "2026-05-10T14:00:00+00:00",
            "show": {"name": "Bad Event", "channels": [{"key": "trance"}]},
        },
        {
            "id": 2,
            "start_at": "2026-05-10T11:00:00+00:00",
            "end_at": "2026-05-10T13:00:00+00:00",
            "show": {"name": "Good Event", "channels": [{"key": "house"}]},
        },
    ]
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert "house" in result and result["house"] == "Good Event"


def test_parse_live_map_skips_events_missing_start_or_end():
    """Phase 68 / A-02 / Pitfall 2: events missing start_at or end_at are skipped without raising."""
    events = [
        {
            "id": 1,
            "end_at": "2026-05-10T13:00:00+00:00",
            "show": {"name": "No Start", "channels": [{"key": "trance"}]},
        },
        {
            "id": 2,
            "start_at": "2026-05-10T11:00:00+00:00",
            "show": {"name": "No End", "channels": [{"key": "house"}]},
        },
    ]
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = _parse_live_map(events, now=now)
    assert result == {}


# ---------------------------------------------------------------------------
# HTTP layer tests (A-04)
# ---------------------------------------------------------------------------

def test_fetch_live_map_http_error_returns_empty():
    """Phase 68 / A-04: HTTP error → empty dict, no exception propagated."""
    with patch("urllib.request.urlopen",
               side_effect=urllib.error.HTTPError(
                   url="https://api.audioaddict.com/v1/di/events",
                   code=500,
                   msg="err",
                   hdrs=None,
                   fp=None,
               )):
        assert fetch_live_map("di") == {}


def test_fetch_live_map_timeout_returns_empty():
    """Phase 68 / A-04: network timeout → empty dict, no exception propagated."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("simulated")):
        assert fetch_live_map("di") == {}


def test_fetch_live_map_invalid_json_returns_empty():
    """Phase 68 / A-04: invalid JSON response → empty dict, no exception propagated."""
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = b"not json"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert fetch_live_map("di") == {}


# ---------------------------------------------------------------------------
# Channel key derivation tests (A-06)
# ---------------------------------------------------------------------------

def test_channel_key_from_di_url_simple():
    """Phase 68 / A-06: DI.fm house URL → channel key 'house'."""
    assert get_di_channel_key(
        _mk_di(1, "House", "http://prem1.di.fm:80/di_house?listen_key=k")
    ) == "house"


def test_channel_key_from_di_url_with_quality_suffix():
    """Phase 68 / A-06: _hi quality suffix stripped from channel key."""
    assert get_di_channel_key(
        _mk_di(2, "Trance", "http://prem1.di.fm:80/di_trance_hi?listen_key=k")
    ) == "trance"


def test_channel_key_alias_round_trip():
    """Phase 68 / A-06 / Pitfall 3: classicelectronica URL → classictechno alias matches events fixture."""
    events = _load("events_aliased_channel.json")
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    station = _mk_di(3, "Classic", "http://prem1.di.fm:80/di_classicelectronica_hi?listen_key=k")
    channel_key = get_di_channel_key(station)
    assert channel_key == "classictechno"
    live_map = _parse_live_map(events, now=now)
    assert "classictechno" in live_map


def test_channel_key_returns_none_for_non_aa_url():
    """Phase 68 / A-06: non-AA URL returns None."""
    assert get_di_channel_key(
        _mk_di(4, "X", "http://example.com/stream.mp3")
    ) is None


def test_channel_key_returns_none_for_no_streams():
    """Phase 68 / A-06 / Pitfall 6: Station with empty streams list → None (cold-start guard)."""
    station = Station(
        id=5,
        name="Empty",
        provider_id=1,
        provider_name="DI.fm",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
    )
    assert get_di_channel_key(station) is None
