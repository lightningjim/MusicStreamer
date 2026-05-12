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

def _stream(
    codec: str,
    sample_rate_hz: int = 0,
    bit_depth: int = 0,
    bitrate_kbps: int = 0,
) -> StationStream:
    """Build a StationStream for tier testing.

    bitrate_kbps kwarg supports the post-2026-05-12 D-04 revision where lossy
    codecs at bitrate > 128 also qualify as Hi-Res (mirrors moOde
    RADIO_BITRATE_THRESHOLD).
    """
    return StationStream(
        id=0,
        station_id=0,
        url="http://example.com",
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        bit_depth=bit_depth,
        bitrate_kbps=bitrate_kbps,
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
    # D-04 (no-bitrate branch): MP3 with no bitrate info → no badge
    ("MP3", 0, 0, ""),
    # D-04 (no-bitrate branch): AAC with no bitrate info → no badge even at
    # synthetic "hi-res" caps (caps without bitrate context can't qualify)
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
# test_classify_tier_lossy_bitrate_threshold (D-04 revised 2026-05-12 post-UAT)
#
# Mirrors moOde Audio playerlib.js RADIO_BITRATE_THRESHOLD = 128:
# lossy codec at bitrate_kbps > 128 → "hires" badge.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codec,bitrate,expected", [
    # 320 kbps MP3 (DI.FM premium tier) — moOde shows HiRes here per live UAT
    ("MP3", 320, "hires"),
    # 256 kbps lossy — also > 128 → hires
    ("AAC", 256, "hires"),
    ("OPUS", 256, "hires"),
    # 192 kbps lossy — still > 128 → hires
    ("MP3", 192, "hires"),
    # 129 kbps — strictly > 128 → hires (boundary just above)
    ("MP3", 129, "hires"),
    # 128 kbps lossy — exactly at threshold, NOT strictly greater → no badge
    # (moOde uses > not >=; matches your screenshot: MP3 128K and AAC 128K
    # show no HiRes badge)
    ("MP3", 128, ""),
    ("AAC", 128, ""),
    # Sub-128 lossy → no badge
    ("MP3", 96, ""),
    ("AAC", 64, ""),
    # Zero / missing bitrate → no badge (pre-Phase-47.2 import compat)
    ("MP3", 0, ""),
    # Lossless codec branch ignores bitrate; FLAC at any kbps still → lossless
    # for CD-quality caps (rate/depth not passed → 0,0 = D-03 default).
    ("FLAC", 320, "lossless"),
    ("FLAC", 0, "lossless"),
    # ALAC same as FLAC.
    ("ALAC", 1500, "lossless"),
    # Unknown / empty codec ignores bitrate.
    ("", 320, ""),
    (None, 320, ""),
])
def test_classify_tier_lossy_bitrate_threshold(codec, bitrate, expected):
    """D-04 revised: lossy codec at bitrate > 128 kbps → 'hires' (moOde mirror).

    Pinned thresholds:
      - bitrate > 128 → "hires" (NOT >=; matches RADIO_BITRATE_THRESHOLD)
      - bitrate <= 128 → ""
      - Lossless codec branch unaffected by bitrate.
    """
    from musicstreamer.hi_res import classify_tier
    assert classify_tier(codec, 0, 0, bitrate) == expected


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
    """T-05: station with only sub-128-kbps MP3 streams → ''."""
    from musicstreamer.hi_res import best_tier_for_station  # RED: ImportError until Plan 70-01
    # rate=128 here is a typo-resistant value — MP3 with no bitrate kwarg
    # passes bitrate_kbps=0 (default), which is below the 128 threshold.
    station = _station(_stream("MP3", sample_rate_hz=44100, bit_depth=0))
    assert best_tier_for_station(station) == ""


def test_best_tier_for_station_returns_hires_for_high_bitrate_lossy():
    """T-05 revised: D-04 lossy>128 path — station with only MP3-320 → 'hires'.

    Matches the moOde behavior verified live 2026-05-12: DI.FM Lounge at MP3
    320K shows the HiRes badge. Phase 70's original D-04 (no badge for lossy)
    was rejected after UAT.
    """
    from musicstreamer.hi_res import best_tier_for_station
    station = _station(_stream("MP3", bitrate_kbps=320))
    assert best_tier_for_station(station) == "hires"


def test_best_tier_for_station_lossy_at_128_kbps_returns_empty():
    """T-05 revised: D-04 boundary — MP3 at exactly 128 kbps → ''.

    Mirrors moOde's `bitrate > RADIO_BITRATE_THRESHOLD` (strict greater-than).
    """
    from musicstreamer.hi_res import best_tier_for_station
    station = _station(_stream("MP3", bitrate_kbps=128))
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
