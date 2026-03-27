---
phase: 11-ui-polish
plan: 02
subsystem: ui
tags: [gtk4, css, border-radius, overflow, python]

requires:
  - phase: 11-01
    provides: UI polish foundation established

provides:
  - Visible 5px rounded corners on station logo and cover art in now-playing panel

affects: []

tech-stack:
  added: []
  patterns: [GTK4 border-radius clipping requires both CSS background node and widget-level Gtk.Overflow.HIDDEN]

key-files:
  created: []
  modified:
    - musicstreamer/__main__.py
    - musicstreamer/ui/main_window.py

key-decisions:
  - "CSS overflow:hidden alone is insufficient in GTK4 — must call set_overflow(Gtk.Overflow.HIDDEN) at the widget API level to clip child paint nodes"

patterns-established:
  - "GTK4 rounded image clipping: border-radius + background-color:transparent in CSS, plus set_overflow(Gtk.Overflow.HIDDEN) on the container widget"

requirements-completed: [UI-03]

duration: 15min
completed: 2026-03-27
---

# Phase 11-02: Fix Station Art Border-Radius Clipping Summary

**GTK4 border-radius now clips station art via widget-level Gtk.Overflow.HIDDEN on logo_stack and cover_stack**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-03-27
- **Tasks:** 2 (1 auto + 1 human verify)
- **Files modified:** 2

## Accomplishments
- Added `background-color: transparent` and `overflow: hidden` to `.now-playing-art` CSS rule
- Discovered CSS overflow alone insufficient; added `set_overflow(Gtk.Overflow.HIDDEN)` to both Gtk.Stack widgets
- User confirmed visible 5px rounded corners on station art

## Task Commits

1. **Task 1: Fix .now-playing-art CSS rule** - `b6556d2` (fix)
2. **Task 1b: Set widget-level overflow after CSS insufficient** - `783438d` (fix)

## Files Created/Modified
- `musicstreamer/__main__.py` - Added background-color and overflow to .now-playing-art CSS rule
- `musicstreamer/ui/main_window.py` - Added set_overflow(Gtk.Overflow.HIDDEN) to logo_stack and cover_stack

## Decisions Made
GTK4's CSS `overflow: hidden` creates a clip hint but does not reliably clip child `Gtk.Image` paint nodes inside a `Gtk.Stack`. Setting `set_overflow(Gtk.Overflow.HIDDEN)` directly on the widget forces GTK's render node pipeline to clip children to the widget boundary, which combined with the CSS `border-radius` produces the expected visual rounding.

## Deviations from Plan

### Auto-fixed Issues

**1. CSS fix insufficient — required widget API override**
- **Found during:** Human verification checkpoint
- **Issue:** CSS `overflow: hidden` did not visually clip children in GTK4 Gtk.Stack
- **Fix:** Added `set_overflow(Gtk.Overflow.HIDDEN)` to both logo_stack and cover_stack in main_window.py
- **Files modified:** musicstreamer/ui/main_window.py
- **Verification:** User confirmed rounded corners visible in running app
- **Committed in:** `783438d`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** Required additional widget-level change beyond CSS; no scope creep.

## Issues Encountered
GTK4 does not reliably honor CSS `overflow: hidden` for clipping child widget paint nodes. Widget-level API call is authoritative.

## Next Phase Readiness
Phase 11 gap closure complete. UAT test 3 closed.

---
*Phase: 11-ui-polish*
*Completed: 2026-03-27*
