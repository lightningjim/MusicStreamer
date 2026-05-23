---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/player.py
  - tests/_fake_player.py
  - tests/test_player.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 83: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 83 introduces a SomaFM-only "preroll" cluster: `Player.play()` randomly
picks a station ID, plays it on playbin3, and at `about-to-finish` performs a
gapless URI handoff to the station's actual stream. The state machine has a
narrow happy-path that the new tests exercise well, but several cross-thread
windows around `_preroll_in_flight` / `_preroll_handler_id` are not defended
against, and one of them is a head-of-queue corruption bug (CR-01) that the
test suite does not catch.

The gapless `set_property("uri", ...)` slot mirrors `_try_next_stream`'s
bookkeeping carefully (tracker bind, elapsed-timer seeding, failover-timer
arm) and routes through `aa_normalize_stream_url`. Backfill worker uses
Pattern 4 thread-local Repo and is single-flight via `_backfill_in_flight`.
The provider-gate literal `"SomaFM"` and `_last_preroll_played_at` are
pinned by drift-guards.

The preroll START itself has no failover-timeout watchdog — only bus-error
and EOS bridges catch a dead preroll URL. `stop()` / `pause()` do not clear
the preroll flag or disconnect the handler, which leaks a handler across
station switches and allows stale `about-to-finish` slots to pop the next
station's queue.

## Critical Issues

### CR-01: `_on_preroll_about_to_finish` has no `_preroll_in_flight` re-entry guard — bus-error + about-to-finish race pops `_streams_queue` twice

**File:** `musicstreamer/player.py:1124-1205`
**Issue:** Both `_handle_gst_error_recovery` (preroll branch, line 738-751)
and `_on_preroll_about_to_finish` (line 1124) are queued onto the main thread
from different GStreamer threads (bus-loop and streaming-thread,
respectively). They each independently disconnect the handler, clear
`_preroll_in_flight`, and pop `_streams_queue[0]`. Neither slot guards
against the other having already run.

Two failure scenarios:

1. **Bus-error fires first → handoff swaps mid-playback.**
   `_handle_gst_error_recovery` runs preroll branch: disconnect, clear flag,
   `_try_next_stream()` pops queue[0] = stream X, sets NULL, plays X via
   `_set_uri`. The queued about-to-finish slot then runs: `if
   self._preroll_handler_id:` is False (skip), `self._preroll_in_flight =
   False` (already False, no-op), `_streams_queue` is non-empty (still has
   stream Y), so the slot pops queue[0] = Y and calls
   `set_property("uri", Y.url)` on the pipeline currently playing X. Result:
   X is interrupted and replaced with Y mid-track.

2. **About-to-finish fires first → spurious failover advance.**
   Handoff completes correctly, then the queued bus-error (e.g. residual
   error from the preroll source still tearing down) runs
   `_handle_gst_error_recovery`. `_preroll_in_flight` is now False, so the
   preroll branch at line 741 is skipped; falls through to
   `_try_next_stream()` at line 762, which pops the next queue entry and
   replaces the just-handed-off stream. The user perceives the post-handoff
   stream skipping immediately to a fallback.

Both windows are small but reproducible — playbin3 emits source errors
during preroll URL teardown and about-to-finish fires on the streaming
thread independently of the bus.

**Fix:** Make the slot idempotent on already-cleared state. Capture the
in-flight flag BEFORE clearing it, and bail out if a bus-error preroll
recovery already advanced the queue:

```python
def _on_preroll_about_to_finish(self) -> None:
    # If D-09 bus-error preroll path already ran on the queued bus-loop
    # signal, _preroll_in_flight is False AND _try_next_stream has
    # already popped queue[0]. Do not pop it again.
    if not self._preroll_in_flight:
        return
    if self._preroll_handler_id:
        try:
            self._pipeline.disconnect(self._preroll_handler_id)
        except (TypeError, RuntimeError):
            pass
        self._preroll_handler_id = 0
    self._preroll_in_flight = False
    ...
```

And symmetrically, gate the bus-error branch in
`_handle_gst_error_recovery` on `_preroll_handler_id` (or set a sentinel
to suppress the next `_handle_gst_error_recovery` call that arrives from
the OLD preroll URL after handoff completed).

Add a regression test that queues both signals before draining the Qt
event loop and asserts `_streams_queue` is consumed exactly once.

## Warnings

### WR-01: Preroll URL has no failover-timeout watchdog — dead preroll hangs UI indefinitely

**File:** `musicstreamer/player.py:1103-1116`
**Issue:** `_start_preroll` calls `_set_uri(preroll_url)` but never arms
`self._failover_timer`. Compare `_try_next_stream` at line 1087 which arms
`self._failover_timer.start(BUFFER_DURATION_S * 1000)` for every direct-URI
stream. If the chosen preroll URL is unreachable or produces no data,
playbin3 *might* surface a bus error eventually, but there is no time-based
watchdog to abandon the preroll and proceed to the actual station stream.
The EOS bridge at line 1207 only fires on actual EOS (e.g. 0-byte response),
not on connection hangs. Result: user hits Play on a SomaFM station, the
selected preroll URL is silently down, and the UI shows "0:00" forever.

