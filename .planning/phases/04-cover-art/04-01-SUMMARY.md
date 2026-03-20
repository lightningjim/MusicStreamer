---
phase: 04-cover-art
plan: 01
subsystem: ui
tags: [gtk4, gtkstack, itunes-api, gdkpixbuf, threading, urllib]

# Dependency graph
requires:
  - phase: 03-icy-metadata-display
    provides: TAG bus on_title callback, GLib.idle_add pattern, GdkPixbuf pre-scaling, cover_placeholder right slot
provides:
  - iTunes Search API cover art fetch with junk detection and session dedup
  - cover_stack Gtk.Stack widget replacing cover_placeholder in now-playing panel
  - TAG-driven art updates wired through on_title closure in _play_station
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "fetch_cover_art uses daemon threading.Thread; UI update via GLib.idle_add nested closure"
    - "Gtk.Stack named children (fallback/art) swapped via set_visible_child_name — mirrors logo_stack pattern"
    - "GdkPixbuf.new_from_file_at_scale for 160x160 pre-scaling before set_from_pixbuf"
    - "_last_cover_icy string for session-level dedup — cleared on stop"

key-files:
  created:
    - musicstreamer/cover_art.py
    - tests/test_cover_art.py
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "stdlib urllib.request used for HTTP (no extra dependency)"
  - "Temp file for image bytes — GdkPixbuf.new_from_file_at_scale requires a path, not bytes"
  - "Keep old art during in-flight request — no placeholder flash between tracks"
  - "_on_cover_art is a method on MainWindow; on_title local closure in _play_station dispatches to it"

patterns-established:
  - "cover_stack: same Gtk.Stack(fallback, art) pattern as logo_stack — extend _stop() for symmetry"
  - "fetch_cover_art callback invoked from background thread — caller always wraps in GLib.idle_add"

requirements-completed: [NOW-05, NOW-06]

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 4 Plan 01: Cover Art Summary

**iTunes Search API cover art fetched on ICY TAG messages, displayed in 160x160 Gtk.Stack right slot with junk detection, session dedup, and stop reset**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-20T23:02:45Z
- **Completed:** 2026-03-20T23:05:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `cover_art.py` module: JUNK_TITLES set, junk detection, iTunes query builder, JSON artwork URL parser, threaded fetch with tempfile callback
- `cover_stack` Gtk.Stack replaces `cover_placeholder` — identical structure to `logo_stack` (fallback + art, 160x160)
- TAG-driven art updates: on_title closure calls `_on_cover_art`, which deduplicates, skips junk, fetches iTunes in background, and swaps stack via GLib.idle_add
- Stop resets both `cover_stack` to fallback and clears `_last_cover_icy`
- 5 unit tests all passing (junk detection, query building, JSON parsing)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for cover_art** - `378eb2d` (test)
2. **Task 1 GREEN: cover_art.py implementation** - `837b41b` (feat)
3. **Task 2: Wire cover_stack into main_window** - `b78dccb` (feat)

## Files Created/Modified

- `musicstreamer/cover_art.py` - iTunes Search API fetch, junk detection, artwork URL parser, threaded fetch_cover_art
- `tests/test_cover_art.py` - Unit tests for is_junk_title, _build_itunes_query, _parse_artwork_url
- `musicstreamer/ui/main_window.py` - cover_stack widget, _on_cover_art method, GLib/cover_art imports, _stop and _play_station wiring

## Decisions Made

- Used `tempfile.NamedTemporaryFile` because GdkPixbuf.new_from_file_at_scale requires a file path, not raw bytes
- `_on_title` local closure in `_play_station` dispatches to both title_label and `_on_cover_art` — keeps on_title callback signature unchanged in Player
- os.unlink in `finally` block of _update_ui cleans up temp file after display

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. iTunes Search API requires no key.

## Next Phase Readiness

Phase 04 is now complete. The now-playing panel has live cover art from iTunes alongside the station logo and ICY track title. No further phases planned in the roadmap.

---
*Phase: 04-cover-art*
*Completed: 2026-03-20*
