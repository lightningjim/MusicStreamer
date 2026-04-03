---
phase: 17-audioaddict-station-art
plan: "01"
subsystem: aa_import, repo, import_dialog
tags: [audioaddict, station-art, logo-fetch, import, threading]
dependency_graph:
  requires: []
  provides: [ART-01-backend, AA-logo-download]
  affects: [musicstreamer/aa_import.py, musicstreamer/repo.py, musicstreamer/ui/import_dialog.py]
tech_stack:
  added: [concurrent.futures.ThreadPoolExecutor, tempfile]
  patterns: [thread-local DB connections for parallel workers, two-phase import progress]
key_files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - musicstreamer/repo.py
    - musicstreamer/ui/import_dialog.py
    - tests/test_aa_import.py
    - tests/test_repo.py
decisions:
  - "on_logo_progress(0, total) emitted before downloads start so UI can transition label immediately"
  - "Thread-local Repo(db_connect()) in each logo worker — no shared connection across threads"
  - "Silent logo failure per D-03 — station imported regardless of logo download outcome"
metrics:
  duration_seconds: 318
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_modified: 5
---

# Phase 17 Plan 01: AudioAddict Logo Fetch Summary

**One-liner:** AA channel logos fetched from public API at import time via parallel ThreadPoolExecutor, stored via repo.update_station_art with silent failure and two-phase UI progress.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests + repo.update_station_art + aa_import backend | 0dd2f66 | musicstreamer/repo.py, musicstreamer/aa_import.py, tests/test_aa_import.py, tests/test_repo.py |
| 2 | Two-phase AA import progress in import_dialog.py | 8c87fb7 | musicstreamer/ui/import_dialog.py, musicstreamer/aa_import.py, tests/test_aa_import.py |

## What Was Built

**repo.py:** Added `update_station_art(station_id, art_path)` — updates `station_art_path` column, commits.

**aa_import.py:**
- `_normalize_aa_image_url(raw)` — strips URI template suffixes (`{?size,...}`), prepends `https:` to protocol-relative URLs
- `_fetch_image_map(slug)` — fetches `https://api.audioaddict.com/v1/{slug}/channels`, returns `{channel_key: image_url}`, empty dict on any failure
- `fetch_channels` — now calls `_fetch_image_map` per network, adds `image_url` key to each result dict
- `import_stations` — accepts `on_logo_progress` callback; after insert phase, downloads logos in parallel with `ThreadPoolExecutor(max_workers=8)`; each worker uses thread-local `Repo(db_connect())`; silent failure on any exception

**import_dialog.py:**
- `_update_aa_station_progress(imported, skipped, total)` — sets label to `"Importing stations… (N/total)"`
- `_update_aa_logo_phase()` — sets label to `"Fetching logos…"`
- `_on_aa_import_done` — sets label to `"Done — N imported, M skipped"` (em dash)
- `_aa_import_worker` passes both `on_progress` and `on_logo_progress` to `import_stations`

## Test Coverage

6 new tests added:
- `test_update_station_art` — round-trip via repo
- `test_normalize_aa_image_url` — strips template, adds https:
- `test_normalize_aa_image_url_already_https` — no-op on already-normalized URL
- `test_fetch_channels_includes_image_url` — mocks AA API, verifies image_url per channel
- `test_fetch_channels_image_url_none_on_failure` — API failure yields image_url=None, no exception
- `test_import_stations_calls_update_art` — logo download calls update_station_art
- `test_import_stations_logo_failure_silent` — network error, station imported, update_station_art not called

Full suite: 138 tests passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Added on_logo_progress(0, total) pre-download signal**
- **Found during:** Task 2 implementation
- **Issue:** import_stations only called on_logo_progress after each future completed (done >= 1), so the "Fetching logos..." label could never be set during download phase — it would only appear after the first logo completed
- **Fix:** Added `on_logo_progress(0, total)` call before ThreadPoolExecutor starts, so UI can transition label immediately when logo phase begins
- **Files modified:** musicstreamer/aa_import.py, tests/test_aa_import.py
- **Commit:** 8c87fb7

## Known Stubs

None.

## Self-Check: PASSED

- musicstreamer/repo.py contains `def update_station_art` — FOUND
- musicstreamer/aa_import.py contains `_normalize_aa_image_url` — FOUND
- musicstreamer/aa_import.py contains `_fetch_image_map` — FOUND
- musicstreamer/aa_import.py contains `ThreadPoolExecutor` — FOUND
- musicstreamer/ui/import_dialog.py contains `Fetching logos` — FOUND
- musicstreamer/ui/import_dialog.py contains `Importing stations` — FOUND
- Commits 0dd2f66, 8c87fb7 — FOUND
