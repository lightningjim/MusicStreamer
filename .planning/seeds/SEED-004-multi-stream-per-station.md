---
id: SEED-004
status: shipped
planted: 2026-04-03
planted_during: v1.3 Phase 15 (AudioAddict Import)
trigger_when: v1.4 / next milestone planning
scope: Large
shipped_date: 2026-04-09
shipped_by: v1.5 Phase 27 (STR-01..14) Multi-Stream Model + v1.5 Phase 28 (D-01..08) Stream Failover
---

> **✅ SHIPPED** — Delivered by the same v1.5 Phase 27+28 work that
> closed SEED-003. The "2 servers × 3 qualities = 6 streams" model
> described here is exactly what the `station_streams` schema captures:
> multiple URLs per station in priority order, each tagged with a
> quality preset. The failover queue (D-01..08) walks the priority list
> on error, satisfying the "backup servers" half. The
> `ManageStreamsDialog` in the edit flow satisfies the per-station
> override half. SEED-003 and SEED-004 were duplicates planted 3 days
> apart — both retired together.

# SEED-004: One station with multiple streams (backup servers + per-quality URLs)

## Why This Matters

Reliability + quality control. Two concrete problems this solves:

1. **Backup servers** — when one stream URL goes down, the app can fall back to an alternate
   server for the same station without the user having to manually edit the URL.

2. **Per-station quality override** — the global Hi/Med/Low preference is the right default,
   but some stations (particularly AudioAddict channels) have multiple quality tiers and the
   user wants to pin a specific station to a specific quality regardless of the global setting.
   Example: 2 servers × 3 qualities = 6 stream URLs for one logical station.

## When to Surface

**Trigger:** v1.4 / next milestone planning

Present this seed when planning the milestone after v1.3 ships. Likely fits in a
"Station Management v2" or "Playback Reliability" milestone.

Surface conditions:
- New milestone scope includes station data model changes
- New milestone scope includes playback reliability / failover
- New milestone scope includes per-station audio settings
- AudioAddict import (Phase 15) is complete and user is planning what's next

## Scope Estimate

**Large** — Full milestone. Requires:
- DB schema change: `stations` table gets a `stream_urls` 1:many child table (or JSON column)
  replacing the single `url` field in `Station` dataclass (`musicstreamer/models.py:15`)
- Migration: existing stations each get one stream entry from their current `url` value
- Player changes: try streams in priority order on failure (`musicstreamer/player.py`)
- Global quality preference: already planned for v1.3 (AudioAddict import) — extend to
  drive stream selection across all multi-URL stations
- Per-station quality override: new field in station editor allowing a pin that overrides
  the global preference for that station
- UI for stream management: add/remove/reorder stream URLs per station in the edit dialog
  (`musicstreamer/ui/edit_dialog.py`)
- Repo CRUD: new methods for stream URL management (`musicstreamer/repo.py`)

## Breadcrumbs

- `musicstreamer/models.py:15` — `Station.url: str` — this single field becomes a 1:many relationship
- `musicstreamer/repo.py` — `create_station()`, `get_station()`, `list_stations()` — all need stream URL awareness
- `musicstreamer/player.py` — stream URL resolution and GStreamer pipeline setup — needs fallback logic
- `musicstreamer/ui/edit_dialog.py` — station editor — needs stream list management UI
- `.planning/phases/15-audioaddict-import/15-CONTEXT.md` — quality selection decisions (D-04) — the Hi/Med/Low toggle planted in Phase 15 is the precursor to per-station overrides

## Notes

Planted during AudioAddict import (Phase 15) where quality selection is introduced as a
global preference. The per-station override is the natural evolution once users accumulate
a diverse library with different quality needs per station.

The "2 servers × 3 qualities = 6 streams" model is AudioAddict's exact structure — but
the implementation should be generic enough to handle any station with multiple URLs,
including non-AudioAddict backup servers.
