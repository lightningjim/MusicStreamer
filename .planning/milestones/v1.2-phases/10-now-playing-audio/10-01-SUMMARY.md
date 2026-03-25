---
phase: 10-now-playing-audio
plan: 01
subsystem: audio
tags: [gstreamer, mpv, volume, player, tdd, pytest]

requires:
  - phase: 06-station-management
    provides: Player class with GStreamer playbin3 pipeline and mpv subprocess

provides:
  - Player.set_volume(float) method with [0.0, 1.0] clamping
  - self._volume instance variable storing current volume for mpv launch
  - GStreamer set_property("volume", clamped) on every set_volume call
  - mpv --volume arg derived from _volume in _play_youtube

affects:
  - 10-02 (volume slider UI wires set_volume)

tech-stack:
  added: []
  patterns:
    - "Volume clamping: max(0.0, min(1.0, value)) before applying to GStreamer"
    - "mpv volume: store float 0.0-1.0, convert to int 0-100 at Popen call site"

key-files:
  created:
    - tests/test_player_volume.py
  modified:
    - musicstreamer/player.py

key-decisions:
  - "Store _volume as float 0.0-1.0 (not int 0-100) so GStreamer and mpv both derive from single source"
  - "mpv volume applied only at launch (--volume arg) — no live IPC adjustment needed per AUDIO-01 scope"

patterns-established:
  - "Player.set_volume(float): clamp -> store _volume -> set_property('volume', clamped)"

requirements-completed:
  - AUDIO-01

duration: 1min
completed: 2026-03-23
---

# Phase 10 Plan 01: Player.set_volume with GStreamer volume property and mpv --volume arg

**Player.set_volume clamps float to [0.0, 1.0], writes GStreamer pipeline volume property, stores for mpv subprocess launch — 4 TDD tests pass, 85-test suite green**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-23T02:45:22Z
- **Completed:** 2026-03-23T02:46:39Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- `Player.set_volume(float)` method with clamping to [0.0, 1.0]
- `self._volume = 1.0` default in `__init__`, updated on every `set_volume` call
- `_play_youtube` passes `f"--volume={int(self._volume * 100)}"` to mpv Popen
- 4-test file covering normal value, clamp-high, clamp-low, and _volume attribute storage

## Task Commits

1. **Task 1: TDD Player.set_volume with clamping and mpv --volume arg** - `e8f2895` (feat)

## Files Created/Modified

- `musicstreamer/player.py` - Added `_volume = 1.0` to `__init__`, `set_volume` method, mpv `--volume` arg in `_play_youtube`
- `tests/test_player_volume.py` - 4 unit tests using `make_player()` pattern from existing test suite

## Decisions Made

- Used `make_player()` helper (same pattern as `test_player_tag.py`) rather than inline patch-per-test for consistency
- `_volume` stored as float 0.0-1.0 (not int 0-100) — single source of truth, converted to int at mpv call site only

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `uv run --with pytest` can't find `gi` module — resolved by using `python3 -m pytest` with `PYTHONPATH` pointing to the worktree. This matches how the existing test suite is run in this project.

## Next Phase Readiness

- `Player.set_volume` API is ready for Plan 02 (volume slider UI)
- Plan 02 will: add `Gtk.Scale` to main window center column, load initial volume from `repo.get_setting("volume", "80")`, wire `value-changed` to call `self.player.set_volume(val / 100.0)` and `repo.set_setting`

---
*Phase: 10-now-playing-audio*
*Completed: 2026-03-23*
