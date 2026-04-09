# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.) and YouTube live streams (e.g., Lofi Girl). Designed for a personal library of 50–200 stations organized by provider with multi-select filtering, recently played, live track title display, cover art from iTunes, volume control, favorites (star ICY tracks), in-app Radio-Browser.info discovery, and bulk import from YouTube playlists or AudioAddict networks.

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Current Milestone: v1.5 Further Polish

**Goal:** Fix bugs and polish issues discovered through 2 weeks of daily use (deadline: 2026-04-19).

**Target features:**
- Fix: YouTube 16:9 thumbnail inflates now-playing panel when window is maximized/fullscreen
- Additional fixes TBD as discovered during use

**Next:** If no new issues found by deadline, close out and move to v2.0 (OS-agnostic revamp).

## Current State (v1.5 in progress — Phase 31 complete 2026-04-09)

- **Package:** `musicstreamer/` — constants, models, repo, assets, player, ui/, radio_browser.py, yt_import.py, aa_import.py, accent_utils.py, mpris.py
- **LOC:** ~3,800 Python source | ~2,100 test LOC | **Tests:** 255 passing
- **Stack:** Python + GTK4/Libadwaita + GStreamer + SQLite + yt-dlp + streamlink + dbus-python + urllib (iTunes API, Radio-Browser API, AudioAddict API)
- **Station list:** Provider-grouped ExpanderRows + recently played section; multi-select chip filters (OR-within/AND-between); search composes with all filters
- **Now-playing:** Three-column panel — logo (16:9 for YouTube via ContentFit.CONTAIN, square otherwise) | "Name · Provider" / track title / Edit+Star+Pause+Stop | cover art; volume slider with GStreamer + persistence; star button for ICY track favorites
- **Cover art:** iTunes Search API, junk detection, session dedup, placeholder fallback; genre cached in `last_itunes_result` for favorites
- **Station management:** ComboRow provider picker, tag chip FlowBox (wrapping, inline creation), delete (playing guard), ICY disable, YouTube thumbnail + title auto-fetch, AA logo auto-fetch
- **Favorites:** Star ICY track titles, store in SQLite with station/provider/genre context, toggle Favorites/Stations view inline via Adw.ToggleGroup, remove with trash button
- **Discovery:** DiscoveryDialog — search Radio-Browser.info by name, filter by tag/country, preview live, save to library; resolves PLS/M3U to direct stream URL
- **Import:** ImportDialog (tabbed) — YouTube playlist tab (scan→checklist, live-streams only, progress feedback); AudioAddict tab (API key, quality selector, all networks, dedup by URL, PLS resolution, logo download)
- **Playback:** GStreamer buffer tuned (10s/10MB); pause keeps station selected; MPRIS2 D-Bus service for OS media keys
- **Personalization:** Custom accent color picker (8 presets + hex), CSS provider at PRIORITY_USER, persisted in SQLite
- **YouTube Cookies:** Import cookies via file picker, paste, or Google login (WebKit2 subprocess); stored at ~/.local/share/musicstreamer/cookies.txt with 0o600 permissions; yt-dlp always gets --no-cookies-from-browser; both yt-dlp and mpv use --cookies when file exists

## Requirements

### Validated

