---
phase: 57
status: clean
findings_critical: 0
findings_warning: 0
findings_info: 0
findings_critical_original: 1
findings_warning_original: 1
files_reviewed:
  - musicstreamer/player.py
  - tests/test_player_failover.py
  - tests/test_player_pause.py
review_depth: standard
reviewed_at: 2026-05-03
fixed_at: 2026-05-03
fix_summary:
  - "CR-01 fixed: _cancel_timers() now also stops _pause_volume_ramp_timer and clears _pause_volume_ramp_state — covers play(), play_stream(), and _handle_gst_error_recovery → _try_next_stream() paths via the shared cancel surface"
  - "WR-01 fixed: tests/test_player_pause.py adds test_cancel_timers_cancels_in_flight_pause_volume_ramp to lock the contract; full player+pause+failover+volume suite (40 tests) green after fix"
---

# Phase 57: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues-found

## Summary

Reviewed the two Phase 57 work products: the bus-message STATE_CHANGED handler + queued Signal (Plan 57-03) and the pause-volume ramp QTimer wrapper (Plan 57-04), plus their associated tests.

The Plan 57-03 bus-message machinery is correct. The Signal is declared at class scope, the queued connection marshals correctly to the main thread per Rule 2 of `qt-glib-bus-threading.md`, the `msg.src is self._pipeline` identity filter is sound, and `_on_playbin_state_changed` writes only `self._pipeline.set_property("volume", self._volume)` with no `_volume_element` anywhere in the file (D-13 invariant holds). The D-03 invariant (`aa_normalize_stream_url(uri)` is first line of `_set_uri`) is preserved. The four regression guard tests in `test_player_failover.py` are structurally correct and use direct slot invocation (synchronous, not wall-clock coupled).

The Plan 57-04 ramp shape — constants, lerp formula, tick indexing, final-tick exact-target commit, state cleanup — is correct in the simple pause-then-resume path and was validated by UAT. However there is one **BLOCKER**: `play()` and `play_stream()` do not cancel the pause-volume ramp timer when called while the ramp is in flight. This means a station-switch during the 40 ms ramp window will allow the ramp's final tick to call `set_state(NULL)` on a pipeline that has already transitioned to `PLAYING` under the new station — killing the stream ~40 ms after it starts. There is a corresponding missing test.

---

## Critical Issues

### CR-01: `play()` and `play_stream()` do not cancel the pause-volume ramp timer — ramp can kill a newly started stream

**File:** `musicstreamer/player.py:280` (`play`) and `musicstreamer/player.py:312` (`play_stream`)

**Issue:**
Both `play()` and `play_stream()` call `_cancel_timers()`, which only stops `_failover_timer` (line 508). Neither method stops `_pause_volume_ramp_timer` or clears `_pause_volume_ramp_state`. If the user pauses a stream (arming the 40 ms, 8-tick ramp) and then immediately switches to a new station — or if a GStreamer error triggers `_handle_gst_error_recovery` → `_cancel_timers()` → `_try_next_stream()` during the ramp window — the still-running ramp timer will fire. The final ramp tick (at the 40 ms boundary) executes:

```python
self._pipeline.set_property("volume", target)   # writes 0 — overrides the re-apply
self._pause_volume_ramp_timer.stop()
self._pause_volume_ramp_state = None
self._pipeline.set_state(Gst.State.NULL)         # kills the newly started PLAYING stream
self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
```

The new stream — already in `PLAYING` state and emitting audio — is silently torn down ~40 ms after start. The error recovery path is also affected: `_handle_gst_error_recovery` calls `_cancel_timers()` (line 416), which has the same gap.

