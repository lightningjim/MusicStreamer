"""Hi-Res audio classification helpers (Phase 70).

Pure functions — no GStreamer imports, no I/O, no Qt.
Mirrors stream_ordering.py shape (small enum-mapped helpers).

Public API:
  bit_depth_from_format(format_str: str) -> int
  classify_tier(codec: str, sample_rate_hz: int, bit_depth: int) -> str
  best_tier_for_station(station: Station) -> str

Constants:
  TIER_LABEL_BADGE: dict[str, str]   # uppercase badge labels
  TIER_LABEL_PROSE: dict[str, str]   # title-case prose labels

Load-bearing constraints (PATTERNS.md lines 53-70):
  - This module MUST remain pure: no GStreamer, no I/O, no Qt imports.
  - classify_tier returns ONLY "" | "lossless" | "hires" (closed enum, D-01).
  - Case-insensitive, whitespace-tolerant, None-safe (mirrors codec_rank idiom).
  - FLAC + unknown rate/depth (0, 0) defaults to "lossless" (D-03).
  - Lossy codecs (MP3, AAC, HE-AAC, OPUS, OGG, WMA) always return "" (D-04).
  - Wave 1 (Plan 70-01) provides the implementation; Wave 0 shipped the skeleton only.

Behavioral rules locked by CONTEXT D-01..D-05:
  - D-01: Two tiers only — "lossless" and "hires".
  - D-02: Lossless = FLAC/ALAC + rate ≤ 48000 AND depth ≤ 16.
           Hi-Res = FLAC/ALAC + (rate > 48000 OR depth > 16).
  - D-03: FLAC/ALAC + unknown rate/depth (0, 0) defaults to "lossless".
  - D-04: Lossy codecs → "" at any rate/depth.
  - D-05: Badge labels "LOSSLESS" / "HI-RES" (all-caps, mirrors Phase 68 LIVE badge).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Private constants
# ---------------------------------------------------------------------------

# DS-02 verbatim mapping (caps validated against GstAudioFormat enum,
# https://lazka.github.io/pgi-docs/GstAudio-1.0/enums.html):
#   - S8 / U8 → 0 (below 16-bit: not classified for hi-res purposes)
#   - S16LE/S16BE/U16LE/U16BE → 16
#   - S24LE/S24BE/U24LE/U24BE/S24_32LE/S24_32BE/U24_32LE/U24_32BE → 24
#   - S32LE/S32BE/U32LE/U32BE → 32
#   - F32LE/F32BE → 32 (treat IEEE 754 32-bit float as 32-bit-equivalent for hi-res)
#   - F64LE/F64BE → 32 (treat IEEE 754 64-bit float as 32-bit-equivalent; DS-02 ceiling)
#   - Anything else → 0 (unknown; dict.get default)
_FORMAT_BIT_DEPTH: dict[str, int] = {
    "S8": 0, "U8": 0,                                    # below 16-bit: not classified
    "S16LE": 16, "S16BE": 16, "U16LE": 16, "U16BE": 16,
    "S24LE": 24, "S24BE": 24, "U24LE": 24, "U24BE": 24,
    "S24_32LE": 24, "S24_32BE": 24, "U24_32LE": 24, "U24_32BE": 24,
    "S32LE": 32, "S32BE": 32, "U32LE": 32, "U32BE": 32,
    "F32LE": 32, "F32BE": 32,
    "F64LE": 32, "F64BE": 32,   # DS-02 caps 64-bit float at 32-bit-equivalent
}

# Hi-res criteria thresholds (D-02, mirrors moOde + JAS "Hi-Res Audio" spec).
_HIRES_RATE_THRESHOLD_HZ: int = 48_000
_HIRES_BIT_DEPTH_THRESHOLD: int = 16

# Lossless codec allow-list (D-02).
_LOSSLESS_CODECS: set[str] = {"FLAC", "ALAC"}

# ---------------------------------------------------------------------------
# Public constants — UI-SPEC Copywriting Contract (lines 182-198)
# ---------------------------------------------------------------------------

# Badge labels: all-caps, identical typography to Phase 68 LIVE badge (D-05).
# Callers MUST look up labels via these dicts; do NOT inline strings in branch
# logic so a future i18n pass has one swap point.
TIER_LABEL_BADGE: dict[str, str] = {
    "hires": "HI-RES",
    "lossless": "LOSSLESS",
    "": "",
}

# Prose labels: title-case for use in tooltips, settings UI, EditStationDialog.
TIER_LABEL_PROSE: dict[str, str] = {
    "hires": "Hi-Res",
    "lossless": "Lossless",
    "": "",
}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def bit_depth_from_format(format_str: str) -> int:
    """Return bit-depth for a GstAudioFormat string. Unknown → 0.

    Case-sensitive (GStreamer's format strings are canonical upper-case
    short-codes, not free-form text); None/empty → 0.

    Examples:
        bit_depth_from_format("S16LE") == 16
        bit_depth_from_format("S24_32LE") == 24
        bit_depth_from_format("F64LE") == 32  # DS-02 ceiling
        bit_depth_from_format(None) == 0
        bit_depth_from_format("GIBBERISH") == 0
    """
    return _FORMAT_BIT_DEPTH.get((format_str or ""), 0)


def classify_tier(codec: str, sample_rate_hz: int, bit_depth: int) -> str:
    """Return "hires" | "lossless" | "" per CONTEXT D-02 / D-03 / D-04.

    Lossy codecs always return "" (D-04).
    Lossless codec + (rate > 48 kHz OR depth > 16) → "hires" (D-02).
    Lossless codec + everything else → "lossless" (D-02 + D-03 fallback).

    Case-insensitive, whitespace-tolerant, None-safe (mirrors codec_rank idiom
    from stream_ordering.py:25-31).

    Examples:
        classify_tier("FLAC", 44100, 16) == "lossless"
        classify_tier("FLAC", 96000, 24) == "hires"
        classify_tier("FLAC", 0, 0) == "lossless"  # D-03 fallback
        classify_tier("MP3", 96000, 24) == ""       # D-04 lossy
        classify_tier(None, 0, 0) == ""             # None-safe
    """
    c = (codec or "").strip().upper()
    if c not in _LOSSLESS_CODECS:
        return ""
    rate = int(sample_rate_hz or 0)
    depth = int(bit_depth or 0)
    if rate > _HIRES_RATE_THRESHOLD_HZ or depth > _HIRES_BIT_DEPTH_THRESHOLD:
        return "hires"
    return "lossless"


def best_tier_for_station(station) -> str:
    """Return the best tier across a station's streams (D-02, DP-02).

    Hi-Res > Lossless > "" (no tier). Pure: reads station.streams attribute;
    no DB calls. Safe with empty or None streams list.

    Each stream item must expose .codec, .sample_rate_hz, .bit_depth.
    The StationStream dataclass gains these fields in Plan 70-02; until then
    any duck-typed object with those attributes is accepted.

    Examples:
        station with MP3 + FLAC-44/16 + FLAC-96/24 → "hires"
        station with MP3 + FLAC-44/16 → "lossless"
        station with only MP3 streams → ""
        station with no streams → ""
    """
    tiers = {
        classify_tier(s.codec, s.sample_rate_hz, s.bit_depth)
        for s in (station.streams or [])
    }
    if "hires" in tiers:
        return "hires"
    if "lossless" in tiers:
        return "lossless"
    return ""
