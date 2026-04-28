---
phase: 52-eq-toggle-dropout-fix
plan: 01
subsystem: audio

tags:
  - gstreamer
  - audio
  - equalizer
  - qtimer
  - dsp

# Dependency graph
requires:
  - phase: 47.2
    provides: equalizer-nbands element in playbin3.audio-filter slot, _apply_eq_state writer, GstChildProxy band mutation primitive
provides:
  - QTimer-driven smooth gain ramp on Player.set_eq_enabled (40ms / 8 ticks of 5ms)
  - 4 new helper methods on Player (_capture_current_gains, _compute_target_gains, _start_eq_ramp, _on_eq_ramp_tick)
  - Reverse-from-current behavior on rapid re-toggle (D-05)
  - T-52-01 mitigation in set_eq_profile (cancels in-flight ramp before potential _rebuild_eq_element)
affects:
  - any future EQ profile-load smoothing
  - any future preamp-slider smoothing (could reuse the same ramp infrastructure)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "QTimer with tick-counter that stops itself after N ticks (bound-method timeout, parent=self) — composes _failover_timer (single-shot) and _elapsed_timer (interval) precedents"
    - "Per-tick dB-linear lerp with final-tick exact-commit (no float residual)"

key-files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player.py

key-decisions:
  - "Ramp constants: _EQ_RAMP_MS=40, _EQ_RAMP_TICKS=8, _EQ_RAMP_INTERVAL_MS=5 placed near _EQ_BAND_TYPE on Player (per CONTEXT discretion)"
  - "Per-tick writes ONLY gain (D-04); freq/bandwidth/type written ONCE in _start_eq_ramp fresh-ramp branch"
  - "Reverse-from-current (D-05): mid-ramp set_eq_enabled re-captures live element gains as new start_gain via GstChildProxy, replaces target, resets tick_index, keeps timer running"
  - "Final tick (k >= _EQ_RAMP_TICKS) commits exact target — no lerp residual"
  - "T-52-01: ramp-cancel guard inserted as FIRST two statements of set_eq_profile before any potential _rebuild_eq_element call — avoids stale GstChildProxy write after element rebuild"
  - "Lifecycle: pause()/stop() also stop the ramp timer + clear ramp state (mirrors _elapsed_timer.stop() precedent)"
  - "Test deviation: existing test_player_eq_apply_profile and test_player_eq_preamp_uniform_offset extended to drive the 8 ticks via _eq_ramp_timer.timeout.emit() before asserting final gains — necessary because set_eq_enabled is now asynchronous"

patterns-established:
  - "EQ gain ramp pattern: GUI-thread QTimer + ramp-state dict {start_gain, target_gain, tick_index} — composable for future smoothing of preamp-slider drags"
  - "Manual timer drive in tests: ramp tests use player._eq_ramp_timer.timeout.emit() instead of qtbot.wait — same idiom as test_elapsed_timer_*"

requirements-completed:
  - BUG-03

# Metrics
duration: 10min
completed: 2026-04-28
---

# Phase 52 Plan 01: EQ Toggle Dropout Fix Summary

**40ms 8-tick QTimer-driven dB-linear gain ramp on Player.set_eq_enabled — eliminates the IIR-coefficient-discontinuity click on EQ toggle while preserving graceful-degrade and the existing profile-load path**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-28T23:02:09Z
- **Completed:** 2026-04-28T23:12:03Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Replaced atomic gain-switch in `Player.set_eq_enabled` with smooth ramp (40ms / 8 ticks of 5ms) — closes BUG-03's click-on-toggle symptom
- Added four new Player helper methods: `_capture_current_gains`, `_compute_target_gains`, `_start_eq_ramp`, `_on_eq_ramp_tick`
- Reverse-from-current on rapid re-toggle (D-05): mid-ramp toggle captures live in-progress band gains as new ramp start; the same QTimer continues running with reset tick_index
- T-52-01 mitigation: `set_eq_profile` now stops any in-flight ramp before potentially calling `_rebuild_eq_element` — prevents a stale GstChildProxy write on the new element
- Five new ramp behavior tests in `tests/test_player.py`: progression lerp, final-tick exact commit, reverse-from-current, graceful-degrade no-timer, and set_eq_profile in-flight cancellation

## Task Commits

1. **Task 1: Add ramp state, timer, and helpers to Player** — `8a8fdee` (feat)
2. **Task 2: Ramp behavior tests in test_player.py** — `5ad26ce` (test)

## Files Created/Modified

- `musicstreamer/player.py` — +141 lines: ramp constants, `_eq_ramp_timer`/`_eq_ramp_state` instance state, refactored `set_eq_enabled`, T-52-01 guard in `set_eq_profile`, lifecycle stops in `pause()`/`stop()`, four new helper methods. `_apply_eq_state` body unchanged; still called from `set_eq_profile`/`set_eq_preamp`/`restore_eq_from_settings` (count = 3, was 4).
- `tests/test_player.py` — +218 lines: 5 new ramp tests + ramp-drive idiom inserted into 2 existing EQ tests (`test_player_eq_apply_profile`, `test_player_eq_preamp_uniform_offset`)

## Decisions Made

All decisions followed PLAN.md + CONTEXT.md D-01..D-07. The plan was executed with no architectural deviations. One test-harness deviation (Rule 1) below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing tests `test_player_eq_apply_profile` and `test_player_eq_preamp_uniform_offset` failed after Task 1 implementation**

