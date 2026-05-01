---
phase: 58-pls-auto-resolve-in-station-editor
plan: "01"
subsystem: parser
tags: [parser, playlist, pls, m3u, xspf, python, pure-module]
dependency_graph:
  requires: []
  provides:
    - musicstreamer/playlist_parser.parse_playlist
    - musicstreamer/playlist_parser._parse_pls
    - musicstreamer/playlist_parser._parse_m3u
    - musicstreamer/playlist_parser._parse_xspf
    - musicstreamer/playlist_parser._extract_bitrate
    - musicstreamer/playlist_parser._extract_codec
  affects:
    - musicstreamer/aa_import._resolve_pls (Plan 02 will delegate to parse_playlist)
    - musicstreamer/ui_qt/edit_station_dialog (Plan 03 will consume parse_playlist via worker)
tech_stack:
  added: []
  patterns:
    - Pure module pattern (no Qt, no I/O — body passed by caller)
    - Format dispatch by URL extension first, Content-Type second (D-19)
    - Gap-06 file-order invariant via sorted(url_dict) numeric N sort
    - Monotonic bitrate regex + priority-ordered codec token scan (D-11)
key_files:
  created:
    - musicstreamer/playlist_parser.py
    - tests/test_playlist_parser.py
  modified: []
decisions:
  - "D-09: parse_playlist(body, content_type, url_hint) -> list[dict] with exactly 4 keys (url, title, bitrate_kbps, codec)"
  - "D-17: accepts both str and bytes for body; XSPF passes bytes to ET.fromstring; PLS/M3U decode bytes with errors=replace"
  - "D-19: format dispatch by URL extension first, Content-Type second, give up third — no body sniffing"
  - "D-11: _BITRATE_RE = r'(\\d+)\\s*k(?:b(?:ps)?)?\\b' case-insensitive; _CODEC_TOKENS priority-ordered list"
  - "D-15: codec='' (empty string) when no token matches — never 'unknown', never None"
  - "D-13: plain xml.etree.ElementTree.fromstring — no defusedxml import"
  - "Known acceptable gaps: HEAACv2 -> 'AAC' (substring match, same family); VORBIS -> '' (not in v1 list)"
metrics:
  duration: "2m 49s"
  completed: "2026-05-01"
  tasks_completed: 2
  files_created: 2
  lines_written: 662
---

# Phase 58 Plan 01: Playlist Parser Module Summary

Pure-Python playlist parser module with `parse_playlist(body, content_type, url_hint) -> list[dict]` dispatching to PLS/M3U/M3U8/XSPF sub-parsers, plus 35-test suite covering all D-09..D-19 behaviors and known codec edge cases.

## What Was Built

### musicstreamer/playlist_parser.py (234 lines)

Public contract per D-09:
```python
def parse_playlist(
    body: str | bytes,
    content_type: str = "",
    url_hint: str = "",
) -> list[dict]:
```

Each returned dict has exactly four keys:
- `url: str` — stream URL (FileN value, M3U URL line, or `<location>` text)
- `title: str` — display name (TitleN, #EXTINF after-comma text, or `<title>`)
- `bitrate_kbps: int` — extracted from title via D-11 regex; 0 if no match
- `codec: str` — recognized D-11 token (uppercase canonical) or "" if no match

### Format dispatch (D-19)

1. URL extension: `.pls` → `_parse_pls`, `.m3u`/`.m3u8` → `_parse_m3u`, `.xspf` → `_parse_xspf`
2. Content-Type substring: `scpls` → PLS, `mpegurl`/`apple.mpegurl` → M3U, `xspf` → XSPF
3. Give up → `[]` (no body sniffing)

### Bytes vs str decision (D-17)

- `parse_playlist` accepts both `str` and `bytes` for `body`
- PLS/M3U/M3U8: bytes decoded with `body.decode("utf-8", errors="replace")`
- XSPF: bytes passed directly to `ET.fromstring` so XML prologue encoding declaration is honored; if str provided, encoded as UTF-8 before passing to ET

This decision matters for Plans 02 and 03: both read raw bytes from urllib and can pass bytes directly without pre-decoding.

### Gap-06 file-order invariant

`_parse_pls` preserves the numeric sort from `aa_import._resolve_pls`:
```python
for idx in sorted(url_dict):  # numeric file-order (gap-06)
```
FileN entries appear in numeric N order regardless of body order.

### Known acceptable codec gaps (RESEARCH Findings 3, 4, 5)

| Input | Returns | Reason |
|-------|---------|--------|
| "HEAACv2 64k" | "AAC" | Substring match on "AAC"; same codec family for ordering |
| "VORBIS 128k" | "" | Not in v1 token list per D-11 |
| "M4A 256k" | "" | Not in v1 token list per D-11 |
| "ALAC 1000k" | "" | Not in v1 token list per D-11 |

These are intentional — D-11 specifies the locked token list and these are documented gaps.

### D-15: Blank codec is correct sentinel

`codec=""` (empty string) when no token matches. Never "unknown", never None. The existing `codec_rank` at `edit_station_dialog.py:621-624` uses `(codec or "").strip().upper()` for None-safety, so blank-codec rows still sort correctly via the failover queue.

### D-16: bitrate_kbps=0 is the "no bitrate" sentinel

Parser emits 0 when no bitrate found. `_add_stream_row` renders `bitrate_kbps=0` as empty string via `str(bitrate_kbps) if bitrate_kbps else ""`. No parser-side change required (Plan 03 consumes this convention as-is).

## Test Coverage (tests/test_playlist_parser.py — 428 lines)

35 test functions, all passing in 0.09s:

| Category | Tests | Key behaviors |
|----------|-------|---------------|
| PLS | 7 | Single entry, file-order (gap-06), missing title, case-variant keys, BOM, CRLF, bytes input |
| M3U/M3U8 | 6 | With/without #EXTINF, no-header, extended attrs, other directives, m3u8 extension |
| XSPF | 6 | Basic, no-location skip, missing title, malformed (returns []), bytes+str inputs |
| Format dispatch | 8 | Unknown format, extension precedence, content_type fallbacks, charset suffix, no body sniffing |
| Bitrate/codec | 8 | Priority order, HE-AAC, HEAACv2 known gap, VORBIS known gap, empty-string sentinel |

Grep guards:
- `grep -c 'def parse_playlist'` = 1
- `grep -c 'def _parse_pls'` = 1
- `grep -c 'def _parse_m3u'` = 1
- `grep -c 'def _parse_xspf'` = 1
- `grep -c 'sorted(url_dict)'` = 1 (gap-06 numeric file-order)
- `grep -c 'defusedxml'` in non-comment lines = 1 (docstring mention only — no import)

## Deviations from Plan

None — plan executed exactly as written. The parser pseudocode from RESEARCH.md §Q1 and PATTERNS.md was implemented verbatim, and all 35 test behaviors listed in the plan were covered.

## Threat Flags

None — no new security surface beyond what is documented in the plan's `<threat_model>` section. The module is pure with no I/O; all threat mitigations (T-58P-01 through T-58P-06) are as documented.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| musicstreamer/playlist_parser.py exists | FOUND |
| tests/test_playlist_parser.py exists | FOUND |
| 58-01-SUMMARY.md exists | FOUND |
| Commit 52b8a40 (Task 1) exists | FOUND |
| Commit 7457b8d (Task 2) exists | FOUND |
| pytest tests/test_playlist_parser.py | 35 passed in 0.09s |
