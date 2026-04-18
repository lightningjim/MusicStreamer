---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 05
subsystem: player
tags: [failover, gstreamer, bus-errors, gap-closure, uat]
requires: []
provides:
  - "Player._recovery_in_flight in-flight guard"
  - "Player._clear_recovery_guard deferred-release helper"
  - "same-URL bus-error cascade coalescing"
affects:
  - "musicstreamer/player.py"
  - "tests/test_player_failover.py"
tech_stack_added: []
patterns:
  - "deferred-clear via QTimer.singleShot(0, ...) for in-flight guards"
  - "reset-on-public-action (co-located with _streams_queue resets)"
key_files_created:
  - path: ""
    note: "no new files"
key_files_modified:
  - path: "musicstreamer/player.py"
    note: "added _recovery_in_flight flag, guard logic in _handle_gst_error_recovery, _clear_recovery_guard helper, 4 reset sites (play/play_stream/pause/stop)"
  - path: "tests/test_player_failover.py"
    note: "2 regression tests for error-cascade coalescing + guard-reset-between-URLs"
decisions:
  - "Defer guard clear via QTimer.singleShot(0, _clear_recovery_guard) instead of clearing synchronously — ensures already-queued recovery callbacks for the OLD URL drain and see the guard set, while fresh errors on the NEW URL find it cleared"
  - "Reset guard in play/play_stream/pause/stop co-located with existing _streams_queue resets — parallels the existing reset-on-public-action pattern"
  - "Guard lives exclusively on the main thread — bus-loop handler continues to only schedule via singleShot; no cross-thread synchronisation required"
metrics:
  duration_min: 4
  tasks_completed: 2
  files_modified: 2
  lines_added_net: 88
  tests_added: 2
  tests_passing_delta: "+1 (26 failed baseline → 25 failed after; all 25 remaining failures are pre-existing missing-deps in system python env)"
completed_date: "2026-04-18"
---

# Phase 47 Plan 05: Stream bitrate quality ordering — gap closure (error-cascade coalescing) Summary

In-flight guard added to `Player._handle_gst_error_recovery` coalesces cascading playbin3 bus errors for a single failing URL into exactly one failover-queue advance, closing UAT gap 5 (spurious "Stream exhausted") and mitigating UAT gap 4 (invisible failover toast).

## Root Cause

playbin3 emits multiple bus errors during pipeline teardown for a single broken stream URL — typically one from the source element, one from the demuxer, and one from the decoder as the pipeline is torn down. Before this fix, each error scheduled an independent `QTimer.singleShot(0, self._handle_gst_error_recovery)` on the main thread. Each queued recovery popped the next entry from `_streams_queue` via `_try_next_stream`.

For a 3-stream station where only the low-quality fallback was actually functional:

```
t=0ms:   play(station) → current=stream1 (broken), queue=[stream2 (broken), stream3 (working)]
t=~10ms: playbin3 source error   → singleShot → recovery pops stream2, current=stream2
t=~12ms: playbin3 demuxer error  → singleShot → recovery pops stream3, current=stream3
t=~14ms: playbin3 decoder error  → singleShot → recovery pops nothing, emits failover(None)
```

The user saw "Stream exhausted" in milliseconds before the working stream ever had a chance to load. The failover toast also fired 3 times in ~14ms, scrolling past too fast to be visible — which is why UAT gap 4 (failover-toast invisibility) was a side-effect of the same bug.

## Fix

Added `self._recovery_in_flight: bool = False` to Player runtime state. `_handle_gst_error_recovery` now early-returns if the guard is set; otherwise sets the guard, performs the recovery, and schedules a deferred clear via `QTimer.singleShot(0, self._clear_recovery_guard)` on both the twitch-resolve branch and the main `_try_next_stream` path.

The deferred clear (rather than a synchronous end-of-method reset) is load-bearing: any already-queued recovery callbacks from the old URL sit behind us in the main-thread event queue. They must see the guard still set so they no-op. The clear only runs after those drain.

Reset sites: `play()`, `play_stream()`, `pause()`, `stop()` all set `_recovery_in_flight = False` alongside their existing `_streams_queue` reset — so a new user action cannot inherit a stale guard from a prior session.

## Reset Sites

| Method | Line | Reason |
| --- | --- | --- |
| `play(station, ...)` | 158 | Fresh station play starts clean |
| `play_stream(stream, ...)` | 192 | Manual stream selection bypasses queue |
| `pause()` | 201 | User-initiated pause clears recovery state |
| `stop()` | 210 | Stop always fully resets |

