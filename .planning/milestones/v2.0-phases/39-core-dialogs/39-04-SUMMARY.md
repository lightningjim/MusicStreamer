---
phase: 39-core-dialogs
plan: "04"
subsystem: ui_qt
tags: [stream-picker, edit-button, dialog-wiring, now-playing, main-window]
dependency_graph:
  requires: [39-01, 39-02, 39-03]
  provides: [UI-13, stream-picker, edit-button, dialog-launch-wiring]
  affects: [now_playing_panel, main_window, station_list_panel]
tech_stack:
  added: []
  patterns: [blockSignals-guard, QComboBox-stream-picker, QToolButton-edit]
key_files:
  created:
    - musicstreamer/ui_qt/icons/document-edit-symbolic.svg
    - tests/test_stream_picker.py
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/icons.qrc
    - musicstreamer/ui_qt/icons_rc.py
    - tests/test_now_playing_panel.py
    - tests/test_main_window_integration.py
decisions:
  - "blockSignals(True/False) wraps all programmatic setCurrentIndex calls in stream picker to prevent re-entrant play_stream (T-39-11)"
  - "refresh_model() added to StationListPanel rebuilds tree + recent + chip rows from repo"
  - "isHidden() used in tests instead of isVisible() — offscreen test widgets never have visible parent"
metrics:
  duration: 25min
  completed: 2026-04-13
  tasks_completed: 2
  files_changed: 9
---

# Phase 39 Plan 04: Edit Button + Stream Picker + Dialog Wiring Summary

Edit button and stream picker added to NowPlayingPanel; all Phase 39 dialogs wired into MainWindow with station list refresh on save/delete/import.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Test scaffolds for stream picker + edit button (RED) | d4795ee | tests/test_stream_picker.py |
| 2 | Edit button + stream picker + dialog wiring (GREEN) | d1344d2 | now_playing_panel.py, main_window.py, station_list_panel.py, icons.*, tests fixes |

## What Was Built

**NowPlayingPanel additions:**
- `edit_btn` (QToolButton, 36x36) — uses `document-edit-symbolic` icon; disabled until station playing
- `stream_combo` (QComboBox, min 140px) — hidden for single-stream stations, visible for multi-stream
- `edit_requested = Signal(object)` — emitted by `_on_edit_clicked` with current Station
- `_populate_stream_picker(station)` — fills combo with "quality — codec" labels, blockSignals guard
- `_on_stream_selected(index)` — calls `player.play_stream(stream)` for manual selection
- `_sync_stream_picker(active_stream)` — updates combo on failover with blockSignals guard (T-39-11)

**MainWindow additions:**
- Imports EditStationDialog, DiscoveryDialog, ImportDialog
- `edit_requested` → `_on_edit_requested`: opens EditStationDialog, wires save/delete signals
- `player.failover` → `now_playing._sync_stream_picker`: syncs picker on auto-failover
- `_on_station_deleted`: refreshes list and stops now-playing if deleted station was playing
- `_refresh_station_list`: calls `station_panel.refresh_model()`

**StationListPanel additions:**
- `refresh_model()` — rebuilds tree (via `StationTreeModel.refresh`), expands all, repopulates recent + chips

**Icon:**
- `document-edit-symbolic.svg` added to icons/; icons.qrc updated; icons_rc.py regenerated

## Verification

- `python -m pytest tests/test_stream_picker.py` — 8/8 pass
- `python -m pytest tests/test_now_playing_panel.py` — 24/24 pass
- `python -m pytest tests/test_main_window_integration.py` — 23/23 pass
- `pyside6-rcc musicstreamer/ui_qt/icons.qrc -o /dev/null` — valid

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] FakeRepo.list_streams missing in two test files**
- **Found during:** Task 2 (GREEN run)
- **Issue:** `test_now_playing_panel.py` and `test_main_window_integration.py` both have FakeRepo classes that lacked `list_streams`, causing AttributeError when `bind_station` called `_populate_stream_picker`
- **Fix:** Added `list_streams(station_id) -> []` stub to both FakeRepo classes
- **Files modified:** tests/test_now_playing_panel.py, tests/test_main_window_integration.py
- **Commit:** d1344d2

**2. [Rule 1 - Bug] isVisible() vs isHidden() in offscreen tests**
- **Found during:** Task 1 RED→GREEN transition
- **Issue:** `panel.stream_combo.isVisible()` returns False for all widgets in offscreen test environment (parent never shown), so the "visible for multi-stream" assertion always failed
- **Fix:** Changed tests 4 and 5 to use `isHidden()` — checks the explicit hide flag set by `setVisible()`, regardless of parent visibility
- **Files modified:** tests/test_stream_picker.py
- **Commit:** d4795ee (test update), d1344d2

## Known Stubs

None — all dialog wiring is functional end-to-end.

## Threat Flags

None — no new network endpoints or auth paths introduced.

## Self-Check

Files exist:
- musicstreamer/ui_qt/icons/document-edit-symbolic.svg — FOUND
- tests/test_stream_picker.py — FOUND
- musicstreamer/ui_qt/now_playing_panel.py (modified) — FOUND
- musicstreamer/ui_qt/main_window.py (modified) — FOUND
- musicstreamer/ui_qt/station_list_panel.py (modified) — FOUND

Commits:
- d4795ee — FOUND
- d1344d2 — FOUND

## Self-Check: PASSED
