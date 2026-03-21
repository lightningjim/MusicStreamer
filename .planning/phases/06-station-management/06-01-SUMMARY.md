---
phase: 06-station-management
plan: 01
subsystem: database
tags: [sqlite, dataclass, icy-metadata, gstreamer]

requires:
  - phase: 05-display-polish
    provides: ICY title display with GLib.idle_add callback pattern in _on_title closure
provides:
  - Station.icy_disabled bool field (default False) in models.py
  - delete_station(station_id) method in Repo
  - Idempotent ALTER TABLE migration for icy_disabled column
  - update_station with icy_disabled parameter
  - ICY suppression guard in _on_title closure
  - _current_station tracking in MainWindow for is-playing detection
  - EditStationDialog.is_playing kwarg stub for Plan 02
affects:
  - 06-station-management plan 02 (UI wires delete button and icy_disabled toggle to these contracts)

tech-stack:
  added: []
  patterns:
    - "ALTER TABLE ... IF NOT EXISTS column via try/except OperationalError for idempotent SQLite migrations"
    - "icy_disabled stored as INTEGER 0/1 in SQLite, mapped to bool via bool() on read, int() on write"
    - "Early-return guard in GLib.idle_add callback checks self._current_station.icy_disabled before updating UI"

key-files:
  created: []
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/ui/main_window.py
    - musicstreamer/ui/edit_dialog.py
    - tests/test_repo.py

key-decisions:
  - "ICY suppression guard lives in the _on_title closure (not in Player), keeping suppression logic UI-side where user intent is tracked"
  - "icy_disabled defaults to False at both dataclass and SQL column level so migration is safe on existing rows"
  - "is_playing lambda passed to EditStationDialog now (stub) so Plan 02 can use it without refactoring call site"

patterns-established:
  - "TDD: failing tests committed (RED) before implementation (GREEN) for all new repo methods"
  - "SQLite boolean: store as INTEGER, read with bool(), write with int()"

requirements-completed: [MGMT-01, ICY-01]

duration: 3min
completed: 2026-03-21
---

# Phase 06 Plan 01: Data Model + Repo + ICY Suppression Summary

**Station.icy_disabled field wired through SQLite migration, Repo CRUD, and MainWindow playback guard — delete_station and is-playing tracking added for Plan 02 UI**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T14:36:33Z
- **Completed:** 2026-03-21T14:39:11Z
- **Tasks:** 2 (Task 1 TDD: 3 commits; Task 2: 1 commit)
- **Files modified:** 5

## Accomplishments
- Station dataclass gains `icy_disabled: bool = False`; DB gets idempotent ALTER TABLE migration
- `delete_station` removes a station row; `update_station` now persists `icy_disabled`
- ICY TAG events suppressed in `_on_title` when `station.icy_disabled` is True; `_current_station` tracked in MainWindow for live is-playing checks

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing tests** - `21383f7` (test)
2. **Task 1 GREEN: models + repo implementation** - `2f3056e` (feat)
3. **Task 2: MainWindow + EditDialog** - `800832e` (feat)

_TDD task had two commits: test (RED) then feat (GREEN). No refactor step needed._

## Files Created/Modified
- `musicstreamer/models.py` - Added `icy_disabled: bool = False` to Station dataclass
- `musicstreamer/repo.py` - db_init migration, delete_station, update_station with icy_disabled, list/get mapping
- `musicstreamer/ui/main_window.py` - _current_station tracking, ICY suppression guard in _on_title, is_playing lambda in _open_editor
- `musicstreamer/ui/edit_dialog.py` - __init__ accepts is_playing=None kwarg, stored as self.is_playing
- `tests/test_repo.py` - 6 new tests: delete_station, delete_station_list, icy_disabled_default, icy_disabled_round_trip, icy_disabled_migration, update_station_preserves_icy_disabled

## Decisions Made
- ICY suppression guard sits in the `_on_title` closure (not Player), keeping suppression logic UI-side where user intent is tracked via `_current_station`
- `icy_disabled` defaults to False at both dataclass and SQL column level so migration is safe on existing rows with no backfill
- `is_playing` lambda passed to EditStationDialog as a stub now so Plan 02 wires the delete/disable UI without touching the call site again

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- All backend contracts for Plan 02 are in place: `delete_station`, `update_station(icy_disabled=)`, `is_playing` lambda on EditStationDialog
- Plan 02 can add the delete button and ICY disable toggle to EditStationDialog without any further model or repo changes

---
*Phase: 06-station-management*
*Completed: 2026-03-21*
