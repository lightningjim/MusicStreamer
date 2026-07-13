---
phase: 90-somafm-preroll-instrumentation
plan: "03"
subsystem: main-window-hamburger
tags: [somafm, preroll, hamburger-menu, qthread, diagnostics, ui]
dependency_graph:
  requires: [90-01 (paths.preroll_events_log_path)]
  provides: [_PrerollRefetchWorker, Open preroll log action, Re-fetch SomaFM prerolls action]
  affects: [musicstreamer/ui_qt/main_window.py, tests/test_main_window_soma.py]
tech_stack:
  added: []
  patterns: [Pattern 4 thread-local Repo, SYNC-05 worker retention, QUrl.fromLocalFile, os.path.isfile guard, silent-failure toast]
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_soma.py
decisions:
  - "QDesktopServices test patched at PySide6.QtGui level (not module-level attribute) because handler uses local import — monkeypatch.setattr('PySide6.QtGui.QDesktopServices', mock)"
  - "Test comment for deviated test strategy documented as Rule 1 (test was structurally correct but wrong patch path)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-18"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
requirements_satisfied: [SOMA-PRE-02, SOMA-PRE-06]
---

# Phase 90 Plan 03: Hamburger Menu Preroll Actions Summary

**One-liner:** "Open preroll log" (QDesktopServices + os.path.isfile guard) and "Re-fetch SomaFM prerolls" (Pattern-4 _PrerollRefetchWorker QThread with SYNC-05 double-click guard) wired to hamburger menu, covering SOMA-PRE-02 and D-07.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Add failing tests for open_preroll_log + refetch | 3d97a66f | tests/test_main_window_soma.py |
| 1+2 GREEN | Open preroll log + _PrerollRefetchWorker + Re-fetch action | a4bfed15 | musicstreamer/ui_qt/main_window.py, tests/test_main_window_soma.py |

## What Was Built

### `musicstreamer/ui_qt/main_window.py` (extended)

**`_PrerollRefetchWorker(QThread)` (new class, ~50 lines):**
- Signals: `refetch_done = Signal(int)` (count of stations updated), `error = Signal(str)`
- Pattern 4 discipline: `con = db_connect()` inside `run()`, `Repo(con)` wrapping, `con.close()` in `finally`
- Iterates `repo.list_stations()` filtering `provider_name == "SomaFM"`
- Pitfall 4 skip: `list(repo.list_prerolls(station.id))` non-empty → skip
- Builds title→preroll_urls map from `fetch_channels()` result
- Inserts up to 50 URLs via `repo.insert_preroll(station_id, url, pos)` — catches `ValueError` per URL (T-83-01 scheme gate + T-83-02 position cap preserved)
- Calls `repo.set_prerolls_fetched_at(station_id, int(time.time()))` after each station
- D-04 silent-failure: `except Exception → self.error.emit(str(exc))`

**`_soma_refetch_worker: QThread | None = None` (new field):**
- SYNC-05 retention alongside `_soma_import_worker`; prevents GC of running QThread

**"Re-fetch SomaFM prerolls" action:**
- Added immediately after "Import SomaFM" in Group 1 of hamburger menu
- Wired to `_on_preroll_refetch_clicked` (QA-05 bound method)

**`_on_preroll_refetch_clicked`, `_on_preroll_refetch_done`, `_on_preroll_refetch_error` (new handlers):**
- Click handler: `_soma_refetch_worker is not None` double-click guard (T-90-08 / SYNC-05)
- Done toast: "Prerolls refreshed for N station(s)" or "Re-fetch: no new prerolls found"
- Error toast: truncated at 80 chars (D-04 silent-failure lineage)

**"Open preroll log" action:**
- Added in a new diagnostics separator-group after Group 3 (Export/Import Settings)
- Wired to `_on_open_preroll_log_clicked` (QA-05 bound method)

**`_on_open_preroll_log_clicked` (new handler):**
- Resolves `paths.preroll_events_log_path()` (from Plan 90-01)
- `not os.path.isfile(log_path)` → toast "No preroll log yet — play a SomaFM station first"; return (Pitfall 5 guard)
- `QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))` — `QUrl.fromLocalFile` (not bare `QUrl(path)`) for correct `file://` construction on all platforms

### `tests/test_main_window_soma.py` (extended, 4 new tests)

- `test_open_preroll_log_action_exists`: SOMA-PRE-02 action label in hamburger menu, enabled
- `test_open_preroll_log_absent_shows_toast`: Pitfall 5 guard — monkeypatches `paths.preroll_events_log_path` to non-existent file; asserts toast fires, `QDesktopServices.openUrl` not called (patched at `PySide6.QtGui.QDesktopServices` level for local-import compatibility)
- `test_refetch_prerolls_action_exists`: D-07 action label in hamburger menu, enabled
- `test_refetch_worker_skips_stations_with_prerolls`: D-07/Pitfall 4 — stub `fetch_channels` + `FakeRepo` with one station having prerolls; verifies only the zero-preroll station gets `insert_preroll`, non-SomaFM station skipped, `refetch_done` emitted

