---
phase: 05-display-polish
plan: 02
subsystem: ui
tags: [gtk4, adwaita, station-row, placeholder-icon]

# Dependency graph
requires:
  - phase: 04-cover-art
    provides: audio-x-generic-symbolic fallback pattern used in now-playing panel
provides:
  - Unconditional prefix widget on every StationRow (image or placeholder icon)
affects: [06-station-management]

# Tech tracking
tech-stack:
  added: []
  patterns: [Always add prefix widget to ActionRow — image if available, placeholder icon otherwise]

key-files:
  created: []
  modified:
    - musicstreamer/ui/station_row.py

key-decisions:
  - "Use audio-x-generic-symbolic at 48px for placeholder, mirroring the now-playing logo_fallback pattern"

patterns-established:
  - "StationRow prefix: unconditional add_prefix — logo Gtk.Picture when art file exists, Gtk.Image icon-name fallback otherwise"

requirements-completed: [DISP-01]

# Metrics
duration: 3min
completed: 2026-03-21
---

# Phase 05 Plan 02: Station Row Placeholder Icon Summary

**Unconditional 48px prefix widget in StationRow: logo image when art file exists, audio-x-generic-symbolic icon otherwise**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T13:40:00Z
- **Completed:** 2026-03-21T13:40:59Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Every station row now has a visual prefix widget — no bare rows
- Stations with a logo file show Gtk.Picture at 48x48 (unchanged behavior)
- Stations without a logo show `audio-x-generic-symbolic` at 48px (consistent with now-playing fallback)
- All 48 existing tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add placeholder icon for stations without logo in list rows** - `b8e941b` (feat)

**Plan metadata:** _(to be added by final commit)_

## Files Created/Modified
- `musicstreamer/ui/station_row.py` - Replaced conditional prefix block with unconditional has_art pattern

## Decisions Made
- Mirrored `audio-x-generic-symbolic` from `main_window.py` logo_fallback — keeps icon name consistent across the app

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 05 complete: BUG-01 (cover art fallback) and DISP-01 (station row placeholder) both shipped
- Phase 06 (Station Management) can proceed: no blockers

---
*Phase: 05-display-polish*
*Completed: 2026-03-21*
