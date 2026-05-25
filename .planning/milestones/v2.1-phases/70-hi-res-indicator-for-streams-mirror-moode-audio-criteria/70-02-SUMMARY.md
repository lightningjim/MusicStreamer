---
phase: 70
plan: "02"
subsystem: data-layer
tags: [schema, sqlite, migration, dataclass, tdd-green]
dependency_graph:
  requires: [70-00]
  provides: [StationStream.sample_rate_hz, StationStream.bit_depth, station_streams schema migration]
  affects: [musicstreamer/models.py, musicstreamer/repo.py]
tech_stack:
  added: []
  patterns: [idempotent-ALTER-try-except-OperationalError, append-trailing-kwargs-default-zero]
key_files:
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
decisions:
  - "Appended sample_rate_hz + bit_depth after bitrate_kbps in StationStream — Phase 47.1 D-01 precedent (positional construction compat preserved)"
  - "Two independent ALTER TABLE blocks (one per column) so partial migration still completes — mirrors Phase 47.2 D-02 idiom"
  - "No PRAGMA user_version bump — codebase invariant confirmed via grep gate"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-12"
  tasks_completed: 2
  files_changed: 2
---

# Phase 70 Plan 02: StationStream + Repo schema extension for sample_rate_hz / bit_depth

## One-liner

Added `sample_rate_hz: int = 0` and `bit_depth: int = 0` to `StationStream` dataclass and `station_streams` SQLite schema via idempotent ALTER TABLE migration, with full Repo CRUD support.

## What Was Built

Extended the data layer to cache per-stream audio quality metadata (sample rate and bit depth) detected at runtime from GStreamer caps. The migration shape mirrors Phase 47.2's `bitrate_kbps` idiom exactly: two new columns in the `CREATE TABLE` body plus two independent `try/except sqlite3.OperationalError` ALTER TABLE blocks that fire on pre-Phase-70 databases. Default 0 for both columns means existing rows roll forward without backfill (DS-05).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend StationStream dataclass + schema + list_streams hydration | f67ed63 | musicstreamer/models.py, musicstreamer/repo.py |
| 2 | Extend insert_stream + update_stream signatures + SQL | f67ed63 | musicstreamer/repo.py |

Both tasks were committed atomically in a single commit since the changes are tightly coupled (dataclass fields, CREATE TABLE columns, ALTER TABLE blocks, and CRUD signatures all form one coherent migration unit).

## Verification Results

- `pytest tests/test_repo.py -k "sample_rate_hz or bit_depth or db_init_idempotent"` — 3/3 passed (RED -> GREEN)
- `pytest tests/test_repo.py` — 61/61 passed (no regression)
- `pytest tests/test_aa_import.py tests/test_yt_import_library.py tests/test_discovery_dialog.py tests/test_settings_import_dialog.py` — 59/59 passed (positional caller regression clean)
- Keyword construction: `StationStream(id=1, station_id=1, url='x', sample_rate_hz=96000, bit_depth=24)` prints `96000 24`
- Positional construction: `StationStream(1, 1, 'x', '', '', 1, '', 'FLAC', 1411)` succeeds unchanged
- Schema validation: `PRAGMA table_info(station_streams)` shows `sample_rate_hz` and `bit_depth` columns present
- Grep gate: `ALTER TABLE station_streams ADD COLUMN sample_rate_hz` appears exactly 1 time
- Grep gate: `ALTER TABLE station_streams ADD COLUMN bit_depth` appears exactly 1 time
- Grep gate: `PRAGMA user_version` count in repo.py == 0

## Deviations from Plan

None — plan executed exactly as written. Both tasks were coalesced into a single commit since they modify the same file set as a coherent migration unit.

## Known Stubs

None. The data layer is fully wired: `insert_stream` writes the values, `list_streams` reads them back, and the schema migration runs idempotently.

## Threat Flags

No new security surface beyond what the plan's threat model documented. All new SQL uses parameterized `?` placeholders (T-70-04 mitigation). The `try/except sqlite3.OperationalError` pattern is the accepted T-70-05 trade-off matching Phase 47.2 D-02 precedent.

## Self-Check: PASSED

Files verified present in worktree:
- musicstreamer/models.py: FOUND (sample_rate_hz, bit_depth fields confirmed)
- musicstreamer/repo.py: FOUND (ALTER TABLE blocks, insert/update/list_streams confirmed)

Commit f67ed63 verified in git log.
