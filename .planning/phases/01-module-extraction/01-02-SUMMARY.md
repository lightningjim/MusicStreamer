---
phase: 01-module-extraction
plan: 02
subsystem: ui
tags: [gtk4, libadwaita, gstreamer, yt-dlp, python, gtk-listbox]

requires:
  - phase: 01-module-extraction plan 01
    provides: data-layer modules (constants, models, repo, assets) that UI imports from

provides:
  - musicstreamer/player.py — Player class with GStreamer playbin, play/stop, yt-dlp YouTube resolution
  - musicstreamer/ui/station_row.py — StationRow(Gtk.ListBoxRow) with full Station object and station_id
  - musicstreamer/ui/edit_dialog.py — EditStationDialog extracted verbatim from main.py
  - musicstreamer/ui/main_window.py — MainWindow wired to Player and StationRow
  - musicstreamer/__main__.py — App entry point with Gst.init, ensure_dirs ordering, App(Adw.Application)
  - org.example.Streamer.desktop — Desktop entry with Exec=python3 -m musicstreamer
  - main.py deleted — monolith is gone

affects:
  - phase 02 (search/filter) — StationRow exposes self.station (full object) for filter_func
  - phase 03 (ICY metadata) — Player._pipeline is instance state, ready for bus message wiring
  - phase 04 (cover art) — StationRow prefix slot used for station_art_path thumbnail

tech-stack:
  added: []
  patterns:
    - "Player class owns GStreamer pipeline state, MainWindow delegates via on_title callback"
    - "StationRow wraps Adw.ActionRow inside Gtk.ListBoxRow to preserve station object reference"
    - "gi.require_version() calls at top of each module before any from gi.repository import"
    - "Gst.init(None) in __main__.py before any Player instantiation"
    - "ensure_dirs() before db_connect() in do_activate — creates DATA_DIR first"

key-files:
  created:
    - musicstreamer/player.py
    - musicstreamer/ui/station_row.py
    - musicstreamer/ui/edit_dialog.py
    - musicstreamer/ui/main_window.py
    - musicstreamer/__main__.py
    - org.example.Streamer.desktop
  modified:
    - main.py (deleted via git rm)

key-decisions:
  - "Player.play() takes on_title callback rather than direct label reference — decouples playback from widget tree"
  - "StationRow subclasses Gtk.ListBoxRow (not Adw.ActionRow) to attach self.station and self.station_id"
  - "Player.stop() only sets pipeline to NULL — MainWindow handles label reset separately"

patterns-established:
  - "Player callback pattern: play(station, on_title=lambda t: ...) for UI decoupling"
  - "Row wrapper pattern: Gtk.ListBoxRow containing Adw.ActionRow, station object on outer widget"

requirements-completed: [CODE-01]

duration: ~15min
completed: 2026-03-18
---

# Phase 1 Plan 2: UI Layer Extraction Summary

**Monolithic main.py eliminated — UI split into Player, StationRow, EditStationDialog, MainWindow, and __main__.py entry point with identical runtime behavior**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-18T22:05:00Z
- **Completed:** 2026-03-18T22:19:24Z
- **Tasks:** 2
- **Files modified:** 7 (6 created, 1 deleted)

## Accomplishments

- Extracted GStreamer playback into `Player` class with callback-based title reporting
- Extracted `StationRow(Gtk.ListBoxRow)` preserving full Station object for Phase 2 filter_func
- Extracted `EditStationDialog` verbatim — zero logic changes
- Wired `MainWindow` to use `Player` and `StationRow` instead of inline implementations
- Created `__main__.py` entry point with correct `Gst.init` / `ensure_dirs` / `db_connect` ordering
- Deleted `main.py` — monolith is gone; all 6 smoke tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract UI-layer modules and entry point** - `37c830b` (feat)
2. **Task 2: Verify app launches and works identically** - `18c64f2` (chore/verification)

## Files Created/Modified

- `musicstreamer/player.py` — Player class: GStreamer playbin + yt-dlp YouTube resolution, callback-based title
- `musicstreamer/ui/station_row.py` — StationRow(Gtk.ListBoxRow) wrapping Adw.ActionRow with station art thumbnail
- `musicstreamer/ui/edit_dialog.py` — EditStationDialog verbatim from main.py, now imports repo/assets/constants
- `musicstreamer/ui/main_window.py` — MainWindow using Player instance and StationRow widgets
- `musicstreamer/__main__.py` — App(Adw.Application) entry point with Gst.init before Player, ensure_dirs before db_connect
- `org.example.Streamer.desktop` — Exec=python3 -m musicstreamer
- `main.py` — deleted via git rm

## Decisions Made

- Player.play() uses an `on_title` callback instead of holding a label reference — cleaner decoupling, Player has no GTK dependency.
- StationRow subclasses `Gtk.ListBoxRow` (not Adw.ActionRow directly) so the row object can carry `self.station` and `self.station_id` — Phase 2 filter_func needs the full Station object.
- Player.stop() only nulls the pipeline; label reset stays in MainWindow — each class owns its own state.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Full musicstreamer package is modular and importable with no circular imports
- StationRow exposes `self.station` (full object) — Phase 2 search/filter filter_func can use it directly
- Player._pipeline is instance state accessible for Phase 3 ICY metadata bus wiring
- All 6 smoke tests pass; app launches via `python3 -m musicstreamer`

---
*Phase: 01-module-extraction*
*Completed: 2026-03-18*
