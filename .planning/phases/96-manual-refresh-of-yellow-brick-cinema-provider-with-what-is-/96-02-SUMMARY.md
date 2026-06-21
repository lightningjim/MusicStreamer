---
phase: 96
plan: "02"
subsystem: data-layer
tags: [wave-1, migrations, repo, models, tdd-green]
dependency_graph:
  requires:
    - "96-01 (RED tests for D-01/D-03/D-04/D-06)"
  provides:
    - "3 additive SQLite migrations (live_url_syncs_from_channel, live_url_title_anchor, channel_scan_url)"
    - "3 dedicated single-column setters (set_live_url_syncs_from_channel, set_live_url_title_anchor, set_provider_channel_scan_url)"
    - "list_flagged_stations_for_provider query"
    - "Station + Provider model fields with safe defaults"
    - "All four Station-building queries carry the two new Phase 96 fields"
  affects:
    - musicstreamer/repo.py
    - musicstreamer/models.py
tech_stack:
  added: []
  patterns:
    - "Additive idempotent ALTER TABLE after the legacy URL-column rebuild block (Pitfall 8 ordering)"
    - "Dedicated single-column setters — never routed through update_station (Pitfall 1)"
    - "500-char title cap in set_live_url_title_anchor before persist (T-96-03)"
    - "list_flagged_stations_for_provider mirrors list_recently_played Station-building loop"
key_files:
  created: []
  modified:
    - musicstreamer/repo.py
    - musicstreamer/models.py
decisions:
  - "Phase 96 D-01: live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0 — existing rows default OFF, no backfill needed"
  - "Phase 96 D-03: live_url_title_anchor TEXT nullable — NULL means anchor not yet captured"
  - "Phase 96 D-04: channel_scan_url TEXT nullable on providers — providers has no rebuild block, safe to add after 89.1 block"
  - "T-96-03: title anchor capped at 500 chars in set_live_url_title_anchor before persist (defense-in-depth against oversized yt-dlp titles)"
  - "Setters never routed through update_station to prevent silent-reset of new columns on saves that do not touch them (Pitfall 1)"
  - "All five Station-building call sites (4 existing + list_flagged_stations_for_provider) carry both Phase 96 fields (Pitfall 2 guard)"
metrics:
  duration: "8 minutes"
  completed: "2026-06-21T17:55:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 96 Plan 02: Data-Layer Foundation Summary

**One-liner:** Three idempotent SQLite migrations + Station/Provider model fields + three dedicated setters + list_flagged_stations_for_provider turn Plan 01's 7 RED repo tests GREEN.

## What Was Built

Plan 02 delivers the complete Phase 96 data layer: schema migrations, model fields, setter methods, and the flagged-station query. All 7 RED repo tests from Plan 01's Wave 0 scaffolding are now GREEN.

### Task 1: Three additive migrations + model fields (D-01/D-03/D-04)

Added three idempotent `try/except sqlite3.OperationalError` ALTER blocks to `db_init()` in `musicstreamer/repo.py`, placed **immediately after** the Phase 89.1 `providers.avatar_path` ALTER at line 334 — ensuring they land after the legacy URL-column rebuild block (Pitfall 8):

1. `ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0` (D-01)
2. `ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT` (D-03, nullable)
3. `ALTER TABLE providers ADD COLUMN channel_scan_url TEXT` (D-04, nullable)

In `musicstreamer/models.py`:
- `Station` dataclass gains `live_url_syncs_from_channel: bool = False` and `live_url_title_anchor: Optional[str] = None` (after `provider_avatar_path`)
- `Provider` dataclass gains `channel_scan_url: Optional[str] = None` (after `name`)

### Task 2: Setters, flagged-station query, and four-query field carry (D-01/D-03/D-04/D-06)

**Three dedicated single-column setters** following the `update_channel_avatar_path` / `update_provider_avatar_path` shape (each does one UPDATE + commit; never routed through `update_station` — Pitfall 1):

- `set_live_url_syncs_from_channel(station_id, value: bool)` — stores `int(value)`, D-01
- `set_live_url_title_anchor(station_id, title: Optional[str])` — caps at 500 chars (T-96-03), D-03
- `set_provider_channel_scan_url(provider_id, url: Optional[str])` — D-04

**`list_flagged_stations_for_provider(provider_id)`** — mirrors `list_recently_played`'s Station-building loop with `WHERE s.provider_id = ? AND s.live_url_syncs_from_channel = 1 ORDER BY s.name COLLATE NOCASE`. Includes both Phase 96 fields in `Station(...)`.

**Four existing Station-building queries** updated to carry the two new fields (Pitfall 2 guard):
- `list_stations` (L641-673)
- `get_station` (L682-712)
- `list_recently_played` (L792-825)
- `list_favorite_stations` (L911-942)

**`list_providers`** updated to `SELECT id, name, channel_scan_url` and pass `channel_scan_url=r["channel_scan_url"]` into `Provider(...)`.

Final count: `grep -c "live_url_syncs_from_channel=bool" repo.py` = **5** (four existing queries + `list_flagged_stations_for_provider`).

## Verification

```
.venv/bin/python -m pytest tests/test_repo.py -x -q
115 passed, 1 warning in 0.88s
```

All 7 Phase 96 repo tests GREEN:
- `test_live_url_syncs_from_channel_migration_idempotent` PASS
- `test_live_url_syncs_from_channel_round_trip` PASS
- `test_station_live_flag_loaded_from_db` PASS
- `test_live_url_title_anchor_migration_idempotent` PASS
- `test_live_url_title_anchor_round_trip` PASS
- `test_provider_channel_scan_url_migration_idempotent` PASS
- `test_list_flagged_stations_for_provider` PASS

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Three migrations + model fields | 51b04b9e | musicstreamer/repo.py, musicstreamer/models.py (+35 lines) |
| Task 2: Setters + flagged query + four-query carry | b5eab0b5 | musicstreamer/repo.py (+103 lines, -2 lines) |

## Known Stubs

None — all new DB columns are wired end-to-end: migration → model field → setter → Station-building query.

## Threat Flags

None — no new network endpoints or auth paths. The title anchor 500-char cap (T-96-03) is the only security-relevant change, and it is applied at the setter boundary before SQLite persist.

## Self-Check: PASSED

- musicstreamer/repo.py modified: FOUND (3 migrations, 3 setters, 1 query, 5 Station-building sites updated)
- musicstreamer/models.py modified: FOUND (Station + Provider new fields)
- Commit 51b04b9e: FOUND
- Commit b5eab0b5: FOUND
- `grep -c "live_url_syncs_from_channel=bool" repo.py` = 5: CONFIRMED
- `grep -n "def set_live_url_syncs_from_channel|def set_live_url_title_anchor|def set_provider_channel_scan_url|def list_flagged_stations_for_provider" repo.py` = 4 lines: CONFIRMED
- ALTER lines at 344, 354, 363 — all after line 334 (Phase 89.1 block): CONFIRMED
- 115 repo tests PASS, 0 regressions from this plan's changes: CONFIRMED
