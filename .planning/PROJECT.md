# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.) and YouTube live streams (e.g., Lofi Girl). Designed for a personal library of 50–200 stations organized by provider with multi-select filtering, recently played, live track title display, cover art from iTunes, volume control, and full per-station management.

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Current Milestone: v1.3 Discovery & Favorites

**Goal:** Add station discovery (Radio-Browser.info, AudioAddict, YouTube playlists) and a favorites system for saving ICY track titles.

**Target features:**
- Favorite songs: star ICY track titles, DB storage with station + provider context, inline list view toggling with station list
- AudioAddict import: all properties (DI.fm, ZenRadio, JazzRadio, RockRadio) via API key + PLS, quality selection
- YouTube playlist import: paste any public playlist URL → imports live streams as stations via yt-dlp
- Radio-Browser.info: live browse/search view + save any station to library

## Current State (v1.2 fully complete — 2026-03-27)

- **Package:** `musicstreamer/` — clean modules (constants, models, repo, assets, player, ui/)
- **LOC:** ~17,505 Python total | **Tests:** 85 passing
- **Stack:** Python + GTK4/Libadwaita + GStreamer + SQLite + yt-dlp + urllib (iTunes API)
- **Station list:** Provider-grouped ExpanderRows + recently played section; multi-select chip filters (OR-within/AND-between); search composes with all filters
- **Now-playing:** Three-column panel — logo | "Name · Provider" / track title / Stop | cover art; volume slider with GStreamer + persistence; panel has rounded corners + gradient; station art has 5px rounded corners (GTK4: set_overflow(HIDDEN) required)
- **Cover art:** iTunes Search API, junk detection, session dedup, placeholder fallback
- **Station management:** ComboRow provider picker, tag chip panel (inline creation), delete (playing guard), ICY disable, YouTube thumbnail + title auto-fetch

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

### Active (v1.3)

- FAVES-01: User can star the currently playing ICY track title
- FAVES-02: Favorites stored in DB with station name, provider, and track title
- FAVES-03: Favorites view replaces station list inline (toggle between Stations / Favorites)
- FAVES-04: User can remove a favorite from the Favorites view
- DISC-01: User can browse and search Radio-Browser.info stations live in-app
- DISC-02: User can play a Radio-Browser.info station directly without importing
- DISC-03: User can save a Radio-Browser.info station to their library
- DISC-04: User can import AudioAddict channels (all properties: DI.fm, ZenRadio, JazzRadio, RockRadio) via API key
- DISC-05: User can select import quality (hi/med/low) for AudioAddict channels
- DISC-06: User can paste a YouTube public playlist URL to import live streams as stations

### Out of Scope

| Feature | Reason |
|---------|--------|
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| Twitch stream support | yt-dlp supports it; revisit if user adds Twitch stations |
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
| Twitch deferred | Requires stations in library to validate | — Pending |
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

## Constraints

- **Tech stack:** Python + GTK4/Libadwaita — no framework changes
- **Platform:** Linux GNOME desktop only
- **No network auth:** No API keys required (iTunes is keyless)
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
*Last updated: 2026-03-27 — v1.3 milestone started*
