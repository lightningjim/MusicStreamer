---
phase: 09-station-editor-improvements
plan: 02
subsystem: ui
tags: [gtk4, libadwaita, edit_dialog, yt-dlp, youtube, threading, GLib]

requires:
  - phase: 09-01
    provides: EditStationDialog with ComboRow/chip provider+tag widgets; fetch_yt_thumbnail pattern established

provides:
  - fetch_yt_title module-level function (daemon thread + GLib.idle_add, mirrors fetch_yt_thumbnail)
  - _thumb_fetch_in_progress and _title_fetch_in_progress split flags (replaces single _fetch_in_progress)
  - _start_title_fetch and _on_title_fetched methods in EditStationDialog
  - YouTube URL focus-out triggers parallel title + thumbnail fetch
  - Name guard: title only auto-populated if name is blank or "New Station"

affects:
  - 09-station-editor-improvements (remaining plans)
  - Any plan modifying EditStationDialog fetch behavior

tech-stack:
  added: []
  patterns:
    - "fetch_yt_title mirrors fetch_yt_thumbnail exactly: daemon thread + GLib.idle_add + 15s timeout"
    - "Split fetch flags allow thumbnail and title fetches to run independently without blocking each other"
    - "Name guard pattern: only auto-populate if current value is blank or sentinel ('New Station')"

key-files:
  created: []
  modified:
    - musicstreamer/ui/edit_dialog.py

key-decisions:
  - "Split _fetch_in_progress into _thumb_fetch_in_progress and _title_fetch_in_progress so thumbnail and title fetches are independent — one slow/failed fetch does not block the other"
  - "Name guard checks for empty string or 'New Station' only — any other existing text is treated as user-set and preserved"
  - "_fetch_cancelled guards both _on_thumbnail_fetched and _on_title_fetched — dialog close cancels all in-flight fetches"

requirements-completed:
  - MGMT-04

duration: 5min
completed: 2026-03-23
---

# Phase 9 Plan 02: YouTube Title Auto-Import Summary

**YouTube URL focus-out now fetches stream title via yt-dlp and auto-populates empty name field, running in parallel with the existing thumbnail fetch using independent flags**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-23T01:00:00Z
- **Completed:** 2026-03-23T01:05:39Z
- **Tasks:** 1 of 1 (Task 2 is human-verify checkpoint)
- **Files modified:** 1

## Accomplishments

- Added `fetch_yt_title()` module-level function mirroring `fetch_yt_thumbnail` pattern (daemon thread, GLib.idle_add, 15s timeout)
- Split `_fetch_in_progress` into `_thumb_fetch_in_progress` and `_title_fetch_in_progress` so fetches are fully independent
- Extended `_on_url_focus_out` to call both `_start_thumbnail_fetch` and `_start_title_fetch` in parallel
- Name guard in `_on_title_fetched`: only populates name if currently `""` or `"New Station"` — never overwrites user-set name

## Task Commits

1. **Task 1: Add fetch_yt_title and wire parallel title fetch on URL focus-out** - `33ec4cb` (feat)
2. **Task 1 auto-fix: strip trailing date/time from YT stream titles** - `51fae19` (fix)
3. **Task 2: Verify YouTube title auto-import** - checkpoint approved by user (no code changes)

**Plan metadata:** (this commit)

## Files Created/Modified

- `musicstreamer/ui/edit_dialog.py` - Added fetch_yt_title(), split fetch flags, _start_title_fetch, _on_title_fetched, extended _on_url_focus_out, strip trailing date/time suffix from yt-dlp title output

## Decisions Made

- Split flags: thumbnail and title fetches are independent; a slow yt-dlp title fetch does not block the spinner from clearing when thumbnail completes
- Name guard only allows two sentinels (empty or "New Station") — matches the "New Station" default assigned when adding a station
- Strip trailing ` YYYY-MM-DD HH:MM` from yt-dlp title output — live streams append this and it makes poor station names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stripped trailing date/time suffix from yt-dlp stream title**
- **Found during:** Task 1 (post-commit verification against live YouTube URL)
- **Issue:** yt-dlp `--print title` for live streams returns title with appended date/time, e.g. `"Lo-Fi Girl 2026-03-23 01:15"` — unusable as a station name
- **Fix:** Added regex strip of trailing ` YYYY-MM-DD HH:MM` pattern before passing title to callback
- **Files modified:** musicstreamer/ui/edit_dialog.py
- **Committed in:** 51fae19

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Necessary for correct output. No scope creep.

## Issues Encountered

None beyond the auto-fixed date/time suffix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 9 complete: provider picker, tag chips, and YouTube title auto-import all shipped
- Phase 10 (Now Playing & Audio) can proceed: provider name in now-playing panel, volume slider
- No blockers.

---
*Phase: 09-station-editor-improvements*
*Completed: 2026-03-23*

## Self-Check: PASSED

- `musicstreamer/ui/edit_dialog.py` exists: FOUND
- Commit `33ec4cb` exists: FOUND
- Commit `51fae19` exists: FOUND
