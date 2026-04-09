---
phase: 29-move-discover-import-and-accent-color-into-the-hamburger-men
plan: "01"
subsystem: ui
tags: [gtk, gio-menu, hamburger-menu, header-bar, gnome]

requires: []
provides:
  - Sectioned hamburger Gio.Menu with Discover, Import, Accent Color, and YouTube Cookies
  - Decluttered header bar (search entry + hamburger button only)
  - SimpleAction registrations for open-discovery, open-import, open-accent
affects: []

tech-stack:
  added: []
  patterns:
    - "Gio.Menu with append_section for grouped menu items in GTK hamburger menus"
    - "SimpleAction loop registration pattern for multiple menu actions"

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Used append_section(None, section) with no label to create visual separator via GTK default styling"
  - "Registered new actions via loop over (name, handler) tuples alongside existing open-cookies action"

patterns-established:
  - "Hamburger menu sections: station actions (top) / settings (bottom)"

requirements-completed: [MENU-01, MENU-02, MENU-03, MENU-04, MENU-05]

duration: 15min
completed: 2026-04-09
---

# Phase 29 Plan 01: Move Discover/Import/Accent Color into Hamburger Menu Summary

**Discover, Import, and Accent Color buttons removed from header bar and reorganized into a two-section Gio.Menu hamburger menu, leaving only search entry and hamburger button in the header.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-09T00:00:00Z
- **Completed:** 2026-04-09T00:15:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Removed `discover_btn`, `import_btn`, and `accent_btn` from header bar construction
- Replaced flat Gio.Menu with two-section layout: station actions (Discover, Import) and settings (Accent Color, YouTube Cookies)
- Registered three new SimpleActions (open-discovery, open-import, open-accent) via loop pattern
- User visually confirmed hamburger menu layout and all four dialog open actions work correctly

## Task Commits

1. **Task 1: Restructure hamburger menu and remove header bar buttons** - `b68f7c0` (feat)
2. **Task 2: Verify hamburger menu layout and dialog opening** - human-verify checkpoint, approved

## Files Created/Modified
- `musicstreamer/ui/main_window.py` - Removed three header bar buttons; restructured Gio.Menu into two sections with SimpleAction registrations

## Decisions Made
- Section labels set to `None` (no visible section heading) so GTK renders a plain separator line between sections — matches GNOME HIG style for grouped menus

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Header bar is decluttered; hamburger menu follows GNOME conventions
- No blockers for subsequent phases

---
*Phase: 29-move-discover-import-and-accent-color-into-the-hamburger-men*
*Completed: 2026-04-09*
