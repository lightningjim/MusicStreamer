---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
plan: "01"
subsystem: test-infrastructure
tags: [soma-import, tdd-red, requirements, fixtures, drift-guard]
dependency_graph:
  requires: []
  provides:
    - SOMA-01..SOMA-17 requirement IDs in REQUIREMENTS.md
    - tests/test_soma_import.py (11 RED tests for soma_import module)
    - tests/test_main_window_soma.py (7 RED tests for MainWindow soma wiring)
    - tests/fixtures/soma_channels_3ch.json
    - tests/fixtures/soma_channels_with_dedup_hit.json
    - test_constants_drift.py soma drift guards (1 GREEN + 1 RED)
  affects:
    - .planning/REQUIREMENTS.md (SOMA-NN block + coverage bump)
    - tests/test_constants_drift.py (appended)
tech_stack:
  added: []
  patterns:
    - RED unit tests via monkeypatched urllib.request.urlopen (AA importer test pattern)
    - Source-grep gates with comment-stripping (feedback_gstreamer_mock_blind_spot.md)
    - Drift-guard tests reading source files via pathlib (test_constants_drift.py pattern)
    - JSON fixtures with top-level channels wrapper (per live SomaFM API probe 2026-05-13)
key_files:
  created:
    - tests/test_soma_import.py
    - tests/test_main_window_soma.py
    - tests/fixtures/soma_channels_3ch.json
    - tests/fixtures/soma_channels_with_dedup_hit.json
  modified:
    - .planning/REQUIREMENTS.md
    - tests/test_constants_drift.py
decisions:
  - "17 SOMA-NN IDs registered (one-to-one with RESEARCH 17-test validation matrix for maximum traceability)"
  - "soma_channels_3ch.json uses groovesalad/dronezone/bootliquor IDs to match live API probe data"
  - "test_per_channel_exception_skips_only_that_channel uses channels dict with streams=None (pre-fetch shape) rather than re-calling fetch_channels to avoid double-mocking complexity"
  - "test_soma_import_logger_registered remains RED as expected (Plan 03 will add setLevel line)"
metrics:
  duration: 8 minutes
  completed: "2026-05-14"
  tasks_completed: 5
  tasks_total: 5
  files_created: 4
  files_modified: 2
---

# Phase 74 Plan 01: SomaFM RED Contract (Wave 0 spec encoding) Summary

**One-liner:** 17 SOMA-NN requirements registered + 4 new test/fixture files encode the SomaFM bulk-importer spec as 19 RED tests pending Plans 02/03 plus 1 GREEN drift-guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register SOMA-01..SOMA-17 in REQUIREMENTS.md | 417a92b | .planning/REQUIREMENTS.md |
| 2 | Create canonical 3-channel + dedup-hit JSON fixtures | f2a05df | tests/fixtures/soma_channels_3ch.json, tests/fixtures/soma_channels_with_dedup_hit.json |
| 3 | Create tests/test_soma_import.py (RED — tests 1–9 + 14–15) | 03315ed | tests/test_soma_import.py |
| 4 | Create tests/test_main_window_soma.py (RED — tests 10–12 + 16) | 13ab226 | tests/test_main_window_soma.py |
| 5 | Extend tests/test_constants_drift.py with two drift-guards | f82cb70 | tests/test_constants_drift.py |

## Verification Results

1. `grep -c "^- \[ \] \*\*SOMA-" .planning/REQUIREMENTS.md` → **17** ✓
2. JSON fixtures parse and shape-check passes ✓
3. `pytest tests/test_soma_import.py --collect-only` → `ImportError: cannot import name 'soma_import' from 'musicstreamer'` (RED confirmed) ✓
4. `pytest tests/test_main_window_soma.py --collect-only` → `ImportError: cannot import name '_SomaImportWorker' from 'musicstreamer.ui_qt.main_window'` (RED confirmed) ✓
5. `pytest tests/test_constants_drift.py::test_soma_nn_requirements_registered` → **1 passed** ✓
6. `pytest tests/test_constants_drift.py::test_soma_import_logger_registered` → **1 failed** (expected RED for Plan 03) ✓

## RED/GREEN State Summary

| Test module | RED count | GREEN count | Blocked on |
|-------------|-----------|-------------|------------|
| tests/test_soma_import.py | 11 | 0 | musicstreamer.soma_import (Plan 02) |
| tests/test_main_window_soma.py | 7 | 0 | _SomaImportWorker in main_window.py (Plan 03) |
| tests/test_constants_drift.py (new) | 1 | 1 | __main__.py setLevel for soma_import (Plan 03) |
| **Total** | **19** | **1** | |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan creates test/fixture files only; no production code with stubs.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Files created are tests and planning artifacts only.

## Self-Check

- [x] .planning/REQUIREMENTS.md contains 17 SOMA-NN checklist rows
- [x] .planning/REQUIREMENTS.md contains 17 SOMA-NN traceability rows
- [x] Coverage block reads "55 total" and "35 pending"
- [x] STATION-ART-04 not present (0 hits)
- [x] tests/fixtures/soma_channels_3ch.json exists with 3 channels × 4 playlists
- [x] tests/fixtures/soma_channels_with_dedup_hit.json exists with 1 channel × 4 playlists
- [x] tests/test_soma_import.py has 11 def test_ functions
- [x] tests/test_main_window_soma.py has 7 def test_ functions
- [x] tests/test_constants_drift.py extended with 2 new functions (existing unchanged)
- [x] All 5 task commits exist in git log

## Self-Check: PASSED
