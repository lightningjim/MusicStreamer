---
phase: 57-windows-audio-glitch-test-fix
plan: 04
subsystem: player / audio-pipeline
tags: [player, gstreamer, qtimer, volume-ramp, smoothing, pause-resume, cross-platform, structural-guard, win-03, tdd]
status: complete
requires:
  - 57-CONTEXT.md (D-15 ramp template = Phase 52 EQ ramp; smoothing target = playbin3.volume)
  - 57-DIAGNOSTIC-LOG.md (sink = wasapi2sink; honors playbin3.volume natively)
  - 57-03-SUMMARY.md (bus-message STATE_CHANGED handler now in place; ramp composes by disjoint write windows)
provides:
  - musicstreamer/player.py: 3 ramp constants + _pause_volume_ramp_timer QTimer + _pause_volume_ramp_state in __init__ + restructured pause() + updated stop() + 2 new methods (_start_pause_volume_ramp, _on_pause_volume_ramp_tick)
  - tests/test_player_pause.py: updated test_pause_sets_pipeline_null + 3 new structural guard tests
affects:
  - Plan 57-05: Win11 VM UAT perceptual gate — verify no audible pop on pause/resume using the ramp shipped here
  - WIN-03 glitch half: ramp wrapper is the pre-NULL volume fade-down; pairs with 57-03's post-PLAYING re-apply
tech-stack:
  added: []
  patterns:
    - "Phase 52 EQ ramp template reused verbatim for pause-volume: QTimer(self) + setInterval(5ms) + timeout.connect + state dict + lerp + final-tick exact-target-then-NULL"
    - "D-05 reverse-from-current: _start_pause_volume_ramp reads live playbin3.volume via get_property, not self._volume"
    - "Composition by disjoint write windows: ramp runs PRE-NULL (pause() invocation), bus-message re-apply runs POST-PLAYING (57-03 handler)"
    - "Synchronous tick drain in tests: directly invoking _on_pause_volume_ramp_tick N times avoids QTimer real-time coupling"

key-files:
  created: []
  modified:
    - musicstreamer/player.py (3 constants + 1 QTimer + 2 methods + pause() restructure + stop() ramp-cancel — 96 lines added)
    - tests/test_player_pause.py (test_pause_sets_pipeline_null update + 3 new tests — 77 lines added)

key-decisions:
  - "D-15 confirmed: ramp writes to playbin3.volume (single property surface) via self._pipeline.set_property — no _volume_element (D-13)"
  - "Final tick owns set_state(NULL)+get_state(CLOCK_TIME_NONE) — audible level is 0 at the NULL transition, which is the no-pop goal"
  - "self._volume never mutated by ramp — Plan 57-03's bus-message handler re-applies the correct slider value on PLAYING-arrival"
  - "test_pause_sets_pipeline_null updated to drain ramp ticks synchronously — QTimer.wait would couple to wall-clock"

requirements-completed: [WIN-03]

duration: ~20min
completed: "2026-05-03"
---

# Phase 57 Plan 04: Pause-Volume Ramp Wrapper Summary

**QTimer-driven 8-tick fade-down of playbin3.volume (self._volume -> 0) in pause(), with final tick performing set_state(NULL), and 3 structural guard tests locking ramp arming + target-zero + self._volume immutability.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-03T15:26:00Z
- **Completed:** 2026-05-03T15:46:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Restructured `pause()` to arm a QTimer-driven 8-tick volume fade-down (from live `playbin3.volume` -> 0) before `set_state(NULL)`; the final tick performs the NULL teardown that used to be inline
- Added `_start_pause_volume_ramp` and `_on_pause_volume_ramp_tick` methods mirroring the Phase 52 EQ ramp pattern (D-05 reverse-from-current; try/except for mock pipeline readback)
- Updated `stop()` to cancel the new ramp timer (mirrors existing EQ ramp cancel pattern)
- Added 3 structural guard tests covering: timer armed on pause(), target=0.0 in ramp state, self._volume unchanged across all 8 ticks

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | feat(57-04): add pause-volume ramp QTimer + methods + invoke from pause() | b3f2199 |
| 2 | test(57-04): structural guard tests for pause-volume ramp (D-15) | 7d98029 |

## Files Created/Modified

- `musicstreamer/player.py` — 3 new class constants (`_PAUSE_VOLUME_RAMP_MS/TICKS/INTERVAL_MS`), QTimer + state in `__init__`, restructured `pause()`, updated `stop()`, new `_start_pause_volume_ramp` + `_on_pause_volume_ramp_tick` methods (96 lines added)
- `tests/test_player_pause.py` — Updated `test_pause_sets_pipeline_null` to drain ramp ticks synchronously; added section divider + 3 new structural guard tests (77 lines added)

## Acceptance Gate Results

