# MusicStreamer

## What This Is

A personal GNOME desktop app for listening to curated internet radio and live streams. Supports ShoutCast-style streams (AudioAddict, Soma.FM, etc.), YouTube live streams (e.g., Lofi Girl), and optionally Twitch music streams. Designed for a personal library of 50–200 stations with fast browsing and discovery via filtering.

## Core Value

Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## Requirements

### Validated

<!-- Inferred from existing codebase — these already work. -->

- ✓ Play ShoutCast/mp3/aac streams via GStreamer — existing
- ✓ Play YouTube live streams via yt-dlp + GStreamer — existing
- ✓ Add and edit stations (name, URL, provider, tags, art) — existing
- ✓ Station art (1:1 logo image per station) — existing
- ✓ Album fallback art per station — existing
- ✓ Provider/source grouping (e.g., Soma.FM, AudioAddict) — existing
- ✓ SQLite persistence in ~/.local/share/musicstreamer/ — existing

### Active (v1.0 Complete)

- ✓ User can filter station list by provider/source via dropdown — Validated Phase 2
- ✓ User can filter station list by genre/tag via dropdown — Validated Phase 2
- ✓ User can search stations by name with a search box — Validated Phase 2
- ✓ Filters and search compose (multiple active simultaneously) — Validated Phase 2
- ✓ User sees currently playing track title from ICY metadata (mp3/aac streams) — Validated Phase 3
- ✓ Station brand logo displayed top-left (1:1, from existing station art) — Validated Phase 3
- ✓ Track/album art displayed top-right via iTunes Search API, placeholder fallback — Validated Phase 4
- [ ] Station list displays station art (1:1 logo) inline per row — v2

### Out of Scope

- Twitch stream support — nice to have, only if lift is small; not blocking v1
- Local music library / file playback — out of scope, this is a streaming app
- Multi-user / authentication — single-user desktop app
- Podcast support — different use case
- Last.fm scrobbling — future enhancement
- Mobile app — Linux desktop only

## Phase History

| Phase | Status | Completed |
|-------|--------|-----------|
| 1: Module Extraction | ✓ Complete | 2026-03-18 |
| 2: Search and Filter | ✓ Complete | 2026-03-19 |
| 3: ICY Metadata Display | ✓ Complete | 2026-03-20 |
| 4: Cover Art | ✓ Complete | 2026-03-20 |

## Context

- Modular Python package (`musicstreamer/`) with GTK4/Libadwaita + GStreamer + SQLite
- Existing station list is a plain `Gtk.ListBox` with no filtering or search
- Tags column exists in the DB schema and station model but is not surfaced in UI filtering
- ICY metadata arrives via GStreamer bus messages (`TAG` messages) — not yet wired to UI
- Cover art lookup would require an external API (MusicBrainz, iTunes Search, or similar)
- Station count target: 50–200 (filtering becomes genuinely useful at this scale)

## Constraints

- **Tech stack**: Python + GTK4/Libadwaita — no framework changes
- **Platform**: Linux GNOME desktop only
- **Refactoring welcome**: Splitting `main.py` into modules is fine if it aids clarity
- **No network auth**: No API keys required for cover art if using free endpoints (iTunes Search API, MusicBrainz)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Search + dropdowns for filtering | User explicitly chose this over sidebar/chips | — Pending |
| ICY metadata via GStreamer TAG bus messages | Already in pipeline; just need to wire to UI | — Pending |
| Cover art via iTunes Search API or MusicBrainz | Free, no key required | — Pending |
| Twitch deferred | Nice to have — yt-dlp already supports it, low effort if included | — Pending |

---
*Last updated: 2026-03-20 — v1.0 milestone complete (all 4 phases)*