Note this is a regression from the pre-Phase 83 path where `_try_next_stream`
would have armed the timer immediately.

**Fix:** Arm the failover-timer in `_start_preroll` so a stuck preroll
advances after BUFFER_DURATION_S:

```python
def _start_preroll(self, preroll_url: str) -> None:
    self._preroll_in_flight = True
    self._last_preroll_played_at = time.monotonic()
    self._preroll_handler_id = self._pipeline.connect(
        "about-to-finish", self._on_preroll_about_to_finish_callback
    )
    self._set_uri(preroll_url)
    # Watchdog: if the preroll URL never produces data, fall through to
    # _try_next_stream via _on_timeout (which D-09 routes through the
    # preroll-in-flight branch — same handler-id disconnect, no double-pop).
    self._failover_timer.start(BUFFER_DURATION_S * 1000)
```

You will also need to make `_on_timeout` aware of preroll state (route
through the same disconnect/clear-flag sequence as `_handle_gst_error_recovery`)
to avoid leaking the handler.

### WR-02: `stop()` and `pause()` do not clear `_preroll_in_flight` or disconnect the preroll handler — leaks across station switches

**File:** `musicstreamer/player.py:606-654`
**Issue:** Neither `pause()` nor `stop()` touches `_preroll_in_flight` or
`_preroll_handler_id`. Test `test_preroll_in_flight_pause_does_not_clear_flag`
explicitly pins pause's behavior as intentional (D-08), but stop() inherits
the same problem and the test does not cover the cross-station case:

1. User starts SomaFM station A → `_start_preroll` connects handler,
   `_preroll_in_flight = True`.
2. User clicks Stop → `set_state(NULL)`, but `_preroll_handler_id` still
   holds the connect-id and `_preroll_in_flight` is still True.
3. User starts SomaFM station B (or any station) — re-enters `play()`.
   - If station B also triggers preroll: `_start_preroll` overwrites
     `_preroll_handler_id` with a NEW connect-id; the OLD handler-id is
     leaked (still connected to the pipeline). Both handlers will fire
     `_on_preroll_about_to_finish_callback` at the next about-to-finish,
     causing double-handoff (queue popped twice, second pop targets the
     wrong stream).
   - If station B does NOT trigger preroll (non-SomaFM, or throttle window
     active): `_streams_queue` is repopulated and `_try_next_stream` runs,
     but `_preroll_in_flight` is still True from station A — `_on_gst_tag`
     will suppress the station's ICY title because of the line-787 guard.
     The Now Playing display freezes on the station name.

**Fix:** Add explicit teardown in `stop()` (and a partial cleanup in pause
if D-08 is revisited):

```python
def stop(self) -> None:
    ...
    if self._preroll_handler_id:
        try:
            self._pipeline.disconnect(self._preroll_handler_id)
        except (TypeError, RuntimeError):
            pass
        self._preroll_handler_id = 0
    self._preroll_in_flight = False
    ...
```

Also reset on every fresh `play()` entry (above the preroll gate) so a
prior leaked handler doesn't survive into a new station's playback.

### WR-03: Queued `_preroll_about_to_finish_requested` signal from a previous play can fire during a subsequent station's playback

**File:** `musicstreamer/player.py:1118-1122` and `play()` at 524-592
**Issue:** `_on_preroll_about_to_finish_callback` (streaming thread) just
emits the queued signal — there is no station-id sequence check. After
`stop()` (WR-02) or rapid station-switch in `play()`, a previously emitted
queued signal can still arrive and run `_on_preroll_about_to_finish` on the
new station's state. Because `play()` repopulates `_streams_queue`, the
stale slot will pop the new station's queue head and `set_property("uri",
<new_stream_url>)` on a pipeline that is in an unrelated lifecycle (e.g.
currently resolving a YouTube URL on a worker thread).

**Fix:** Stamp `_preroll_handler_id` (or a separate `_preroll_seq` counter)
into the queued payload and verify it matches at slot entry:

```python
self._preroll_about_to_finish_requested = Signal(int)  # seq
...
def _on_preroll_about_to_finish_callback(self, pipeline) -> None:
    self._preroll_about_to_finish_requested.emit(self._preroll_handler_id)

def _on_preroll_about_to_finish(self, expected_seq: int) -> None:
    if expected_seq != self._preroll_handler_id or not self._preroll_in_flight:
        return
    ...
