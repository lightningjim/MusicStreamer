---
phase: 27-add-multiple-streams-per-station-for-backup-round-robin-and-
plan: "01"
subsystem: data-model
tags: [sqlite, migration, dataclass, streams, tdd]
dependency_graph:
  requires: []
  provides: [station_streams-table, StationStream-dataclass, stream-CRUD, url-migration]
  affects: [repo, models, player, discovery_dialog, edit_dialog, main_window]
tech_stack:
  added: [StationStream dataclass, station_streams SQLite table]
  patterns: [table-recreation migration, cascade FK delete, N+1 streams per station]
key_files:
  created: []
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/player.py
    - musicstreamer/ui/discovery_dialog.py
    - musicstreamer/ui/edit_dialog.py
    - musicstreamer/ui/main_window.py
    - tests/test_repo.py
decisions:
  - "Station.url removed in favor of Station.streams: List[StationStream]; position=1 stream is primary"
  - "SQLite table recreation used for url column removal (no DROP COLUMN in SQLite < 3.35)"
  - "Migration idempotency via NOT EXISTS guard on INSERT and try/except on url column probe"
  - "edit_dialog url_entry shows streams[0].url; _save updates position=1 stream or creates/deletes as needed"
metrics:
  duration: "~10 min"
  completed: "2026-04-09T03:39:12Z"
  tasks_completed: 2
  files_modified: 7
requirements: [STR-01, STR-02, STR-03, STR-04, STR-05, STR-07, STR-08]
---

# Phase 27 Plan 01: StationStream Data Layer Summary

**One-liner:** SQLite station_streams table with url migration and StationStream dataclass replacing Station.url across all layers.

## What Was Built

- `StationStream` dataclass in models.py (id, station_id, url, label, quality, position, stream_type, codec)
- `Station.url` field removed; replaced with `streams: List[StationStream]` (default empty list)
- `station_streams` table in repo.py with FK cascade delete from stations
- Migration block in `db_init()`: probes for `url` column, migrates rows to `station_streams`, recreates `stations` table without `url`, restores `stations_updated_at` trigger
- New Repo methods: `list_streams`, `insert_stream`, `update_stream`, `delete_stream`, `reorder_streams`, `get_preferred_stream_url`
- Updated Repo methods: `station_exists_by_url` (queries station_streams), `insert_station` (routes url to stream row), `list_stations`/`get_station`/`list_recently_played` (populate streams field), `create_station`/`update_station` (no url column)
- `player.py`: resolves URL from `station.streams[0].url`; message updated to "(no streams configured)"
- `discovery_dialog.py`: preview Station uses `streams=[StationStream(...)]`; toggle-off check uses `streams[0].url`
- `edit_dialog.py`: url_entry initialized from `streams[0].url`; `_save` updates/creates/deletes the position=1 stream
- `main_window.py`: YouTube detection uses `st.streams[0].url`
- 22 new tests in test_repo.py covering schema, migration, idempotency, cascade delete, all CRUD methods, preferred stream fallback

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | afd643f | feat(27-01): add StationStream model, station_streams schema, migration, stream CRUD |
| 2 | e8197f0 | feat(27-01): update player and discovery_dialog for streams-based URL resolution |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Fixed edit_dialog.py and main_window.py station.url references**
- **Found during:** Task 1 (post-implementation grep)
- **Issue:** `edit_dialog.py` initialized `url_entry` from `station.url` and called `update_station(url=...)`. `main_window.py` used `st.url` for YouTube detection. Both would crash at runtime with AttributeError.
- **Fix:** `edit_dialog.py` now reads `streams[0].url` for url_entry init; `_save` updates/creates/deletes the position=1 stream. `main_window.py` reads `st.streams[0].url if st.streams else ""`.
- **Files modified:** musicstreamer/ui/edit_dialog.py, musicstreamer/ui/main_window.py
- **Commits:** afd643f (main_window.py, edit_dialog.py included in Task 1 commit)

## Known Stubs

None — all stream data is wired from SQLite. Existing stations with no streams will get an empty list (not a stub — this is correct behavior until streams are added via editor).

## Threat Flags

None beyond what was in the plan's threat model (T-27-01 migration idempotency mitigated via NOT EXISTS guard).

## Self-Check: PASSED

- musicstreamer/models.py: FOUND (contains StationStream)
- musicstreamer/repo.py: FOUND (contains station_streams, list_streams, insert_stream)
- tests/test_repo.py: FOUND (contains test_station_streams_schema)
- Commits afd643f and e8197f0: FOUND in git log
- 52 tests passing
- Zero `station.url` attribute references in musicstreamer/ source
