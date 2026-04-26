---
phase: 39-core-dialogs
plan: "03"
subsystem: ui_qt
tags: [qt, dialog, import, youtube, audioaddict, threading]
dependency_graph:
  requires: []
  provides: [ImportDialog]
  affects: [musicstreamer/ui_qt/import_dialog.py, tests/test_import_dialog_qt.py]
tech_stack:
  added: []
  patterns: [QThread daemon worker, Signal queued connection, thread-local Repo(db_connect())]
key_files:
  created:
    - musicstreamer/ui_qt/import_dialog.py
    - tests/test_import_dialog_qt.py
  modified: []
decisions:
  - "Workers create thread-local Repo(db_connect()) — yt_import.import_stations and aa_import.import_stations_multi both require a repo parameter (not self-sufficient)"
  - "fetch_channels_multi(listen_key) takes no qualities param — fetches all three quality tiers per channel; quality combo is retained for UX consistency"
  - "AA tab isVisible() tests require setCurrentIndex(1) before invoking error handler — Qt QTabWidget hides inactive tab children"
metrics:
  duration_minutes: 22
  completed_date: "2026-04-13"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 39 Plan 03: ImportDialog Summary

ImportDialog QDialog with YouTube playlist tab (scan → checkable list → import) and AudioAddict tab (API key + quality → fetch channels → import with progress) using four QThread workers with thread-local DB connections.

## Tasks

| # | Name | Commit | Status |
|---|------|--------|--------|
| 1 | Test scaffolds for ImportDialog (RED) | c9bfead | Done |
| 2 | Implement ImportDialog (GREEN) | 7c96095 | Done |

## Verification

```
uv run --with pytest --with pytest-qt python -m pytest tests/test_import_dialog_qt.py -x
# 11 passed in 0.30s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Actual yt_import/aa_import signatures differ from plan interfaces**
- **Found during:** Task 2
- **Issue:** Plan stated `import_stations_multi` creates its own DB connection internally and takes no `repo` parameter. Actual signatures: `yt_import.import_stations(entries, repo)` and `aa_import.import_stations_multi(channels, repo, on_progress, on_logo_progress)` both require a caller-provided `repo`. Also `fetch_channels_multi(listen_key)` has no `qualities` parameter.
- **Fix:** Workers create `Repo(db_connect())` inside `QThread.run()` — correct thread-local pattern per Pitfall 3.
- **Files modified:** musicstreamer/ui_qt/import_dialog.py

**2. [Rule 1 - Bug] Test visibility assertion fails for inactive tab widgets**
- **Found during:** Task 2 (test run)
- **Issue:** `_aa_status.isVisible()` returns False when tested because `_aa_status` lives on the AudioAddict tab (tab index 1) while the active tab is 0 (YouTube). Qt hides inactive tab content.
- **Fix:** Tests that assert AA tab widget visibility call `dialog._tabs.setCurrentIndex(1)` before invoking the error handler.
- **Files modified:** tests/test_import_dialog_qt.py

## Known Stubs

None — ImportDialog is fully wired to yt_import and aa_import backends.

## Threat Flags

None — no new trust boundaries beyond those in plan's threat model (T-39-07 through T-39-10).

T-39-07 mitigated: `scan_playlist` call is inside `_YtScanWorker.run()` — URL is passed through to yt_import which internally validates via `is_yt_playlist_url()` before calling yt-dlp.

## Self-Check: PASSED

- musicstreamer/ui_qt/import_dialog.py: FOUND
- tests/test_import_dialog_qt.py: FOUND
- Commit c9bfead: FOUND
- Commit 7c96095: FOUND