- ✓ Play ShoutCast/mp3/aac streams via GStreamer — existing pre-v1.0
- ✓ Play YouTube live streams via yt-dlp + GStreamer — existing pre-v1.0
- ✓ Add and edit stations (name, URL, provider, tags, art) — existing pre-v1.0
- ✓ Station art (1:1 logo image per station) — existing pre-v1.0
- ✓ SQLite persistence in ~/.local/share/musicstreamer/ — existing pre-v1.0
- ✓ Codebase modularised (constants, models, repo, assets, player, UI) — v1.0 Phase 1
- ✓ Live search filters station list by name in real time — v1.0 Phase 2
- ✓ Provider dropdown filters to selected provider — v1.0 Phase 2
- ✓ Tag dropdown filters to selected genre/tag — v1.0 Phase 2
- ✓ Search + dropdowns compose with AND logic — v1.0 Phase 2
- ✓ Clear all filters returns full list — v1.0 Phase 2
- ✓ ICY track title shown and auto-updates mid-stream — v1.0 Phase 3
- ✓ YouTube streams show station name when no ICY metadata — v1.0 Phase 3
- ✓ Station brand logo displayed top-left in now-playing — v1.0 Phase 3
- ✓ Cover art displayed top-right via iTunes Search API — v1.0 Phase 4
- ✓ Placeholder shown when no cover art available — v1.0 Phase 4
- ✓ ICY track titles with &, <, > display as literal characters — v1.1 Phase 5
- ✓ Cover art slot shows station logo when no ICY title available — v1.1 Phase 5
- ✓ Station list shows each station's logo inline per row — v1.1 Phase 5
- ✓ User can delete a station from the list — v1.1 Phase 6
- ✓ Station editor auto-populates image from YouTube thumbnail — v1.1 Phase 6
- ✓ User can disable ICY metadata per station — v1.1 Phase 6
- ✓ BROWSE-01: Stations grouped by provider in list, collapsed by default, expandable — v1.2 Phase 7
- ✓ BROWSE-04: "Recently Played" section at top showing last 3 played stations, most recent first — v1.2 Phase 7
- ✓ BROWSE-02: User can filter by multiple providers simultaneously — v1.2 Phase 8
- ✓ BROWSE-03: User can filter by multiple genres/tags simultaneously — v1.2 Phase 8
- ✓ MGMT-01: Station editor shows existing providers as selectable options — v1.2 Phase 9
- ✓ MGMT-02: Station editor shows existing genres/tags as selectable options (multi-select) — v1.2 Phase 9
- ✓ MGMT-03: User can add a new provider/genre inline from the station editor — v1.2 Phase 9
- ✓ MGMT-04: YouTube station URL auto-imports stream title — v1.2 Phase 9
- ✓ NP-01: Now Playing panel shows provider name alongside station name — v1.2 Phase 10
- ✓ AUDIO-01: Volume slider in main window controls playback volume — v1.2 Phase 10
- ✓ AUDIO-02: Volume setting persists between sessions — v1.2 Phase 10
- ✓ UI-01: Panels use rounded corners — v1.2 Phase 11
- ✓ UI-02: Colors softened with subtle gradients — v1.2 Phase 11
- ✓ UI-03: Station list rows have more vertical padding — v1.2 Phase 11
- ✓ UI-04: Now Playing panel has more internal whitespace — v1.2 Phase 11
- ✓ FAVES-01: User can star the currently playing ICY track title — v1.3 Phase 12
- ✓ FAVES-02: Favorites stored in DB with station name, provider, and track title — v1.3 Phase 12
- ✓ FAVES-03: Favorites view replaces station list inline (toggle between Stations / Favorites) — v1.3 Phase 12
- ✓ FAVES-04: User can remove a favorite from the Favorites view — v1.3 Phase 12
- ✓ DISC-01: User can search Radio-Browser.info stations by name/provider from in-app discovery dialog — v1.3 Phase 13
- ✓ DISC-02: User can filter Radio-Browser.info results by tag (genre) or country — v1.3 Phase 13
- ✓ DISC-03: User can play a Radio-Browser.info station as a preview without saving to library — v1.3 Phase 13
- ✓ DISC-04: User can save a Radio-Browser.info station to their library — v1.3 Phase 13
- ✓ IMPORT-01: User can paste a YouTube playlist URL and import live streams as stations with progress feedback — v1.3 Phase 14
- ✓ IMPORT-02: User can enter an AudioAddict API key to import all network channels, skipping duplicates — v1.3 Phase 15
- ✓ IMPORT-03: User can select stream quality (hi / med / low) before importing AudioAddict channels — v1.3 Phase 15
- ✓ STREAM-01: GStreamer buffer-duration (10s) and buffer-size (10 MB) tuned — ShoutCast/HTTP drop-outs eliminated — v1.4 Phase 16
- ✓ ART-01: AudioAddict channel logos fetched from AA API at bulk import time via ThreadPoolExecutor workers — v1.4 Phase 17
- ✓ ART-02: Station editor auto-fetches AA logo on URL paste (same UX as YouTube thumbnail) — v1.4 Phase 17
- ✓ ART-03: YouTube thumbnails displayed as full 16:9 via ContentFit.CONTAIN; non-YouTube art unaffected — v1.4 Phase 18
- ✓ ACCENT-01: Custom accent color with 8 presets + hex input, CSS at PRIORITY_USER, persisted in SQLite — v1.4 Phase 19
- ✓ CTRL-01: Play/pause button between star and stop; pause keeps station selected and now-playing visible — v1.4 Phase 20
- ✓ CTRL-02: MPRIS2 D-Bus service wired via dbus-python — OS media keys control pause/resume/stop — v1.4 Phase 20

