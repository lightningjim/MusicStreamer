---
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
plan: "01"
subsystem: db-repo
tags: [phase-82, schema, repo, station, preferred-stream, sqlite, tdd]
dependency_graph:
  requires: []
  provides:
    - stations.preferred_stream_id column (nullable INTEGER FK to station_streams.id ON DELETE SET NULL)
    - Station.preferred_stream_id field (Optional[int] = None)
    - Repo.set_preferred_stream(station_id, stream_id)
    - preferred_stream_id propagated through all four Station-builders
    - FakeRepo.set_preferred_stream no-op in test_stream_picker.py and test_now_playing_panel.py
  affects:
    - musicstreamer/models.py (Station dataclass extended)
    - musicstreamer/repo.py (migration + 4 builders + new setter)
    - tests/test_repo.py (9 new tests)
    - tests/test_stream_picker.py (FakeRepo no-op shield)
    - tests/test_now_playing_panel.py (FakeRepo no-op shield)
tech_stack:
  added: []
  patterns:
    - try/except sqlite3.OperationalError ALTER TABLE idiom (Phase 47/73 precedent)
    - Station dataclass append-after-last-field rule (keyword default preserves positional compat)
    - FakeRepo no-op shield pattern (Plan 82-03 AttributeError prevention)
key_files:
  created: []
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - tests/test_repo.py
    - tests/test_stream_picker.py
    - tests/test_now_playing_panel.py
decisions:
  - "FK target corrected: plan said REFERENCES streams(id) but actual table is station_streams; corrected to REFERENCES station_streams(id) (Rule 1 auto-fix)"
  - "No PRAGMA user_version introduced: D-08 try/except ALTER idiom only, matching Phase 47/73 precedent"
  - "ALTER TABLE lands AFTER cover_art_source block: Pitfall 2 mitigated (legacy URL-column rebuild block ends before the new ALTER)"
metrics:
  duration: "~7 min"
  completed: "2026-05-22T13:06:00Z"
  tasks_completed: 2
  files_modified: 5
---

# Phase 82 Plan 01: DB + Repo Layer for preferred_stream_id Summary

Adds nullable `preferred_stream_id INTEGER` FK column to `stations` table, threads it through the `Station` dataclass and all four `Station`-constructing Repo methods, adds `Repo.set_preferred_stream()` setter, and seeds `set_preferred_stream` no-ops into the two inline `FakeRepo` classes used by the existing UI test suite.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests: migration + schema | 048673e | tests/test_repo.py |
| 1 (GREEN) | preferred_stream_id migration + Station field | d673450 | musicstreamer/models.py, musicstreamer/repo.py |
| 2 (RED) | Failing tests: Station-builders + set_preferred_stream | 796dd24 | tests/test_repo.py |
| 2 (GREEN) | Station-builders + setter + FakeRepo shields | c8f2702 | musicstreamer/repo.py, tests/test_stream_picker.py, tests/test_now_playing_panel.py |

## Output Spec Confirmations

**ALTER TABLE placement (Pitfall 2 mitigated):** The `preferred_stream_id` ALTER block was placed immediately after the `cover_art_source` ALTER block (lines 268-280 of the final repo.py), which is already after the legacy URL-column rebuild block (lines 195-252). This ensures the column lands on the rebuilt table.

**No PRAGMA user_version:** Verified — `grep -c user_version musicstreamer/repo.py` outputs `0`.

**Exact 4 line numbers where `preferred_stream_id=r["preferred_stream_id"]` was added:**
- Line 474: `list_stations()` Station-builder
- Line 511: `get_station()` Station-builder
- Line 607: `list_recently_played()` Station-builder
- Line 720: `list_favorite_stations()` Station-builder

**Test counts:**
- New tests added in tests/test_repo.py: **9** (3 migration/schema + 6 round-trip)
- FakeRepo no-ops added: 1 in tests/test_stream_picker.py, 1 in tests/test_now_playing_panel.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected FK target from `streams(id)` to `station_streams(id)`**
- **Found during:** Task 1 GREEN
- **Issue:** Plan specified `REFERENCES streams(id)` but the actual table name is `station_streams`. SQLite raised `OperationalError: no such table: main.streams` on `create_station()` with PRAGMA foreign_keys = ON.
- **Fix:** Changed FK reference to `REFERENCES station_streams(id) ON DELETE SET NULL`
- **Files modified:** musicstreamer/repo.py
- **Commit:** d673450

## Verification Results

- `uv run pytest tests/test_repo.py -k preferred_stream -x -q` — 12 tests pass (9 new + 3 pre-existing)
- `uv run pytest tests/test_repo.py -x -q` — 78/78 pass (full Repo suite, no regressions)
- `uv run pytest tests/test_stream_picker.py tests/test_now_playing_panel.py -x -q` — 150/150 pass (FakeRepo no-ops prevent AttributeError)

## Known Stubs

None — all new functionality is fully wired. `set_preferred_stream` writes to the DB; all four Station-builders read back the value. The UI hookup (Plan 82-03 `_on_stream_selected`) and Player layer consultation (Plan 82-02) are deferred per the plan's stated scope boundary.

## Self-Check: PASSED

- musicstreamer/models.py: `preferred_stream_id: Optional[int] = None` field present
- musicstreamer/repo.py: `ALTER TABLE stations ADD COLUMN preferred_stream_id` migration present (1 occurrence)
- musicstreamer/repo.py: `def set_preferred_stream` method present (1 occurrence)
- musicstreamer/repo.py: `preferred_stream_id=r["preferred_stream_id"]` in exactly 4 Station-builders
- tests/test_repo.py: 9 new tests added (3 migration + 6 round-trip)
- tests/test_stream_picker.py: `def set_preferred_stream` no-op present (1 occurrence)
- tests/test_now_playing_panel.py: `def set_preferred_stream` no-op present (1 occurrence)
- Commits: 048673e, d673450, 796dd24, c8f2702 all verified in git log
