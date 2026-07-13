---
phase: 92-fix-pls-pls-url-fallback-for-codec-bitrate
plan: "01"
subsystem: playlist_parser
tags: [tdd, extractor, pls, m3u, xspf, somafm, codec, bitrate, url-fallback]
dependency_graph:
  requires: []
  provides:
    - "_extract_codec(title, url='') with URL fallback on title miss"
    - "_extract_bitrate(title, url='') with delimiter-bounded URL regex fallback"
    - "3 wired call sites: _parse_pls, _parse_m3u, _parse_xspf pass entry URL"
  affects:
    - "musicstreamer/playlist_parser.py"
    - "tests/test_playlist_parser.py"
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN: failing tests written before implementation"
    - "Backwards-compatible optional url param with title-wins priority"
    - "Delimiter-bounded regex (_URL_BITRATE_RE) to guard against false positives"
key_files:
  created: []
  modified:
    - musicstreamer/playlist_parser.py
    - tests/test_playlist_parser.py
decisions:
  - "_URL_BITRATE_RE uses [-/_] delimiters + 2-4 digit bound + optional trailing k to avoid /v2/path-2/ false positives"
  - "url param defaults to '' on both extractors — existing callers remain valid, call sites updated explicitly in Task 3"
  - "Task 2 extractor-only commit + Task 3 call-site commit sequence: TDD discipline maintained; GREEN achieved after Task 3 wiring"
metrics:
  duration: "3m"
  completed: "2026-06-18T21:10:13Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
---

# Phase 92 Plan 01: PLS URL-Fallback for Codec/Bitrate Summary

**One-liner:** URL-fallback codec/bitrate extraction via delimiter-bounded regex and _CODEC_TOKENS scan on entry URL when title carries no token (SomaFM groovesalad-256-mp3 -> MP3/256).

## What Was Built

Extended `_extract_codec` and `_extract_bitrate` in `musicstreamer/playlist_parser.py` to accept an optional `url` parameter. When the title field yields no codec or bitrate token, each extractor falls back to inspecting the entry's stream URL. Title-derived values always win (backwards-compatible). Three parsers (`_parse_pls`, `_parse_m3u`, `_parse_xspf`) now pass the entry URL to both extractors.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write 4 RED URL-fallback tests | 530b144c | tests/test_playlist_parser.py |
| 2 | Add URL fallback to extractors (GREEN) | e6741cdc | musicstreamer/playlist_parser.py |
| 3 | Wire entry URL through 3 call sites | f09eef35 | musicstreamer/playlist_parser.py |

## TDD Gate Compliance

- RED gate: commit `530b144c` — 4 named tests fail against title-only extractors
- GREEN gate: commits `e6741cdc` + `f09eef35` — extractors widened, call sites wired, 4 tests pass
- REFACTOR gate: not required (implementation was clean on first pass)

## Verification Results

```
.venv/bin/python -m pytest tests/test_playlist_parser.py
39 passed, 1 warning in 0.12s
```

All 35 pre-existing tests pass. All 4 new URL-fallback tests pass.

Acceptance criteria grep gates:
- `_extract_codec(title, url="")` and `_extract_bitrate(title, url="")` signatures: PASS
- `_URL_BITRATE_RE` constant with delimiter-bounded pattern: PASS
- `grep -c 'url.upper()'` (non-comment lines) returns 2: PASS
- `_CODEC_TOKENS` order (HE-AAC, AAC+, AAC, OGG, FLAC, OPUS, MP3, WMA): UNCHANGED
- `_extract_bitrate(title, url)` call sites count == 3: PASS
- `_extract_codec(title, url)` call sites count == 3: PASS
- No HTTP imports added: PASS
- AudioAddict "Ambient 320k AAC+" -> codec=AAC+, bitrate=320 (title wins): PASS

## Success Criteria

- [x] SC1: SomaFM groovesalad-256-mp3 blank-title entry -> codec="MP3", bitrate=256; title wins when present
- [x] SC2: All 3 parsers (_parse_pls, _parse_m3u, _parse_xspf) pass entry URL to both extractors
- [x] SC3: stream_ordering._CODEC_RANK ordering invariant preserved — extractors only changed, sorted(url_dict) / EXTINF pairing untouched
- [x] AudioAddict regression: AAC+ / 320 still derived from title, URL not consulted
- [x] FIX-PLS-01: satisfied

## Deviations from Plan

### Notes

**Task 2 GREEN test verification:** The plan's Task 2 acceptance criteria states "the 4 url-fallback tests now PASS" but also says "do NOT touch the call sites yet (Task 3)." These are contradictory because the tests go through `parse_playlist()` -> `_parse_pls()` -> `_extract_codec(title)` (no url arg until Task 3). Resolution: Task 2 committed the extractor signature + logic changes; Task 3 wired the call sites and achieved GREEN. This is the intended TDD flow — GREEN is reached at end of Task 3, not after Task 2 alone. Noted, not a bug.

None — plan executed exactly as designed. The Task 2/3 split is the correct sequence for TDD: extractor contract first, wiring second.

## Known Stubs

None — all data flows are wired end-to-end. Codec and bitrate are populated from the URL when the title lacks tokens.

## Threat Flags

No new threat surface identified. The `_URL_BITRATE_RE` is anchored and bounded (2-4 digits, no unbounded backtracking), applied only to short single-URL strings per T-92-01 disposition. T-92-02 (title wins over URL) enforced by the if-title-miss guard.

## Self-Check

See below.
