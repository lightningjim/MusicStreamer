---
phase: 41-platform-media-keys
plan: 04
subsystem: ui
tags: [mpris, media-keys, logging, qt, pyside6]

requires:
  - phase: 41-03
    provides: MediaKeysBackend wiring in MainWindow, spy test fixtures

provides:
  - publish_metadata(None, "", None) on all five stop transitions in main_window.py
  - logging.basicConfig(WARNING) in __main__.main() so media_keys warnings reach stderr
  - Five regression tests for metadata-clear on stop (UAT gap closure)

affects: [41-platform-media-keys, 43-windows-media-keys]

tech-stack:
  added: []
  patterns:
    - "publish_metadata(None) always precedes set_playback_state('stopped') on stop transitions"
    - "logging.basicConfig in main() entry point — not in _run_gui or _run_smoke"

key-files:
  created:
    - .planning/phases/41-platform-media-keys/41-04-SUMMARY.md
  modified:
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/__main__.py
    - tests/test_main_window_media_keys.py

key-decisions:
  - "publish_metadata(None) placed BEFORE set_playback_state('stopped') so MPRIS clients see cleared metadata before stopped state"
  - "logging.basicConfig in main() only — _run_smoke and _run_gui do not configure logging independently"

patterns-established:
  - "Stop transitions: publish_metadata(None, '', None) then set_playback_state('stopped') — always in that order"

requirements-completed: [MEDIA-04, MEDIA-05]

duration: 5min
completed: 2026-04-16
---

# Phase 41 Plan 04: Gap Closure — Stale MPRIS Metadata + Logging Summary

**Cleared MPRIS metadata on all five stop transitions and wired logging.basicConfig so media_keys warnings reach stderr**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-16T02:51:07Z
- **Completed:** 2026-04-16T02:56:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- All five stop paths in MainWindow now call `publish_metadata(None, "", None)` before `set_playback_state("stopped")`, clearing stale MPRIS metadata from playerctl (UAT gap 1 resolved)
- `logging.basicConfig(level=WARNING)` added as first line of `main()` so module-level `_log.warning()` calls in media_keys reach stderr (UAT gap 9 resolved)
- Five TDD tests added covering all stop transitions; full test suite at 13/13 for media keys module

## Task Commits

1. **Task 1 RED: failing tests for metadata-clear** - `7d94d14` (test)
2. **Task 1 GREEN: clear MPRIS metadata on all stop transitions** - `ca9cc11` (feat)
3. **Task 2: configure logging in __main__** - `842f7cf` (feat)

## Files Created/Modified
- `musicstreamer/ui_qt/main_window.py` - Added `publish_metadata(None, "", None)` to `_on_panel_stopped`, `_on_media_key_stop`, `_on_failover(None)`, `_on_offline`, `_on_station_deleted`
- `musicstreamer/__main__.py` - Added `import logging` and `logging.basicConfig(level=logging.WARNING)` in `main()`
- `tests/test_main_window_media_keys.py` - Five new tests: `test_panel_stopped_clears_metadata`, `test_media_key_stop_clears_metadata`, `test_failover_none_clears_metadata`, `test_offline_clears_metadata`, `test_station_deleted_clears_metadata`

## Decisions Made
- `publish_metadata(None)` placed before `set_playback_state("stopped")` — MPRIS clients observe cleared metadata before the stopped state, avoiding a window where playerctl could show stale track info with "stopped" state
- `logging.basicConfig` lives only in `main()` — not duplicated in `_run_smoke` or `_run_gui`, both of which are called from `main()`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None - no new trust boundaries introduced. WARNING-level logging only; no PII in media_keys warnings; stderr is local-only (per T-41-04-01 accept disposition in plan).

## Self-Check: PASSED

- `musicstreamer/ui_qt/main_window.py` — FOUND, 5 publish_metadata(None) calls confirmed
- `musicstreamer/__main__.py` — FOUND, `logging.basicConfig` confirmed (grep: 1 occurrence)
- `tests/test_main_window_media_keys.py` — FOUND, 13/13 tests pass
- Commits: 7d94d14, ca9cc11, 842f7cf — all present in git log

## Next Phase Readiness

Phase 41 UAT gaps fully closed. All stop transitions clear MPRIS metadata. Media keys warnings visible on stderr. Phase 41 acceptance criteria met.

---
*Phase: 41-platform-media-keys*
*Completed: 2026-04-16*