## Thread Safety

The guard is read/written exclusively on the main thread:
- `_handle_gst_error_recovery` — scheduled onto main thread by bus handler via `QTimer.singleShot(0, ...)`
- `_clear_recovery_guard` — scheduled onto main thread via `QTimer.singleShot(0, ...)`
- `play` / `play_stream` / `pause` / `stop` — called by UI code on main thread

The bus-loop thread (`_on_gst_error`) only emits signals and schedules the recovery via singleShot — it never touches `_recovery_in_flight` directly. No locks, no atomics, no cross-thread races.

## New Tests

- `test_multiple_gst_errors_advance_queue_once` — invokes `_handle_gst_error_recovery()` three times synchronously (simulating cascading errors for one URL) without letting the singleShot(0) clear fire; asserts the queue advanced exactly once.
- `test_recovery_guard_resets_between_distinct_url_failures` — calls recovery, waits 20ms for the guard-clear singleShot to fire, calls recovery again; asserts both advances took effect.

## Verification Results

- `test_multiple_gst_errors_advance_queue_once`: PASS (GREEN)
- `test_recovery_guard_resets_between_distinct_url_failures`: PASS
- `test_gst_error_triggers_failover` (pre-existing single-error test): PASS — guard is a superset of prior behavior when exactly one error fires.
- Full failover suite: **18 passed, 2 pre-existing env failures** (`test_youtube_resolve_*` — missing `yt_dlp` in worktree system python, not related to this fix).
- Full suite delta: baseline 485 passed / 26 failed → after fix 486 passed / 25 failed. Net: +1 pass (our new coalescing test). All 25 remaining failures are pre-existing `ModuleNotFoundError` for `yt_dlp`, `streamlink`, etc. in the worktree's system python environment — out of scope for this plan.

## Acceptance Criteria Status

| Criterion | Status |
| --- | --- |
| `Player._recovery_in_flight` field initialized to False | PASS |
| `_handle_gst_error_recovery` early-returns when guard is set | PASS |
| Sets guard before `_try_next_stream`; schedules clear via `QTimer.singleShot(0, ...)` on both twitch and main paths | PASS (grep count = 2) |
| `_clear_recovery_guard` method sets `_recovery_in_flight = False` | PASS |
| `play`, `play_stream`, `stop`, `pause` all reset `_recovery_in_flight = False` | PASS (grep count = 5 total including init) |
| Two regression tests pass; existing failover tests pass | PASS |
| Full suite green (modulo pre-existing env issues) | PASS |

## UAT Gap Closure

- **Gap 5 (major):** CLOSED — failover queue no longer drains prematurely on cascading bus errors.
- **Gap 4 (side-effect):** MITIGATED — each stream now gets its full BUFFER_DURATION_S window so the "Stream failed, trying next…" toast actually has time to render instead of scrolling past in milliseconds.

## Deviations from Plan

None — plan executed exactly as written. The plan's fix block was lifted verbatim from `.planning/debug/stream-exhausted-premature.md` and applied as specified.

**Note on debug doc location:** The debug doc `stream-exhausted-premature.md` was not physically present in this worktree (it was moved to `debug/resolved/` in a later commit beyond this worktree's base). The plan itself contains the complete verbatim fix in the `<action>` blocks, so no context was missing.

**Note on orphan environment failures:** The worktree's system python is missing `yt_dlp` and `streamlink` — this causes 25 pre-existing failures across unrelated test modules. Those are out of scope per the SCOPE BOUNDARY rule; they were present before this plan and remain after. Logged only as context here.

## Commits

- `38b21b1` test(47-05): add failing regressions for error-cascade coalescing (RED gate)
- `a8e6e0b` fix(47-05): guard _handle_gst_error_recovery against cascading bus errors (GREEN gate)

## TDD Gate Compliance

RED and GREEN gates present in git log. REFACTOR not needed — the fix is minimal (single guard flag + deferred-clear helper + 4 one-line resets) and has no dead code or duplication to clean up.

## Self-Check: PASSED

- FOUND: `musicstreamer/player.py` (modified)
- FOUND: `tests/test_player_failover.py` (modified)
- FOUND: commit `38b21b1` (RED test)
- FOUND: commit `a8e6e0b` (GREEN fix)
- FOUND: `_recovery_in_flight` flag, guard check, `_clear_recovery_guard` helper, 2 singleShot clear-schedules, 4 public-API reset sites (grep counts match acceptance criteria)
