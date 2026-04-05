# Milestones

## v1.4 Media & Art Polish (Shipped: 2026-04-05)

**Phases completed:** 5 phases (16–20), 8 plans | **Stats:** 153 tests | 69 files changed, 8,484 insertions | 2 days

**Delivered:** Tuned GStreamer buffer to eliminate ShoutCast drop-outs, added AudioAddict logo fetch at import + editor, YouTube 16:9 thumbnail display, custom accent color picker, play/pause button, and MPRIS2 OS media key integration.

**Key accomplishments:**

- GStreamer playbin3 `buffer-duration` (10s) and `buffer-size` (10 MB) set via TDD — eliminates ShoutCast/HTTP audible drop-outs; constants live in `constants.py` per project pattern
- `ThreadPoolExecutor` workers with thread-local `db_connect()` download AA channel logos at bulk import time; two-phase progress in `ImportDialog`; silent failure on fetch error
- AA URL detection for all 6 network domains in station editor with daemon-thread logo fetch and API key popover; `_aa_channel_key_from_url` uses `urllib.parse` (not regex) to correctly strip network slug prefix
- YouTube thumbnails displayed as full 16:9 using `ContentFit.CONTAIN` in now-playing logo slot; cover slot stays on fallback to avoid duplication
- `AccentDialog` with 8 GNOME-preset swatches and hex entry — immediate CSS provider reload at `PRIORITY_USER`, inline error state on invalid hex, persisted via SQLite settings
- `Player.pause()` (GStreamer NULL state) + play/pause button between star and stop; station stays selected on pause; MPRIS2 D-Bus service wired via `dbus-python` — OS media keys fully functional

---

## v1.3 Discovery & Favorites (Shipped: 2026-04-03)

**Phases completed:** 4 phases (12–15), 8 plans | **Stats:** 127 tests | 3,150 source + 1,468 test Python LOC | 59 commits | 8 days

**Delivered:** Added favorites (star ICY tracks, Favorites list), Radio-Browser.info discovery dialog, YouTube playlist importer, and AudioAddict bulk importer with tabbed ImportDialog.

**Key accomplishments:**

- `Favorite` dataclass, SQLite table with UNIQUE(station_name, track_title) dedup, repo CRUD — `INSERT OR IGNORE` for silent dedup; `cover_art.last_itunes_result` caches genre for favorites without a second API call
- Star button in now-playing panel (gated on non-junk ICY title), `Adw.ToggleGroup` Stations/Favorites view switcher, favorites list with trash removal and empty state
- `radio_browser.py` API client (`search_stations`, `fetch_tags`, `fetch_countries`) using urllib + daemon threads; `repo.station_exists_by_url` and `repo.insert_station` for discovery save
- `DiscoveryDialog` modal: live search, tag/country dropdowns, per-row play buttons with prior-station resume, save to library — `url_resolved` preferred over `url` (avoids PLS/M3U)
- `yt_import.py` backend with `scan_playlist`/`import_stations`; `ImportDialog` two-stage scan→checklist flow with spinner, progress count, and per-item selection; thread-local SQLite for import worker
- `aa_import.py` backend: `fetch_channels`/`import_stations` across all AudioAddict networks, PLS→direct URL resolution at fetch time, quality tier selection; `ImportDialog` refactored to `Gtk.Notebook` tabs (YouTube + AudioAddict)

---

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
