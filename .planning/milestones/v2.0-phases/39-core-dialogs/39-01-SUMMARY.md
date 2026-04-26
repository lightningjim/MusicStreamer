---
phase: 39-core-dialogs
plan: "01"
subsystem: ui_qt
tags: [dialog, station-editor, pyside6, tdd]
dependency_graph:
  requires: [musicstreamer/ui_qt/flow_layout.py, musicstreamer/repo.py, musicstreamer/models.py]
  provides: [musicstreamer/ui_qt/edit_station_dialog.py]
  affects: []
tech_stack:
  added: []
  patterns: [QDialog modal, FlowLayout chip area, QTableWidget stream CRUD, Qt.UserRole stream_id persistence]
key_files:
  created:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py
  modified: []
key_decisions:
  - "stream_id stored in URL item Qt.UserRole so it survives row swaps without a parallel dict"
  - "Chip toggle closure uses @staticmethod factory to avoid self-capture"
  - "uv run --with pytest --with pytest-qt required — system PySide6 6.9.2 missing QtTest"
metrics:
  duration_minutes: 15
  completed_date: "2026-04-13"
  tasks_completed: 2
  files_changed: 2
requirements_satisfied: [UI-05]
---

# Phase 39 Plan 01: EditStationDialog Summary

EditStationDialog — modal PySide6 QDialog for full station CRUD with tag chip editor, multi-stream table, and playing guard.

## What Was Built

`EditStationDialog(station, player, repo, parent=None)` — a modal QDialog providing:

- **QFormLayout fields:** Name (QLineEdit), URL (QLineEdit with 500ms debounce timer D-07), Provider (editable QComboBox from `repo.list_providers()`), Tags (FlowLayout chip area + inline tag creation), ICY disable checkbox
- **Tag chips:** `QPushButton` with `chipState` property using `_CHIP_QSS` verbatim from `station_list_panel.py`; toggling flips selected/unselected state and polishes the widget
- **Stream table:** 4-column `QTableWidget` (URL stretch, Quality 80px, Codec 80px, Position 60px); stream_id stored in URL item's `Qt.UserRole` for persistence across row reorder swaps
- **Stream CRUD:** Add / Remove / Move Up / Move Down buttons
- **Button box:** Save Station (AcceptRole) → `ensure_provider` + `update_station` + stream persist + `reorder_streams`; Discard (RejectRole); Delete Station (DestructiveRole, `#c0392b` QSS)
- **Delete guard (T-39-03):** `delete_btn.setEnabled(not is_playing)` checked at construction against `player._current_station_name`
- **Signals:** `station_saved = Signal()`, `station_deleted = Signal(int)`
- **Security (T-39-01):** All display fields are `QLineEdit` / `QCheckBox` / `QTableWidgetItem` — no `QLabel` displaying untrusted metadata uses rich-text; `Qt.PlainText` constraint is naturally satisfied

## Tests

11 pytest-qt tests — all pass GREEN:

| Test | Covers |
|------|--------|
| test_name_field_populated | Name field pre-populated |
| test_provider_combo_editable_and_populated | Editable combo + provider list |
| test_tag_chips_render_and_toggle | Chips render + chipState toggle |
| test_add_tag_creates_chip | Add Tag button |
| test_stream_table_populated_and_add | Stream table + Add row |
| test_remove_stream_removes_row | Remove button |
| test_move_up_down_reorder | Move Up / Move Down |
| test_delete_disabled_when_playing | Playing guard |
| test_delete_enabled_when_not_playing | Guard off when not playing |
| test_save_calls_repo_correctly | ensure_provider + update_station args |
| test_icy_checkbox_maps_to_icy_disabled | ICY checkbox → icy_disabled arg |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest-qt not installed in uv venv**
- **Found during:** Task 1 verification
- **Issue:** System PySide6 6.9.2 missing `QtTest` module; `pytest-qt` installed globally crashed with `AttributeError: module 'PySide6' has no attribute 'QtTest'`
- **Fix:** Used `uv run --with pytest --with pytest-qt` which installs into the venv with PySide6 6.11.0 (full module set)
- **Files modified:** none (runtime configuration)
- **Commit:** n/a

## Known Stubs

None — all fields populated from real repo/station data; no placeholder text or hardcoded empties in the render path.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- edit_station_dialog.py: FOUND
- test_edit_station_dialog.py: FOUND
- 39-01-SUMMARY.md: FOUND
- commit 54b292c (test RED): FOUND
- commit 57d0ffb (impl GREEN): FOUND
