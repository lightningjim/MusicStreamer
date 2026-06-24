---
phase: 97-resolve-station-url-duplication-between-the-top-level-standa
plan: "02"
subsystem: data-layer
tags: [tdd, wave-2, canonical, green-tests, models, repo]
dependency_graph:
  requires:
    - "97-01 (Wave-0 RED tests)"
  provides:
    - "Station.canonical_stream_id field (Optional[int] = None)"
    - "Station.canonical_url property (4-branch resolution)"
    - "stations.canonical_stream_id FK column (ON DELETE SET NULL)"
    - "db_init idempotent ALTER + position-1 backfill"
    - "repo.set_canonical_stream() dedicated single-column setter"
    - "canonical_stream_id threaded into all 6 Station builders"
  affects:
    - musicstreamer/models.py
    - musicstreamer/repo.py
tech_stack:
  added: []
  patterns:
    - "Phase 97 D-04: canonical FK mirrors preferred_stream_id field pattern (Phase 82)"
    - "Dedicated single-column setter (never via update_station) — Pitfall 1"
    - "try/except OperationalError idempotent ALTER (mirrors Phase 82/96 shape)"
    - "updated_at guard on backfill — mirrors Phase 89.1 _backfill_eligible pattern"
key_files:
  created: []
  modified:
    - path: musicstreamer/models.py
      purpose: "canonical_stream_id field + canonical_url property on Station dataclass"
    - path: musicstreamer/repo.py
      purpose: "ALTER + backfill + set_canonical_stream + builder threading"
decisions:
  - "Backfill guarded by updated_at column presence to avoid trigger failure on legacy test-fixture schemas (mirrors Phase 89.1 _backfill_eligible)"
  - "canonical_stream_id threaded in Task 2 commit (not deferred to Task 3) to turn all 5 RED canonical tests GREEN in a single GREEN gate"
metrics:
  duration: "~4 minutes"
  completed: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 2
---

# Phase 97 Plan 02: Data-Layer Canonical Stream FK Summary

**One-liner:** canonical_stream_id INTEGER FK (ON DELETE SET NULL) added to stations table with idempotent position-1 backfill, dedicated set_canonical_stream setter, and Station.canonical_url 4-branch property — all 6 repo canonical/accessor tests GREEN.

## What Was Built

Implemented the persisted canonical marker data layer established in the Plan-01 RED tests: the `Station.canonical_stream_id` field, the `Station.canonical_url` computed property, the `stations.canonical_stream_id` DB column with FK on-delete semantics, and the supporting repo infrastructure.

### Task 1 — models.py (commit `22cd6bac`)

Added to `Station` dataclass in `musicstreamer/models.py`:

- `canonical_stream_id: Optional[int] = None  # Phase 97 D-04` immediately after `preferred_stream_id` (mirrors Phase 82 field pattern)
- `@property def canonical_url(self) -> str` at end of class: 3-branch resolution: FK match → position-1 (by position ASC, id ASC) → ""

Test turned GREEN: `test_canonical_url_resolves_fk_with_position1_fallback` (all 4 branches: FK hit, FK None fallback, stale FK fallback, empty-streams empty-string).

### Task 2 — repo.py ALTER + backfill + setter (commit `7ddb0f5c`)

Added to `musicstreamer/repo.py`:

- `ALTER TABLE stations ADD COLUMN canonical_stream_id INTEGER REFERENCES station_streams(id) ON DELETE SET NULL` — placed after the last Phase-96 ALTER block (after the legacy URL rebuild block, Pitfall 2)
- Idempotent position-1 backfill UPDATE guarded by `WHERE canonical_stream_id IS NULL AND EXISTS(streams)` and an `updated_at` column presence check (see Deviations)
- `def set_canonical_stream(station_id, stream_id)` — dedicated single-column UPDATE, NOT routed through `update_station` (Pitfall 1); parameterized SQL (T-97-02)
- `canonical_stream_id=r["canonical_stream_id"]` in `list_stations` and `get_station` builders (needed to turn 5 repo canonical tests GREEN in one commit)

All 5 canonical repo tests turned GREEN: migration idempotence, default None on streamless station, position-1 backfill, set_canonical_stream round-trip, ON DELETE SET NULL.

### Task 3 — repo.py remaining builders (commit `18d501f5`)

Added `canonical_stream_id=r["canonical_stream_id"]` to the 4 remaining Station builders:
- `list_recently_played`
- `list_favorite_stations`
- `list_flagged_stations_for_provider`
- `list_stations_for_provider`

All 6 builders now carry the column (canonical count == preferred_stream_id count == 6). Full 121-test repo suite passes with no regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Backfill UPDATE triggered stations_updated_at on legacy test-fixture schema**
- **Found during:** Task 3 overall verification (test_bitrate_kbps_migration_adds_column failed)
- **Issue:** The `CREATE TRIGGER IF NOT EXISTS stations_updated_at` in `db_init`'s initial CREATE TABLE block always runs (even if the main table already exists). When a legacy test creates a bare `stations` table without `updated_at`, the trigger is created. My backfill UPDATE then fires the trigger, which references `updated_at` → OperationalError.
- **Fix:** Added `updated_at` + `canonical_stream_id` column presence guard (mirrors Phase 89.1 `_backfill_eligible` pattern). Backfill only runs on schemas that have `updated_at` (i.e. properly-migrated tables).
- **Files modified:** musicstreamer/repo.py
- **Commit:** `18d501f5`

**2. [Rule 2 - Missing Critical Functionality] Builder threading done in Task 2 commit**
- **Found during:** Task 2 — after ALTER + setter, the backfill test (`test_canonical_stream_id_backfill_defaults_position1`) called `repo.get_station()` and expected `canonical_stream_id != None` but got None (builder not threading yet)
- **Fix:** Added `canonical_stream_id=r[...]` to `list_stations` and `get_station` in the Task 2 commit to turn all 5 RED tests GREEN in a single GREEN gate rather than waiting for Task 3. Task 3 then added the remaining 4 builders.
- **Files modified:** musicstreamer/repo.py
- **Commit:** `7ddb0f5c`

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-97-02: SQL injection in set_canonical_stream | All values bound via `?` placeholders — no string interpolation of IDs |
| T-97-03: Dangling FK after stream delete | ON DELETE SET NULL FK active; position-1 fallback in canonical_url |

## Self-Check: PASSED

### Files exist:
- FOUND: musicstreamer/models.py
- FOUND: musicstreamer/repo.py

### Commits exist:
- FOUND: `22cd6bac` — feat(97-02): add Station.canonical_stream_id field + canonical_url property
- FOUND: `7ddb0f5c` — feat(97-02): add canonical_stream_id ALTER + backfill + set_canonical_stream setter
- FOUND: `18d501f5` — feat(97-02): thread canonical_stream_id through all Station builders in repo.py

### Acceptance criteria verified:
- `grep -c "canonical_stream_id" musicstreamer/models.py` = 5 (>= 1)
- `grep -c "def canonical_url" musicstreamer/models.py` = 1
- `grep -c "ADD COLUMN canonical_stream_id" musicstreamer/repo.py` = 1
- `grep -c "def set_canonical_stream" musicstreamer/repo.py` = 1
- canonical_stream_id=r[ count == preferred_stream_id=r[ count == 6
- 5 repo canonical tests GREEN; 1 url_helpers canonical test GREEN; 121 total repo tests pass
