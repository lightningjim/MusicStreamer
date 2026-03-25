---
phase: 07-station-list-restructuring
plan: 03
subsystem: ui
tags: [gtk4, libadwaita, station-list, recently-played, expander-row]

# Dependency graph
requires:
  - phase: 07-02
    provides: grouped ExpanderRow station list with _rp_rows attribute and _any_filter_active()
  - phase: 07-01
    provides: repo.list_recently_played(), repo.update_last_played(), repo.get_setting()
provides:
  - Recently Played section at top of station list, showing up to 3 most-recent stations
  - _refresh_recently_played() for in-place RP refresh without collapsing ExpanderRows
  - _play_station wired to update_last_played on every play event
affects: [08-now-playing, any phase touching main_window play flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-place ListBox section refresh: remove tracked rows, re-insert at position 0 without full rebuild"
    - "RP visibility gate: check _any_filter_active() + search_text before rendering RP section"

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Use Gtk.ListBox.insert(row, 0) for in-place RP refresh rather than full _rebuild_grouped — preserves ExpanderRow expand/collapse state"
  - "recently_played_count configurable via settings table (default 3)"

patterns-established:
  - "RP refresh pattern: remove self._rp_rows, re-query repo, re-insert at position 0"
  - "Filter visibility gate: RP hidden when search_text or _any_filter_active()"

requirements-completed: [BROWSE-04]

# Metrics
duration: ~15min
completed: 2026-03-22
---

# Phase 07 Plan 03: Recently Played Section Summary

**Recently Played section above provider groups using in-place ListBox insert to preserve ExpanderRow collapse state, wired to play hook and hidden during active filters**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-22
- **Completed:** 2026-03-22
- **Tasks:** 1 auto + 1 human-verify
- **Files modified:** 1

## Accomplishments

- Wired `_play_station` to call `repo.update_last_played(st.id)` and `_refresh_recently_played()` on every play event
- Added Recently Played section (header label + up to 3 StationRow instances) rendered at top of grouped view in `_rebuild_grouped`
- Added `_refresh_recently_played()` method that swaps RP rows in-place without triggering a full list rebuild, preserving ExpanderRow expand/collapse state
- RP hidden automatically when any filter (search, provider, tag) is active
- RP persists across restarts via `last_played_at` column (written in Plan 01)
- Human verified all 10 interaction scenarios: grouped layout, expand/collapse, play from group, RP updates, RP playability, filter modes, persistence

## Task Commits

1. **Task 1: Add Recently Played section and wire play hook** - `cdc8ae1` (feat)
2. **Task 2: Human verify** - no commit (visual verification only)

## Files Created/Modified

- `musicstreamer/ui/main_window.py` - Added `_refresh_recently_played()`, updated `_rebuild_grouped` to render RP section, wired `_play_station` to update last_played_at

## Decisions Made

- Used `Gtk.ListBox.insert(row, 0)` for in-place RP refresh rather than calling `reload_list()` — avoids collapsing all ExpanderRows on every play event (per RESEARCH.md Pitfall 3)
- `recently_played_count` read from settings table with default 3 — configurable without code changes

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Station list restructuring complete: grouped collapsible layout + Recently Played section fully functional
- BROWSE-04 requirement satisfied
- `_refresh_recently_played()` and `_rp_rows` tracking available to any future phase that adds play-event side effects

---
*Phase: 07-station-list-restructuring*
*Completed: 2026-03-22*
