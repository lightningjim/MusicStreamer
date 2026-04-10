---
phase: 31-integrate-twitch-streaming-via-streamlink
plan: "01"
subsystem: player
tags: [twitch, streamlink, playback, tdd, threading]
dependency_graph:
  requires: []
  provides: [twitch-url-detection, streamlink-resolution, offline-detection, gst-error-re-resolve]
  affects: [musicstreamer/player.py]
tech_stack:
  added: [threading (stdlib)]
  patterns: [daemon-thread + GLib.idle_add for background subprocess, list args subprocess.run (no shell=True)]
key_files:
  created: [tests/test_twitch_playback.py]
  modified: [musicstreamer/player.py]
decisions:
  - "Use list args (not shell=True) for subprocess.run — satisfies T-31-01 (Tampering threat)"
  - "Re-resolve bounded to one attempt per stream to avoid infinite retry loops"
  - "on_offline callback does NOT call _try_next_stream — offline is terminal for that channel (D-05)"
  - "Twitch excluded from failover timer guard — streamlink handles its own timing"
metrics:
  duration: ~8min
  completed: "2026-04-09"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
---

# Phase 31 Plan 01: TDD — Twitch Playback via streamlink Summary

**One-liner:** Twitch URL detection routed to streamlink subprocess resolution with live/offline/error handling and bounded GStreamer error re-resolve.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Add failing Twitch playback tests | 5d2f031 | tests/test_twitch_playback.py (created, 11 tests) |
| GREEN | Implement Twitch playback via streamlink | 50c4576 | musicstreamer/player.py |

## What Was Built

`_play_twitch(url)` method in `Player`:
- Builds env with `~/.local/bin` on PATH (same pattern as `_play_youtube`)
- Spawns daemon thread running `subprocess.run(["streamlink", "--stream-url", url, "best"], capture_output=True, text=True)`
- On exit 0 + stdout starts with "http": `GLib.idle_add(_on_twitch_resolved, resolved_url)` → `_set_uri`
- On "No playable streams found" in stdout: `GLib.idle_add(_on_twitch_offline, url)` → calls `on_offline(channel)`, no failover
- On other error: `GLib.idle_add(_on_twitch_error)` → `_try_next_stream()`

Detection/routing in `_try_next_stream()`:
- `elif "twitch.tv" in url:` branch between YouTube and default
- Failover timer guard extended to exclude `"twitch.tv" not in url`

GStreamer error re-resolve in `_on_gst_error()`:
- Checks `_current_stream.url` for "twitch.tv" and `_twitch_resolve_attempts < 1`
- Re-resolves once; second error falls through to `_try_next_stream()`

New public interface additions:
- `play(on_offline=None)` — stored as `self._on_offline`, resets `_twitch_resolve_attempts = 0`
- `play_stream(on_offline=None)` — stored as `self._on_offline`

## Verification

- `python -m pytest tests/test_twitch_playback.py -x -q` — 11/11 passed
- `python -m pytest tests/ -x -q` — 255/255 passed (no regressions)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all behavior is fully implemented and tested.

## Threat Flags

None — T-31-01 mitigated as designed (list args, no shell=True). T-31-02 accepted (streamlink stdout parsed, malformed URL rejected by GStreamer).

## Self-Check: PASSED

- tests/test_twitch_playback.py: FOUND
- musicstreamer/player.py (modified): FOUND
- Commit 5d2f031 (RED): FOUND
- Commit 50c4576 (GREEN): FOUND
