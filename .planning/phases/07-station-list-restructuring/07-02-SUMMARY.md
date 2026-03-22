---
phase: 07-station-list-restructuring
plan: 02
subsystem: ui

tags: [gtk4, libadwaita, adw-expander-row, adw-action-row, station-list]

requires:
  - phase: 07-01
    provides: "Repo.list_stations() ordered by provider then name; Station.provider_name field"

provides:
  - "_rebuild_grouped: builds Adw.ExpanderRow per provider, collapsed by default, Uncategorized at bottom"
  - "_rebuild_flat: flat StationRow list for provider-filtered mode"
  - "_render_list: dispatcher selecting grouped vs flat based on filter state"
  - "_make_action_row: Adw.ActionRow with art prefix and activated->_play_by_id"
  - "_play_by_id: play dispatch by station ID (no row reference needed)"
  - "_clear_listbox: removes all children from listbox"
  - "_rp_rows: instance list initialized for Plan 03 recently played rows"

affects:
  - 07-03 (recently played section wires into _rebuild_grouped via _rp_rows)

tech-stack:
  added: []
  patterns:
    - "Explicit list rebuild replaces set_filter_func (filter_func cannot see ExpanderRow children)"
    - "Two render modes: _rebuild_grouped (default) and _rebuild_flat (provider filter active)"
    - "ExpanderRow children use activated signal directly; row-activated only fires for top-level ListBox rows"
    - "Empty state toggled inline in rebuild methods via shell.set_content()"

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Drop set_filter_func entirely — it cannot inspect ExpanderRow children added via add_row()"
  - "Dispatch via _play_by_id(station_id) from ActionRow activated signal instead of row.station_id"
  - "_rp_rows initialized as empty list now; Plan 03 will populate it in _rebuild_grouped"

patterns-established:
  - "Grouped mode: _rebuild_grouped(stations, search_text) called from _render_list"
  - "Flat mode: _rebuild_flat(filtered_stations) called when provider filter active"
  - "_make_action_row encapsulates ActionRow construction with art prefix + activated signal"

requirements-completed: [BROWSE-01]

duration: 2min
completed: 2026-03-22
---

# Phase 07 Plan 02: Grouped ExpanderRow Station List Summary

**Adw.ExpanderRow provider groups replacing flat StationRow list, with dual render modes (grouped/flat) driven by filter state**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-22T17:40:25Z
- **Completed:** 2026-03-22T17:41:56Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced flat `set_filter_func` architecture with explicit rebuild-based dual-mode rendering
- Grouped mode: one `Adw.ExpanderRow` per provider (alphabetical, collapsed by default), `Uncategorized` at bottom
- Flat mode: plain `StationRow` list when provider filter active (D-12, D-14)
- Search-only: grouped with non-matching rows excluded and empty groups hidden (D-13)
- Each station in a group is an `Adw.ActionRow` with art prefix; `activated` signal calls `_play_by_id`
- All 68 tests still passing

## Task Commits

1. **Task 1: Rewrite station list with grouped ExpanderRow layout** - `023dbe3` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `musicstreamer/ui/main_window.py` - Replaced _filter_func/reload_list/set_filter_func with _render_list/_rebuild_grouped/_rebuild_flat/_make_action_row/_play_by_id/_clear_listbox

## Decisions Made

- Dropped `set_filter_func` entirely. `filter_func` only sees top-level `ListBox` children (`ExpanderRow` instances), not the `ActionRow` children added via `add_row()`. Explicit rebuild is simpler and correct.
- Used `_play_by_id(station_id)` dispatched from each `ActionRow`'s `activated` signal. `row-activated` on the outer `ListBox` does not fire for `ExpanderRow` children (RESEARCH.md Pitfall 2).
- Initialized `self._rp_rows = []` now; Plan 03 will populate this list during `_rebuild_grouped` to track recently played rows for visibility toggling (D-15).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all new methods are fully wired. `_rp_rows` is intentionally empty (Plan 03 will populate).

## Next Phase Readiness

- Grouped station list complete; BROWSE-01 satisfied
- `_rp_rows` stub ready for Plan 03 recently played section
- `_play_by_id` method available for any row type that knows a station ID
- No blockers

---
*Phase: 07-station-list-restructuring*
*Completed: 2026-03-22*
