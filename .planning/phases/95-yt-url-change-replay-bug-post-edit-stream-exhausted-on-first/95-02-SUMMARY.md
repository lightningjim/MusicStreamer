---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: 02
subsystem: player
tags: [gstreamer, youtube, qt, signals, failover, generation-guard, pyside6, gap-closure]

# Dependency graph
requires:
  - phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
    plan: 01
    provides: invalidate_for_edit + _youtube_resolve_seq guard (the resolve-path generation idiom mirrored here for the error-recovery path)

provides:
  - "_recovery_seq generation counter — bumped at play() entry; supersedes any error-recovery POSTED before the restart"
  - "_error_recovery_requested widened to Signal(int) carrying the recovery generation captured at error-POST time"
  - "_handle_gst_error_recovery -1-sentinel stale-recovery early-return — rejects stale (pre-restart) deliveries, passes through genuine current-generation exhaustions"
  - "V11/V12/V13 unit coverage for the recovery-generation guard"
affects: [player, youtube, failover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recovery-path generation guard: _recovery_seq bumped at play() entry; _on_gst_error captures it at POST time on the bus thread; _handle_gst_error_recovery rejects deliveries whose stamp != current at RUN time — identical to _preroll_seq / _youtube_resolve_seq idiom"
    - "-1 sentinel for backward-compat on 1-arg signal widening: default=-1 means 'no explicit stamp → skip staleness check'; only explicitly-stamped real QueuedConnection deliveries are checked"

key-files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/_fake_player.py
    - tests/test_player_edit_invalidation.py

key-decisions:
  - "Dedicated _recovery_seq (not reusing _youtube_resolve_seq): the error-recovery path is semantically independent; reusing the resolve-path counter would over-suppress (it is bumped unconditionally on every invalidate_for_edit including metadata-only edits, while _recovery_seq must NOT be bumped on D-02/D-04/D-05 no-restart branches)"
  - "POST-time stamp capture: _on_gst_error reads self._recovery_seq on the bus thread and carries it on the Signal; run-time capture would read the post-restart seq and let a pre-restart recovery pass the guard — defeating the fix"
  - "Bump exactly once at play() entry (covers all restarts including invalidate_for_edit D-01 delegation; D-04/D-05 no-restart branches do NOT bump)"
  - "-1 sentinel default (not 0): play() bumps _recovery_seq to ≥1; a default of 0 would evaluate '0 != 1' → True → early-return on every existing no-arg direct test caller; -1 unconditionally skips the staleness check for backward compat"

requirements-completed: []

# Metrics
duration: ~15min
completed: 2026-06-19
---

# Phase 95 Plan 02: _recovery_seq Generation Guard on Error-Recovery Path Summary

**`_recovery_seq` generation guard on the error-recovery path closes the spurious "Stream exhausted" toast gap: a queued error-recovery POSTED before an edit→restart now early-returns in `_handle_gst_error_recovery` instead of hitting `_try_next_stream()` against the freshly-emptied queue.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-19
- **Completed:** 2026-06-19
- **Tasks:** 2 (RED → GREEN)
- **Files modified:** 3 (0 created, 3 modified)

## Accomplishments

- `_recovery_seq: int = 0` declared in `__init__` alongside `_youtube_resolve_seq` with the same CPython-atomic-int rationale comment.
- `_error_recovery_requested` widened from `Signal()` to `Signal(int)`; `_on_gst_error` now emits `self._error_recovery_requested.emit(self._recovery_seq)` to capture the recovery generation at POST time (bus thread).
- `_recovery_seq += 1` bump added at the top of `play()` (after `_recovery_in_flight = False`, before the preroll-teardown block) — covers every restart including `invalidate_for_edit`'s `self.play(station)` delegation; D-04/D-05 no-restart branches left untouched.
- `_handle_gst_error_recovery` widened to `(self, recovery_seq: int = -1)` with a leading `if recovery_seq != -1 and recovery_seq != self._recovery_seq: return` guard placed ABOVE the `_recovery_in_flight` coalescing check. The -1 sentinel means "no explicit stamp → skip staleness check" so every existing no-arg direct caller is preserved without edits.
- FakePlayer `_error_recovery_requested = Signal(int)` parity mirrored.
- V11 (stale recovery suppressed), V12 (genuine current-generation exhaustion still toasts), V13 (metadata-only edit leaves legitimate recovery unaffected) — 100 tests pass (14 edit-invalidation + 27 failover + 59 player + 2 parity = 100 total, 0 failures).

## Task Commits

Each task committed atomically (TDD: test → feat):

1. **Task 1: RED — failing tests + FakePlayer parity** - `41e7b618` (test)
2. **Task 2: GREEN — _recovery_seq guard implementation** - `918a7e0e` (feat)

_TDD gate compliance: `test(95-02)` commit (RED) precedes `feat(95-02)` commit (GREEN)._

## Files Modified

- `musicstreamer/player.py` — `_error_recovery_requested = Signal(int)`; `_recovery_seq: int = 0` declaration; `_recovery_seq += 1` at play() entry; `_on_gst_error` emits `self._error_recovery_requested.emit(self._recovery_seq)`; `_handle_gst_error_recovery(self, recovery_seq: int = -1)` with leading staleness guard.
- `tests/_fake_player.py` — `_error_recovery_requested = Signal(int)` (parity mirror, Phase 95-02).
- `tests/test_player_edit_invalidation.py` — V11, V12, V13 test functions appended (140+ lines).

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface introduced.
- T-95-03 (CPython-atomic int read cross-thread): mitigated — identical justification to `_preroll_seq`; int read on the bus thread, carried on the queued Signal payload; no shared mutable state crosses the boundary.
- T-95-04 (over-suppression hiding genuine exhaustion): mitigated — V12 enforces the hard constraint (explicit current-seq passes through to `_try_next_stream` → `failover.emit(None)`); the D-04/D-05 no-restart branches do not bump `_recovery_seq`.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: musicstreamer/player.py (contains `_recovery_seq`, `Signal(int)` for `_error_recovery_requested`, `_recovery_seq += 1` in play(), `-1` sentinel guard in `_handle_gst_error_recovery`)
- FOUND: tests/_fake_player.py (contains `_error_recovery_requested = Signal(int)`)
- FOUND: tests/test_player_edit_invalidation.py (contains V11, V12, V13 test functions)
- FOUND commits: 41e7b618 (RED test), 918a7e0e (GREEN feat)
- VERIFIED: 100 tests pass (0 failures) across test_player_edit_invalidation.py + test_player_failover.py + test_player.py + test_fake_player_signal_parity.py

---
*Phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first*
*Completed: 2026-06-19*
