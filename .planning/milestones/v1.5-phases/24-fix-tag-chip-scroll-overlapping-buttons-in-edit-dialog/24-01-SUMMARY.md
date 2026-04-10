---
phase: 24-fix-tag-chip-scroll-overlapping-buttons-in-edit-dialog
plan: "01"
subsystem: ui
tags: [layout, gtk4, flowbox, tag-chips]
dependency_graph:
  requires: []
  provides: [FlowBox-based tag chip container in edit_dialog.py]
  affects: [musicstreamer/ui/edit_dialog.py]
tech_stack:
  added: []
  patterns: [Gtk.FlowBox for wrapping chip layout]
key_files:
  created: []
  modified:
    - musicstreamer/ui/edit_dialog.py
decisions:
  - "FlowBox with NONE selection mode replaces ScrolledWindow+Box; toggle logic stays in ToggleButton handlers"
  - "hexpand=False on FlowBox is critical to prevent column 1 overflow"
metrics:
  duration: ~5min
  completed: 2026-04-08
  tasks_completed: 1
  tasks_total: 2
  files_changed: 1
---

# Phase 24 Plan 01: Replace ScrolledWindow Tag Chips with FlowBox Summary

**One-liner:** Replaced horizontal-scrolling tag chip container with Gtk.FlowBox that wraps chips at column boundary, eliminating overlap with Save/Delete buttons.

## What Was Built

`musicstreamer/ui/edit_dialog.py` tag chip section (lines ~234–258) was reworked:

- Removed `chip_scroll` (`Gtk.ScrolledWindow`) and the wrapping horizontal `Gtk.Box`
- Added `self._chip_box = Gtk.FlowBox()` with `SelectionMode.NONE`, 8px column spacing, 4px row spacing, `hexpand=False`, and existing margins (4/4/8/8)
- `tags_box` now appends `self._chip_box` directly (no scroll wrapper)
- `_on_tag_chip_toggled`, `_selected_tags`, `_tag_chip_btns`, and `new_tag_entry` are untouched

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 22b1f9f | feat(24-01): replace ScrolledWindow chip container with FlowBox |

## Deviations from Plan

None — plan executed exactly as written.

## Checkpoint Pending

Task 2 (`checkpoint:human-verify`) requires visual confirmation that:
- Chips wrap to multiple lines instead of scrolling
- No overlap with Save/Delete buttons
- Toggle and new tag entry still functional

## Known Stubs

None.

## Threat Flags

None — layout-only change, no new trust boundaries.

## Self-Check: PASSED

- `musicstreamer/ui/edit_dialog.py` exists and imports cleanly
- Commit `22b1f9f` present in git log
- `grep "Gtk.FlowBox"` returns 1 match
- `grep "chip_scroll"` returns 0 matches
