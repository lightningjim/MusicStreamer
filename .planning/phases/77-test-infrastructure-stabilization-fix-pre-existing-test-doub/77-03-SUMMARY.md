---
phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub
plan: 03
subsystem: testing
tags: [mpris2, dbus, pytest-fixture, monkeypatch, test-isolation]

# Dependency graph
requires:
  - phase: 77-01
    provides: base test infrastructure stabilization work
provides:
  - unique_mpris_service_name fixture in tests/conftest.py eliminating D-Bus service name collisions
  - 8 MPRIS2 LinuxMprisBackend tests now race-safe and repeatable across sequential runs
affects: [any future plan touching tests/test_media_keys_mpris2.py, MPRIS2 backend testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-test unique D-Bus service name via monkeypatch.setattr at module level (D-10/D-18)"
    - "Fixture teardown with try/except unregisterService belt-and-suspenders (D-11)"
    - "Opt-in (not autouse) fixture injection to avoid cost on unrelated tests"

key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_media_keys_mpris2.py

key-decisions:
  - "D-10: Per-test unique SERVICE_NAME suffix using os.getpid() + uuid4().hex[:8] prevents registerService collision on shared session bus"
  - "D-11: Fixture teardown explicitly unregisters unique service name via bus.unregisterService with try/except guard"
  - "D-18: unique_mpris_service_name fixture lives in tests/conftest.py (not a separate _mpris_helpers.py)"
  - "Production musicstreamer/media_keys/mpris2.py byte-identical — zero production code change"
  - "Fixture is NOT autouse: 5 cover-art tests pay no monkeypatch cost since they don't touch the D-Bus bus"

patterns-established:
  - "Pattern: monkeypatch.setattr(module, 'CONSTANT', value) is visible to bare-name module-level lookups at call time — no closure capture workaround needed"
  - "Pattern: Lazy import inside fixture teardown clause (PySide6.QtDBus.QDBusConnection) avoids module-scope import ordering issues with conftest.py:13 QT_QPA_PLATFORM setup"

requirements-completed: [INFRA-01]

# Metrics
duration: 12min
completed: 2026-05-17
---

# Phase 77 Plan 03: MPRIS2 unique_mpris_service_name fixture + 8 test wiring Summary

**Per-test unique D-Bus service name via conftest fixture eliminates the `registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error` cluster across all 8 LinuxMprisBackend tests**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-17T17:05:00Z
- **Completed:** 2026-05-17T17:17:46Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `unique_mpris_service_name` fixture to `tests/conftest.py` that monkeypatches `musicstreamer.media_keys.mpris2.SERVICE_NAME` to a per-test unique value (`org.mpris.MediaPlayer2.musicstreamer.test_{pid}_{uuid8}`) before `LinuxMprisBackend.__init__` runs
- Wired fixture into all 8 MPRIS2 tests (`test_linux_mpris_backend_constructs`, `_publish_metadata`, `_publish_metadata_none`, `_set_playback_state`, `test_playerctl_lists_service`, `_slot_play_pause_emits_signal`, `_shutdown_idempotent`, `test_xesam_title_passthrough_verbatim`)
- Swapped Test 6's hardcoded literal assertion to use `unique_mpris_service_name in registered`
- Two sequential `uv run pytest tests/test_media_keys_mpris2.py` runs both exit 0 with 12 passed, 1 skipped (`test_playerctl_lists_service` requires playerctl binary)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add unique_mpris_service_name fixture to tests/conftest.py** - `b4b8065` (feat)
2. **Task 2: Inject unique_mpris_service_name into 8 MPRIS2 tests** - `7b72c8d` (feat)

## Files Created/Modified
- `tests/conftest.py` - Added `import uuid` + `unique_mpris_service_name(monkeypatch)` fixture (23 lines added)
- `tests/test_media_keys_mpris2.py` - 8 test signatures updated; Test 6 assertion literal swapped for fixture variable (9 insertions, 9 deletions)

## Decisions Made
- Applied D-10/D-11/D-18 exactly as specified in CONTEXT.md — no implementation choices were needed beyond following the locked decisions
- Fixture placement: inserted between `_stub_bus_bridge` (autouse) and the Phase 60 GBS fixtures block, consistent with module grouping convention
- Baseline test run before Task 2 showed tests passing in a clean bus state — this is expected; the collision occurs when tests run repeatedly without a dbus-launch reset between runs, which the fixture now prevents

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `uv run python -c "import tests.conftest"` raised `ModuleNotFoundError: No module named 'pytest'` because the plain `python -c` invocation inside `uv run` does not pre-activate the project's pytest env; verified conftest correctness via `uv run pytest --collect-only tests/conftest.py` which showed clean 0-item collection with no parse errors.

## Known Stubs
None.

## Threat Flags
None - plan modifies only test files; no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Pre-fix Baseline
- Failure cluster: `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`
- Cause: shared session bus, no per-test suffix on the module-level `SERVICE_NAME` constant
- Affected tests: all 7 LinuxMprisBackend tests + `test_xesam_title_passthrough_verbatim` = 8 tests total
- Post-fix: `git diff musicstreamer/` returns empty; `uv run pytest tests/test_media_keys_mpris2.py` exits 0 both sequentially

## Self-Check: PASSED
- `tests/conftest.py`: FOUND
- `tests/test_media_keys_mpris2.py`: FOUND
- Commit b4b8065: FOUND
- Commit 7b72c8d: FOUND
- `grep -cE "def test_.*unique_mpris_service_name" tests/test_media_keys_mpris2.py` = 8
- `git diff musicstreamer/media_keys/mpris2.py` = empty

## Next Phase Readiness
- MPRIS2 D-Bus collision cluster (cluster 2 of 6 in Phase 77) eliminated
- No residual work for this plan; 77-03 is self-contained
- Parallel plans 77-02 and 77-04 operate on disjoint files and are unaffected

---
*Phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub*
*Completed: 2026-05-17*
