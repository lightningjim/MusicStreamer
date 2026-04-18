"""Tests for musicstreamer/stream_ordering.py — Phase 47 failover ordering."""
from __future__ import annotations

import pytest

from musicstreamer.models import StationStream
from musicstreamer.stream_ordering import codec_rank, order_streams


def _s(codec: str = "", bitrate_kbps: int = 0, position: int = 1, url: str = "u") -> StationStream:
    return StationStream(
        id=0, station_id=0, url=url, codec=codec,
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