- **Found during:** Task 1 verification (`pytest tests/test_player.py -k "eq" -x`)
- **Issue:** Plan acceptance criterion stated "existing 8 EQ tests still pass without modification" but this is structurally impossible. Both tests called `set_eq_enabled(True)` then immediately read `band.get_property("gain")` — relying on synchronous gain application. After Phase 52, `set_eq_enabled` triggers an asynchronous QTimer ramp; the gain stays at 0.0 until ticks fire. Asserting `gain == -3.5` on the next line failed.
- **Fix:** Inserted ramp-drive after each `set_eq_enabled(True/False)` call in the affected tests:
  ```python
  for _ in range(player._EQ_RAMP_TICKS):
      player._eq_ramp_timer.timeout.emit()
  ```
  This is the same manual-tick idiom used by the new ramp tests and by `test_elapsed_timer_emits_seconds_while_playing`. Semantic assertions (Pitfall 5 ADD, gain values, bypass zeroing) are unchanged — they now run after the final tick commits the exact target.
- **Files modified:** `tests/test_player.py` (test_player_eq_apply_profile, test_player_eq_preamp_uniform_offset)
- **Verification:** All 13 EQ tests pass (`pytest -k "eq"`); full test_player.py 17/17 passes
- **Committed in:** `8a8fdee` (rolled into Task 1 commit since the fix was inseparable from the implementation)
- **Why this is Rule 1, not Rule 4 (architectural):** The fix preserves the planner's exact contract — same ramp shape, same constants, same semantic assertions. Only the test harness migrated from "assume sync" to "drive async to completion". No code architecture changed; the test simulation just had to match the now-asynchronous ramp contract that the plan itself prescribed. This is the natural consequence of the plan's own D-02 decision and could not be avoided regardless of implementation choices short of defeating the ramp's purpose.

---

**Total deviations:** 1 auto-fixed (1 bug — test harness lag behind async contract)
**Impact on plan:** No scope creep. Code architecture matches plan exactly. The deviation was a misalignment between plan's `<verification>` "existing tests pass without modification" claim and the plan's own D-02 ramp specification — they were structurally incompatible. The 2-test fix preserves all existing assertion semantics.

## Issues Encountered

- **Worktree path resolution:** Initial Read/Edit tool calls used the bare repo path (`/home/kcreasey/OneDrive/Projects/MusicStreamer/...`) instead of the worktree path (`/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-aad03ca82db55ee05/...`). Edits were applied to the main repo working tree; git status in the worktree showed no changes. Resolved by `cp` of edited file to worktree + `git checkout --` of main repo, then continued using only worktree-prefixed absolute paths. No data loss.

## Pre-existing Test Failures (out of scope, not caused by Phase 52)

Documented for completeness — these failures pre-date Phase 52 and were observed in the broader test run (`pytest tests/`). All are in subsystems Phase 52 did not touch:

- `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` — D-Bus `registerObject` runtime failure (environment-dependent)
- `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` — Windows SMTC backend on Linux env
- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — pre-existing per Phase 50 verification report
- `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present` — Twitch auth, unrelated to EQ

Excluding these, suite is 785/785 passing. Including them, 785 passed / 4 failed — and Phase 50's verification confirmed at least one was already failing before any v2.1 work.

## User Setup Required

None — no external service configuration required.

UAT (manual, Kyle to perform when convenient — not blocking automated verify):
- Start a representative AudioAddict station; let it play for ~5s
- Click the EQ toggle once; listen for click/pop (SC #1: no audible artifact)
- Click again (SC #2: no audible artifact)
- Click rapidly 10× in 2s (SC #3: smooth audible transitions, no clicks, no lockup, no double-fire perception)

## Next Phase Readiness

- BUG-03 implementation complete; awaiting UAT pass to formally close the requirement
- Plan 52-02 (the SC #3 defensive `clicked`-wiring test in `test_now_playing_panel.py`) can run now — Wave 1 disjoint files, no dependency on this plan's commits beyond `set_eq_enabled` signature being unchanged (it is)
- Future smoothing work (preamp-slider drag, profile-load READY-state silence) could reuse the `_eq_ramp_*` infrastructure; both deferred per CONTEXT.md
- T-52-02 (ramp tick after pause()/stop() pipeline-NULL transition) is mitigated by lifecycle stops + defensive `if self._eq is None: return` in `_on_eq_ramp_tick`

## Self-Check: PASSED

- FOUND: musicstreamer/player.py
- FOUND: tests/test_player.py
- FOUND: .planning/phases/52-eq-toggle-dropout-fix/52-01-SUMMARY.md
- FOUND commit: 8a8fdee (Task 1)
- FOUND commit: 5ad26ce (Task 2)
- All 9 phase-level grep gates pass (constants, timer construction, four new method defs, no-lambda, _apply_eq_state count == 3, _eq_ramp_timer.stop count >= 3)
- 5 ramp tests pass (`pytest -k "eq_ramp"`)
- 13 EQ tests pass (`pytest -k "eq"` — 8 original + 5 new)
- 17 test_player.py tests pass (full file)

---
*Phase: 52-eq-toggle-dropout-fix*
*Completed: 2026-04-28*
