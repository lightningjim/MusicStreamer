---
phase: 28-stream-failover-logic-with-server-round-robin-and-quality-fa
plan: "02"
subsystem: ui
tags: [toast, stream-picker, failover-ui, main-window, adwaita]
dependency_graph:
  requires: [28-01]
  provides: [failover-toast-notifications, stream-picker-ui]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [Adw.ToastOverlay for notifications, Gtk.MenuButton+Popover for stream picker, GLib.idle_add for cross-thread callback]
key_files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "toast_overlay wraps scroller and all empty-state pages — shell.set_content(toast_overlay) is permanent; child swaps happen on toast_overlay"
  - "stream_btn hidden for 0-or-1 stream stations; only shown when 2+ streams available"
  - "_on_player_failover returns False (GLib.idle_add contract) and shows stream label not full URL (T-28-05 mitigation)"
  - "GLib.markup_escape_text applied to stream labels in popover rows (labels may contain special chars)"
metrics:
  duration: "~8 min"
  completed: "2026-04-09"
  tasks_completed: 1
  files_changed: 1
---

# Phase 28 Plan 02: Failover UI Summary

**One-liner:** ToastOverlay wrapping content area with auto-dismissing failover toasts and a MenuButton stream picker that shows quality badges and active-stream checkmark.

## What Was Built

Modified `musicstreamer/ui/main_window.py` to wire up the failover UI from Plan 01's player backend.

### Key Changes in `musicstreamer/ui/main_window.py`

**Structural change — ToastOverlay wrapping (D-06):**
- Added `self.toast_overlay = Adw.ToastOverlay()` wrapping `scroller`
- `shell.set_content(self.toast_overlay)` is now permanent
- All empty-state swaps updated: `self.toast_overlay.set_child(...)` instead of `self.shell.set_content(...)`
  - `_rebuild_grouped`: empty_page / scroller
  - `_rebuild_flat`: empty_page / scroller
  - `_render_favorites`: favorites_empty / scroller

**New controls_box button — stream picker (D-07):**
- `self.stream_btn = Gtk.MenuButton()` with `network-wireless-symbolic` icon
- Added after `stop_btn` in `controls_box`
- `set_visible(False)` by default; hidden again in `_stop()`

**New methods:**
- `_show_toast(message, timeout=3)` — creates `Adw.Toast`, sets timeout, calls `toast_overlay.add_toast()`
- `_on_player_failover(stream)` — called via `GLib.idle_add` from player; shows toast with stream label (not URL) for T-28-05 compliance; returns `False` per idle_add contract
- `_update_stream_picker(station)` — rebuilds popover with sorted streams, quality badges, active-stream checkmark (emblem-ok-symbolic); uses `GLib.markup_escape_text` on labels
- `_on_stream_picker_row_activated(listbox, row)` — pops down popover, calls `player.play_stream()` with failover callback, refreshes picker

**Updated `_play_station` (D-04, D-06, D-08):**
- Reads `preferred_quality` from settings via `QUALITY_SETTING_KEY`
- Passes `preferred_quality` and `on_failover=self._on_player_failover` to `player.play()`
- Calls `self._update_stream_picker(st)` after starting playback

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

T-28-05 (Information Disclosure via toast message) mitigated: `_on_player_failover` shows `stream.label or stream.url[:40]` — truncated URL, not full URL which may contain API keys for AudioAddict streams.

No new threat surface introduced.

## Self-Check: PASSED

- `musicstreamer/ui/main_window.py` — FOUND
- Commit `3caeb61` — FOUND
- 244 tests passing
