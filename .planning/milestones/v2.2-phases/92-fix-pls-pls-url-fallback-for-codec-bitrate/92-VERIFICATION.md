---
phase: 92-fix-pls-pls-url-fallback-for-codec-bitrate
verified: 2026-06-18T21:30:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 92: FIX-PLS — PLS URL-Fallback for Codec/Bitrate Verification Report

**Phase Goal:** When a PLS file's title field lacks codec/bitrate info, the resolver inspects the resolved stream URL pattern to populate the missing fields — closing the Phase 58 pending-todo carry-over.
**Verified:** 2026-06-18T21:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                       | Status     | Evidence                                                                                                                           |
|----|-------------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------------------------------------------------|
| 1  | FIX-PLS-01 / SC1: title miss -> URL codec scan returns URL-derived token (groovesalad-256-mp3 -> MP3)      | VERIFIED   | `_extract_codec` scans `url.upper()` via identical `_CODEC_TOKENS` loop on title miss; `test_pls_codec_extracted_from_url_when_title_blank` PASSES                        |
| 2  | FIX-PLS-01 / SC1: title miss -> URL bitrate regex returns URL-derived bitrate (groovesalad-256-mp3 -> 256) | VERIFIED   | `_URL_BITRATE_RE` applied on title miss; `test_pls_bitrate_extracted_from_url_when_title_blank` PASSES; regex spot-checks confirm 256                                     |
| 3  | FIX-PLS-01 / SC1 (backwards-compat): title codec/bitrate wins; URL never consulted                         | VERIFIED   | `_extract_bitrate`/`_extract_codec` return on first `if m:` branch before URL checked; `test_url_fallback_does_not_override_title_match` PASSES (title "128k AAC" wins)   |
| 4  | FIX-PLS-01 / SC2: `_parse_pls`, `_parse_m3u`, `_parse_xspf` all pass entry URL to both extractors         | VERIFIED   | grep finds exactly 3 `_extract_bitrate(title, ...)` and 3 `_extract_codec(title, ...)` call sites at lines 123-124, 158-159, 187-188                                     |
| 5  | FIX-PLS-01 / SC1 (false-positive guard): URL bitrate regex requires >=2 digits with delimiters             | VERIFIED   | `_URL_BITRATE_RE = re.compile(r"[-/_](\d{2,4})k?(?:[-/_]|$)", ...)` — single-digit `/v2/` and `/path-2/` produce no match; `test_url_bitrate_only_matches_with_delimiters` PASSES |
| 6  | FIX-PLS-01 / SC3: `stream_ordering._CODEC_RANK` ordering invariant preserved; extractors only changed      | VERIFIED   | `stream_ordering.py` `_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}` unchanged; `sorted(url_dict)` iteration untouched; no changes to `stream_ordering.py` in commits  |
| 7  | FIX-PLS-01 (AudioAddict regression): AAC+/AAC title fixtures still extract from title unchanged             | VERIFIED   | `_PLS_BASIC` "Ambient 320k AAC+" title wins (title branch returns before URL checked); 35 pre-existing tests including `test_parse_pls_single_entry` all PASS            |

**Score: 7/7 truths verified**

---

### Required Artifacts

| Artifact                              | Expected                                                                      | Status     | Details                                                                                                   |
|---------------------------------------|-------------------------------------------------------------------------------|------------|-----------------------------------------------------------------------------------------------------------|
| `musicstreamer/playlist_parser.py`    | `_extract_codec(title, url='')` and `_extract_bitrate(title, url='')` with URL fallback; `_URL_BITRATE_RE`; 3 call sites | VERIFIED   | Signatures confirmed at lines 219 and 238; `_URL_BITRATE_RE` at line 34; 3 call sites each at lines 123-124, 158-159, 187-188 |
| `tests/test_playlist_parser.py`       | 4 new URL-fallback tests + 35 pre-existing tests still green                  | VERIFIED   | All 4 named functions present at lines 468, 475, 482, 491; 39 tests pass (0 failures)                    |

---

### Key Link Verification

