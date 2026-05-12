---
phase: 70
plan: 10
subsystem: settings-export
tags: [settings-export, zip-roundtrip, forward-compat, tdd-green, hres-01]
dependency_graph:
  requires: [70-02]
  provides: [sample_rate_hz-bit_depth-zip-roundtrip]
  affects: [settings_export.py]
tech_stack:
  added: []
  patterns: [Phase-47.3-forward-compat-int-or-0-idiom, parameterized-SQL]
key_files:
  modified:
    - musicstreamer/settings_export.py
decisions:
  - "Applied Phase 47.3 int(stream.get('KEY', 0) or 0) idiom verbatim for both new columns — neutralizes missing key, None, empty string, and malformed values in a single expression"
  - "Extended both _insert_station and _replace_station with identical SQL column + placeholder + value-tuple additions for symmetry"
metrics:
  duration: 5m
  completed: 2026-05-12
---

# Phase 70 Plan 10: settings_export ZIP Round-Trip for sample_rate_hz + bit_depth Summary

Wave 5 GREEN: `settings_export.py` ZIP round-trip now preserves `sample_rate_hz` and `bit_depth` per stream, with Phase 47.3 forward-compat idiom for pre-Phase-70 ZIPs.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Extend _station_to_dict, _insert_station, _replace_station with sample_rate_hz + bit_depth | e3b864c | musicstreamer/settings_export.py |

## What Was Built

Three targeted additions to `musicstreamer/settings_export.py`:

1. `_station_to_dict`: appended `"sample_rate_hz": s.sample_rate_hz` and `"bit_depth": s.bit_depth` keys to the per-stream dict comprehension after `bitrate_kbps`.

2. `_insert_station`: extended the INSERT SQL column list (`sample_rate_hz, bit_depth`), VALUES placeholder count (`?,?`), and value tuple with `int(stream.get("sample_rate_hz", 0) or 0)` and `int(stream.get("bit_depth", 0) or 0)`.

3. `_replace_station`: mirrored the identical three-part extension verbatim.

The forward-compat idiom `int(x or 0)` handles missing key, `None`, `""`, `False`, and any malformed non-numeric value — all coerce to 0 before the parameterized SQL bind. Pre-Phase-70 ZIPs without these keys import cleanly with both columns defaulting to 0 (cache rebuilds on next replay per DS-05).

## Test Results

| Test | Status |
|------|--------|
| test_export_import_roundtrip_preserves_sample_rate_hz_and_bit_depth | GREEN |
| test_commit_import_forward_compat_missing_quality_keys | GREEN |
| test_station_to_dict_emits_quality_keys | GREEN |
| All 23 pre-existing test_settings_export.py tests | GREEN (regression invariant) |
| **Total** | **26/26 passed** |

## Grep Gate Results

- `sample_rate_hz` non-comment occurrences in settings_export.py: **5** (gate >= 4: PASS)
- `bit_depth` non-comment occurrences in settings_export.py: **5** (gate >= 4: PASS)

## Deviations from Plan

None - plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The only changes are two additional keys in the to-dict serializer and two additional column bindings in existing parameterized SQL INSERT statements. T-70-28 (tampered ZIP payload) and T-70-29 (SQL injection) mitigations are in place: `int(x or 0)` coercion + static column-name literals + `?` placeholder binding.

## Self-Check

- [x] `musicstreamer/settings_export.py` exists and contains `sample_rate_hz`
- [x] Commit `e3b864c` exists in git log
- [x] 26/26 tests pass
