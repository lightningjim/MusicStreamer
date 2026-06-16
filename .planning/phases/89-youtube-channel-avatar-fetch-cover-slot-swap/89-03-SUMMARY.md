---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
plan: 03
subsystem: testing
tags: [cover-art, drift-guard, source-grep, avatar, precedence]

# Dependency graph
requires:
  - phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
    provides: "89-01 DB migration (channel_avatar_path column), 89-02 yt_import fetch_channel_avatar"
provides:
  - "Named _mb_caa_lookup and _channel_avatar_lookup wrappers in cover_art.py (ART-AVATAR-09 structurally stable)"
  - "Source-grep precedence drift-guard test_mb_caa_runs_before_channel_avatar (tests/test_cover_art_avatar.py)"
  - "Phase 89 RichText parity guard test_richtext_baseline_unchanged_by_phase_89 (ART-AVATAR-10)"
affects:
  - "89-04 (bind_station avatar swap uses _channel_avatar_lookup hook)"
  - "89b Twitch avatar (precedence drift-guard already in place)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Source-grep drift-guard over named functions (not behavioral mocks) for cover-resolver precedence"
    - "_channel_avatar_lookup synchronous never-raise stub contract (WR-04)"

key-files:
  created:
    - tests/test_cover_art_avatar.py
  modified:
    - musicstreamer/cover_art.py
    - tests/test_constants_drift.py

key-decisions:
  - "_channel_avatar_lookup is intentionally NOT wired into fetch_cover_art auto dispatch — live trigger is bind_station in 89-04 (RESEARCH.md Q2, RESOLVED)"
  - "Added os import to cover_art.py (required by _channel_avatar_lookup path ops, was missing)"

patterns-established:
  - "Named wrapper pattern: thin wrapper functions before fetch_cover_art lock precedence structurally, tested by source-grep on function positions"
  - "RichText baseline parity guard: each phase that touches render paths appends its own test mirroring the Phase 71 baseline"

requirements-completed: [ART-AVATAR-07, ART-AVATAR-09, ART-AVATAR-10]

# Metrics
duration: 8min
completed: 2026-06-16
---

# Phase 89 Plan 03: cover_art.py named wrappers + precedence drift-guard

**Named _mb_caa_lookup / _channel_avatar_lookup wrappers inserted in cover_art.py; source-grep precedence drift-guard (ART-AVATAR-09) and Phase 71 RichText parity guard (ART-AVATAR-10) both green**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-16T19:20:00Z
- **Completed:** 2026-06-16T19:28:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Inserted `_mb_caa_lookup` (thin wrapper over `_cover_art_mb.fetch_mb_cover`) and `_channel_avatar_lookup` (synchronous never-raise stub reading `channel_avatar_path`) between `_split_artist_title` and `fetch_cover_art` in `cover_art.py`, in that exact source order
- Replaced both inline `_cover_art_mb.fetch_mb_cover(...)` call sites inside `fetch_cover_art` (mb_only and auto branches) with `_mb_caa_lookup(...)` so the precedence drift-guard is structurally stable
- Created `tests/test_cover_art_avatar.py` with `test_mb_caa_runs_before_channel_avatar` (source-grep assert mb_pos < avatar_pos) plus field-filter and `_channel_avatar_lookup` unit tests (9 tests total)
- Appended `test_richtext_baseline_unchanged_by_phase_89` to `tests/test_constants_drift.py` — asserts RichText count remains 3 after Phase 89 (ART-AVATAR-10)
- All 28 tests pass (1 pre-existing failure `test_soma_nn_requirements_registered` is unrelated to Phase 89)

## Task Commits

1. **Task 1: Named wrappers + precedence drift-guard** - `3e608183` (feat)
2. **Task 2: Phase 89 RichText parity drift-guard** - `9b8109f6` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `musicstreamer/cover_art.py` - Added `os` import; inserted `_mb_caa_lookup` and `_channel_avatar_lookup`; replaced inline MB dispatch calls with `_mb_caa_lookup`
- `tests/test_cover_art_avatar.py` - New: source-grep drift-guard + field-filter + `_channel_avatar_lookup` unit tests
- `tests/test_constants_drift.py` - Appended `test_richtext_baseline_unchanged_by_phase_89`

## Decisions Made

- `_channel_avatar_lookup` is intentionally NOT called from `fetch_cover_art`'s `auto` dispatch chain per RESEARCH.md Q2 (RESOLVED). The live ICY-disabled avatar swap fires from `bind_station` in `now_playing_panel` (Plan 89-04), not through `fetch_cover_art`. The stub is positioned for ART-AVATAR-09 drift-guard only.
- Added `os` import to `cover_art.py` — it was missing but required by `_channel_avatar_lookup`'s `os.path.join` / `os.path.exists` calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing `os` import to cover_art.py**
- **Found during:** Task 1 (test_channel_avatar_lookup_existing_path_calls_cb_abs failing)
- **Issue:** `_channel_avatar_lookup` uses `os.path.join` and `os.path.exists` but `os` was not imported at module level in `cover_art.py`; call returned `None` instead of the resolved path
- **Fix:** Added `import os` to the module-level imports in `cover_art.py`
- **Files modified:** `musicstreamer/cover_art.py`
- **Verification:** `test_channel_avatar_lookup_existing_path_calls_cb_abs` turns GREEN; all 20 cover-art avatar tests pass
- **Committed in:** `3e608183` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking missing import)
**Impact on plan:** Essential for correctness; `_channel_avatar_lookup` would have returned `None` for all valid paths. No scope creep.

## Issues Encountered

None beyond the auto-fixed `os` import gap.

## Known Stubs

`_channel_avatar_lookup` is a real synchronous stub reading `station.channel_avatar_path` — it is intentionally not wired into `fetch_cover_art`'s auto dispatch. This is by design (RESEARCH.md Q2, RESOLVED); the live trigger is `bind_station` in now_playing_panel (Plan 89-04). The stub is fully functional and satisfies the ART-AVATAR-09 drift-guard.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary crossings introduced. `_channel_avatar_lookup` reads only a local filesystem path; the path resolution uses `paths.data_dir()` (existing trusted root). T-89-07, T-89-08, T-89-09 mitigations are all in place.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Named wrappers and precedence drift-guard are locked; ART-AVATAR-07/09 satisfied
- ART-AVATAR-10 RichText baseline guard green
- Plan 89-04 can implement `bind_station` ICY-disabled avatar swap and wire `_set_avatar_pixmap_from_path` — the `_channel_avatar_lookup` hook is ready

---
*Phase: 89-youtube-channel-avatar-fetch-cover-slot-swap*
*Completed: 2026-06-16*