| From                                               | To                                | Via                                  | Status     | Details                                                                                      |
|----------------------------------------------------|-----------------------------------|--------------------------------------|------------|----------------------------------------------------------------------------------------------|
| `playlist_parser.py:_parse_pls` (line 123-124)     | `_extract_codec` / `_extract_bitrate` | `url_dict[idx]` as 2nd positional arg | VERIFIED   | `_extract_bitrate(title, url_dict[idx])` and `_extract_codec(title, url_dict[idx])`         |
| `playlist_parser.py:_parse_m3u` (line 158-159)     | `_extract_codec` / `_extract_bitrate` | URL `line` as 2nd positional arg      | VERIFIED   | `_extract_bitrate(title, line)` and `_extract_codec(title, line)`                           |
| `playlist_parser.py:_parse_xspf` (line 187-188)    | `_extract_codec` / `_extract_bitrate` | `url` variable as 2nd positional arg  | VERIFIED   | `_extract_bitrate(title, url)` and `_extract_codec(title, url)`                             |
| `playlist_parser.py:_extract_codec` (lines 251-255) | `_CODEC_TOKENS`                   | `url.upper()` scanned on title miss   | VERIFIED   | `url_upper = url.upper()` + loop over `_CODEC_TOKENS` in same priority order                |

---

### Data-Flow Trace (Level 4)

Not applicable — `playlist_parser.py` is a pure parser (no network I/O, no DB queries). Data flows from the body literal passed by the caller through parser -> extractor -> returned dict. The extractors operate on already-materialized strings (title, URL). No dynamic data source to trace.

---

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                           | Result                           | Status |
|-------------------------------------------------------|-----------------------------------------------------------------------------------|----------------------------------|--------|
| All 39 tests pass                                     | `.venv/bin/python -m pytest tests/test_playlist_parser.py -q`                    | 39 passed, 1 warning in 0.10s   | PASS   |
| SomaFM URL (groovesalad-256-mp3) -> bitrate 256       | `_URL_BITRATE_RE.search("https://ice2.somafm.com/groovesalad-256-mp3")` group(1) | 256                              | PASS   |
| `/v2/api/path-2/stream` -> no match (false-pos guard) | `_URL_BITRATE_RE.search("http://host/v2/api/path-2/stream")`                     | None                             | PASS   |
| `/stream-128k-aac` -> bitrate 128                     | `_URL_BITRATE_RE.search("http://host/stream-128k-aac")` group(1)                 | 128                              | PASS   |

---

### Probe Execution

No probes declared or conventional probe scripts found for this phase.

---

### Requirements Coverage

| Requirement | Source Plan | Description                                         | Status    | Evidence                                                        |
|-------------|-------------|-----------------------------------------------------|-----------|-----------------------------------------------------------------|
| FIX-PLS-01  | 92-01-PLAN  | URL fallback for codec/bitrate when title blank     | SATISFIED | All 3 SC verified; 39 tests pass; call sites wired in all 3 parsers |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None | — | — |

No TBD/FIXME/XXX markers, no stub returns, no empty handlers, no HTTP imports found in modified files.

---

### Human Verification Required

None. All success criteria are mechanically verifiable:

- SC1 (URL fallback behavior) is exercised by 4 automated unit tests that pass.
- SC2 (call-site wiring) is verified by source inspection and grep counts.
- SC3 (`_CODEC_RANK` ordering) is verified by source inspection of `stream_ordering.py` — no changes made to that file.

---

### Gaps Summary

No gaps. All 7 must-have truths are VERIFIED. The phase goal is achieved.

**TDD discipline confirmed:** Commit sequence `530b144c` (4 RED tests) -> `e6741cdc` (extractor widening) -> `f09eef35` (3 call sites wired, GREEN) matches the plan's task sequence exactly.

**Purity preserved:** `musicstreamer/playlist_parser.py` imports only `os`, `re`, `urllib.parse`, `xml.etree.ElementTree` — no network I/O added.

**Priority order invariant confirmed:** `_CODEC_TOKENS = ["HE-AAC", "AAC+", "AAC", "OGG", "FLAC", "OPUS", "MP3", "WMA"]` unchanged; URL scan uses the identical loop so HE-AAC still wins over AAC on URL paths too.

---

_Verified: 2026-06-18T21:30:00Z_
_Verifier: Claude (gsd-verifier)_