```

CR-01's fix (guarding on `_preroll_in_flight` at entry) plus WR-02's stop()
cleanup mitigates the common case; a sequence stamp is the airtight fix.

### WR-04: Preroll path arms NO caps watch — `audio_caps_detected` Signal never fires for preroll-prefixed playbacks until the post-handoff state-change

**File:** `musicstreamer/player.py:831-876` (`_arm_caps_watch_for_current_stream`) and `_start_preroll` at 1103
**Issue:** `_arm_caps_watch_for_current_stream` returns early when
`self._current_stream is None` (line 846-847). `_start_preroll` does NOT
set `self._current_stream` — it only sets `_preroll_in_flight = True` and
calls `_set_uri(preroll_url)`. So the caps watch is silently disabled for
the entire preroll duration. After the gapless handoff sets
`_current_stream = stream`, the watch will be re-armed on the next
`PAUSED → PLAYING` transition via `_on_playbin_state_changed` (line 956,
"Pattern 1b") — BUT the gapless handoff explicitly does NOT call
`set_state(NULL)` or `set_state(PLAYING)`, so that transition may never
fire. The caps watch for the post-handoff stream is therefore not armed
unless playbin3 internally cycles PAUSED → PLAYING during the URI swap.

Result: SomaFM stations may show "Unknown rate / Unknown depth" in the
stats-for-nerds row for the entire playback session.

**Fix:** In `_on_preroll_about_to_finish` after the `set_property("uri",
...)` call, also invoke `self._arm_caps_watch_for_current_stream()` so the
caps pad is re-armed for the post-handoff stream:

```python
self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))
self._arm_caps_watch_for_current_stream()  # Phase 70 / DS-01 re-arm after gapless handoff
self._failover_timer.start(BUFFER_DURATION_S * 1000)
```

### WR-05: Throttle check in `play()` uses `time.monotonic()` but does not handle the case where `_last_preroll_played_at` was set during a prior play() but the preroll was preempted

**File:** `musicstreamer/player.py:567-578`
**Issue:** `_start_preroll` sets `_last_preroll_played_at = time.monotonic()`
at preroll START (per D-12). If the user starts SomaFM station A (preroll
fires, timestamp updated), then clicks Stop within 1 second (preroll never
completed handoff), then clicks Play on SomaFM station B — the throttle
gate (line 571-572 `> 600`) suppresses station B's preroll for 10 minutes,
even though no preroll was ever heard to completion.

Discretion / D-12 anti-pattern call ("update on handoff") explicitly chose
this — but the user experience is "I never heard a preroll, why is the
throttle blocking it?" Worth confirming the spec intent matches this
behavior, especially since the failure mode is silent.

**Fix:** If the spec intent is "throttle on the most-recent COMPLETED
preroll," move the timestamp update into the about-to-finish slot. If the
intent is "throttle on the most-recent ATTEMPTED preroll," document the
edge case so future maintainers don't refactor it away. Either way, add a
regression test for "user starts SomaFM A, stops within 1s, plays SomaFM
B — second preroll status should match the spec's chosen semantics."

## Info

### IN-01: `tests/_fake_player.py` signal-count comments are stale after Phase 83

**File:** `tests/_fake_player.py:62-71`
**Issue:** Comment on line 62 says `# Internal cross-thread marshaling
signals (8 — underscore-prefixed)`. Counting the actual declarations:
`_cancel_timers_requested`, `_error_recovery_requested`,
`_try_next_stream_requested`, `_preroll_about_to_finish_requested`,
`_playbin_playing_state_reached`, `_underrun_cycle_opened`,
`_underrun_cycle_closed`, `underrun_recovery_started`,
`underrun_count_changed` = 9 entries (7 underscore-prefixed + 2
non-underscore in the same comment block). Header comment at module
docstring (line 5) also says "all 19 Signals" — adding
`_preroll_about_to_finish_requested` brought the count to 20. The drift
guard `test_fake_player_signal_parity.py` will continue to enforce parity,
but the human-readable counts are inconsistent.

**Fix:** Update the docstring "19 Signals" to "20 Signals" and the inline
comment "(8 — underscore-prefixed)" to match the new count.

### IN-02: `_on_gst_eos_during_preroll` is wired as a generic `message::eos` handler — name implies preroll-only

**File:** `musicstreamer/player.py:344, 1207-1234`
**Issue:** Line 344 connects `_on_gst_eos_during_preroll` to ALL
`message::eos` bus messages, not just preroll-context EOS. The handler
early-returns when `_preroll_in_flight is False` so behavior is correct,
but the function name misleads a future maintainer into thinking EOS
handling for non-preroll streams is already handled elsewhere (it is not).
A code search for "EOS" will only surface this preroll-named handler.

**Fix:** Rename to `_on_gst_eos` with the preroll-only branch documented
inline, OR add an explicit comment at the `bus.connect` site noting that
the only EOS path in the codebase is this preroll-bridge handler.

### IN-03: `_start_preroll` does not call `_cancel_timers()` between handler-connect and `_set_uri`

**File:** `musicstreamer/player.py:1103-1116`
**Issue:** `play()` at line 527 calls `_cancel_timers()` before reaching
the preroll gate, so the failover timer is stopped when `_start_preroll`
runs. But the relationship between `_start_preroll` and prior state cleanup
is implicit — a future caller of `_start_preroll` (e.g. a "retry preroll"
feature) would not get the same hygiene. Defensive: `_start_preroll` should
either assert or call `_cancel_timers()` itself.

**Fix:** Add a defensive `self._cancel_timers()` at the top of
`_start_preroll`, or document the precondition in the docstring:
```python
def _start_preroll(self, preroll_url: str) -> None:
    """... Precondition: caller has invoked _cancel_timers() and reset
    _streams_queue/_recovery_in_flight. Currently only called from play()."""
```

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
