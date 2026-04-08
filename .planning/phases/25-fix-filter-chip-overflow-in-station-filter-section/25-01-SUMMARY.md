---
phase: 25-fix-filter-chip-overflow-in-station-filter-section
plan: "01"
subsystem: ui
tags: [gtk4, flowbox, filter-bar, layout]
dependency_graph:
  requires: []
  provides: [FlowBox-based provider and tag chip containers in main_window filter bar]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [Gtk.FlowBox wrapping chip container (matches Phase 24 edit_dialog.py pattern)]
key_files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "D-03: Matched Phase 24 FlowBox config exactly (8px column spacing, 4px row spacing, hexpand=False)"
metrics:
  completed: 2026-04-08
---

# Phase 25 Plan 01: Replace ScrolledWindow chip containers with FlowBox Summary

Replaced horizontal-scrolling ScrolledWindow+Box filter chip containers with wrapping Gtk.FlowBox containers in main_window.py filter bar.

## What Was Built

Replaced two ScrolledWindow-based chip containers (`_provider_scroll`/`_provider_chip_box` and `_tag_scroll`/`_tag_chip_box`) with `Gtk.FlowBox` instances (`_provider_flow` and `_tag_flow`). Updated `_rebuild_filter_state` to use the new attribute names. All chip logic (toggle callbacks, `_provider_chip_btns`, `_tag_chip_btns`, `_rebuilding` flag, `_make_chip`) unchanged.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace ScrolledWindow chip containers with FlowBox | 8abb89c | musicstreamer/ui/main_window.py |
| 2 | Visual verification of filter chip wrapping | checkpoint:human-verify | — |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — layout-only change, no new trust boundaries.

## Self-Check: PASSED

- musicstreamer/ui/main_window.py: modified (confirmed)
- Commit 8abb89c: exists (confirmed)
- `_provider_flow = Gtk.FlowBox()`: 1 occurrence
- `_tag_flow = Gtk.FlowBox()`: 1 occurrence
- `_provider_scroll`, `_tag_scroll`, `_provider_chip_box`, `_tag_chip_box`: 0 occurrences
- `python -c "import musicstreamer.ui.main_window"`: exits 0
