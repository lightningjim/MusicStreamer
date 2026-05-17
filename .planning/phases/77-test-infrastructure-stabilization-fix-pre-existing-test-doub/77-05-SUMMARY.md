---
phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub
plan: "05"
subsystem: test-infrastructure
tags: [test-infrastructure, qt-teardown, network-block, daemon-thread, phase-77]
dependency_graph:
  requires: ["77-02", "77-03", "77-04"]
  provides: ["block_real_network fixture", "cluster-3 cross-file teardown fix", "worker.wait drain"]
  affects: ["tests/conftest.py", "tests/test_main_window_underrun.py", "tests/test_main_window_integration.py", "tests/test_now_playing_panel.py", "tests/test_phase72_now_playing_panel.py", "tests/test_phase72_assumptions.py", "tests/test_import_dialog_qt.py"]
tech_stack:
  added: []
  patterns: ["file-autouse fixture opt-in", "worker.wait QThread drain", "monkeypatch.setattr stdlib network stubs"]
key_files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_main_window_underrun.py
    - tests/test_main_window_integration.py
    - tests/test_now_playing_panel.py
    - tests/test_phase72_now_playing_panel.py
    - tests/test_phase72_assumptions.py
    - tests/test_import_dialog_qt.py
decisions:
  - "D-12 REVISED: block_real_network stubs both urllib.request.urlretrieve AND urllib.request.urlopen at module level"
  - "D-14: test-side worker.wait(2000) drain after qtbot.waitSignal to prevent QThread teardown race"
  - "D-13 scope-deferred: cover_art.py production refactor not done — network-block closure is sufficient for Phase 77 scope"
  - "Rule 1 auto-fix: extend scan_playlist lambda to accept node_runtime=None kwarg matching production _YtScanWorker.run() signature"
  - "File-autouse per-file opt-in (not session-wide) per RESEARCH §Open Question Q2 recommendation"
metrics:
  duration: "229s"
  completed: "2026-05-17T17:34:16Z"
  tasks_completed: 3
  files_modified: 7
  fixture_injections: 5
  worker_wait_additions: 1
---

# Phase 77 Plan 05: block_real_network fixture + worker.wait teardown Summary

**One-liner:** Per-test `block_real_network` fixture stubs both `urllib.request.urlretrieve` and `urllib.request.urlopen`, closing the 4 cluster-3 cross-file Qt-teardown-abort reproducers via file-autouse opt-in plus a `worker.wait(2000)` drain for `test_yt_scan_passes_through`.

## What Was Built

### Task 1: block_real_network fixture (tests/conftest.py)

Added sibling fixture to `unique_mpris_service_name` (Plan 77-03). The fixture:
- Stubs `urllib.request.urlretrieve` with a file-writer that writes empty bytes to `filename` (if provided) and returns `(filename or "/tmp/stub", {})` — matches the urlretrieve return shape so `_LogoFetchWorker` result-unpacking doesn't crash
- Stubs `urllib.request.urlopen` with `MagicMock(side_effect=OSError("blocked in test"))` — forces `cover_art._itunes_attempt`'s daemon thread's except clause to invoke `on_done(None)` instead of a real network round-trip
- Bare `@pytest.fixture` (NOT autouse) — opt-in via parameter injection or per-file autouse wrapper
- Zero new dependencies (stdlib + existing `MagicMock` already imported)

**Coverage:** Closes the network-call leak at all four production sites:
- `edit_station_dialog.py:94,125` (urlretrieve — logo-fetch worker)
- `cover_art.py:111,119` (urlopen — iTunes daemon thread)
- `cover_art_mb.py:290,312` (urlopen — MusicBrainz daemon thread)

### Task 2: Apply block_real_network to cluster-3 reproducers

**Pattern A — per-test injection:**
- `tests/test_main_window_underrun.py::test_first_call_shows_toast` — added `block_real_network` to parameter list

