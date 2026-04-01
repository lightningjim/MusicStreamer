---
id: SEED-003
status: dormant
planted: 2026-03-31
planted_during: v1.3 Phase 13 (Radio-Browser Discovery)
trigger_when: station management improvements, import enhancements, or network-aware playback
scope: Medium
---

# SEED-003: Multi-URL / quality selection per station

## Why This Matters

Stations often provide multiple stream URLs at different qualities (128kbps, 320kbps, FLAC) or via different protocols (direct, PLS, M3U). Currently the app stores a single URL per station. Users on variable internet connections (mobile, rural, travel) need to pick the stream quality that fits their bandwidth. Importing PLS files natively would also preserve all alternate URLs instead of resolving to just one.

Additionally, having backup URLs means if one stream endpoint goes down, the app could fall back to an alternate automatically.

## When to Surface

**Trigger:** When a milestone involves station management improvements, import enhancements, or network-aware playback.

This seed should be presented during `/gsd:new-milestone` when the milestone scope matches any of these conditions:
- Station data model changes (adding fields to Station)
- Import pipeline improvements (PLS/M3U/XSPF handling)
- Playback reliability or network adaptation features
- AudioAddict import (which has hi/med/low quality selection — IMPORT-03)

## Scope Estimate

**Medium** — Requires schema change (station_urls table or JSON field), UI for quality picker, PLS/M3U parser, and player fallback logic. Likely 2-3 phases.

## Breadcrumbs

Related code and decisions found in the current codebase:

- `musicstreamer/models.py` — Station dataclass (currently single `url` field)
- `musicstreamer/repo.py` — Station CRUD (single URL per station)
- `musicstreamer/player.py` — Playback engine (takes Station.url directly)
- `musicstreamer/ui/discovery_dialog.py` — PLS resolver added in Phase 13 (`_resolve_stream_url`), currently resolves to single URL and discards alternatives
- `musicstreamer/radio_browser.py` — Radio-Browser API returns both `url` and `url_resolved`
- `.planning/REQUIREMENTS.md` — IMPORT-03 already mentions quality selection for AudioAddict
- `.planning/notes/2026-03-20-icy-override-per-station.md` — Related per-station customization

## Notes

Came up during Phase 13 testing when SomaFM stations returned PLS files. The current fix resolves PLS to a single stream URL, but the user wants to preserve all URLs from PLS files and let them choose quality/backup streams.
