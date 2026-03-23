---
phase: 10-now-playing-audio
plan: 02
subsystem: ui
tags: [gtk, volume, now-playing, provider, gstreamer, persistence]

requires:
  - phase: 10-now-playing-audio
    plan: 01
    provides: Player.set_volume(float) API

provides:
  - provider name display in station_name_label ("Name · Provider" format)
  - Gtk.Scale volume slider in now-playing center column
  - Volume persistence via repo.get_setting/set_setting("volume")
  - Initial volume applied to GStreamer pipeline on startup

affects:
  - musicstreamer/ui/main_window.py

tech-stack:
  added: []
  patterns:
    - "Gtk.Scale.new_with_range with set_draw_value(False) for clean slider UI"
    - "value-changed signal -> player.set_volume(val/100.0) + repo.set_setting"
    - "provider_name conditional in _play_station: 'Name · Provider' or just name"

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "Middle dot U+00B7 with single spaces: 'Name · Provider' — per D-01/D-02 locked decisions"
  - "Default volume 80 (not 100) — avoids blasting on first launch"
  - "No debounce on volume slider — local GStreamer property write is fast enough"

requirements-completed:
  - NP-01
  - AUDIO-01
  - AUDIO-02

duration: 4min
completed: 2026-03-23
---

# Phase 10 Plan 02: Provider label formatting and volume slider

**Provider name shown inline as "Name · Provider" in now-playing label; Gtk.Scale volume slider wired to GStreamer and persisted via settings — 85 tests green**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-23T02:45:48Z
- **Completed:** 2026-03-23T02:49:48Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `_play_station` now shows `"Station · Provider"` when `provider_name` is set, plain name otherwise (NP-01)
- `volume_slider` (`Gtk.Scale`, 0-100, no value display) appended below stop button in center column
- `_on_volume_changed` handler: converts 0-100 int to float, calls `player.set_volume`, persists via `repo.set_setting`
- Initial volume loaded from settings and applied to GStreamer pipeline before `reload_list()`

## Task Commits

1. **Task 1: Provider name in station_name_label (NP-01)** - `9eafa7b` (feat)
2. **Task 2: Volume slider with persistence (AUDIO-01, AUDIO-02)** - `f828006` (feat)

## Files Created/Modified

- `musicstreamer/ui/main_window.py` - Provider label formatting in `_play_station`; `volume_slider` widget; `_on_volume_changed` handler; initial volume applied in `__init__`

## Decisions Made

- `get_setting("volume", "80")` default — 80% is reasonable on first launch, avoids full blast
- No mute button — slide to zero is sufficient for scope
- `_on_volume_changed` placed in Playback section after `_stop` for logical grouping

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `musicstreamer/ui/main_window.py` — exists and contains all required symbols
- Commit `9eafa7b` — Task 1 present in git log
- Commit `f828006` — Task 2 present in git log
- 85 tests pass
