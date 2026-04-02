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

key-files:
  created:
    - musicstreamer/ui/import_dialog.py
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Track import button handler ID to safely disconnect on import complete and reconnect as Done"
  - "spinner.start() called immediately in constructor — spinner page always animating when visible"

patterns-established:
  - "Two-stage dialog: scan (thread) -> checklist review -> import (thread) -> Done"
  - "GLib.markup_escape_text on Adw.ActionRow title/subtitle (markup-parsed)"

requirements-completed: [IMPORT-01]

duration: 4min
completed: 2026-04-02
---

# Phase 14 Plan 02: ImportDialog UI Summary

**Two-stage YouTube playlist import dialog: URL scan via yt-dlp, live-stream checklist with checkboxes, import with real-time progress, and Import button wired into main window header bar**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-02T01:57:40Z
- **Completed:** 2026-04-02T02:01:00Z
- **Tasks:** 2 of 3 (Task 3 is checkpoint:human-verify — awaiting user)
- **Files modified:** 2

## Accomplishments

- Created `musicstreamer/ui/import_dialog.py` (230 lines) — full two-stage ImportDialog with scan, checklist, and import flow
- Wired Import button into main window header bar (pack_end, left of Discover)
- All 117 tests passing after changes

## Task Commits

1. **Task 1: Create ImportDialog with two-stage flow** - `a785d4b` (feat)
2. **Task 2: Wire Import button into main window header bar** - `bd24cff` (feat)

## Files Created/Modified

- `musicstreamer/ui/import_dialog.py` — ImportDialog(Adw.Window): URL entry, Scan Playlist button, 4-page Stack (prompt/scanning/error/checklist), checklist with CheckButton prefix on ActionRows, import worker with on_progress callback, Done button wired after completion
- `musicstreamer/ui/main_window.py` — Import button added to header bar; `_open_import` handler added after `_open_discovery`

## Decisions Made

- Track `_import_handler_id` to disconnect old handler before reconnecting as Done — avoids signal accumulation
- `spinner.start()` called in constructor so spinner page is always animated when switched to (mirrors DiscoveryDialog)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Task 3 (human-verify) is pending — user must launch app and verify the full import flow
- After approval: phase 14 is complete; DISC-06 requirement will be satisfied

---
*Phase: 14-youtube-playlist-import*
*Completed: 2026-04-02*
