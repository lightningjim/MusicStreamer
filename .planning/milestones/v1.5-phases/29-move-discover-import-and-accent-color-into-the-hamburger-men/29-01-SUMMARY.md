---
phase: 29-move-discover-import-and-accent-color-into-the-hamburger-men
plan: "01"
subsystem: ui
tags: [gtk4, hamburger-menu, header-bar, gio-menu]
dependency_graph:
  requires: []
  provides: [sectioned-hamburger-menu, decluttered-header-bar]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [Gio.Menu.append_section, Gio.SimpleAction loop registration]
key_files:
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "Used append_section(None, ...) for unnamed sections — produces visual separator without a section header label, matching GNOME HIG"
  - "Registered actions via loop to eliminate 3 identical SimpleAction registration blocks"
metrics:
  duration: ~5 min
  completed: 2026-04-09
  tasks_completed: 1
  tasks_total: 2
  files_changed: 1
---

# Phase 29 Plan 01: Move Discover/Import/Accent into Hamburger Menu Summary

Restructured header bar — removed three inline buttons (Discover, Import, Accent Color) and placed them into a two-section Gio.Menu under the existing hamburger MenuButton, using app-level SimpleActions.

## What Was Built

- Deleted `discover_btn`, `import_btn`, and `accent_btn` from the header bar construction block
- Replaced the flat single-item `Gio.Menu` with two `append_section` groups:
  - **Top section (station actions):** "Discover Stations…" (`app.open-discovery`), "Import Stations…" (`app.open-import`)
  - **Bottom section (settings):** "Accent Color…" (`app.open-accent`), "YouTube Cookies…" (`app.open-cookies`)
- Registered `open-discovery`, `open-import`, `open-accent` as `Gio.SimpleAction` objects on the app via a loop; kept `open-cookies` registration unchanged
- Header bar now contains only the search entry (`set_title_widget`) and the hamburger `MenuButton`

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Restructure hamburger menu and remove header bar buttons | b68f7c0 | musicstreamer/ui/main_window.py |

## Deviations from Plan

None — plan executed exactly as written.

## Awaiting Human Verification (Task 2 — checkpoint:human-verify)

Launch: `cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m musicstreamer`

Verify:
1. Header bar shows ONLY search entry + hamburger button — no Discover, Import, or Accent buttons
2. Hamburger opens with top section: "Discover Stations…" and "Import Stations…"
3. Visual separator between sections
4. Bottom section: "Accent Color…" and "YouTube Cookies…"
5. All four items open their respective dialogs

## Known Stubs

None.

## Threat Flags

None — UI-only reorganization, no new trust boundaries.

## Self-Check: PASSED

- `musicstreamer/ui/main_window.py` — exists and syntax-valid (ast.parse)
- Commit b68f7c0 — verified in git log
- 2 `append_section` calls — confirmed
- 0 occurrences of `discover_btn`, `import_btn`, `accent_btn` — confirmed
- All 4 action names present in source — confirmed
