---
phase: 14-youtube-playlist-import
plan: 02
subsystem: ui
tags: [gtk4, libadwaita, yt-dlp, threading, GLib.idle_add]

requires:
  - phase: 14-01
    provides: scan_playlist, import_stations, is_yt_playlist_url in musicstreamer/yt_import.py

provides:
  - ImportDialog (Adw.Window) — two-stage YouTube playlist import flow
  - Import button in main window header bar opening ImportDialog

affects:
  - main_window (header bar now has Import button)
  - yt_import (called from ImportDialog)

tech-stack:
  added: []
  patterns:
    - daemon thread + GLib.idle_add for scan and import workers (mirrors DiscoveryDialog)
    - Gtk.Stack for multi-page dialog state (prompt/scanning/error/checklist)
    - Gtk.CheckButton prefix on Adw.ActionRow for per-item selection
    - Disconnect/reconnect handler pattern for repurposing Import button to Done
    - Thread-local db_connect() in import worker to avoid SQLite cross-thread errors

key-files:
  created:
    - musicstreamer/ui/import_dialog.py
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Track import button handler ID to safely disconnect on import complete and reconnect as Done"
  - "spinner.start() called immediately in constructor — spinner page always animating when visible"
  - "Open thread-local DB connection in _import_worker — SQLite connections cannot be shared across threads"

patterns-established:
  - "Two-stage dialog: scan (thread) -> checklist review -> import (thread) -> Done"
  - "GLib.markup_escape_text on Adw.ActionRow title/subtitle (markup-parsed)"

requirements-completed: [IMPORT-01]

duration: ~10min
completed: 2026-04-01
---

# Phase 14 Plan 02: ImportDialog UI Summary

**Two-stage YouTube playlist import dialog: URL scan via yt-dlp, live-stream checklist with checkboxes, import with real-time progress, and Import button wired into main window header bar**

## Performance

- **Duration:** ~10 min (including human verify + threading fix)
- **Completed:** 2026-04-01
- **Tasks:** 3 of 3 (complete)
- **Files modified:** 2

## Accomplishments

- Created `musicstreamer/ui/import_dialog.py` (230 lines) — full two-stage ImportDialog with scan, checklist, and import flow
- Wired Import button into main window header bar (pack_end, left of Discover)
- Human verified: 11 stations imported, 7 skipped — flow confirmed working end-to-end
- All 117 tests passing after changes

## Task Commits

1. **Task 1: Create ImportDialog with two-stage flow** - `a785d4b` (feat)
2. **Task 2: Wire Import button into main window header bar** - `bd24cff` (feat)
3. **Task 3: Verify full import flow** - approved by user (11 imported, 7 skipped)
4. **Post-checkpoint fix: SQLite threading bug** - `64d31bc` (fix)

## Files Created/Modified

- `musicstreamer/ui/import_dialog.py` — ImportDialog(Adw.Window): URL entry, Scan Playlist button, 4-page Stack (prompt/scanning/error/checklist), checklist with CheckButton prefix on ActionRows, import worker with on_progress callback, Done button wired after completion; thread-local DB connection in _import_worker
- `musicstreamer/ui/main_window.py` — Import button added to header bar; `_open_import` handler added after `_open_discovery`

## Decisions Made

- Track `_import_handler_id` to disconnect old handler before reconnecting as Done — avoids signal accumulation
- `spinner.start()` called in constructor so spinner page is always animated when switched to (mirrors DiscoveryDialog)
- Open thread-local `db_connect()` in `_import_worker` — SQLite connections are not thread-safe across the main-thread connection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite ProgrammingError: DB connection used from worker thread**
- **Found during:** Task 3 (post-checkpoint, discovered during human verification)
- **Issue:** `import_stations()` in `_import_worker` used `self.repo` which holds a main-thread SQLite connection. Calling it from a daemon thread raised `sqlite3.ProgrammingError: Recursive use of cursors not allowed`.
- **Fix:** `_import_worker` now opens its own thread-local `db_connect()` and passes a fresh `Repo` instance to `import_stations()`.
- **Files modified:** `musicstreamer/ui/import_dialog.py`
- **Commit:** `64d31bc`

## Issues Encountered

None beyond the SQLite threading bug (documented above as deviation).

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

---
*Phase: 14-youtube-playlist-import*
*Completed: 2026-04-01*
