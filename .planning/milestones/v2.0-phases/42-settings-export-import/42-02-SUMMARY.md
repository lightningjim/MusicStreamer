---
phase: 42-settings-export-import
plan: "02"
subsystem: ui
tags: [export, import, qt, dialog, qthread, settings, sync]
dependency_graph:
  requires: [musicstreamer.settings_export]
  provides: [musicstreamer.ui_qt.settings_import_dialog, main_window export/import handlers]
  affects: [musicstreamer.ui_qt.main_window]
tech_stack:
  added: [QStandardPaths, QFileDialog]
  patterns: [qthread-worker-background-io, qt-queued-connection-signals, worker-reference-retention]
key_files:
  created:
    - musicstreamer/ui_qt/settings_import_dialog.py
    - tests/test_settings_import_dialog.py
  modified:
    - musicstreamer/ui_qt/main_window.py
decisions:
  - "Used isHidden() in test for replace_warning instead of isVisible() — QWidget.isVisible() returns False for unshown dialogs even when setVisible(True) was called; isHidden() reflects the explicit hide/show state independent of parent visibility"
  - "Worker classes (_ExportWorker, _ImportPreviewWorker) placed at module level before MainWindow — consistent with existing _YtScanWorker pattern in import_dialog.py"
  - "Lazy import of SettingsImportDialog inside _on_import_preview_ready — avoids circular import at module load time"
metrics:
  duration: "~3 minutes"
  completed: "2026-04-16T17:04:06Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 42 Plan 02: Settings Export/Import UI Summary

Settings export/import UI wired: QThread workers for background I/O, SettingsImportDialog with merge/replace-all modes and expandable detail tree, enabled hamburger menu items with QFileDialog pickers defaulting to Documents folder.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create SettingsImportDialog and wire main_window.py handlers | 32471f8 | musicstreamer/ui_qt/settings_import_dialog.py, musicstreamer/ui_qt/main_window.py, tests/test_settings_import_dialog.py |
| 2 | Manual UAT — export and import round-trip | (auto-approved) | — |

## What Was Built

### `musicstreamer/ui_qt/settings_import_dialog.py`

- **`_ImportCommitWorker(QThread)`** — background worker calling `commit_import`; emits `finished` / `error(str)`
- **`SettingsImportDialog(QDialog)`** — import summary dialog with:
  - Merge / Replace All radio toggle with `QButtonGroup`
  - Red warning label (`color: #c0392b`) shown when Replace All selected
  - 13pt DemiBold summary label showing added/replaced/skipped/errors counts
  - Expandable `QTreeWidget` detail list (hidden by default unless errors present)
  - QMessageBox.warning confirmation before Replace All commit (T-42-05)
  - `import_complete` signal emitted after successful commit (for station list refresh)
  - All DB I/O on background QThread (T-42-06)

### `musicstreamer/ui_qt/main_window.py` (modified)

- Added imports: `datetime`, `os`, `QThread`, `Signal`, `QFileDialog`, `QStandardPaths`, `settings_export`, `db_connect`
- Added `_ExportWorker(QThread)` and `_ImportPreviewWorker(QThread)` worker classes
- Replaced disabled Export/Import Settings menu placeholders with connected actions (SYNC-05)
- Added worker reference attributes `_export_worker`, `_import_preview_worker` for GC prevention
- Added handler methods: `_on_export_settings`, `_on_export_done`, `_on_export_error`, `_on_import_settings`, `_on_import_preview_ready`, `_on_import_preview_error`
- Export default path: `Documents/musicstreamer-export-YYYY-MM-DD.zip` via `QStandardPaths.DocumentsLocation`
- Invalid ZIP shows toast "Invalid settings file" (preview worker error path)

### `tests/test_settings_import_dialog.py`

5 widget tests covering: summary label counts, merge default mode, replace warning visibility (hide/show), detail tree row count, dialog title.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed replace warning visibility test — isVisible() vs isHidden()**
- **Found during:** Task 1 test run
- **Issue:** `test_replace_warning_visibility` used `dlg._replace_warning.isVisible()` which returns False for unshown dialogs even after `setVisible(True)` is called — Qt considers a widget visible only when all parent widgets are also visible
- **Fix:** Changed test assertions to use `isHidden()` which reflects the explicit widget show/hide state independent of parent visibility
- **Files modified:** tests/test_settings_import_dialog.py

## Checkpoint Auto-Approval

Task 2 (Manual UAT) was a `checkpoint:human-verify` task. Auto-approved in `--auto` mode.
What was built: full export/import round-trip — hamburger menu items enabled, file pickers, ZIP export with stations/streams/favorites/settings/logos, import summary dialog with merge/replace-all modes.

## Threat Model Compliance

| Threat | Mitigation |
|--------|-----------|
| T-42-05: Replace All tampering | QMessageBox.warning confirmation in `_on_import` before commit |
| T-42-06: UI thread blocking | All I/O (_ExportWorker, _ImportPreviewWorker, _ImportCommitWorker) on QThread; Qt.QueuedConnection for result signals |

## Known Stubs

None — all data flows from DB through ZIP and back via the settings_export module built in Plan 01.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary changes. File picker is user-initiated and restricted to *.zip filter.

## Self-Check: PASSED

- musicstreamer/ui_qt/settings_import_dialog.py: FOUND
- tests/test_settings_import_dialog.py: FOUND
- musicstreamer/ui_qt/main_window.py: modified (verified)
- Commit 32471f8: FOUND
- 5 new dialog tests + 17 export tests = 22 pass
- `setEnabled(False)` count in main_window.py for export/import: 0
- `_on_export_settings` matches: 2 (def + connect)
- `QStandardPaths.StandardLocation.DocumentsLocation` matches: 2
