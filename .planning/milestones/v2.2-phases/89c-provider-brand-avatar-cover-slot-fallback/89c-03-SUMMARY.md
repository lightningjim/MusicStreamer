---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: "03"
subsystem: ui
tags: [pyside6, qt, edit-station-dialog, brand-avatar, provider-avatar, dialog-populate]

# Dependency graph
requires:
  - phase: 89c-01
    provides: "brand-avatar cover-slot fallback logic in now_playing_panel.py"
  - phase: 89c-02
    provides: "WR-01/WR-02 code-review fixes and drift-guards"
provides:
  - "_populate() in EditStationDialog invokes _refresh_avatar_preview() so persisted provider_avatar_path renders in the avatar preview on dialog reopen (Phase 89.1 D-07 reuse-on-open)"
  - "Drift-guard test test_populate_refreshes_avatar_preview pinning the call inside _populate body"
affects: [89c-HUMAN-UAT, test_brand_avatars]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_populate() mirrors logo-preview pattern for avatar-preview: both refresh previews from persisted paths before _capture_dirty_baseline()"
    - "Source-grep drift-guard: locate method def, extract body to next \\n    def, assert token in body (structural contract, no Qt behavioral mocks)"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_brand_avatars.py

key-decisions:
  - "Avatar preview refresh placed after _refresh_logo_preview() and before _capture_dirty_baseline() — matches existing logo-preview-on-open pattern; dirty baseline is unaffected (avatar/logo state outside snapshot scope)"
  - "Source-grep drift-guard chosen over Qt behavioral mock per feedback_gstreamer_mock_blind_spot project convention"

patterns-established:
  - "Reuse-on-open pattern (D-07): _populate() refreshes all persistent previews (logo + avatar) from stored paths before baseline capture"

requirements-completed: [ART-AVATAR-05]

# Metrics
duration: 5min
completed: 2026-06-17
---

# Phase 89c Plan 03: Gap Closure Summary

**One-line addition to EditStationDialog._populate() — `self._refresh_avatar_preview()` alongside `self._refresh_logo_preview()` — closes 89c UAT Test 5 (brand image not shown on dialog reopen, Phase 89.1 D-07)**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-17T17:35:00Z
- **Completed:** 2026-06-17T17:40:17Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `self._refresh_avatar_preview()` call in `EditStationDialog._populate()` immediately after `self._refresh_logo_preview()` and before `self._capture_dirty_baseline()`, with an inline comment citing Phase 89.1 D-07 and 89c UAT Test 5
- Added drift-guard test `test_populate_refreshes_avatar_preview` in `tests/test_brand_avatars.py` using the established method-body-extraction source-grep pattern, asserting the call appears in the extracted `_populate` body
- All 11 `tests/test_brand_avatars.py` tests pass; `grep -c` confirms 4 total `_refresh_avatar_preview()` call sites (3 pre-existing fetch/pick + 1 new populate)

## Task Commits

1. **Task 1: Refresh avatar preview on dialog open + drift-guard** - `abaad3d9` (fix)

**Plan metadata:** (included in final docs commit)

## Files Created/Modified

- `musicstreamer/ui_qt/edit_station_dialog.py` — Added `self._refresh_avatar_preview()` call in `_populate()` at ~L678 (after `_refresh_logo_preview()`, before `_capture_dirty_baseline()`)
- `tests/test_brand_avatars.py` — Added `test_populate_refreshes_avatar_preview` drift-guard test (source-grep structural contract)

## Decisions Made

- Avatar-preview refresh placed before `_capture_dirty_baseline()` so the render does not perturb the dirty-state snapshot (avatar/logo state is outside the dirty-tracked widget set — verified by existing plan notes)
- Source-grep structural guard chosen (not Qt behavioral mock) per project convention (`feedback_gstreamer_mock_blind_spot`)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The single UAT Test 5 gap from 89c UAT (brand image not shown on dialog reopen) is structurally closed by this fix
- Ready for UAT re-verification on Test 5 (manual confirm: reopen EditStationDialog for a station with a persisted brand image — avatar preview should populate on open)
- Phase 89c is now complete (all 3 plans done, all 5 UAT tests addressed)

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check

- [x] `musicstreamer/ui_qt/edit_station_dialog.py` exists and contains `self._refresh_avatar_preview()` in `_populate()` body
- [x] `tests/test_brand_avatars.py` contains `def test_populate_refreshes_avatar_preview`
- [x] Commit `abaad3d9` confirmed in git log
- [x] All 11 `tests/test_brand_avatars.py` tests pass
- [x] 4 call sites confirmed via grep

## Self-Check: PASSED

---
*Phase: 89c-provider-brand-avatar-cover-slot-fallback*
*Completed: 2026-06-17*
