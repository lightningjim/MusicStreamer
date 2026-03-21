# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.) and YouTube live streams (e.g., Lofi Girl). Designed for a personal library of 50–200 stations with fast browsing via search and filtering, live track title display, cover art from iTunes, and per-station management (delete, ICY override, thumbnail auto-fetch).

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Current Milestone: v1.2 Station UX & Polish

**Goal:** Better station browsing with provider grouping, multi-select filters, recently played, volume control, and visual polish.

**Target features:**
- Provider-grouped station list (collapsible) + recently played section
- Multi-select provider/genre filters; inline provider/genre creation in editor
- YouTube stream title auto-import; provider name in Now Playing
- Volume slider with persistence
- Rounded corners, subtle gradients, improved spacing

## Current State (v1.1 shipped 2026-03-21)

- **Package:** `musicstreamer/` — clean modules (constants, models, repo, assets, player, ui/)
- **LOC:** ~1,782 Python | **Tests:** 58 passing
- **Stack:** Python + GTK4/Libadwaita + GStreamer + SQLite + yt-dlp + urllib (iTunes API)
- **Filtering:** Live search + provider/tag dropdowns + AND composition + empty state
- **Now-playing:** Three-column panel — logo | title/name/stop | cover art
- **Cover art:** iTunes Search API, junk detection, session dedup, placeholder fallback
- **Station list:** 48px logo prefix per row, generic icon placeholder when no art
- **Station management:** Delete (playing guard), ICY disable per-station, YouTube thumbnail auto-fetch

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

### Active (v1.2)

- [ ] BROWSE-01: Stations grouped by provider in list, collapsed by default, expandable
- [ ] BROWSE-02: User can filter by multiple providers simultaneously
- [ ] BROWSE-03: User can filter by multiple genres/tags simultaneously
- [ ] BROWSE-04: "Recently Played" section at top of station list showing last 3 played stations (most recent first)
- [ ] MGMT-01: Station editor shows existing providers as selectable options
- [ ] MGMT-02: Station editor shows existing genres/tags as selectable options (multi-select)
- [ ] MGMT-03: User can add a new provider/genre inline from the station editor
- [ ] MGMT-04: YouTube station URL auto-imports stream title
- [ ] NP-01: Now Playing panel shows provider name
- [ ] AUDIO-01: Volume slider controls playback volume
- [ ] AUDIO-02: Volume persists between sessions
- [ ] UI-01: Panels use rounded corners
- [ ] UI-02: Colors softened with subtle gradients
- [ ] UI-03: Station list rows have more vertical padding
- [ ] UI-04: Now Playing panel has more internal whitespace

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
*Last updated: 2026-03-21 after v1.2 milestone started*
