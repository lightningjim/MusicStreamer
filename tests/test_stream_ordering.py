"""Tests for musicstreamer/stream_ordering.py — Phase 47 failover ordering."""
from __future__ import annotations

import pytest

from musicstreamer.models import StationStream
from musicstreamer.stream_ordering import codec_rank, order_streams, quality_rank


def _s(
    codec: str = "", bitrate_kbps: int = 0, position: int = 1,
    url: str = "u", quality: str = "",
) -> StationStream:
    return StationStream(
        id=0, station_id=0, url=url, codec=codec, quality=quality,
        bitrate_kbps=bitrate_kbps, position=position,
    )


@pytest.mark.parametrize("codec,expected", [
    ("FLAC", 3), ("flac", 3), ("  FLAC  ", 3),
    ("AAC", 2), ("aac", 2),
    ("MP3", 1), ("mp3", 1),
    ("OPUS", 0), ("", 0), (None, 0),
])
def test_codec_rank(codec, expected):
    # PB-10: case-insensitive + whitespace-tolerant + None-safe
    assert codec_rank(codec) == expected


@pytest.mark.parametrize("quality,expected", [
    ("hi", 3), ("HI", 3), ("  hi  ", 3),
    ("med", 2), ("MED", 2),
    ("low", 1), ("LOW", 1),
    ("premium", 0), ("", 0), (None, 0),
])
def test_quality_rank(quality, expected):
    # WR-01: case-insensitive + whitespace-tolerant + None-safe quality-tier rank
    assert quality_rank(quality) == expected


def test_quality_tier_beats_codec_rank():
    # WR-01: hi-MP3-320 must beat med-AAC-128 (user's explicit quality choice
    # outranks codec-efficiency tiebreak). Before the quality_rank primary key
    # was added, AAC=2 > MP3=1 flipped the order to med-AAC first.
    result = order_streams([
        _s("AAC", 128, 2, quality="med"),
        _s("MP3", 320, 1, quality="hi"),
    ])
    assert [(s.quality, s.codec, s.bitrate_kbps) for s in result] == [
        ("hi", "MP3", 320),
        ("med", "AAC", 128),
    ]


def test_quality_tier_full_order():
    # WR-01: full three-tier ordering — hi > med > low regardless of codec/bitrate.
    result = order_streams([
        _s("MP3", 64, 3, quality="low"),
        _s("AAC", 128, 2, quality="med"),
        _s("MP3", 320, 1, quality="hi"),
    ])
    assert [s.quality for s in result] == ["hi", "med", "low"]


def test_quality_tie_falls_through_to_codec():
    # WR-01: within the same quality tier, codec_rank tiebreak still applies.
    result = order_streams([
        _s("MP3", 128, 2, quality="hi"),
        _s("AAC", 128, 1, quality="hi"),
    ])
    assert [s.codec for s in result] == ["AAC", "MP3"]


def test_unknown_quality_falls_through_to_codec():
    # WR-01: custom/blank quality tiers rank 0 — legacy streams without
    # explicit hi/med/low labels still sort by codec+bitrate.
    result = order_streams([
        _s("MP3", 320, 1),          # quality="" -> rank 0
        _s("FLAC", 64, 2),           # quality="" -> rank 0, but FLAC outranks MP3
    ])
    assert [s.codec for s in result] == ["FLAC", "MP3"]


def test_same_codec_bitrate_sort():
    # PB-03: 320 > 128 > 64 for MP3
    result = order_streams([_s("MP3", 64, 1), _s("MP3", 320, 2), _s("MP3", 128, 3)])
    assert [s.bitrate_kbps for s in result] == [320, 128, 64]


def test_codec_rank_wins():
    # PB-04: FLAC > AAC > MP3 regardless of bitrate
    result = order_streams([_s("MP3", 320, 1), _s("FLAC", 64, 2), _s("AAC", 128, 3)])
    assert [s.codec for s in result] == ["FLAC", "AAC", "MP3"]


