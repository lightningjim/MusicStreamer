---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
plan: "03"
subsystem: ui-qt/main-window
tags: [soma-import, tdd-green, qthread, hamburger-menu, logging]
dependency_graph:
  requires: [74-01]
  provides:
    - _SomaImportWorker QThread in musicstreamer/ui_qt/main_window.py
    - act_soma_import hamburger menu action (bound method, QA-05)
    - _on_soma_import_clicked / _on_soma_import_done / _on_soma_import_error handlers
    - musicstreamer.soma_import logger registered at INFO in __main__.py
  affects:
    - tests/test_main_window_soma.py (7 RED → GREEN)
    - tests/test_constants_drift.py::test_soma_import_logger_registered (RED → GREEN)
    - tests/test_main_window_gbs.py (pre-existing failure fixed as deviation)
tech_stack:
  added: []
  patterns:
    - QThread subclass worker (mirrors _GbsImportWorker, no auth_expired branch — SomaFM is public)
    - QA-05 bound-method connect (no self-capturing lambda)
    - SYNC-05 worker retention on MainWindow attribute (prevents mid-run GC)
    - Per-logger INFO registration in __main__.py
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/__main__.py
    - tests/test_main_window_soma.py
    - tests/test_main_window_gbs.py
decisions:
  - "Tasks 1 and 2 merged into a single commit: PySide6 binds self._on_soma_import_clicked at MainWindow.__init__ connect time, so all three handler methods must exist before the first commit for the fixture to construct."
  - "FakePlayer deviation: added underrun_recovery_started + audio_caps_detected signals to both test_main_window_soma.py and test_main_window_gbs.py _FakePlayer classes — pre-existing gap from Phase 62/70 additions to main_window.py."
metrics:
  duration: 15 minutes
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 4
---

# Phase 74 Plan 03: SomaFM GUI Wiring (Wave 2 GREEN tier 2) Summary

**One-liner:** _SomaImportWorker QThread + 'Import SomaFM' hamburger menu action + three handler methods wired into MainWindow; soma_import logger registered at INFO; 7 RED tests turned GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | Add _SomaImportWorker class + menu action + three handler methods | 5e6e0fb | musicstreamer/ui_qt/main_window.py, tests/test_main_window_soma.py, tests/test_main_window_gbs.py |
| 3 | Register musicstreamer.soma_import logger at INFO in __main__.py | 3b74a09 | musicstreamer/__main__.py |

## Verification Results

1. `pytest tests/test_main_window_soma.py` → **7 passed** (all RED → GREEN) ✓
2. `pytest tests/test_constants_drift.py` → **8 passed** (test_soma_import_logger_registered GREEN) ✓
3. `pytest tests/test_main_window_gbs.py` → **8 passed** (no regression; pre-existing bug also fixed) ✓
4. `git diff musicstreamer/__main__.py` → exactly one line added ✓
5. `grep -c "auth_expired" musicstreamer/ui_qt/main_window.py` → 4 (GBS-only, no SomaFM auth_expired branch) ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tasks 1 and 2 merged: PySide6 connect() requires method at bind time**
- **Found during:** Task 1 verification
- **Issue:** `act_soma_import.triggered.connect(self._on_soma_import_clicked)` in `MainWindow.__init__` evaluates `self._on_soma_import_clicked` immediately (PySide6 does `getattr(self, '_on_soma_import_clicked')` at connect time). With Task 2's methods deferred, `MainWindow.__init__` would raise `AttributeError`, preventing the `main_window` fixture from constructing — making Task 1's tests uncollectable.
- **Fix:** Added all three handler methods (`_on_soma_import_clicked`, `_on_soma_import_done`, `_on_soma_import_error`) in the same commit as the worker class + menu action. Task 2 becomes a no-new-code verification step.
- **Files modified:** musicstreamer/ui_qt/main_window.py
- **Commit:** 5e6e0fb

**2. [Rule 2 - Missing Critical Functionality] _FakePlayer missing underrun_recovery_started + audio_caps_detected signals**
- **Found during:** Task 1 verification (first uv run --with pytest-qt run)
- **Issue:** `test_main_window_soma.py` and `test_main_window_gbs.py` both define `_FakePlayer` without the `underrun_recovery_started` (Phase 62 BUG-09) and `audio_caps_detected` (Phase 70 DS-01) signals. `MainWindow.__init__` connects both signals at construction time, causing `AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'`. This was a pre-existing issue (already failing in the base before this plan's changes).
- **Fix:** Added `underrun_recovery_started = Signal()` and `audio_caps_detected = Signal(object)` to `_FakePlayer` in both test files.
- **Files modified:** tests/test_main_window_soma.py, tests/test_main_window_gbs.py
- **Commit:** 5e6e0fb

## Known Stubs

None — all handler methods are fully implemented per D-06, D-07, D-14 specs. Worker's `run()` body calls `soma_import.fetch_channels()` and `soma_import.import_stations(channels, repo)` by name (soma_import module will be provided by Plan 74-02 in the parallel worktree; the post-merge test suite will validate the full call chain).

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. The new toast surfaces use `show_toast()` (plain text, no HTML/RichText). T-40-04 invariant unchanged (`setTextFormat(Qt.RichText)` count in musicstreamer/ unaffected). STRIDE mitigations T-74-05 (bare Exception → error.emit) and T-74-07 (SYNC-05 worker retention) are both implemented.

## Self-Check

- [x] musicstreamer/ui_qt/main_window.py exists and contains `class _SomaImportWorker(QThread):`
- [x] musicstreamer/ui_qt/main_window.py contains `act_soma_import = self._menu.addAction("Import SomaFM")`
- [x] musicstreamer/ui_qt/main_window.py contains `act_soma_import.triggered.connect(self._on_soma_import_clicked)` (bound method, no lambda)
- [x] musicstreamer/ui_qt/main_window.py contains `self._soma_import_worker` attribute initialized in `__init__`
- [x] musicstreamer/ui_qt/main_window.py contains all 3 handler methods
- [x] musicstreamer/__main__.py contains `logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)`
- [x] Commit 5e6e0fb exists in git log
- [x] Commit 3b74a09 exists in git log
- [x] All 7 test_main_window_soma.py tests GREEN
- [x] All 8 test_constants_drift.py tests GREEN
- [x] All 8 test_main_window_gbs.py tests GREEN

## Self-Check: PASSED