### Active (v1.5)

- [ ] FIX-01: YouTube 16:9 thumbnail does not inflate now-playing panel when window is maximized/fullscreen

### Out of Scope

| Feature | Reason |
|---------|--------|
| Radio-Browser.info as primary browse mode | Anti-feature — undermines curated library model; discovery is modal/import flow only |
| Playback history distinct from favorites | Different use case; favorites are intentional stars, not automatic history |
| Auto-refresh saved Radio-Browser stations | Stations in library are managed manually; auto-refresh adds complexity for unclear benefit |
| Social sharing / export of favorites | Single-user desktop app |
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| ~~Twitch stream support~~ | Implemented in Phase 31 via streamlink |
| Local music library / file playback | Streaming app only |
| Multi-user / authentication | Single-user desktop app |
| Podcast support | Different use case |
| Last.fm scrobbling | Future enhancement |
| Mobile app | Linux GNOME desktop only |

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Search + dropdowns for filtering | User explicitly chose this over sidebar/chips | ✓ Good — clean UX, easy to compose |
| ICY metadata via GStreamer TAG bus | Already flowing in pipeline | ✓ Good — zero extra dependencies |
| Cover art via iTunes Search API | Free, no key required | ✓ Good — works for most western music |
| `urllib` over `requests` for iTunes fetch | No extra dependency | ✓ Good — stdlib sufficient |
| GLib.idle_add for cross-thread UI updates | GStreamer bus on non-GTK thread | ✓ Good — established pattern, no races |
| GdkPixbuf pre-scale to 160×160 | Avoid GTK downscale artifacts | ✓ Good — consistent with logo slot |
| Gtk.Stack for logo/art slots | Smooth fallback swap without flicker | ✓ Good — reused across both slots |
| Session dedup via `_last_cover_icy` | Avoid redundant API calls on repeated TAG | ✓ Good — no external cache needed |
| set_text() not set_markup() for ICY labels | set_text() does not parse Pango markup | ✓ Good — no escaping needed for plain labels |
| markup_escape_text in Adw.ActionRow | ActionRow title/subtitle ARE parsed as Pango markup | ✓ Good — escaping required here |
| Adw.SwitchRow for ICY toggle | Native Adwaita toggle, integrates with form layout | ✓ Good — consistent with Adwaita HIG |
| daemon thread + GLib.idle_add for YT thumbnail | yt-dlp subprocess must not block GTK main loop | ✓ Good — established cross-thread pattern |
| Gtk.Stack (pic/spinner) in arts grid | Avoids re-parenting station_pic during fetch | ✓ Good — no flicker during thumbnail load |
| strftime ms precision for last_played_at | datetime('now') second-level granularity caused ordering failures | ✓ Good |
| Drop set_filter_func for grouped list | filter_func cannot inspect ExpanderRow children added via add_row() | ✓ Good |
| ExpanderRow activated signal for play | row-activated on outer ListBox does not fire for group children | ✓ Good |
| ListBox.insert(row,0) for RP refresh | Preserves ExpanderRow expand/collapse state vs. full reload | ✓ Good |
| Empty set = inactive filter dimension | Parallel to None/empty string convention in matches_filter | ✓ Good |
| _rebuilding flag for bulk chip mutations | Prevents spurious filter updates during rebuild/clear | ✓ Good |
| new_provider_entry takes precedence | Typed value always wins over combo selection | ✓ Good |
| Volume stored as float 0.0–1.0 | Convert to int only at mpv call site | ✓ Good |
| Provider as "Name · Provider" (U+00B7) | Clean inline label without extra UI elements | ✓ Good |
| Volume default 80 not 100 | Avoid blasting on first launch | ✓ Good |
| CSS on Gtk.Stack container for border-radius | Stack is the clip container — radius not visible on Gtk.Image | ✓ Good |
| INSERT OR IGNORE for favorites dedup | UNIQUE(station_name, track_title) constraint; silent no-op on repeat star | ✓ Good |
| last_itunes_result module-level dict | Caches full iTunes result so genre is available for favorites without a second API call | ✓ Good |
| Adw.ToggleGroup for Stations/Favorites switcher | Native Adwaita segmented control, HIG-compliant | ✓ Good |
| url_resolved preferred over url (Radio-Browser) | url is often a PLS/M3U playlist, url_resolved is the direct stream | ✓ Good |
| is_live is True strict identity check (yt-dlp) | Non-live entries return None not False in flat-playlist extract mode | ✓ Good |
| Thread-local db_connect() in import workers | SQLite connections cannot be shared across threads | ✓ Good |
| ch['key'] not ch['name'] for AudioAddict PLS slug | Channel names have spaces; keys are lowercase slugs used in URL paths | ✓ Good |
| ValueError('no_channels') for empty AudioAddict response | Catches expired API keys returning 200+empty instead of 401 | ✓ Good |
| Resolve PLS to direct URL in aa_import.fetch_channels | GStreamer cannot play PLS playlists; resolution must happen at import time | ✓ Good |
| Twitch via streamlink | `_play_twitch()` resolves HLS URL via `streamlink --stream-url`, feeds to GStreamer playbin3; offline detection with toast | ✓ Good — Phase 31 |
| Buffer constants in constants.py (not inlined) | Consistent with project pattern, allows future tuning | ✓ Good |
| ThreadPoolExecutor for AA logo downloads | Async/decoupled from insert loop — avoids import regression | ✓ Good |
| Thread-local db_connect() in logo workers | SQLite connections cannot be shared across threads | ✓ Good |
| _aa_channel_key_from_url strips network slug prefix | Stream URL paths are slug-prefixed; AA API images by bare channel name | ✓ Good |
| ContentFit.CONTAIN for YouTube 16:9 in 160×160 slot | No slot widening — CONTAIN letterboxes cleanly within existing dimensions | ✓ Good |
| Cover slot stays on fallback for YouTube stations | Avoids duplicate thumbnail in both logo and cover slots | ✓ Good |
| CssProvider at PRIORITY_USER for accent color | Overrides app-level theme tokens; PRIORITY_APPLICATION insufficient | ✓ Good |
| Player.pause() identical to stop() | "Keep station selected" logic lives in main_window, not player | ✓ Good |
| DBusGMainLoop(set_as_default=True) at module import | Must be called before dbus.service.Object class definition | ✓ Good |
| Edit icon in now-playing controls_box, not filter bar | Filter bar Edit button was broken by ExpanderRow grouping; per-row edit icons already exist; now-playing edit is more useful | ✓ Good |

