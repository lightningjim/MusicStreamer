---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: "03"
subsystem: player
tags: [gap-closure, tdd, youtube, resolve, exhaustion-gate, phase-95]
dependency_graph:
  requires: [95-01, 95-02]
  provides: [_youtube_resolve_in_flight gate, V14, V15, V16]
  affects: [musicstreamer/player.py, tests/test_player_edit_invalidation.py]
tech_stack:
  added: []
  patterns:
    - "Instance-attribute stamp for resolution-failed staleness (no Signal arity change)"
    - "CPython-atomic bool gate pattern (mirrors _preroll_in_flight)"
    - "TDD RED/GREEN: test first, gate logic second"
key_files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player_edit_invalidation.py
decisions:
  - "Instance-attribute stamp approach (_youtube_resolve_in_flight_seq) chosen for _on_youtube_resolution_failed staleness detection — avoids widening youtube_resolution_failed Signal arity and keeps FakePlayer parity guard GREEN with no FakePlayer edit"
  - "_handle_gst_error_recovery early-return placed AFTER the _recovery_seq (95-02) guard and the _recovery_in_flight (Gap-05) coalescing guard, WITHOUT setting _recovery_in_flight before the new early-return, so a later legitimate recovery after the gate clears is not coalesced away"
  - "V12 reconciled in place: _youtube_resolve_in_flight=False added to setup explicitly (genuine exhaustion path); docstring narrowed to 'no resolve in flight' case; not folded into V15 so the test remains discoverable as a 95-02 hard constraint"
metrics:
  duration: "~3m"
  completed: "2026-06-20"
  tasks_completed: 2
  files_modified: 2
---

# Phase 95 Plan 03: YouTube-Resolve-In-Flight Exhaustion Gate Summary

**One-liner:** `_youtube_resolve_in_flight` bool gate in player.py that suppresses spurious `failover(None)` toasts while an async YouTube resolve is pending, with seq-matched clearing on settle and instance-attribute staleness guard for failure deliveries.

## What Was Built

Phase 95-03 closes the residual Phase 95 UAT gap: editing a YouTube station whose stream had already ended, then saving a new working URL, flashed a single "Stream exhausted" toast before the new stream played.

Root cause: the bus error from the ended old stream carries the CURRENT `_recovery_seq` (posted after the restart), so the 95-02 `_recovery_seq` generation guard cannot block it. The queue is transiently empty during async YouTube resolution — a current-gen error recovery arriving in this window declares spurious exhaustion.

Fix: a `_youtube_resolve_in_flight` boolean gate that suppresses `failover.emit(None)` while the current generation's YouTube resolution is still pending.

### Implementation Details

**Gate declaration** (`player.py` ~line 604):
- `self._youtube_resolve_in_flight: bool = False` — CPython-atomic bool, same pattern as `_preroll_in_flight`
- `self._youtube_resolve_in_flight_seq: int = 0` — instance-attribute stamp for failure-slot staleness detection

**Set point** (`_play_youtube`): gate set `True` + `_youtube_resolve_in_flight_seq = seq` immediately after capturing `seq = self._youtube_resolve_seq`, before `threading.Thread(...).start()`. Set on the main thread before spawn — no race with the worker.

**Clear on success** (`_on_youtube_resolved`): `self._youtube_resolve_in_flight = False` AFTER the existing 95-01 seq guard, so a stale delivery never clears a fresh gate.

**Clear on failure** (`_on_youtube_resolution_failed`): instance-attribute staleness check (`_youtube_resolve_in_flight_seq != _youtube_resolve_seq`) — stale deliveries early-return without clearing gate or calling `_try_next_stream`. Current-gen failures: gate cleared BEFORE `_try_next_stream` so legitimate exhaustion (`failover(None)`) is still reachable.

**Gate on exhaustion** (`_try_next_stream`): `if self._youtube_resolve_in_flight: return` before `self.failover.emit(None)` — the pending resolve owns the next state transition.

