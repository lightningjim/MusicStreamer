---
created: 2026-05-10T19:00:00.000Z
title: PLS auto-resolve — fall back to URL parsing for codec/bitrate when title lacks them
area: import
files:
  - musicstreamer/playlist_parser.py:212 — _extract_bitrate (title-only)
  - musicstreamer/playlist_parser.py:223 — _extract_codec (title-only)
  - tests/test_playlist_parser.py — extend with URL-fallback fixtures
  - .planning/phases/58-pls-auto-resolve/58-CONTEXT.md (D-11, D-15) — current title-only design
---

## Problem

When importing a SomaFM PLS via EditStationDialog, the codec and bitrate columns come up blank even though the URL clearly encodes both:

```
File1=https://ice2.somafm.com/groovesalad-256-mp3
Title1=SomaFM: Groove Salad (#1): A nicely chilled plate of ambient/downtempo beats and grooves.
```

Phase 58's `_extract_codec` and `_extract_bitrate` only inspect the `TitleN` value, per D-11 / D-15. SomaFM titles are pure prose ("a nicely chilled plate...") and never mention `mp3`/`aac`/`256k` etc. — so both extractors return their empty sentinels (`""` and `0`).

AudioAddict imports work fine because AA titles include codec/bitrate tokens (`"DI.fm Trance | AAC 64k"`-style). SomaFM (and likely other ICY-providers that put descriptive prose in `TitleN`) hit the gap.

Surfaced 2026-05-10 by user import test against `https://somafm.com/groovesalad256.pls`.

## Solution

Extend `_extract_codec` and `_extract_bitrate` to fall back to URL parsing when the title yields no match. Backwards-compatible — title still wins when it has a token; URL only consulted on miss.

1. Update `_extract_codec(title, url="")` signature: scan `_CODEC_TOKENS` against `title` first; if no match and `url` provided, scan `url.upper()` against the same token list. Same priority order (HE-AAC before AAC+ before AAC).
2. Update `_extract_bitrate(title, url="")` signature: existing regex `(\d+)\s*k(?:b(?:ps)?)?\b` against title first; if no match and `url` provided, also try a URL-specific regex like `[-/](\d{2,4})(?:[-_/]|$)` (matches `/groovesalad-256-mp3` → 256, `-128k-` → 128). Be conservative — at least 2 digits and a delimiter on both sides — to avoid matching arbitrary numbers in path segments.
3. Update both callers in `_parse_pls`, `_parse_m3u`, `_parse_xspf` (lines 138-139, 173-174, 202-203) to pass the entry's URL as the fallback.
4. New test cases:
   - `test_pls_codec_extracted_from_url_when_title_blank` — SomaFM-style fixture
   - `test_pls_bitrate_extracted_from_url_when_title_blank` — `groovesalad-256-mp3` → 256
   - `test_url_fallback_does_not_override_title_match` — title with codec/bitrate still wins
   - `test_url_bitrate_only_matches_with_delimiters` — guard against arbitrary digit runs
5. No CONTEXT.md migration needed — D-11/D-15 design language can stay; this is an additive enhancement to the same extractors. A short note in 58-CONTEXT.md `<deferred>` could document the v2 behavior.

Severity: low. Feature works; the codec/bitrate columns are user-editable and SomaFM streams play correctly without them populated. Cosmetic + ergonomic only.

## Notes

- ICY HEAD-probe (option 3 from the diagnosis) is a separate, larger todo — adds network I/O per import. Keep this todo URL-only to stay pure.
- The existing `(\d+)\s*k\b` title regex is permissive ("Some 2k station" → 2 — RESEARCH Finding 1). The URL fallback should be more restrictive (require delimiters) to avoid false positives like `/v2/api/path-2/stream`.
- AudioAddict imports MAY now produce different results if the URL parsing extracts something the title didn't — verify with `tests/fixtures/aa_*.pls` before shipping.
- File-order invariant (gap-06) is preserved — this change touches extractors only, not the iteration order.