def test_position_tiebreak():
    # PB-05: same codec + same bitrate -> position asc wins
    result = order_streams([_s("MP3", 128, 3), _s("MP3", 128, 1), _s("MP3", 128, 2)])
    assert [s.position for s in result] == [1, 2, 3]


def test_aac_beats_mp3():
    # PB-06: AAC ranks above MP3 at the same bitrate (efficiency advantage)
    result = order_streams([_s("MP3", 128, 1), _s("AAC", 128, 2)])
    assert [s.codec for s in result] == ["AAC", "MP3"]


def test_all_unknown_position_order():
    # PB-07: all bitrate_kbps == 0 -> degenerate to position asc
    result = order_streams([_s("MP3", 0, 3), _s("AAC", 0, 1), _s("FLAC", 0, 2)])
    assert [s.position for s in result] == [1, 2, 3]


def test_mixed_known_unknown():
    # PB-08: knowns first (by codec/bitrate), unknowns last (by position)
    streams = [
        _s("MP3", 0, 1),      # unknown, pos 1
        _s("AAC", 128, 2),    # known, AAC/128
        _s("MP3", 0, 3),      # unknown, pos 3
        _s("FLAC", 64, 4),    # known, FLAC/64
    ]
    result = order_streams(streams)
    # FLAC/64 (rank 3) beats AAC/128 (rank 2); unknowns come last in position order
    assert [(s.codec, s.bitrate_kbps, s.position) for s in result] == [
        ("FLAC", 64, 4),
        ("AAC", 128, 2),
        ("MP3", 0, 1),
        ("MP3", 0, 3),
    ]


def test_empty_list():
    # PB-09
    assert order_streams([]) == []


def test_does_not_mutate_input():
    # PB-11: pure function — no mutation of input list
    streams = [_s("MP3", 64, 1), _s("FLAC", 320, 2), _s("AAC", 128, 3)]
    original_order = list(streams)  # shallow copy for comparison
    _ = order_streams(streams)
    assert streams == original_order  # list not reordered
    assert streams is not original_order  # sanity: different objects, same values


# Phase 60 / GBS-01f: regression — FLAC bitrate sentinel sorts FIRST among GBS quality tiers.
def test_gbs_flac_ordering():
    """RESEARCH §Open Question Q1: bitrate_kbps=1411 for FLAC interacts with
    Phase 47.1 D-09 partition logic so FLAC sorts above all MP3 tiers.

    With codec_rank(FLAC)=3 > codec_rank(MP3)=1, FLAC wins regardless of
    bitrate_kbps as long as bitrate_kbps > 0 (otherwise FLAC would be
    partitioned LAST as 'unknown bitrate').
    """
    from musicstreamer.gbs_api import _GBS_QUALITY_TIERS
    streams = []
    for i, t in enumerate(_GBS_QUALITY_TIERS, start=1):
        streams.append(StationStream(
            id=i, station_id=1, url=t["url"], label="",
            quality=t["quality"], position=t["position"],
            stream_type="shoutcast", codec=t["codec"],
            bitrate_kbps=t["bitrate_kbps"],
        ))
    ordered = order_streams(streams)
    # FLAC must be first
    assert ordered[0].codec == "FLAC", f"FLAC should sort first; got {ordered[0].codec}"
    assert ordered[0].bitrate_kbps == 1411
    # All FLAC tiers come before all MP3 tiers
    flac_indices = [i for i, s in enumerate(ordered) if s.codec == "FLAC"]
    mp3_indices = [i for i, s in enumerate(ordered) if s.codec == "MP3"]
    assert max(flac_indices) < min(mp3_indices)
    # Among MP3 tiers, highest bitrate wins
    mp3_streams = [s for s in ordered if s.codec == "MP3"]
    assert mp3_streams[0].bitrate_kbps == 320
