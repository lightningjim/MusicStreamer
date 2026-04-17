---
status: complete
phase: 42-settings-export-import
source:
  - .planning/phases/42-settings-export-import/42-01-SUMMARY.md
  - .planning/phases/42-settings-export-import/42-02-SUMMARY.md
  - .planning/phases/42-settings-export-import/42-03-SUMMARY.md
started: 2026-04-16T00:00:00Z
updated: 2026-04-17T10:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Export Settings from Hamburger Menu
expected: Click hamburger menu → Export Settings. QFileDialog opens at Documents with default name "musicstreamer-export-YYYY-MM-DD.zip". ZIP file appears at chosen location. Menu disabled + busy cursor during export.
result: pass

### 2. Import Valid ZIP — Preview Dialog
expected: Click hamburger menu → Import Settings. File picker restricted to *.zip. Selecting a valid export ZIP opens SettingsImportDialog showing correct added/replaced/skipped/errors counts with 13pt DemiBold summary label.
result: pass

### 3. Import Merge Mode
expected: In import dialog with "Merge" selected (default), click Import. Dialog closes, station list refreshes with imported + existing entries preserved. No warning label visible in Merge mode.
result: pass

### 4. Import Replace All Mode — Confirmation Gate
expected: In import dialog, select "Replace All" radio. Red warning label (#c0392b) appears. Click Import. QMessageBox.warning confirmation dialog appears with Yes/Cancel (Cancel default). Clicking Cancel returns to dialog; clicking Yes commits and closes.
result: pass

### 5. Import Invalid ZIP — Error Toast
expected: Select a non-settings ZIP or malformed file from picker. Toast appears saying "Invalid settings file" (with specific error detail from validation). No dialog opens. No DB changes.
result: pass

### 6. Expandable Detail Tree
expected: In import dialog, click the disclosure/expander on the detail QTreeWidget. Tree expands showing per-row details (station/stream/favorite/setting). Error rows show warning icon + red (#c0392b) foreground. Tree is hidden by default unless errors present.
result: pass
note: "Error-row visual treatment (warning icon + #c0392b) verified by automated tests in commits 0b23550 and a6ce100; no error data available to exercise visually at UAT time."

### 7. Round-Trip Export → Import
expected: Export current settings to ZIP. Make a change (add a station or favorite). Import the original ZIP in Replace All mode. Station list, favorites, and settings match the pre-change state exactly. audioaddict_listen_key is NOT overwritten from ZIP (excluded per T-42-03).
result: skipped
reason: "audioaddict_listen_key is not being persisted in DB (upstream issue, not phase 42 scope). Phase 42 exclusion behavior is verified by automated tests in test_settings_export.py. Round-trip core flow covered by tests 1-4."

### 8. Import Commit Error Handling
expected: If DB commit fails mid-import (e.g., disk full), "Import failed: <error>" toast appears and the Import button re-enables so the user can retry or cancel. No partial DB state (transaction rolled back).
result: issue
reported: "Did the read-only chmod trick on the SQLite DB, removed a stream, then ran Import to re-add it. Import claimed success but the stream was not restored."
severity: major

## Summary

total: 8
passed: 6
issues: 1
pending: 0
skipped: 1

## Gaps

- truth: "Import reports success only when the DB commit actually succeeds; on a read-only/failing DB, Import displays an 'Import failed' toast and re-enables the Import button."
  status: resolved
  reason: "User reported: Did the read-only chmod trick on the SQLite DB, removed a stream, then ran Import to re-add it. Import claimed success but the stream was not restored."
  severity: major
  test: 8
  artifacts:
    - .planning/phases/42-settings-export-import/42-03-PLAN.md
    - .planning/phases/42-settings-export-import/42-03-SUMMARY.md
    - .planning/debug/resolved/settings-import-silent-fail-on-readonly-db.md
  missing: []
  resolved_by: 42-03
  resolution: "Renamed `_ImportCommitWorker.finished`/`error` signals to `commit_done`/`commit_error` to stop shadowing `QThread.finished`. Added `test_commit_error_on_readonly_db_real_filesystem` regression test using real `chmod 0o444` SQLite file."
