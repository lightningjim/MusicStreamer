---
phase: 30-add-time-counter-showing-how-long-current-stream-has-been-ac
plan: "01"
subsystem: ui
tags: [timer, now-playing, gtk, glib]
one_liner: "Elapsed time counter with GLib tick source, M:SS/H:MM:SS format, full play/pause/stop lifecycle wiring"

dependency_graph:
  requires: []
  provides: [elapsed-time-counter]
  affects: [musicstreamer/ui/main_window.py]

tech_stack:
  added: []
  patterns: [GLib.timeout_add_seconds, GLib.source_remove, Gtk.Label dim-label]

key_files:
  modified:
    - musicstreamer/ui/main_window.py

key_decisions:
  - _start_timer always calls _stop_timer first to prevent GLib source leaks (T-30-01 mitigation)
  - Resume path saves/restores _elapsed_seconds around _play_station call so counter is not reset on unpause
  - timer_row inserted between station_name_label and controls_box in center column
  - _resume_timer defined but resume goes through _play_station; saved_elapsed pattern used instead for correctness

metrics:
  duration_minutes: 5
  completed_date: "2026-04-09"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 30 Plan 01: Elapsed Time Counter Summary

Elapsed time counter with GLib tick source, M:SS/H:MM:SS format, full play/pause/stop lifecycle wiring.

## What Was Built

Added an elapsed time counter row to the now-playing panel in `musicstreamer/ui/main_window.py`:

- `timer_row`: `Gtk.Box(HORIZONTAL)` with `timer-symbolic` icon (16px, dim-label) and `timer_label` (dim-label), hidden by default, inserted between `station_name_label` and `controls_box`
- `_elapsed_seconds: int` and `_timer_source_id: int | None` instance variables
- 7 timer helper methods: `_format_elapsed`, `_update_timer_label`, `_on_timer_tick`, `_start_timer`, `_pause_timer`, `_resume_timer`, `_stop_timer`
- Lifecycle wiring: `_play_station` → `_start_timer()`, `_stop` → `_stop_timer()`, `_toggle_pause` pause branch → `_pause_timer()`, resume branch → save/restore `_elapsed_seconds` around `_play_station`

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 29cd144 | feat(30-01): add timer row widget and helper methods |
| 2 | a01fa7e | feat(30-01): wire timer into play/pause/stop lifecycle |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. GLib source leak mitigation (T-30-01) applied as designed.

## Self-Check: PASSED

- musicstreamer/ui/main_window.py modified: confirmed
- Commit 29cd144 exists: confirmed
- Commit a01fa7e exists: confirmed
- All 7 timer methods present: verified by automated check
- Format logic correct (0:00, 1:01, 1:01:01, 1:00:00, 0:59): verified
- Lifecycle wiring (_play_station/_stop/_toggle_pause): verified by AST check
