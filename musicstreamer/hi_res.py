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
  - Wave 1 (Plan 70-01) provides the implementation; Wave 0 ships this skeleton only.
"""
