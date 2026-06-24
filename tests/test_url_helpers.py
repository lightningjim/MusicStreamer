"""Phase 97 Plan 01: Wave-0 tests for Station.canonical_url property.

These tests are intentionally RED — Station.canonical_url does not exist yet.
They will turn GREEN when Plan 02 adds the property to Station in models.py.

Tests assert all four resolution branches of the planned canonical_url property:
  (a) canonical_stream_id set + matching stream present -> that stream's url
  (b) canonical_stream_id None -> position-1 stream url (sorted by position, id)
  (c) canonical_stream_id set but stale (no matching stream id) -> position-1 url
  (d) no streams -> ""
"""
from musicstreamer.models import Station, StationStream


def _make_stream(id_: int, station_id: int, url: str, position: int = 1) -> StationStream:
    """Factory: build a minimal StationStream dataclass (no mock, per TESTING.md)."""
    return StationStream(
        id=id_,
        station_id=station_id,
        url=url,
        label="",
        quality="hi",
        position=position,
        stream_type="",
        codec="MP3",
    )


def _make_station(id_: int, streams: list, canonical_stream_id=None) -> Station:
    """Factory: build a minimal Station dataclass (no mock, per TESTING.md)."""
    return Station(
        id=id_,
        name=f"Station {id_}",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
        canonical_stream_id=canonical_stream_id,
    )


def test_canonical_url_resolves_fk_with_position1_fallback():
    """D-07: Station.canonical_url resolves all four branches correctly.

    Branch (a): canonical_stream_id set + matching stream present
                -> returns that stream's url (even if not position 1).
    Branch (b): canonical_stream_id None
                -> returns position-1 stream url (sorted by position, id).
    Branch (c): canonical_stream_id set but stale (no matching stream id)
                -> falls back to position-1 url.
    Branch (d): no streams -> returns "".

    RED: Station has no canonical_url property until Plan 02. Accessing it will
    raise AttributeError.
    """
    # Branch (a): canonical_stream_id points to stream s2 (position 2, not position 1)
    s1 = _make_stream(id_=10, station_id=1, url="http://pos1.mp3", position=1)
    s2 = _make_stream(id_=20, station_id=1, url="http://pos2.mp3", position=2)
    station_a = _make_station(id_=1, streams=[s1, s2], canonical_stream_id=20)
    # canonical_url should return pos2.mp3 (canonical FK points to s2)
    result_a = station_a.canonical_url  # AttributeError until Plan 02
    assert result_a == "http://pos2.mp3", (
        f"Branch (a): expected canonical FK URL 'http://pos2.mp3', got {result_a!r}"
    )

    # Branch (b): canonical_stream_id None -> position-1 stream
    station_b = _make_station(id_=2, streams=[s2, s1], canonical_stream_id=None)
    # sorted by (position, id): s1(pos=1,id=10) comes first
    result_b = station_b.canonical_url  # AttributeError until Plan 02
    assert result_b == "http://pos1.mp3", (
        f"Branch (b): expected position-1 URL 'http://pos1.mp3', got {result_b!r}"
    )

    # Branch (c): canonical_stream_id set but stale (stream id 999 does not exist)
    station_c = _make_station(id_=3, streams=[s1, s2], canonical_stream_id=999)
    # stale FK -> fall back to position-1 (s1)
    result_c = station_c.canonical_url  # AttributeError until Plan 02
    assert result_c == "http://pos1.mp3", (
        f"Branch (c): expected position-1 fallback 'http://pos1.mp3', got {result_c!r}"
    )

    # Branch (d): no streams -> ""
    station_d = _make_station(id_=4, streams=[], canonical_stream_id=None)
    result_d = station_d.canonical_url  # AttributeError until Plan 02
    assert result_d == "", (
        f"Branch (d): expected empty string for no-stream station, got {result_d!r}"
    )
