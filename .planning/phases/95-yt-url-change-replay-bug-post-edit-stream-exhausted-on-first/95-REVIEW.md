---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: 95-02
reviewed: 2026-06-19T00:00:00Z
depth: deep
commits_reviewed:
  - 918a7e0e (feat(95-02): add _recovery_seq guard to error-recovery path)
  - 41e7b618 (test(95-02): add failing tests for recovery-generation guard)
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/player.py
  - tests/_fake_player.py
  - tests/test_player_edit_invalidation.py
findings:
  blocker: 0
  major: 0
  warning: 2
  nit: 2
  total: 4
status: clean
---

# Phase 95-02: Code Review Report

**Reviewed:** 2026-06-19
**Depth:** deep (cross-file, call-chain tracing)
**Files Reviewed:** 3
**Commits:** 918a7e0e (feat), 41e7b618 (test)
**Status:** clean — no blocker or major issues; 2 warnings and 2 nits noted

## Summary

The PR introduces a monotonic `_recovery_seq` generation counter on `Player`, mirrors
the existing `_preroll_seq` / `_youtube_resolve_seq` CPython-atomic-int pattern, widens
`_error_recovery_requested` from `Signal()` to `Signal(int)`, stamps the emission in
`_on_gst_error`, and adds an early-return guard at the top of `_handle_gst_error_recovery`
that rejects stale (pre-restart) deliveries while leaving the `-1` sentinel path for all
existing no-arg direct callers.

The core logic is correct:
- The bump happens inside `play()` atomically from the main thread; no window exists
  between clearing the queue and invalidating the stamp (Qt queued-signal delivery cannot
  interrupt a synchronous function body on the main thread).
- The `-1` sentinel is safe because `_recovery_seq` starts at 0 and only increments
  (Python integers are unbounded; it can never naturally equal -1).
- Guard ordering (above `_recovery_in_flight` coalescing check) is correct: a stale
  delivery is rejected before the coalescing flag is consulted.
- `_fake_player.py` arity parity is correct; the FakePlayer signal is not connected to
  a slot so no downstream tests break.
- Thread-safety reasoning is sound: the int read on the GStreamer bus thread is atomic
  under CPython's GIL, consistent with the `_preroll_seq` / `_youtube_resolve_seq` precedent.

---

## Warnings

### WR-01: `play_stream()` does not bump `_recovery_seq` — coverage claim is inaccurate

**File:** `musicstreamer/player.py:851-861`

**Issue:** `play_stream()` (called when the user manually selects a stream from the picker,
`now_playing_panel.py:1663`) clears `_streams_queue` and calls `_try_next_stream()` directly
without bumping `_recovery_seq`. If a stale queued `_error_recovery_requested` delivery
arrives after `play_stream()` completes, the guard comparison is:

```
recovery_seq (old stamp) != -1   → True
recovery_seq == self._recovery_seq   → True (seq was never bumped)
```

The guard does NOT suppress it. `_recovery_in_flight` is False (set so by `play_stream()`
at line 859 and never re-set to True by `_try_next_stream`). The queue is now empty (stream
was already popped). Result: `_try_next_stream()` fires on an empty queue → `failover.emit(None)` →
spurious "Stream exhausted" toast.

The comment at `player.py:706-707` states "this single bump covers every restart path" —
that is factually inaccurate. `play_stream()`, `stop()`, and `pause()` are all restart/interrupt
paths that do not bump `_recovery_seq`.

**Context:** This gap pre-dates this PR (the prior `_recovery_in_flight` coalescing check
provided imperfect mitigation). This PR does not introduce the gap but also does not close
it for the `play_stream()` path, and the coverage comment overstates what is protected.

**Fix (two-part):**

1. Bump `_recovery_seq` in `play_stream()`:

```python
def play_stream(self, stream: StationStream, on_title=None,
                on_failover=None, on_offline=None) -> None:
    """Manually play a specific stream, bypassing the failover queue (D-08)."""
    self._cancel_timers()
    self._install_legacy_callbacks(on_title, on_failover, on_offline)
    self._current_station_name = ""
    self._current_station_id = 0
    self._streams_queue = [stream]
    self._recovery_in_flight = False
    self._recovery_seq += 1  # Phase 95-02: invalidate any stale pre-switch recovery
    self._is_first_attempt = True
    self._try_next_stream()
```

2. Correct the comment at line 706 to scope the claim accurately:

```python
# invalidate_for_edit's restart branch delegates to play() (D-01), so
# this bump covers the play()/invalidate_for_edit(D-01) restart paths.
# play_stream() bumps independently; stop()/pause() do not bump because
# they are not restart paths that arm a new GStreamer session.
```

---

### WR-02: V11 and V12 tests manually manipulate `_recovery_seq` instead of driving through `play()`

**File:** `tests/test_player_edit_invalidation.py:351, 385`

**Issue:** Both V11 and V12 directly write `p._recovery_seq += 1` (V11) or read `p._recovery_seq`
without having called `play()` first (V12). The tests validate the guard function in isolation
but do not verify that `play()` itself actually performs the bump. A future regression where the
bump line is accidentally removed from `play()` would leave V11 and V12 green while the production
race reappears.

V13 correctly tests the D-02 no-bump contract by calling `invalidate_for_edit()` and then asserting
`_recovery_seq == recovery_seq_before`. V11/V12 should follow a similar pattern — call the real
`play()` to produce the bump, then verify the guard reacts correctly.

**Fix:** Replace the manual bump in V11 with a call to `play()` (using mock pipeline infra already
in `make_player`), then capture the stale stamp from before that call:

```python
stale_recovery_seq = p._recovery_seq  # stamp before restart

# Trigger the real bump via play() — same path as the production race.
with patch.object(p, "_play_youtube", MagicMock()):
    p.play(station_with_new_url)  # bumps _recovery_seq, clears queue

assert p._recovery_seq == stale_recovery_seq + 1  # verifies bump happened

with patch.object(p, "_try_next_stream", MagicMock()) as mock_try_next:
    p._handle_gst_error_recovery(stale_recovery_seq)
    mock_try_next.assert_not_called()
```

This is a test-quality issue, not a correctness defect. The guard logic is correct.

---

## Nits

### NI-01: Comment at `player.py:706` overstates coverage ("every restart path")

**File:** `musicstreamer/player.py:706`

**Issue:** "no redundant bump elsewhere" implies the single bump covers all restarts. `play_stream()`
is also a restart path. The comment should be scoped to the `play()`/`invalidate_for_edit(D-01)`
path only, with an explicit note that `play_stream()` is handled separately (or acknowledged as
a known remaining gap if WR-01 is not fixed this phase).

**Fix:** See WR-01 fix part 2 above.

---

### NI-02: `make_stream` URL construction is non-obvious in V11/V12 test setup

**File:** `tests/test_player_edit_invalidation.py:341, 380`

**Issue:** `make_stream(10, position=1, quality="hi", url="http://yt/old")` produces the URL
`"http://yt/old10"` (the helper appends `id_` at line 48: `url=f"{url}{id_}"`). The test comments
and docstrings refer to the URL as `"http://yt/old"`, which is misleading. This does not affect
correctness — the URL value is never parsed by the generation guard — but it can confuse future
maintainers reading the test.

**Fix:** Either pass the full intended URL directly via `StationStream(...)` instead of `make_stream`,
or note in the docstring that `make_stream` appends the stream id to the URL base.

---

_Reviewed: 2026-06-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep (cross-file, call chain)_
