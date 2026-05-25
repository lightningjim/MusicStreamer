---
phase: 70
plan: "01"
subsystem: hi-res-classifier
tags: [hi-res, classifier, pure-helper, tdd-green]
dependency_graph:
  requires: [70-00]
  provides: [musicstreamer.hi_res public API]
  affects: [stream_ordering, station_star_delegate, station_filter_proxy, now_playing_panel, edit_station_dialog]
tech_stack:
  added: []
  patterns: [closed-enum return, case/None-safe dict lookup, set-comprehension tier aggregation]
key_files:
  created: []
  modified:
    - musicstreamer/hi_res.py
decisions:
  - "Used RESEARCH.md Pattern 3 verbatim for all function bodies (no improvisation)"
  - "F64LE/F64BE → 32 per DS-02 ceiling (treat 64-bit float as 32-bit-equivalent)"
  - "S8/U8 → 0 (below 16-bit threshold; excluded from hi-res classification)"
  - "best_tier_for_station uses set comprehension; no short-circuit needed (correctness over micro-opt)"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-12"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 70 Plan 01: Hi-Res Classifier Helpers — Summary

Pure-Python classifier for hi-res audio tier detection: `classify_tier`, `bit_depth_from_format`, `best_tier_for_station`, and `TIER_LABEL_BADGE`/`TIER_LABEL_PROSE` constants in `musicstreamer/hi_res.py`.

## What Was Built

Filled in the Wave 0 docstring-only skeleton in `musicstreamer/hi_res.py` with a complete implementation sourced verbatim from RESEARCH.md Pattern 3. The module exposes five public symbols usable by all downstream consumers (player, UI panels, delegates, filter proxy) without circular-import risk.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement musicstreamer/hi_res.py pure helpers + TIER_LABEL constants | e313405 | musicstreamer/hi_res.py |

## Test Results

- **32 tests GREEN** (all `test_classify_tier_truth_table` parametrize cases, all `test_bit_depth_from_format` cases, `test_best_tier_for_station_returns_empty_for_no_streams`, `test_tier_label_badge_constants`, `test_tier_label_prose_constants`)
- **3 tests remain RED** as expected: `test_best_tier_for_station_returns_hires_when_any_stream_is_hires`, `test_best_tier_for_station_returns_lossless_when_no_hires`, `test_best_tier_for_station_returns_empty_for_lossy_only` — all fail because `_stream()` helper constructs `StationStream(sample_rate_hz=..., bit_depth=...)` which requires Plan 70-02's model changes.

## Verification Gates Passed

- `python -c "from musicstreamer.hi_res import classify_tier, bit_depth_from_format, best_tier_for_station, TIER_LABEL_BADGE, TIER_LABEL_PROSE; print('ok')"` — passes
- Module purity: `grep -c "import gi|import Gst|..." musicstreamer/hi_res.py` returns 0
- Non-blank non-comment lines: 104 (>= 30 minimum, >= 50 target)
- D-04 invariant: `classify_tier("MP3", 96000, 24) == ""`
- D-03 invariant: `classify_tier("FLAC", 0, 0) == "lossless"`

## Implementation Details

**`_FORMAT_BIT_DEPTH` dict (DS-02 mapping):**
- S8/U8 → 0 (below threshold, excluded from hi-res classification)
- S16*/U16* → 16
- S24*/U24*/S24_32*/U24_32* → 24
- S32*/U32* → 32
- F32*/F64* → 32 (DS-02 caps float formats at 32-bit-equivalent)

**`classify_tier` logic:**
- Codec normalized via `(codec or "").strip().upper()` (mirrors `codec_rank` idiom, stream_ordering.py:31)
- Lossy codecs (not in `{"FLAC", "ALAC"}`) → ""
- `int(sample_rate_hz or 0)` and `int(bit_depth or 0)` defensively coerce None/falsy
- `rate > 48_000 or depth > 16` → "hires"; else → "lossless" (D-03 fallback covers 0,0 case)

**`best_tier_for_station` logic:**
- Set comprehension over `station.streams or []` (None-safe)
- Precedence: "hires" > "lossless" > ""
- Reads `.codec`, `.sample_rate_hz`, `.bit_depth` from each stream (duck-typed; Plan 70-02 adds these fields to `StationStream`)

## Deviations from Plan

None — plan executed exactly as written. Implementation sourced verbatim from RESEARCH.md Pattern 3 as directed.

## Known Stubs

None. This plan is pure classification logic with no UI wiring or data sources.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Module is pure-Python computation only.

The threat mitigations called out in the plan's threat model are implemented:
- **T-70-01**: `classify_tier` returns closed-enum `{"", "lossless", "hires"}` only — no injection surface.
- **T-70-02**: `bit_depth_from_format` uses closed-allowlist dict with `default=0` — unknown input returns 0.
- **T-70-03**: Accepted (station objects are in-process).

## Self-Check: PASSED

- musicstreamer/hi_res.py: FOUND
- Task commit e313405: FOUND
- 32 tests GREEN, 3 tests intentionally RED (Plan 70-02 dependency)
