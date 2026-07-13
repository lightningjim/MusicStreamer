---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
plan: "01"
subsystem: test-scaffolding
tags: [wave-0, tdd, red-tests, sidebar-thumbnails, phase-94]
depends_on: []
provides:
  - "9 new test contracts (5 in test_art_paths.py, 4 in test_station_thumb_async.py) encoding D-01..D-06"
  - "Drift-guard for now_playing_panel._load_scaled_pixmap (GREEN immediately)"
affects:
  - tests/test_art_paths.py
  - tests/test_station_thumb_async.py
tech_stack:
  added: []
  patterns:
    - "Inline import pattern for RED tests (deferred import so collection-level fails don't break existing tests)"
    - "QTest.qWait(N) for daemon-thread Signal delivery in integration tests"
    - "inspect.getsource() for static drift-guard assertions"
key_files:
  created:
    - tests/test_station_thumb_async.py
  modified:
    - tests/test_art_paths.py
decisions:
  - "Used inline imports inside each new test function (not module-level) so the 5 RED tests in test_art_paths.py don't prevent the 9 existing tests from collecting/running. This diverges from the plan's module-level import suggestion but achieves the intended RED+GREEN split."
  - "test_thumb_landing_emits_datachanged: model.data() calls load_station_icon without on_thumb_needed (Plan-02 symbol absent), so no async work fires — test fails on assert len(emissions)==1. This is the correct RED posture."
  - "THUMB_FILENAME import also deferred to inline per the same reason."
metrics:
  duration: "~7 minutes"
  completed: "2026-06-16T00:17:10Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 94 Plan 01: Wave-0 Test Scaffolding Summary

**One-liner:** 9 RED/GREEN test contracts across 2 files locking D-01..D-06 thumb-generation decisions before any implementation.

## What Was Built

### Task 1 — Extended tests/test_art_paths.py (+5 tests)

5 new test functions appended after the existing 9 tests. All 5 use inline imports of Plan-02 symbols (`THUMB_FILENAME`, `_thumb_path_for`, `_is_thumb_fresh`, `_generate_thumb`) so existing tests continue to collect and pass unaffected.

| Test | Decision | RED Reason |
|------|----------|------------|
| `test_thumb_path_derivation` | D-05 | `ImportError: cannot import name 'THUMB_FILENAME'` |
| `test_thumb_is_96px` | D-04 | `ImportError: cannot import name '_generate_thumb'` |
| `test_generate_thumb_writes_png` | D-02 (disk) | `ImportError: cannot import name '_generate_thumb'` |
| `test_thumb_freshness_check` | D-06 | `ImportError: cannot import name '_is_thumb_fresh'` |
| `test_thumb_missing_returns_fallback` | D-02 (lazy) | `ImportError: cannot import name '_thumb_path_for'` |

### Task 2 — Created tests/test_station_thumb_async.py (+4 tests)

New file with 4 tests covering D-01 and D-03. Includes `_get_qapp()` helper, replicated fixtures (`_isolate_pixmap_cache`, `tmp_data_dir`, `_make_station`), and imports from project peers per the pattern map.

| Test | Decision | Status | Reason |
|------|----------|--------|--------|
| `test_now_playing_panel_does_not_use_thumb` | D-01 | GREEN | Static source assertion; no Plan-03 symbols needed |
| `test_thumb_landing_emits_datachanged` | D-03 (async repaint) | RED | `AssertionError: expected 1 dataChanged emission, got 0` (no on_thumb_needed wiring yet) |
| `test_in_flight_dedup` | D-03 (dedup) | RED | `AttributeError: 'StationTreeModel' has no attribute '_in_flight_thumbs'` |
| `test_index_for_station_id_roundtrip` | D-03 (coordination) | RED | `AttributeError: 'StationTreeModel' has no attribute 'index_for_station_id'` |

## Test Tally

```
tests/test_art_paths.py            9 existing PASS + 5 new RED = 14 total
tests/test_station_thumb_async.py  1 GREEN (drift-guard) + 3 RED = 4 total
tests/test_station_icon_integration.py  4 PASS (no change)
----------------------------------------------------------------------
Total new: 9  |  RED: 8  |  GREEN: 1  |  Existing regression: 0
```

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 — Extend test_art_paths.py | `1b057a5c` | tests/test_art_paths.py |
| 2 — Create test_station_thumb_async.py | `caf37a26` | tests/test_station_thumb_async.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deferred Plan-02 imports to test function bodies instead of module level**
- **Found during:** Task 1
- **Issue:** Module-level `from musicstreamer.ui_qt._art_paths import THUMB_FILENAME, _thumb_path_for, _is_thumb_fresh, _generate_thumb` caused a collection-time `ImportError` that prevented all tests in the file (including the 9 existing ones) from running.
- **Fix:** Moved each import to the first line of its respective test function body. Existing tests collect and pass; new tests ERROR at the import line inside the function body (RED). Both outcomes — existing tests passing AND new tests failing — are achieved.
- **Files modified:** tests/test_art_paths.py
- **Commit:** 1b057a5c

## Threat Flags

None — plan adds only test files under `pytest tmp_path`; no production paths touched; no new network endpoints or file system writes outside test fixtures.

## Self-Check: PASSED

- [x] tests/test_art_paths.py exists and has 5 new test functions (grep count = 5)
- [x] tests/test_station_thumb_async.py exists and has 4 test functions (grep count = 4)
- [x] Commits 1b057a5c and caf37a26 exist in git log
- [x] 8 RED / 1 GREEN / 14 existing tests unaffected (confirmed by pytest run)
