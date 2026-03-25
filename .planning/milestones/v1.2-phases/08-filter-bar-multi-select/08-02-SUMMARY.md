---
phase: 08-filter-bar-multi-select
plan: 02
subsystem: ui
tags: [gtk4, adwaita, filter, multi-select, toggle-button, chip-strip]

# Dependency graph
requires:
  - phase: 08-01
    provides: matches_filter_multi function with set-based OR/AND logic
provides:
  - Chip strip UI replacing DropDown widgets in main_window.py
  - Multi-select provider filter (_selected_providers set)
  - Multi-select tag filter (_selected_tags set)
  - _make_chip, _make_provider_toggle_cb, _make_tag_toggle_cb helpers
affects: [future phases using main_window.py filter state]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Gtk.ToggleButton chip strips in Gtk.ScrolledWindow rows for horizontal overflow
    - _rebuilding guard flag prevents toggled signals firing during chip creation/clear
    - Callback factory pattern (_make_provider_toggle_cb) captures name in closure
    - Dismiss button (window-close-symbolic) calls btn.set_active(False) — fires toggled signal rather than calling _on_filter_changed directly

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Chip x dismiss calls btn.set_active(False) which fires toggled — no duplicate _on_filter_changed call needed"
  - "_rebuilding guard in both _rebuild_filter_state and _on_clear prevents spurious filter updates during state changes"
  - "tag_set casefolded at _render_list call site — no mutation of _selected_tags storage"

patterns-established:
  - "Pattern: _rebuilding flag wraps any bulk chip state mutation to suppress toggled callbacks"
  - "Pattern: callback factory returns closure capturing provider/tag name — avoids late-binding pitfall"

requirements-completed: [BROWSE-02, BROWSE-03]

# Metrics
duration: 10min
completed: 2026-03-22
---

# Phase 08 Plan 02: Filter Bar Multi-Select Summary

**Gtk.DropDown provider/tag filters replaced with scrollable Gtk.ToggleButton chip strips supporting OR-within-dimension, AND-between-dimensions multi-select**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-22T19:30:00Z
- **Completed:** 2026-03-22T19:40:00Z
- **Tasks:** 1 of 2 (Task 2 is human-verify checkpoint)
- **Files modified:** 1

## Accomplishments

- Removed provider_dropdown and tag_dropdown (Gtk.DropDown) entirely from main_window.py
- Added two Gtk.ScrolledWindow chip rows (provider + tag) with Gtk.ToggleButton chips
- _rebuild_filter_state now populates chip boxes from station data, restoring prior selection
- _selected_providers and _selected_tags sets drive filter state through matches_filter_multi
- _on_clear iterates chip button lists and clears sets with _rebuilding guard
- _any_filter_active checks set membership (bool()) instead of dropdown index

## Task Commits

1. **Task 1: Replace DropDown widgets with chip strips and wire multi-select filter logic** - `e0c1701` (feat)

## Files Created/Modified

- `musicstreamer/ui/main_window.py` - DropDowns replaced with chip strips; filter logic wired to matches_filter_multi

## Decisions Made

- Chip x dismiss calls `btn.set_active(False)` which fires the `toggled` signal naturally — avoids calling `_on_filter_changed` twice (D-03)
- `_rebuilding` flag wraps bulk mutations in both `_rebuild_filter_state` and `_on_clear` to prevent spurious filter updates
- Tag set casefolded at call site in `_render_list` — `_selected_tags` stores display form as entered, casefold applied only at match time

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Task 2 (checkpoint:human-verify) is pending — user needs to launch app and verify chip filter behavior visually
- Once approved: BROWSE-02 and BROWSE-03 requirements are complete

---
*Phase: 08-filter-bar-multi-select*
*Completed: 2026-03-22*