The UAT "rapid pause/resume" test (SC #1 Test 2) exercised pause → resume on the **same** station; by the time the user can physically click resume, the 40 ms ramp has typically completed and the pipeline is in NULL state. The bug surfaces on programmatic station-switch or a GStreamer error arriving mid-ramp, which are not human-reaction-time-gated.

**Fix:**
The cleanest fix is to add cancellation to `_cancel_timers()` itself, since every call site that starts a new stream already calls it:

```python
def _cancel_timers(self) -> None:
    """Cancel pending failover timeout and any in-flight pause-volume ramp."""
    self._failover_timer.stop()
    # Phase 57 / WIN-03 D-15: if a pause-volume ramp is in flight and a new
    # play() / play_stream() / error recovery fires, cancel the ramp before
    # the final tick can call set_state(NULL) on the new stream.
    self._pause_volume_ramp_timer.stop()
    self._pause_volume_ramp_state = None
```

Alternatively, add the two lines explicitly in `play()` and `play_stream()` (lines 280 and 312) mirroring how `stop()` cancels it at lines 352–353 and how `pause()` cancels the EQ ramp at lines 337–338.

---

## Warnings

### WR-01: No test guards the play()-after-pause-mid-ramp cancellation contract

**File:** `tests/test_player_pause.py` (no matching line — missing test)

**Issue:**
There is no test asserting that `play()` or `play_stream()` cancels an in-flight pause-volume ramp. The structural guard tests added in Plan 57-04 cover the "ramp armed", "target=0", and "self._volume immutable" invariants, but not the "ramp cancelled when play() overrides pause" invariant. Without a test, the fix for CR-01 could regress silently.

**Fix:**
Add a test in `tests/test_player_pause.py` that: arms the ramp via `pause()`, then calls `play()` (or `play_stream()`), then asserts the ramp timer is stopped and state is cleared:

```python
def test_play_cancels_in_flight_pause_ramp(qtbot):
    """play() must cancel any in-flight pause-volume ramp so the ramp's
    final tick cannot call set_state(NULL) on the newly started stream."""
    from musicstreamer.player import Player
    from musicstreamer.models import Station, StationStream
    p = make_player(qtbot)
    p._pipeline.get_property.return_value = 1.0
    p.pause()
    assert p._pause_volume_ramp_timer.isActive()
    station = Station(
        id=1, name="S", provider_id=None, provider_name=None,
        tags="", station_art_path=None, album_fallback_path=None,
        streams=[StationStream(id=1, station_id=1, url="http://x/1",
                               quality="hi", position=1)],
    )
    with patch.object(p, "_set_uri"):
        p.play(station)
    assert not p._pause_volume_ramp_timer.isActive()
    assert p._pause_volume_ramp_state is None
```

---

## Dimensions Verified (no issues found)

- **D-03 invariant:** `aa_normalize_stream_url(uri)` is the first executable line of `_set_uri` (`player.py:560`). Confirmed preserved.
- **D-13 invariant:** No `_volume_element` reference anywhere in `player.py`. Confirmed absent.
- **Qt/GLib Rule 2 (bus-threading SKILL.md):** `_on_gst_state_changed` only emits a queued Signal; all property writes happen in `_on_playbin_state_changed` on the main thread. Correct.
- **Qt/GLib Rule 1:** `bus.add_signal_watch()` is marshalled via `_bridge.run_sync()` at line 139. The new `bus.connect("message::state-changed", ...)` at line 143 follows the same correct pattern as the pre-existing `message::error`, `message::tag`, `message::buffering` connects.
- **Composition contract (D-12 + D-15):** In the normal pause-then-resume path, ramp writes happen PRE-NULL (pause invocation window) and the bus-message re-apply writes `self._volume` POST-PLAYING. No double-write in the normal path. `self._volume` is never mutated by the ramp.
- **Filter invariants:** The `msg.src is not self._pipeline` identity filter and the `new != Gst.State.PLAYING` state filter are both correct. Tests cover both filter branches.
- **Signal at class scope:** `_playbin_playing_state_reached = Signal()` is at class scope (line 101), not instance scope. Correct per PySide6 rules.
- **Ramp arithmetic:** tick_index increments before comparison, so 8 loop iterations drive `k` through 1..8 and the final tick fires at `k=8 >= 8`. Lerp `start * (1 - k/8)` reaches 0 exactly on the final tick commit. Correct.
- **stop() cancellation:** `stop()` correctly cancels the ramp at lines 352–353. `pause()` correctly cancels the EQ ramp at lines 337–338 before starting the volume ramp.
- **Security:** The bus-message handler reads only the GStreamer state-changed payload (state enum + `msg.src` identity). No external input ingested, no trust boundary crossed.
- **Test synchronous tick drain:** All Phase 57-04 tests that drive the ramp call `_on_pause_volume_ramp_tick()` directly N times without wall-clock coupling. Correct per the Phase 52 EQ ramp convention and `qt-glib-bus-threading.md` Rule 2.

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