```
Gate 1: grep -c "_pause_volume_ramp_timer" musicstreamer/player.py   => 8   PASS (>=5)
Gate 2: grep -c "_start_pause_volume_ramp" musicstreamer/player.py   => 2   PASS (1 def + 1 invocation in pause())
Gate 3: grep -c "_on_pause_volume_ramp_tick" musicstreamer/player.py => 3   PASS (1 timeout.connect + 1 docstring + 1 def; 2 code refs)
Gate 4: grep -c "_PAUSE_VOLUME_RAMP_TICKS" musicstreamer/player.py   => 5   PASS (>=2)
Gate 5: ! grep -q "_volume_element" musicstreamer/player.py          => PASS (D-13 invariant — no _volume_element)
Gate 6: grep -q "aa_normalize_stream_url(uri)" musicstreamer/player.py => PASS (Phase 56 D-04 preserved)
Gate 7: 3 new test functions in tests/test_player_pause.py            => 3   PASS
Gate 8: "Phase 57 / WIN-03 D-15" section divider in test file        => 2   PASS (section divider + test docstring)
```

## Test Results

```
PYTHONPATH=. uv run pytest tests/test_player_failover.py tests/test_player_pause.py tests/test_player_volume.py -v

collected 39 items — 39 passed, 1 warning in 0.64s
```

- 27 tests in test_player_failover.py (all Plan 57-03 + existing) GREEN
- 8 tests in test_player_pause.py (5 existing with test_pause_sets_pipeline_null updated + 3 new) GREEN
- 4 tests in test_player_volume.py (unchanged) GREEN

## Decisions Made

- **D-15 ramp template applied exactly:** Phase 52 EQ ramp (40ms/8 ticks/5ms) used verbatim with `playbin3.volume` as the write surface — no custom ramp cadence needed.
- **Final tick owns NULL teardown:** The last tick writes `volume=0` to the pipeline, then immediately calls `set_state(NULL)` + `get_state(CLOCK_TIME_NONE)`. This ensures the audible level is zero at the exact moment of NULL transition (the pop is at the NULL boundary).
- **self._volume immutable:** Ramp only writes to `playbin3.volume` (the pipeline property), never to `self._volume` (the Player attribute). This preserves Plan 57-03's bus-message re-apply contract — after resume, `_on_playbin_state_changed` reads `self._volume` and restores the user's slider position.
- **test_pause_sets_pipeline_null updated:** The test now calls `_on_pause_volume_ramp_tick()` N times synchronously before asserting `set_state(NULL)` — this avoids flaky wall-clock coupling while preserving the contract that pause() eventually transitions to NULL.

## Deviations from Plan

None — plan executed exactly as written. All invariants held:
- No `_volume_element` reference (D-13)
- `_set_uri` untouched — `aa_normalize_stream_url(uri)` first line preserved (Phase 56 D-04)
- `set_volume()` unchanged
- Ramp methods placed after `_on_eq_ramp_tick` and before `_rebuild_eq_element` as specified

## Issues Encountered

None.

## Note for Plan 57-05 VM UAT

The pause-volume ramp ships in this plan as a structural implementation. Linux CI cannot judge perceived audibility — the ramp's correctness is verified by:

1. **Structural invariants (this plan):** Timer armed, target=0, self._volume immutable, NULL eventually called.
2. **Composition contract (Plan 57-03 + 57-04 together):** Ramp runs PRE-NULL; bus-message re-apply runs POST-PLAYING. Disjoint write windows confirmed by test coverage on both sides.
3. **Perceptual gate (Plan 57-05 Win11 VM UAT):** The only way to confirm "no audible pop / gap / restart artifact" is a human listener on real Windows hardware.

**Exact pause-resume sequence for Plan 57-05 VM UAT:**
1. Open MusicStreamer on Win11 VM
2. Tune to SomaFM Drone Zone (or any non-YouTube/Twitch stream)
3. Confirm audio is playing at ~50% volume slider
4. Click Pause
5. Listen: expect a ~40ms smooth fade-out, then silence (no pop or click)
6. Wait 2 seconds
7. Click Play
8. Listen: expect audio to restart at the same volume level (no volume reset to 100%, no pop or click on rebuild)
9. Attest: "no audible pop / gap / restart artifact on pause, no volume jump on resume"

## Known Stubs

None — the ramp writes live arithmetic values (lerp from float readback to 0.0) directly to the mock pipeline in tests, and will write to the real `playbin3.volume` property in production. No hardcoded placeholders or TODO paths.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The pause-volume ramp operates entirely in-process on `playbin3.volume` — a GObject property write on the main thread. No new trust boundaries crossed. All STRIDE threats T-57-04-01 through T-57-04-05 are mitigated as designed (see plan's threat_model section).

## Self-Check: PASSED

- FOUND: musicstreamer/player.py (modified)
- FOUND: tests/test_player_pause.py (modified)
- FOUND: .planning/phases/57-windows-audio-glitch-test-fix/57-04-SUMMARY.md (this file)
- FOUND: commit b3f2199 (feat(57-04): player.py)
- FOUND: commit 7d98029 (test(57-04): tests)
