---
phase: 39-core-dialogs
plan: "02"
subsystem: ui_qt
tags: [discovery, radio-browser, qt-dialog, pyside6, tdd]
dependency_graph:
  requires:
    - musicstreamer/radio_browser.py
    - musicstreamer/repo.py
    - musicstreamer/models.py
  provides:
    - musicstreamer/ui_qt/discovery_dialog.py
  affects:
    - tests/test_discovery_dialog.py
tech_stack:
  added: []
  patterns:
    - QThread worker pattern for non-blocking API calls
    - QStandardItemModel + QTableView for results display
    - setIndexWidget for per-row QPushButton actions
    - showEvent lazy-start for filter worker threads
key_files:
  created:
    - musicstreamer/ui_qt/discovery_dialog.py
    - tests/test_discovery_dialog.py
  modified: []
decisions:
  - "Move filter worker start to showEvent (not __init__) to prevent segfault when dialog is constructed but not shown in tests"
  - "Extend QStandardItemModel to 6 columns (Name/Tags/Country/Bitrate/Play/Save) — setIndexWidget embeds QPushButton per row in Play and Save columns"
  - "url_resolved preferred over url in both save and preview paths (D-12, existing key decision)"
metrics:
  duration: "~8 min"
  completed: "2026-04-13T13:22:31Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 39 Plan 02: DiscoveryDialog Summary

**One-liner:** Non-modal DiscoveryDialog for Radio-Browser.info search, preview, and save — QThread workers for filter population and search, per-row Play/Save buttons via setIndexWidget, url_resolved preference enforced.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Test scaffolds for DiscoveryDialog (RED) | ee0dbb0 | tests/test_discovery_dialog.py |
| 2 | Implement DiscoveryDialog (GREEN) | fe5efa1 | musicstreamer/ui_qt/discovery_dialog.py |

## What Was Built

`musicstreamer/ui_qt/discovery_dialog.py` — `DiscoveryDialog(QDialog)`:

- **Search bar row:** `QLineEdit` (Return key triggers search) + tag/country `QComboBox` filters + "Search Stations" `QPushButton`.
- **Filter population:** `_TagWorker` and `_CountryWorker` (`QThread`) started lazily in `showEvent` on first show. Each emits `finished(list)` → combo population slots. Errors silently suppressed (non-critical).
- **Results table:** `QTableView` with `QStandardItemModel` — 6 columns: Name (stretch), Tags (160px), Country (80px), Bitrate (80px), Play (60px), Save (60px). `setIndexWidget` embeds `QPushButton` per row in the Play and Save columns. `setAlternatingRowColors(True)`, single-row `SelectRows`.
- **Search flow (D-13):** `_SearchWorker(QThread)` calls `radio_browser.search_stations(limit=50)`. During search: button disabled, progress bar shown with `setRange(0, 0)` (indeterminate). After results: progress hidden, button re-enabled.
- **Save flow (D-12):** `_on_save_row` calls `repo.insert_station` with `url_resolved` preference (`result.get("url_resolved") or result.get("url", "")`). Toast via `toast_callback`. Save button disabled after first use.
- **Preview play flow (D-11):** `_on_play_row` builds temp `Station(id=-1)` + `StationStream(id=-1)` from result data and calls `player.play(temp_station)`. Toggling same row calls `player.stop()`. Button text toggles Play/Stop.
- **Close behavior:** `closeEvent` and `reject` stop active preview before closing.
- **`station_saved = Signal()`** emitted after each successful save for list refresh.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] QThread has no setDaemon() method**
- **Found during:** Task 2 implementation
- **Issue:** `QThread` is not a Python `threading.Thread` — it has no `setDaemon()`. Called in filter load start code.
- **Fix:** Removed `setDaemon(True)` calls. QThreads don't prevent app exit by default.
- **Files modified:** musicstreamer/ui_qt/discovery_dialog.py
- **Commit:** fe5efa1

**2. [Rule 1 - Bug] Worker threads started in `__init__` caused segfault in tests**
- **Found during:** Task 2 test run (GREEN phase)
- **Issue:** Filter workers started immediately in `__init__`, completed fast in headless env, emitted signals onto objects being torn down by pytest fixture cleanup → segfault.
- **Fix:** Moved `_start_filter_load()` call to `showEvent` with a `_filter_load_started` guard (once-only). Tests construct the dialog without showing it, avoiding thread start.
- **Files modified:** musicstreamer/ui_qt/discovery_dialog.py
- **Commit:** fe5efa1

## Known Stubs

None — all behaviors wired and tested.

## Threat Flags

No new threat surface beyond the plan's threat model (T-39-04, T-39-05, T-39-06 all addressed).

## Self-Check: PASSED

- `musicstreamer/ui_qt/discovery_dialog.py` — FOUND
- `tests/test_discovery_dialog.py` — FOUND
- Commit ee0dbb0 — FOUND
- Commit fe5efa1 — FOUND
- All 9 tests pass: confirmed