## Verification Results

```
12 passed, 11 warnings in 0.55s
```
All 12 tests pass (8 existing SomaFM suite + 4 new).

## Acceptance Criteria

- [x] `grep -q "Open preroll log" main_window.py` PASS
- [x] `grep -q "QUrl.fromLocalFile" main_window.py` PASS (cross-platform file:// idiom)
- [x] `grep -c "Open buffer" main_window.py` returns 0 (no buffer-log entry added)
- [x] `grep -q "class _PrerollRefetchWorker" main_window.py` PASS
- [x] `grep -q "Re-fetch SomaFM prerolls" main_window.py` PASS
- [x] Pattern 4: `db_connect()` inside `run()`, `con.close()` in `finally` PASS
- [x] Scheme gate: `insert_preroll` used (not raw SQL); `ValueError` caught per URL PASS
- [x] Double-click guard: `_soma_refetch_worker is not None` check PASS
- [x] `test_main_window_soma.py -q` exits 0 (12/12) PASS

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] QDesktopServices mock patch path corrected in test**
- **Found during:** Task 1 GREEN phase, first test run
- **Issue:** `patch("musicstreamer.ui_qt.main_window.QDesktopServices")` fails with `AttributeError` because `QDesktopServices` is imported locally inside `_on_open_preroll_log_clicked` (not at module level), so it never appears as a module-level attribute.
- **Fix:** Changed test to `monkeypatch.setattr("PySide6.QtGui.QDesktopServices", mock_ds, raising=False)` — patches the class at the PySide6 import source, so the local `from PySide6.QtGui import QDesktopServices` inside the handler picks up the mock.
- **Files modified:** `tests/test_main_window_soma.py`
- **Commit:** a4bfed15

**2. [Rule 2 - Clarity] Comment removed "Open buffer" reference**
- **Found during:** Task 1 acceptance check
- **Issue:** A comment explaining "net-new UI" referenced `"Open buffer-events log"` by name, causing `grep -c "Open buffer" main_window.py` to return 1 (acceptance criterion requires 0).
- **Fix:** Rephrased comment to "no existing log-viewer action to mirror" without naming the deferred buffer-log entry.
- **Files modified:** `musicstreamer/ui_qt/main_window.py`
- **Commit:** a4bfed15

## Known Stubs

None — both actions are fully wired. `_on_open_preroll_log_clicked` calls `QDesktopServices.openUrl` with the real path. `_PrerollRefetchWorker.run()` calls the real `soma_import.fetch_channels()` and real `repo.insert_preroll`.

## Threat Surface Scan

All threats covered by the plan's threat model:
- T-90-06 (upstream preroll URL tampering): `insert_preroll` scheme gate preserved (`ValueError` caught per URL in worker)
- T-90-07 (SQLite write from QThread): Pattern 4 thread-local Repo (`db_connect()` inside `run()`, `con.close()` in `finally`)
- T-90-08 (concurrent re-fetch workers): SYNC-05 double-click guard (`_soma_refetch_worker is not None`)
- T-90-09 (path disclosure via OS open): `os.path.isfile` guard + `QUrl.fromLocalFile` + fixed path (not user input)

No new threat surface introduced beyond the plan's threat model.

## TDD Gate Compliance

- RED gate commit: `3d97a66f` — `test(90-03): add RED tests for Open preroll log + Re-fetch SomaFM prerolls actions`
- GREEN gate commit: `a4bfed15` — `feat(90-03): add Open preroll log + Re-fetch SomaFM prerolls hamburger actions`

Both TDD gate commits present and in correct order. No REFACTOR commit needed — implementation was clean on first pass.

## Self-Check: PASSED

- [x] `musicstreamer/ui_qt/main_window.py` — `_PrerollRefetchWorker`, "Open preroll log", "Re-fetch SomaFM prerolls" all present
- [x] `tests/test_main_window_soma.py` — 4 new tests, all GREEN (12/12 total)
- [x] Commit `3d97a66f` — exists (Task 1+2 RED)
- [x] Commit `a4bfed15` — exists (Task 1+2 GREEN)
- [x] No "Open buffer-events log" menu entry
- [x] Pattern 4 discipline: `db_connect()` inside `run()`, `con.close()` in `finally`
- [x] Scheme gate: `insert_preroll` used exclusively in worker (no raw SQL)
- [x] Double-click guard: `_soma_refetch_worker is not None` check present