**Pattern B — file-autouse wrapper (4 files):**
Each file received a `_block_real_network_for_this_file(block_real_network)` fixture with `@pytest.fixture(autouse=True)`. The indirection (wrapper depends on `block_real_network`) keeps the actual monkeypatching in conftest.py while enabling per-file opt-in without global session-level autouse.
- `tests/test_main_window_integration.py`
- `tests/test_now_playing_panel.py`
- `tests/test_phase72_now_playing_panel.py` (also added `import pytest` — missing)
- `tests/test_phase72_assumptions.py`

**Pre-fix baseline crash signature (Pair A):**
```
Extension modules: shiboken6.Shiboken, PySide6.QtCore, PySide6.QtGui, ...
[abort signal — daemon thread races QObject GC during cross-file ordering]
```
The abort produced a full pytest process crash (exit code 134 / SIGABRT), not a normal test failure, consistent with `QObjectPrivate::deleteChildren` stack trace documented in CONTEXT cluster 3.

**Post-fix:** Both cross-file pairs run to completion with only the pre-existing `test_hamburger_menu_actions` failure (a different cluster).

### Task 3: worker.wait(2000) drain for test_yt_scan_passes_through (D-14)

Added `worker.wait(2000)` with Phase 77 D-14 comment immediately after `with qtbot.waitSignal(worker.finished, timeout=3000):` block in `tests/test_import_dialog_qt.py::test_yt_scan_passes_through`. Mirrors the `_shutdown_logo_fetch_worker` pattern at `edit_station_dialog.py:1342`.

## Verification Results

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_main_window_underrun.py::test_first_call_shows_toast -x` | 1 passed |
| `uv run pytest tests/test_main_window_integration.py tests/test_now_playing_panel.py` | 205 passed, 1 pre-existing fail (hamburger menu) |
| `uv run pytest tests/test_phase72_now_playing_panel.py tests/test_phase72_assumptions.py` | 10 passed |
| `uv run pytest tests/test_import_dialog_qt.py` | 23 passed |
| `git diff musicstreamer/` | empty — zero production code change |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] scan_playlist monkeypatch lambda missing node_runtime kwarg**
- **Found during:** Task 3 verification
- **Issue:** `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` monkeypatches `scan_playlist` with `lambda url, toast_callback=None: scan_results`. The production `_YtScanWorker.run()` calls `yt_import.scan_playlist(self._url, toast_callback=self._toast, node_runtime=self._node_runtime)`. The lambda rejected the `node_runtime` kwarg with `TypeError`, causing the worker's except clause to fire `self.error.emit(str(exc))` instead of `self.finished.emit(results)`. `qtbot.waitSignal(worker.finished)` then timed out — the test was pre-existing broken even before Task 3's `worker.wait(2000)` addition.
- **Fix:** Extended lambda to `lambda url, toast_callback=None, node_runtime=None: scan_results` to match the production call signature.
- **Files modified:** `tests/test_import_dialog_qt.py`
- **Commit:** f8ff1e4 (included in Task 3 commit)

## Known Stubs

None — this plan adds test fixtures only; no production UI changes.

## Threat Surface Scan

No new production network endpoints, auth paths, or schema changes introduced. The `block_real_network` fixture patches are test-process-only at the `urllib.request` module level and have no effect outside the test process.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 9b616c1 | feat(77-05): add block_real_network fixture to tests/conftest.py |
| Task 2 | e3a1fb8 | fix(77-05): apply block_real_network to cluster-3 cross-file teardown-crash reproducers |
| Task 3 | f8ff1e4 | fix(77-05): add worker.wait(2000) drain to test_yt_scan_passes_through (D-14) |

## Self-Check: PASSED

- [x] tests/conftest.py contains `def block_real_network(monkeypatch):` with bare `@pytest.fixture`
- [x] Fixture stubs both `urllib.request.urlretrieve` and `urllib.request.urlopen`
- [x] 5 total fixture injections: 1 per-test (test_first_call_shows_toast) + 4 file-autouse wrappers
- [x] 1 worker.wait(2000) addition in test_yt_scan_passes_through
- [x] `git diff musicstreamer/` returns empty — zero production code change
- [x] Commits 9b616c1, e3a1fb8, f8ff1e4 exist in git log
- [x] D-13 scope-deferred: cover_art.py production refactor not performed (per CONTEXT.md `<discretion>` clause)
