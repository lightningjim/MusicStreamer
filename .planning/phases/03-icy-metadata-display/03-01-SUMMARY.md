---
phase: 03-icy-metadata-display
plan: 01
subsystem: player
tags: [gstreamer, icy, metadata, tdd, python, glib]

# Dependency graph
requires:
  - phase: 01-module-extraction
    provides: Player class with on_title callback pattern and GStreamer pipeline setup
provides:
  - _fix_icy_encoding module-level function for latin-1 mojibake correction
  - Player._on_gst_tag method wired to message::tag bus signal
  - Player._on_title instance attribute lifecycle (set on play, cleared on stop)
affects: [03-02, ui-now-playing, future-track-display]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GStreamer TAG bus handler: connect message::tag, parse_tag(), get_string(Gst.TAG_TITLE)"
    - "ICY encoding fix: encode latin-1 -> decode utf-8, fall through on exception"
    - "GLib.idle_add for cross-thread callback dispatch from GStreamer bus thread to GTK main loop"
    - "Callback lifecycle: stored on play(), cleared to None on stop() to prevent stale updates"

key-files:
  created:
    - tests/test_player_tag.py
  modified:
    - musicstreamer/player.py

key-decisions:
  - "_set_uri no longer calls on_title() directly — ICY TAG bus provides async track title updates; station name set by UI in _play_station"
  - "_play_youtube retains direct on_title(fallback_name) call — mpv has no GStreamer TAG bus"
  - "GLib.idle_add used instead of direct callback — GStreamer bus messages arrive on non-GTK thread"

patterns-established:
  - "TAG handler pattern: parse_tag() -> get_string(TAG_TITLE) -> encoding fix -> idle_add dispatch"
  - "Callback guard: check self._on_title is not None before idle_add (handles post-stop TAG messages)"

requirements-completed: [NOW-01, NOW-02, NOW-03]

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 03 Plan 01: GStreamer TAG Bus Handler Summary

**GStreamer TAG bus handler with latin-1 mojibake correction wired into Player, dispatching track titles to UI via GLib.idle_add**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T02:24:10Z
- **Completed:** 2026-03-20T02:26:32Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- `_fix_icy_encoding` corrects UTF-8 bytes misread as latin-1 (common ICY stream issue) with safe fallthrough
- `_on_gst_tag` extracts `Gst.TAG_TITLE` from bus TAG messages and dispatches via `GLib.idle_add` for GTK thread safety
- `play()` stores callback; `stop()` clears it — stale TAG messages after stop are silently dropped
- 10 new unit tests, all passing; full suite 38/38

## Task Commits

1. **Task 1: RED -- Write failing tests** - `699c4ac` (test)
2. **Task 2: GREEN -- Implement TAG handler and ICY encoding** - `d98ab8e` (feat)

## Files Created/Modified
- `tests/test_player_tag.py` - 10 unit tests covering encoding fix, TAG handler, idle_add dispatch, callback lifecycle
- `musicstreamer/player.py` - Added `_fix_icy_encoding`, `_on_gst_tag`, `message::tag` bus connection, `_on_title` lifecycle

## Decisions Made
- `_set_uri` no longer calls `on_title()` directly. The ICY TAG bus delivers track titles asynchronously; the UI is responsible for showing the station name immediately via `_play_station`. Removing the direct call avoids a redundant/stale title flash on stream start.
- `_play_youtube` retains its direct `on_title(fallback_name)` call because mpv handles YouTube playback outside GStreamer — there is no TAG bus for those streams.
- `GLib.idle_add` instead of direct callback invocation: GStreamer bus signals arrive on a non-GTK thread; idle_add safely marshals the call to the GTK main loop.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- TAG pipeline is fully wired: GStreamer TAG messages -> `_on_gst_tag` -> `_fix_icy_encoding` -> `GLib.idle_add(on_title, title)`
- Ready for Phase 03-02: UI now-playing panel that consumes the `on_title` callback to display track info

---
*Phase: 03-icy-metadata-display*
*Completed: 2026-03-20*