**Gate on recovery** (`_handle_gst_error_recovery`): `if self._youtube_resolve_in_flight: return` placed AFTER the 95-02 `_recovery_seq` guard (line 1056) and AFTER the Gap-05 `_recovery_in_flight` coalescing guard (line 1064), WITHOUT setting `_recovery_in_flight = True` before the gate early-return. This ensures V11/V12/V13 (which leave `_youtube_resolve_in_flight=False`) are unaffected, and a later legitimate recovery after the gate clears is not coalesced away.

### Key Design Choice: Instance-Attribute Stamp

`_on_youtube_resolution_failed` currently takes only a `str` argument. The plan offered two options:
1. Widen `youtube_resolution_failed` to `Signal(str, int)` — requires updating `tests/_fake_player.py` (FakePlayer parity guard)
2. Instance-attribute stamp — store `_youtube_resolve_in_flight_seq` at spawn; compare in the slot against `_youtube_resolve_seq`

**Chosen: option 2 (instance-attribute stamp).** No Signal arity change, no FakePlayer edit, FakePlayer parity guard stays GREEN.

## Tests (TDD Red/Green)

**RED commit (59ca75bf):** V14/V15/V16 added; V12 reconciled. 4 tests failed for correct reasons (missing gate logic in player.py). V11/V13 unaffected.

**GREEN commit (152481f1):** Implementation landed. All 18 tests pass (V1-V16 + existing suite).

### Test Coverage

| Test | Scenario | Result |
|------|----------|--------|
| V14a | gate=True + current-seq recovery → `_try_next_stream` NOT called | GREEN |
| V14b | gate=True + direct `_try_next_stream()` + empty queue → no `failover(None)` | GREEN |
| V15 | gate=False + empty queue + current-seq recovery → `failover(None)` exactly once | GREEN |
| V16a | Current-gen `_on_youtube_resolved` → gate cleared | GREEN |
| V16b | Stale `_on_youtube_resolved` → gate NOT cleared, `_set_uri` NOT called | GREEN |
| V16c | Current-gen `_on_youtube_resolution_failed` → gate cleared + `failover(None)` | GREEN |
| V16d | Stale `_on_youtube_resolution_failed` → gate NOT cleared, `_try_next_stream` NOT called | GREEN |
| V12 | Reconciled: explicit gate=False; empty queue + no resolve → `failover(None)` | GREEN |
| V11/V13 | Unchanged; scenarios never set gate | GREEN |

## Deviations from Plan

None — plan executed exactly as written. Instance-attribute stamp was the RECOMMENDED approach and was implemented as specified.

## Self-Check

### Created files exist
- `.planning/phases/95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first/95-03-SUMMARY.md` — this file

### Commits exist
- 59ca75bf — test(95-03): add failing V14/V15/V16 + reconcile V12
- 152481f1 — feat(95-03): implement _youtube_resolve_in_flight gate

### Known Stubs

None — all gate logic is fully wired. Tests exercise the actual production code paths.

### Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The gate is a pure internal boolean on the Player object, read and written exclusively on the Qt main thread via queued signals. No new trust boundaries.

## Self-Check: PASSED

- [x] musicstreamer/player.py: `_youtube_resolve_in_flight` declared, set in `_play_youtube`, cleared in settle slots, consulted in `_try_next_stream` and `_handle_gst_error_recovery`
- [x] tests/test_player_edit_invalidation.py: V14/V15/V16 added, V12 reconciled, V11/V13 unchanged
- [x] 59ca75bf (RED commit) exists
- [x] 152481f1 (GREEN commit) exists
- [x] All 18 tests pass: `18 passed, 1 warning in 0.16s`
- [x] FakePlayer parity guard: `2 passed`
- [x] No Signal arity change; `tests/_fake_player.py` unchanged
- [x] 95-01 (`_youtube_resolve_seq`) and 95-02 (`_recovery_seq`) guards intact
