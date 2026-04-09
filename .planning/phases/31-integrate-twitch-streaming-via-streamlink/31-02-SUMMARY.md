---
phase: 31-integrate-twitch-streaming-via-streamlink
plan: "02"
subsystem: ui
tags: [twitch, offline, toast, timer, callback]
dependency_graph:
  requires: [31-01]
  provides: [TWITCH-07, TWITCH-08]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [GLib.idle_add callback, toast notification, timer pause]
key_files:
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "Offline callback pauses timer without stopping playback — station stays selected (matches D-05 'like pause' semantics)"
  - "on_offline wired to both player.play() and player.play_stream() for consistency"
metrics:
  duration: "5 min"
  completed: "2026-04-09"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 1
---

# Phase 31 Plan 02: Wire Twitch Offline Callback Summary

**One-liner:** Twitch offline callback wired from player to main_window showing "[channel] is offline" toast and pausing elapsed timer without disrupting now-playing UI.

## What Was Built

Added `_on_twitch_offline(channel: str)` to `MainWindow` and wired it into both `player.play()` and `player.play_stream()` call sites. When a Twitch channel is offline, the player fires the callback via `GLib.idle_add`, which triggers a 5-second toast and pauses the elapsed timer — the station remains selected and now-playing stays visible.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire on_offline callback and toast | a26faaf | musicstreamer/ui/main_window.py |
| 2 | Verify Twitch playback end-to-end | ⚡ Auto-approved | — |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — T-31-03 accepted: channel name in toast is public information (Twitch URLs are not sensitive).

## Self-Check: PASSED

- `def _on_twitch_offline` present in main_window.py: FOUND
- `on_offline=self._on_twitch_offline` in player.play(): FOUND
- `on_offline=self._on_twitch_offline` in player.play_stream(): FOUND
- Commit a26faaf: FOUND
- 255 tests passing: CONFIRMED
