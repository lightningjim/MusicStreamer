# Milestones

## v1.2 Station UX & Polish (Shipped: 2026-03-27)

**Phases completed:** 5 phases, 12 plans, 13 tasks

**Key accomplishments:**

- SQLite data layer for recently-played tracking (millisecond-precision timestamps) and key/value settings storage, with idempotent migrations and 10 new passing tests
- Adw.ExpanderRow provider groups replacing flat StationRow list, with dual render modes (grouped/flat) driven by filter state
- Recently Played section above provider groups using in-place ListBox insert to preserve ExpanderRow collapse state, wired to play hook and hidden during active filters
- `matches_filter_multi` added to filter_utils.py — set-based multi-select filter with OR-within-dimension, AND-between-dimension logic and case-insensitive tag matching
- Gtk.DropDown provider/tag filters replaced with scrollable Gtk.ToggleButton chip strips supporting OR-within-dimension, AND-between-dimensions multi-select
- Replaced freeform provider and tags text entries in EditStationDialog with Adw.ComboRow picker and scrollable ToggleButton chip panel, both supporting inline creation of new values
- YouTube URL focus-out now fetches stream title via yt-dlp and auto-populates empty name field, running in parallel with the existing thumbnail fetch using independent flags
- Player.set_volume clamps float to [0.0, 1.0], writes GStreamer pipeline volume property, stores for mpv subprocess launch — 4 TDD tests pass, 85-test suite green
- Provider name shown inline as "Name · Provider" in now-playing label; Gtk.Scale volume slider wired to GStreamer and persisted via settings — 85 tests green
- Rounded panel gradient, station art 5px border-radius (GTK4: set_overflow(HIDDEN) required on Gtk.Stack — CSS overflow alone insufficient), improved spacing throughout

---

## v1.1 Polish & Station Management (Shipped: 2026-03-21)

**Phases completed:** 2 phases, 4 plans | **Stats:** 58 tests | 1,782 Python LOC | 27 commits | 1 day

**Delivered:** Fixed GTK markup escaping for ICY titles, surfaced station logos in the list, added delete station, per-station ICY disable, and YouTube thumbnail auto-fetch.

**Key accomplishments:**

- GTK markup escaping: `&`, `<`, `>` in ICY titles and station names display as literal characters
- Station logo pre-loaded into cover art slot as default; junk ICY title no longer clears it
- Station list always shows 48px prefix widget — logo when available, generic icon otherwise
- `Station.icy_disabled` field, SQLite migration, repo CRUD, and MainWindow playback guard for per-station ICY suppression
- Delete Station in edit dialog with playing guard (blocks deletion while streaming) and confirmation dialog
- YouTube URL auto-fetch: entering a YT URL triggers yt-dlp thumbnail fetch with spinner feedback

---

## v1.0 MVP (Shipped: 2026-03-20)

**Phases completed:** 4 phases, 8 plans, 0 tasks

**Delivered:** Transformed a monolithic GTK4/Python radio player into a modular, feature-rich app with live search/filter, ICY metadata display, and iTunes cover art.

**Stats:** 4 phases | 8 plans | 43 tests | 1,409 Python LOC | 74 files changed | 35 days

**Key accomplishments:**

- Refactored ~512-line `main.py` monolith into clean `musicstreamer/` package (constants, models, repo, assets, player, UI)
- TDD filter engine with real-time AND-composed search + provider/tag dropdowns and empty-state handling
- GStreamer ICY TAG bus wired to now-playing panel — live track titles with latin-1 mojibake correction
- Three-column now-playing panel: station logo (left), track info + Stop (center), cover art (right)
- iTunes Search API cover art with junk title detection, session dedup, and smooth in-flight transitions
- 43 automated tests across 4 modules; zero regressions across all phases

---