## Constraints

- **Tech stack:** Python + GTK4/Libadwaita — no framework changes
- **Platform:** Linux GNOME desktop only
- **No network auth:** API keys only where required by service (AudioAddict)
- **Test runner:** pytest via `uv run --with pytest` (no system pip)

## Phase History

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1: Module Extraction | v1.0 | ✓ Complete | 2026-03-18 |
| 2: Search and Filter | v1.0 | ✓ Complete | 2026-03-19 |
| 3: ICY Metadata Display | v1.0 | ✓ Complete | 2026-03-20 |
| 4: Cover Art | v1.0 | ✓ Complete | 2026-03-20 |
| 5: Display Polish | v1.1 | ✓ Complete | 2026-03-21 |
| 6: Station Management | v1.1 | ✓ Complete | 2026-03-21 |
| 7: Station List Restructuring | v1.2 | ✓ Complete | 2026-03-22 |
| 8: Filter Bar Multi-Select | v1.2 | ✓ Complete | 2026-03-22 |
| 9: Station Editor Improvements | v1.2 | ✓ Complete | 2026-03-23 |
| 10: Now Playing & Audio | v1.2 | ✓ Complete | 2026-03-24 |
| 11: UI Polish | v1.2 | ✓ Complete | 2026-03-25 |
| 12: Favorites | v1.3 | ✓ Complete | 2026-03-31 |
| 13: Radio-Browser Discovery | v1.3 | ✓ Complete | 2026-04-01 |
| 14: YouTube Playlist Import | v1.3 | ✓ Complete | 2026-04-02 |
| 15: AudioAddict Import | v1.3 | ✓ Complete | 2026-04-03 |

---
## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after Phase 31 (Integrate Twitch streaming via streamlink) complete*
