# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.) and YouTube live streams (e.g., Lofi Girl). Designed for a personal library of 50–200 stations with fast browsing via search and filtering, live track title display, and cover art from iTunes.

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Current Milestone: v1.1 Polish & Station Management

**Goal:** Fix GTK markup escaping, improve station management UX, and surface station art in the list.

**Target features:**
- Fix ampersand/markup escaping in ICY track title display
- Auto-load YouTube thumbnail as station image when adding/editing
- Per-station ICY override option (disable ICY where it returns wrong data)
- Station list shows station art inline per row
- Delete station from list

## Current State (v1.0 shipped 2026-03-20)

- **Package:** `musicstreamer/` — clean modules (constants, models, repo, assets, player, ui/)
- **LOC:** ~1,409 Python | **Tests:** 43 passing (test_repo, test_filter_utils, test_player_tag, test_cover_art)
- **Stack:** Python + GTK4/Libadwaita + GStreamer + SQLite + yt-dlp + urllib (iTunes API)
- **Filtering:** Live search + provider/tag dropdowns + AND composition + empty state
- **Now-playing:** Three-column panel — logo | title/name/stop | cover art
- **Cover art:** iTunes Search API, junk detection, session dedup, placeholder fallback

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

### Active (v1.1)

- [ ] Fix GTK markup escaping for ICY track titles (ampersand and other special chars)
- [ ] Auto-load YouTube thumbnail as station image when adding/editing a YouTube station
- [ ] Per-station ICY override option (disable ICY for stations where it returns wrong data)
- [ ] Station list displays station art (1:1 logo) inline per row
- [ ] Delete station from list

### Out of Scope

- Twitch stream support — yt-dlp supports it; revisit if user adds Twitch stations
- Local music library / file playback — streaming app only
- Multi-user / authentication — single-user desktop app
- Podcast support — different use case
- Last.fm scrobbling — future enhancement
- Mobile app — Linux GNOME desktop only
- MusicBrainz fallback for cover art — v2 if iTunes proves insufficient

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

---
*Last updated: 2026-03-20 after v1.1 milestone start*
