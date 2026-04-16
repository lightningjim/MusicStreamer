---
phase: 42-settings-export-import
plan: "01"
subsystem: backend
tags: [export, import, zip, sqlite, settings, sync]
dependency_graph:
  requires: []
  provides: [musicstreamer.settings_export]
  affects: []
tech_stack:
  added: []
  patterns: [zipfile-stdlib, with-repo-con-atomic-transaction, paths-root-override-testing]
key_files:
  created:
    - musicstreamer/settings_export.py
    - tests/test_settings_export.py
  modified: []
decisions:
  - "Used repo.con.execute() directly inside with repo.con: for atomicity — avoids Repo high-level methods that each call con.commit() and would break single-transaction guarantee"
  - "_sanitize uses NFKD decompose + ASCII encode — é→e (not dropped), slashes/colons stripped, truncated at 80 chars"
  - "logo_file in ZIP uses sanitized station name; import remaps to assets/{station_id}/station_art{ext} convention"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-16T16:58:28Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 42 Plan 01: Settings Export/Import Logic Summary

Pure-logic settings export/import module implementing ZIP creation with credential exclusion, ZIP validation with path traversal guard, and atomic merge/replace-all import with logo extraction.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing tests for settings export/import | 04aac66 | tests/test_settings_export.py |
| GREEN | settings_export.py implementation | c6b8061 | musicstreamer/settings_export.py, tests/test_settings_export.py |

## What Was Built

### `musicstreamer/settings_export.py`

Qt-free module with:

- **`ImportDetailRow`** dataclass — per-station action row (add/replace/skip/error)
- **`ImportPreview`** dataclass — aggregate result from preview_import passed to commit_import
- **`_EXCLUDED_SETTINGS`** — `{"audioaddict_listen_key"}` credential blocklist
- **`_sanitize(name)`** — NFKD Unicode normalize → ASCII → strip non-word chars → underscore spaces → truncate 80
- **`_station_to_dict(station)`** — serialize Station + streams to settings.json schema
- **`_fav_to_dict(fav)`** — serialize Favorite to dict
- **`build_zip(repo, dest_path)`** — full settings ZIP with settings.json + logos/; credentials excluded
- **`preview_import(zip_path, repo)`** — validate ZIP (BadZipFile, path traversal, missing settings.json, bad version), dry-run merge analysis
- **`commit_import(preview, repo, mode)`** — atomic DB write via `with repo.con:`; merge and replace_all modes; logo extraction to `assets/{station_id}/station_art{ext}`

### `tests/test_settings_export.py`

17 tests covering all SYNC requirements:
- Build ZIP structure and content completeness (SYNC-01)
- Credential exclusion (SYNC-02)
- Logo file round-trip
- Filename sanitization edge cases
- Preview merge counts, invalid ZIP, missing settings.json, path traversal, bad version (SYNC-03)
- Commit merge add, merge replace, replace_all, favorites union, settings restore, logo extraction (SYNC-03, SYNC-04)
- Cancel no-change (all-or-nothing, SYNC-04)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed logo filename mismatch in test helper**
- **Found during:** GREEN phase test run
- **Issue:** `_make_import_zip` hardcoded `"logos/Groove_Radio.jpg"` but `test_commit_logo_extraction` expected `"logos/Logo_Station.jpg"` — logo extraction check `logo_file in zip_names` returned False, silently skipping extraction
- **Fix:** Added `logo_filename` parameter to `_make_import_zip`; updated test to pass `logo_filename="logos/Logo_Station.jpg"`
- **Files modified:** tests/test_settings_export.py

**2. [Rule 1 - Bug] Fixed test assertion for Unicode sanitization**
- **Found during:** First GREEN test run
- **Issue:** Test expected `_sanitize("Café Radio") == "Caf_Radio"` but NFKD decomposition of é → `e` + combining accent → ASCII encode strips combining → `e` retained, giving `"Cafe_Radio"`
- **Fix:** Updated test assertion to match correct behavior `"Cafe_Radio"`
- **Files modified:** tests/test_settings_export.py

## Threat Model Compliance

All mitigations from plan threat model implemented:

| Threat | Mitigation |
|--------|-----------|
| T-42-01: Path traversal in ZIP | `'..' in fname` and `fname.startswith('/')` checks in `preview_import` |
| T-42-03: Credential disclosure | `_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` in `build_zip` |
| T-42-04: SQL injection | All DB writes use `repo.con.execute()` with parameterized queries |

T-42-02 (ZIP bomb) accepted per plan — no mitigation needed for personal-use scale.

## Known Stubs

None — all data is wired from the DB through to ZIP and back.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary changes introduced. The ZIP import path traversal guard is the only new trust boundary surface and is mitigated.

## Self-Check: PASSED

- musicstreamer/settings_export.py: FOUND
- tests/test_settings_export.py: FOUND
- .planning/phases/42-settings-export-import/42-01-SUMMARY.md: FOUND
- Commit 04aac66 (RED): FOUND
- Commit c6b8061 (GREEN): FOUND
- All 17 tests pass
