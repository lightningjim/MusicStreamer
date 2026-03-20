---
phase: 03-icy-metadata-display
plan: 02
subsystem: ui
tags: [gtk, adwaita, gstreamer, icy-metadata, station-logo, now-playing]

# Dependency graph
requires:
  - phase: 03-01
    provides: Player TAG bus handler and on_title callback
  - phase: 02-search-and-filter
    provides: MainWindow filter strip, station list, HeaderBar structure
provides:
  - Three-column now-playing panel (station logo | track title + station name + Stop | cover art placeholder)
  - TAG-driven real-time track title display via on_title callback
  - Station logo loading from station_art_path with GdkPixbuf pre-scaling
  - Idle/playing/stopped UI state transitions
  - Relocated Add/Edit buttons to filter strip; Stop button in panel center
affects:
  - 04-cover-art
  - any phase touching MainWindow layout

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Gtk.Stack for logo/fallback swap (logo vs audio-x-generic-symbolic)
    - GdkPixbuf.Pixbuf pre-scaling before Gtk.Picture.set_pixbuf to avoid GTK downscale artifacts
    - Window close-request signal connected to _stop() for clean mpv teardown

key-files:
  created: []
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "GdkPixbuf pre-scale logo to 160x160 before setting on Gtk.Picture — avoids rendering artifacts from GTK automatic downscaling"
  - "Window close-request connected to _stop() — ensures mpv exits cleanly when window is closed rather than leaving orphan process"

patterns-established:
  - "Gtk.Stack pattern: add fallback child first (named 'fallback'), then content child (named 'logo'), toggle via set_visible_child_name"
  - "Logo loading: os.path.join(DATA_DIR, station_art_path) → GdkPixbuf.Pixbuf.new_from_file_at_scale(160,160,True) → Gtk.Picture.set_pixbuf"

requirements-completed: [NOW-01, NOW-02, NOW-03, NOW-04]

# Metrics
duration: ~90min (includes checkpoint visual verification)
completed: 2026-03-20
---

# Phase 3 Plan 02: Now-Playing Panel Summary

**Three-column now-playing panel with TAG-driven track title, GdkPixbuf-scaled station logo, and clean idle/playing/stopped state transitions**

## Performance

- **Duration:** ~90 min (includes human-verify checkpoint)
- **Started:** 2026-03-20T02:28:03Z
- **Completed:** 2026-03-20T03:48:29Z
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 1

## Accomplishments

- Built three-column now-playing panel inserted as second top bar in Adw.ToolbarView
- Wired TAG bus on_title callback to update title_label in real time from ICY metadata
- Station logo loads from station_art_path via GdkPixbuf pre-scaled to 160x160; falls back to audio-x-generic-symbolic
- Relocated Add/Edit buttons to filter strip; Stop button lives in panel center column
- HeaderBar now contains only the search entry
- Window close-request stops mpv cleanly (no orphan processes)

## Task Commits

1. **Task 1: Build now-playing panel and rewire main_window.py** - `88add3f` (feat)
2. **Task 2: Checkpoint fixes (logo pre-scale + window close)** - `975fce7` (fix)

## Files Created/Modified

- `musicstreamer/ui/main_window.py` - Now-playing panel, button relocation, TAG callback, logo loading, state transitions

## Decisions Made

- **GdkPixbuf pre-scaling:** Gtk.Picture renders logos at wrong aspect ratio when GTK scales down from large source images. Pre-scaling to 160x160 via GdkPixbuf.Pixbuf.new_from_file_at_scale with preserve_aspect=True fixes this.
- **Window close-request:** mpv process was left running after window close. Connected close-request signal to _stop() to ensure clean teardown.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Logo rendering artifacts from GTK auto-downscaling**
- **Found during:** Task 2 (visual verification checkpoint)
- **Issue:** Gtk.Picture was rendering logos with distorted aspect ratio when source images were larger than 96x96 and GTK scaled them down automatically
- **Fix:** Pre-scale via GdkPixbuf.Pixbuf.new_from_file_at_scale(160, 160, True) before calling set_pixbuf on the Gtk.Picture
- **Files modified:** musicstreamer/ui/main_window.py
- **Verification:** User confirmed logo displays correctly at checkpoint
- **Committed in:** 975fce7

**2. [Rule 2 - Missing Critical] Window close leaves mpv orphan process**
- **Found during:** Task 2 (visual verification checkpoint)
- **Issue:** Closing the window did not call _stop(), leaving mpv running in background
- **Fix:** Connected close-request signal to self._stop() in __init__
- **Files modified:** musicstreamer/ui/main_window.py
- **Verification:** User confirmed stop fires on window close at checkpoint
- **Committed in:** 975fce7

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes discovered during visual verification; essential for correct behavior and resource cleanup. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 (cover-art) can now fill the right slot (self.cover_placeholder) with album art from iTunes Search API
- The on_title callback pattern is established — Phase 4 can hook into title changes to trigger art lookups
- Station logo and fallback patterns are set; Phase 4 only needs to wire the right-slot image

---
*Phase: 03-icy-metadata-display*
*Completed: 2026-03-20*
