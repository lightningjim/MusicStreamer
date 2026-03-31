---
phase: 12-favorites
plan: "01"
subsystem: database
tags: [sqlite, dataclass, tdd, pytest, itunes-api]

# Dependency graph
requires: []
provides:
  - Favorite dataclass in musicstreamer.models
  - favorites table with UNIQUE(station_name, track_title) dedup constraint
  - Repo.add_favorite, remove_favorite, list_favorites, is_favorited
  - cover_art._parse_itunes_result returning {artwork_url, genre}
  - cover_art.last_itunes_result module-level dict for genre access
affects: [12-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - INSERT OR IGNORE for silent dedup on favorites
    - strftime millisecond precision for created_at (matches existing last_played_at pattern)
    - module-level result dict for cross-function state sharing without extra HTTP calls

key-files:
  created:
    - tests/test_favorites.py
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/cover_art.py

key-decisions:
  - "strftime('%Y-%m-%dT%H:%M:%f','now') for favorites created_at — datetime('now') second granularity caused ordering test failure (same fix applied to last_played_at in Phase 7)"
  - "last_itunes_result module-level dict stores full iTunes result so genre is available without a second API call"

patterns-established:
  - "Favorites dedup: UNIQUE(station_name, track_title) + INSERT OR IGNORE — callers never need to pre-check existence"

requirements-completed: [FAVES-02]

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 12 Plan 01: Favorites Data Layer Summary

**SQLite favorites table with INSERT OR IGNORE dedup, four Repo CRUD methods, and iTunes genre extraction via _parse_itunes_result — all backed by 9 passing unit tests**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-30T03:04:15Z
- **Completed:** 2026-03-30T03:07:07Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Favorite dataclass with all required fields added to models.py
- favorites DB table with millisecond-precision created_at and UNIQUE(station_name, track_title) constraint
- All four Repo methods (add_favorite, remove_favorite, list_favorites, is_favorited) with correct dedup via INSERT OR IGNORE
- _parse_itunes_result extracts both artwork_url and primaryGenreName from iTunes JSON without extra HTTP calls
- 9 TDD tests covering dedup, ordering, removal, and genre parsing

## Task Commits

1. **Task 1: Favorite dataclass, DB schema, repo CRUD, genre parser** - `98f3eff` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `musicstreamer/models.py` - Added Favorite dataclass
- `musicstreamer/repo.py` - Added favorites table to db_init; added add_favorite, remove_favorite, list_favorites, is_favorited to Repo
- `musicstreamer/cover_art.py` - Added _parse_itunes_result, last_itunes_result; updated _worker to use _parse_itunes_result
- `tests/test_favorites.py` - 9 new unit tests (TDD)

## Decisions Made

- strftime millisecond precision for `created_at` default — `datetime('now')` has second-level granularity which caused the ordering test to fail when inserts happened within the same second. Same fix used for `last_played_at` in Phase 7.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used ms-precision strftime for favorites created_at**
- **Found during:** Task 1 (GREEN phase — test_list_favorites_order failed)
- **Issue:** `datetime('now')` has second-level granularity; 0.05s sleep between inserts is insufficient to distinguish rows
- **Fix:** Changed `DEFAULT (datetime('now'))` to `DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))` in schema
- **Files modified:** musicstreamer/repo.py
- **Verification:** test_list_favorites_order passes
- **Committed in:** 98f3eff (task commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for correct ordering behavior; identical pattern already established in Phase 7.

## Issues Encountered

Pre-existing test failures in test_icy_escaping.py, test_player_tag.py, test_player_volume.py, test_yt_thumbnail.py — all fail due to missing `gi` (GTK) module in uv environment. Unrelated to this plan; no regressions introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Favorite dataclass importable from musicstreamer.models
- All four Repo CRUD methods ready for UI layer consumption
- Genre available from last_itunes_result for display in favorites view
- Ready for Plan 02: favorites UI (star button, favorites list toggle)
</content>
</invoke>