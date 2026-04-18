"""Pure stream ordering for failover (Phase 47).

Sorts a station's streams by
(quality_rank desc, codec_rank desc, bitrate_kbps desc, position asc)
per D-04/D-05. Quality-tier rank is primary so hi-MP3-320 beats med-AAC-128 —
otherwise the codec-efficiency tiebreak would invert the user's explicit
quality choice (WR-01 from Phase 47 gap-closure review).
Unknown bitrates (bitrate_kbps <= 0) sort LAST per D-07.
Pure functions — no DB access, no mutation (D-09).
"""
from __future__ import annotations

from typing import List

from musicstreamer.models import StationStream

# D-05: FLAC=3 > AAC=2 > MP3=1 > other=0.
_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}

# WR-01: quality tier is the primary sort key so hi-MP3-320 beats med-AAC-128.
# hi=3, med=2, low=1, unknown/custom=0 (falls through to codec+bitrate ordering).
_QUALITY_RANK = {"hi": 3, "med": 2, "low": 1}


def codec_rank(codec: str) -> int:
    """Return the codec rank for failover ordering.

    Case-insensitive, whitespace-tolerant, None-safe.
    FLAC=3, AAC=2, MP3=1, anything else = 0.
    """
    return _CODEC_RANK.get((codec or "").strip().upper(), 0)


def quality_rank(quality: str) -> int:
    """Return the quality-tier rank for failover ordering.

    Case-insensitive, whitespace-tolerant, None-safe.
    hi=3, med=2, low=1, anything else (including "", None, custom tiers) = 0.
    """
    return _QUALITY_RANK.get((quality or "").strip().lower(), 0)


def order_streams(streams: List[StationStream]) -> List[StationStream]:
    """Return a NEW list of streams sorted for failover.

    Sort key: (quality_rank desc, codec_rank desc, bitrate_kbps desc, position asc).
    Unknown bitrates (bitrate_kbps <= 0) are partitioned LAST and sorted
    among themselves by position asc (D-07).

    PURE: does not mutate the input list (D-09, G-6, P-3).
    """
    known = [s for s in streams if (s.bitrate_kbps or 0) > 0]
    unknown = [s for s in streams if (s.bitrate_kbps or 0) <= 0]
    known_sorted = sorted(
        known,
        key=lambda s: (
            -quality_rank(s.quality),
            -codec_rank(s.codec),
            -(s.bitrate_kbps or 0),
            s.position,
        ),
    )
    unknown_sorted = sorted(unknown, key=lambda s: s.position)
    return known_sorted + unknown_sorted
