"""Phase 70 / Wave 0 RED stubs — musicstreamer/hi_res.py public API contract.

These tests cover T-01 (classify_tier truth table), DS-02 (bit_depth_from_format
mapping), best_tier_for_station, and TIER_LABEL_* constants. ALL tests are
intentionally RED until Plan 70-01 ships the implementation.

Phase 62-00 idiom: ImportError IS the RED state; no pytest.fail() placeholders.
The top-level module import is deliberately deferred into each test function
so that pytest collection succeeds while execution of each test raises ImportError.
"""
from __future__ import annotations

import pytest

from musicstreamer.models import Station, StationStream


# ---------------------------------------------------------------------------
# Helper — minimal Station + StationStream construction
# ---------------------------------------------------------------------------

def _stream(codec: str, sample_rate_hz: int = 0, bit_depth: int = 0) -> StationStream:
    """Build a StationStream for tier testing.

    NOTE: sample_rate_hz + bit_depth are Phase 70 / Plan 70-02 fields.
    Constructing them here is intentionally RED until Plan 70-02 lands.
    """
    return StationStream(
        id=0,
        station_id=0,
        url="http://example.com",
        codec=codec,
        sample_rate_hz=sample_rate_hz,  # RED until Plan 70-02
        bit_depth=bit_depth,             # RED until Plan 70-02
    )


def _station(*streams: StationStream) -> Station:
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=list(streams),
    )


# ---------------------------------------------------------------------------
# test_classify_tier_truth_table (T-01)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codec,rate,depth,expected", [
    # Lossless at CD-quality — must return "lossless"
    ("FLAC", 44100, 16, "lossless"),
    # Hi-Res by both rate and depth
    ("FLAC", 96000, 24, "hires"),
    # Hi-Res by bit-depth only (rate == 48000 is NOT > 48000, but depth 24 > 16)
    ("FLAC", 48000, 24, "hires"),
    # Hi-Res by rate only (rate 96000 > 48000, depth 16 == 16)
    ("FLAC", 96000, 16, "hires"),
    # D-03: FLAC + unknown rate/depth defaults to "lossless"
    ("FLAC", 0, 0, "lossless"),
    # ALAC defaults to "lossless" (mirrors FLAC)
    ("ALAC", 0, 0, "lossless"),
    # D-04: MP3 — no badge regardless of synthetic rate/depth
    ("MP3", 0, 0, ""),
    # D-04: AAC — no badge even at "hi-res" rates
    ("AAC", 96000, 24, ""),
    # Case-insensitive (lowercase flac)
    ("flac", 44100, 16, "lossless"),
    # None-safe (None codec)
    (None, 0, 0, ""),
    # Empty string codec
    ("", 0, 0, ""),
    # Whitespace-tolerant ("  FLAC  ")
    ("  FLAC  ", 44100, 16, "lossless"),
])
def test_classify_tier_truth_table(codec, rate, depth, expected):
    """T-01: classify_tier returns the correct tier for all canonical input cases."""
    from musicstreamer.hi_res import classify_tier  # RED: ImportError until Plan 70-01
    assert classify_tier(codec, rate, depth) == expected


# ---------------------------------------------------------------------------
# test_bit_depth_from_format (DS-02)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("format_str,expected", [
    # 16-bit signed
    ("S16LE", 16),
    ("S16BE", 16),
    ("U16LE", 16),
    ("U16BE", 16),
    # 24-bit signed
    ("S24LE", 24),
    ("S24BE", 24),
    # 24-bit in 32-bit container
    ("S24_32LE", 24),
    ("S24_32BE", 24),
    # 32-bit signed and float
    ("S32LE", 32),
    ("F32LE", 32),
    ("F32BE", 32),
    # 64-bit float — treat as 32-bit equivalent (per DS-02)
    ("F64LE", 32),
    # 8-bit — below 16-bit threshold, return 0 (unknown/unsupported)
    ("S8", 0),
    ("U8", 0),
    # Empty string
    ("", 0),
    # Unknown/bogus
    ("GIBBERISH", 0),
    ("UNKNOWN_FORMAT", 0),
])
def test_bit_depth_from_format(format_str, expected):
    """DS-02: bit_depth_from_format maps GstAudioFormat strings to bit-depth ints."""
    from musicstreamer.hi_res import bit_depth_from_format  # RED: ImportError until Plan 70-01
    assert bit_depth_from_format(format_str) == expected


# ---------------------------------------------------------------------------
# test_best_tier_for_station (T-05)
# ---------------------------------------------------------------------------

def test_best_tier_for_station_returns_hires_when_any_stream_is_hires():
    """T-05: a station with MP3 + CD-FLAC + 96/24-FLAC → 'hires' (best-across-streams)."""
    from musicstreamer.hi_res import best_tier_for_station  # RED: ImportError until Plan 70-01
    station = _station(
        _stream("MP3", 0, 0),
        _stream("FLAC", 44100, 16),
        _stream("FLAC", 96000, 24),
    )
    assert best_tier_for_station(station) == "hires"


def test_best_tier_for_station_returns_lossless_when_no_hires():
    """T-05: station with MP3 + CD-FLAC → 'lossless'."""
    from musicstreamer.hi_res import best_tier_for_station  # RED: ImportError until Plan 70-01
    station = _station(
        _stream("MP3", 0, 0),
        _stream("FLAC", 44100, 16),
    )
    assert best_tier_for_station(station) == "lossless"


def test_best_tier_for_station_returns_empty_for_lossy_only():
    """T-05: station with only MP3 streams → ''."""
    from musicstreamer.hi_res import best_tier_for_station  # RED: ImportError until Plan 70-01
    station = _station(_stream("MP3", 128, 0))
    assert best_tier_for_station(station) == ""


def test_best_tier_for_station_returns_empty_for_no_streams():
    """T-05: station with no streams → ''."""
    from musicstreamer.hi_res import best_tier_for_station  # RED: ImportError until Plan 70-01
    station = _station()
    assert best_tier_for_station(station) == ""


# ---------------------------------------------------------------------------
# test_tier_label_badge_constants
# ---------------------------------------------------------------------------

def test_tier_label_badge_constants():
    """UI-SPEC Copywriting Contract: TIER_LABEL_BADGE maps tier key to all-caps badge text."""
    from musicstreamer.hi_res import TIER_LABEL_BADGE  # RED: ImportError until Plan 70-01
    assert TIER_LABEL_BADGE["hires"] == "HI-RES"
    assert TIER_LABEL_BADGE["lossless"] == "LOSSLESS"
    assert TIER_LABEL_BADGE[""] == ""


# ---------------------------------------------------------------------------
# test_tier_label_prose_constants
# ---------------------------------------------------------------------------

def test_tier_label_prose_constants():
    """UI-SPEC Copywriting Contract: TIER_LABEL_PROSE maps tier key to title-case prose text."""
    from musicstreamer.hi_res import TIER_LABEL_PROSE  # RED: ImportError until Plan 70-01
    assert TIER_LABEL_PROSE["hires"] == "Hi-Res"
    assert TIER_LABEL_PROSE["lossless"] == "Lossless"
    assert TIER_LABEL_PROSE[""] == ""
