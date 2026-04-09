---
phase: 26-fix-broken-edit-button-next-to-add-station
plan: "01"
subsystem: ui
tags: [bug-fix, ui, filter-bar, now-playing, edit-button]
dependency_graph:
  requires: []
  provides: [now-playing-edit-button]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [gtk-button-sensitivity, icon-button-flat]
key_files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
decisions:
  - "Replace _edit_selected (listbox selection) with _on_edit_playing_clicked (_current_station or _paused_station) — avoids ExpanderRow child selection issue"
  - "Edit button placed after star_btn in controls_box, before pause_btn — groups edit with other per-station actions"
metrics:
  duration: ~8min
  completed: 2026-04-08
  tasks: 2
  files: 3
---

# Phase 26 Plan 01: Remove Filter Bar Edit Button, Add Now-Playing Edit Icon — Summary

**One-liner:** Replaced non-functional filter bar Edit button (broken listbox selection) with a flat pencil icon in the now-playing controls that opens the editor for the currently playing or paused station.

## What Was Built

- Removed `_edit_selected` method and the `edit_btn = Gtk.Button(label="Edit")` from the filter bar
- Added `self.edit_btn` with `document-edit-symbolic` icon and `flat` CSS class to `controls_box` (after `star_btn`)
- Edit button starts insensitive; enabled in `_play_station()` callback alongside `pause_btn`/`stop_btn`; disabled in `_stop()` alongside `stop_btn`
- New handler `_on_edit_playing_clicked` uses `self._current_station or self._paused_station` to open the editor
- Filter bar now appends: `add_btn`, `chip_scroll`, `self.clear_btn` (3 items, no edit button)
- FIX-06 added to REQUIREMENTS.md with traceability; ROADMAP.md Phase 26 progress table updated

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Remove filter bar Edit button, add now-playing edit button | c601aca | musicstreamer/ui/main_window.py |
| 2 | Add FIX-06 requirement and update ROADMAP | d21ea0b | .planning/REQUIREMENTS.md, .planning/ROADMAP.md |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — UI button wiring only; no new network endpoints, auth paths, or file I/O.

## Self-Check: PASSED

- musicstreamer/ui/main_window.py: FOUND
- Commit c601aca (feat): FOUND
- Commit d21ea0b (chore): FOUND
