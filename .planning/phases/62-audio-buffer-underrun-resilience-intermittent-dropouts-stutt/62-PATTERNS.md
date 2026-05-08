# Phase 62: Audio Buffer Underrun Resilience — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 6 (3 NEW tests + 3 MODIFIED source)
**Analogs found:** 6 / 6 (every file has at least one role-exact precedent)

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `tests/test_player_underrun_tracker.py` (NEW) | unit-test (pure logic) | request-response (no Qt, no I/O) | `tests/test_stream_ordering.py` | exact (pure-Python helper, no fixture) |
| `tests/test_player_underrun.py` (NEW) | integration-test (Player + Qt) | event-driven (bus-loop → queued Signal) | `tests/test_player_buffering.py` | exact (same `make_player` + `_fake_buffering_msg` seam) |
| `tests/test_main_window_underrun.py` (NEW) | integration-test (MainWindow slot) | event-driven (Signal → slot → toast) | `tests/test_main_window_integration.py` | exact (FakePlayer + qtbot fixture pattern) |
| `musicstreamer/player.py` (MODIFY) | controller (state machine + Qt bridge) | event-driven (bus-loop → queued Signal → main slot) | self (`_cancel_timers_requested` + `_failover_timer` precedents at same file) | exact (4 Signal+queued precedents, 4 QTimer precedents already in file) |
| `musicstreamer/ui_qt/main_window.py` (MODIFY) | controller (Signal-to-toast wiring + cooldown) | event-driven (Player Signal → cooldown gate → `show_toast`) | self (`cookies_cleared.connect(self.show_toast)` at line 280) | role-match (cooldown gate is novel; rest is verbatim precedent) |
| `musicstreamer/__main__.py` (MODIFY) | config (per-logger level adjustment) | one-shot startup config | self (`logging.basicConfig` line 222) | exact (1-line append) |

---

## Pattern Assignments

### 1. `musicstreamer/player.py` — Controller (event-driven, cycle state machine + Qt bridge)

**Analog:** SELF (`musicstreamer/player.py` already encodes every required pattern). The novel work is composing existing primitives.

#### 1a. Module-level logger (NEW — first logger in file)

**Source pattern:** `musicstreamer/aa_import.py:8-20` (verbatim project convention; 14 modules use this idiom)

```python
# Source: musicstreamer/aa_import.py:8-20 — exact 3-line shape
import json
import logging
import os
# ... other imports ...

_log = logging.getLogger(__name__)
```

**Apply:** Add `import logging` near the existing `os` / `threading` imports at `player.py:34-35`, and add `_log = logging.getLogger(__name__)` at module scope **after** the `_BUS_BRIDGE` block (around line 60, before `def _fix_icy_encoding`). Single new module-level binding.

**Other precedents:** `musicstreamer/media_keys/mpris2.py:53`, `musicstreamer/url_helpers.py:16`, `musicstreamer/single_instance.py:27`, `musicstreamer/runtime_check.py:22`. All use the same 1-line pattern at module scope.

---

#### 1b. Class-level Signal + queued connection (BINDING — Pitfall 2 + Pitfall 4)

**Source pattern:** `musicstreamer/player.py:80-101` (Signal declarations) + `player.py:185-208` (queued `.connect(...)`).

**Existing class-level Signals (excerpt):**

```python
# Source: musicstreamer/player.py:71-101 — class-scope Signal declarations
class Player(QObject):
    # Class-level Signals (Pitfall 4 -- MUST be at class scope, not instance)
    title_changed              = Signal(str)
    buffer_percent             = Signal(int)     # 0-100 GStreamer buffer fill; de-duped in _on_gst_buffering (47.1 D-12)
    cookies_cleared            = Signal(str)     # Phase 999.7
    # Internal cross-thread marshaling (43.1 follow-up fix). Bus handlers run
    # on the GstBusLoopThread (pure GLib, not a QThread)...
    _cancel_timers_requested   = Signal()        # bus-loop → main: stop failover timer
    _error_recovery_requested  = Signal()        # bus-loop → main: run _handle_gst_error_recovery
    _try_next_stream_requested = Signal()        # worker → main: advance failover queue
    _playbin_playing_state_reached = Signal()    # bus-loop -> main: re-apply volume on PLAYING
```

**Existing queued-connection wiring (excerpt):**

```python
# Source: musicstreamer/player.py:194-208 — queued cross-thread connect
# 43.1 follow-up: queue bus-loop → main for timer/recovery work.
self._cancel_timers_requested.connect(
    self._cancel_timers, Qt.ConnectionType.QueuedConnection
)
self._error_recovery_requested.connect(
    self._handle_gst_error_recovery, Qt.ConnectionType.QueuedConnection
)
# 999.8 WR-03: queue worker-thread → main failover advance.
self._try_next_stream_requested.connect(
    self._try_next_stream, Qt.ConnectionType.QueuedConnection
)
# Phase 57 / WIN-03 D-12: queue bus-loop -> main re-apply on PLAYING.
self._playbin_playing_state_reached.connect(
    self._on_playbin_state_changed, Qt.ConnectionType.QueuedConnection
)
```

**Apply:** Add three new class-level Signals adjacent to the existing block (after line 101), and three queued `.connect(...)` calls in `__init__` adjacent to the existing block (after line 208):

```python
# NEW — append after player.py:101
_underrun_cycle_opened    = Signal()         # bus-loop → main: arm dwell timer
_underrun_cycle_closed    = Signal(object)   # bus-loop → main: log + cancel dwell  (object = _CycleClose)
underrun_recovery_started = Signal()         # main → MainWindow: show_toast (queued — D-07)

# NEW — append in __init__ after player.py:208
self._underrun_cycle_opened.connect(
    self._on_underrun_cycle_opened, Qt.ConnectionType.QueuedConnection
)
self._underrun_cycle_closed.connect(
    self._on_underrun_cycle_closed, Qt.ConnectionType.QueuedConnection
)
```

The third Signal `underrun_recovery_started` is connected on the **MainWindow** side (see §2 below). Bound-method connect (QA-05); no lambdas.

---

#### 1c. Pre-built `QTimer(self)` parented to main thread (BINDING — Pitfall 2)

**Source pattern:** `musicstreamer/player.py:148-180` (4 instances: `_failover_timer`, `_elapsed_timer`, `_eq_ramp_timer`, `_pause_volume_ramp_timer`).

**Existing template (verbatim shape to copy):**

```python
# Source: musicstreamer/player.py:148-151 — _failover_timer template
# QTimer objects -- constructed on the main thread (Pitfall 2)
self._failover_timer = QTimer(self)
self._failover_timer.setSingleShot(True)
self._failover_timer.timeout.connect(self._on_timeout)
```

```python
# Source: musicstreamer/player.py:167-170 — _eq_ramp_timer template (interval set explicitly)
self._eq_ramp_timer = QTimer(self)
self._eq_ramp_timer.setInterval(self._EQ_RAMP_INTERVAL_MS)
self._eq_ramp_timer.timeout.connect(self._on_eq_ramp_tick)
self._eq_ramp_state: dict | None = None
```

**Apply:** Add the dwell timer in `__init__` adjacent to the existing four-timer block:

```python
# NEW — append after player.py:180 (after _pause_volume_ramp_timer block)
# Phase 62 / D-07: 1500ms dwell timer. Pitfall 2 — parented to self (main-thread).
# QA-05 — bound-method timeout, no lambda.
self._underrun_dwell_timer = QTimer(self)
self._underrun_dwell_timer.setSingleShot(True)
self._underrun_dwell_timer.setInterval(1500)
self._underrun_dwell_timer.timeout.connect(self._on_underrun_dwell_elapsed)
```

**Why pre-built over `QTimer.singleShot(1500, slot)`:** matches the project's 4-instance convention; `isActive()` cleanly answers "is dwell armed?"; `.stop()` cancels deterministically; `.start()` is idempotent (resets interval, the right thing for cycle reopen).

---

#### 1d. Bus-handler emits queued Signal — never touches Qt directly (BINDING — Pitfall 2)

**Source pattern:** `musicstreamer/player.py:399-461` (every bus-loop handler ends in a Signal emit).

**Existing parallel — `_on_gst_error` and `_on_gst_buffering`:**

```python
# Source: musicstreamer/player.py:399-404 — bus handler emits queued Signal
def _on_gst_error(self, bus, msg) -> None:
    err, debug = msg.parse_error()
    self.playback_error.emit(f"{err} | {debug}")
    # Marshal recovery onto the main thread via queued signal. Bus-loop
    # thread has no Qt event loop, so QTimer.singleShot from here vanishes.
    self._error_recovery_requested.emit()
```

```python
# Source: musicstreamer/player.py:448-461 — _on_gst_buffering, the extension site
def _on_gst_buffering(self, bus, msg) -> None:
    """Bus-loop-thread handler: parse buffer percent, emit Qt signal.

    Runs on GstBusLoopThread (not main thread). May only emit signals,
    never touch Qt widgets directly (Pitfall 2). De-dups on unchanged
    percent (47.1 D-14) to avoid UI churn.
    """
    result = msg.parse_buffering()
    # PyGObject may flatten single-out-param to bare int OR return tuple (Pitfall 1)
    percent = result[0] if isinstance(result, tuple) else int(result)
    if percent == self._last_buffer_percent:
        return
    self._last_buffer_percent = percent
    self.buffer_percent.emit(percent)  # auto-queued cross-thread to main
```

**Apply:** Extend `_on_gst_buffering` after the existing `buffer_percent.emit(percent)` (line 461). Drive the tracker, branch on the return sentinel, emit the matching queued Signal. **Never touch `QTimer` from here** (Pitfall 2):

```python
# NEW — append at end of _on_gst_buffering, after line 461
# Phase 62 / D-01..D-04: cycle state machine.
transition = self._tracker.observe(percent)
if transition == "OPENED":
    self._underrun_cycle_opened.emit()              # queued → main: arm dwell timer
elif transition is not None:
    self._underrun_cycle_closed.emit(transition)    # queued → main: log + cancel dwell
```

`note_error_in_cycle()` is called from `_on_gst_error` BEFORE its `_error_recovery_requested.emit()` — bus-loop thread is fine, the tracker has no Qt:

```python
# NEW — insert in _on_gst_error after line 401, before _error_recovery_requested.emit()
self._tracker.note_error_in_cycle()   # D-02 / Discretion: cause_hint='network' if cycle is open
```

---

#### 1e. Per-URL state reset inside `_try_next_stream` (BINDING — Pitfall 3)

**Source pattern:** `musicstreamer/player.py:543-545` (Phase 47.1 D-14 sentinel reset).

**Existing block (verbatim):**

```python
# Source: musicstreamer/player.py:543-545 — per-URL reset site
stream = self._streams_queue.pop(0)
self._current_stream = stream
self._last_buffer_percent = -1  # 47.1 D-14: reset so new URL's first buffer emits (Pitfall 3)
```

**Apply:** Adjacent to line 545 — force-close any open cycle on the OUTGOING URL, then bind the tracker to the NEW URL. The force-close is on the OLD URL context, so it must run BEFORE `bind_url`:

```python
# NEW — append after player.py:545, BEFORE existing failover-emit block at line 547
# Phase 62 / D-03: force-close outgoing cycle as outcome=failover BEFORE binding new URL.
prior_close = self._tracker.force_close("failover")
if prior_close is not None:
    self._underrun_cycle_closed.emit(prior_close)   # queued → main: log + cancel dwell
# Phase 62 / D-04: bind tracker to the new URL (mirror of D-14 sentinel reset).
self._tracker.bind_url(
    station_id=getattr(self._current_station, "id", 0) if hasattr(self, "_current_station") else 0,
    station_name=self._current_station_name,
    url=stream.url,
)
```

> **Note for planner:** `Player` currently stores `_current_station_name: str` (line 220) but NOT a `_current_station` reference or `_current_station_id`. To populate `station_id` in the log line, either (a) add `self._current_station_id: int = 0` to `play()` at line 284 alongside `_current_station_name = station.name`, or (b) keep `station_id=0` end-to-end this phase (the log already has `station_name + url`). Recommendation: add `self._current_station_id` — it's a 1-line addition with no churn, mirrors `_current_station_name`, and makes the log machine-grouppable.

---

#### 1f. Force-close on terminator events (`pause`, `stop`)

**Source pattern:** `musicstreamer/player.py:320-358` — both terminators already start with `self._cancel_timers()` and clear analogous bookkeeping.

**Existing `pause()` head (excerpt):**

```python
# Source: musicstreamer/player.py:320-340 — pause() terminator pattern
def pause(self) -> None:
    """Stop audio output without clearing station context (D-04).

    Phase 57 / WIN-03 D-15: fades playbin3.volume to 0 across an 8-tick
    ramp BEFORE set_state(NULL) — masks the audible pop on Windows ...
    """
    self._cancel_timers()
    self._elapsed_timer.stop()
    self._eq_ramp_timer.stop()
    self._eq_ramp_state = None
    self._streams_queue = []
    self._recovery_in_flight = False
    # Phase 57 / WIN-03 D-15: arm the volume fade-down ramp; the final
    # tick performs set_state(NULL) + get_state(CLOCK_TIME_NONE).
    self._start_pause_volume_ramp()
```

**Apply:** Insert at the head of both `pause()` (line 332-ish) and `stop()` (line 346-ish), adjacent to the other timer/state cleanup:

```python
# NEW — insert at top of pause() body (after line 332, alongside _cancel_timers)
# Phase 62 / D-03: force-close any open cycle as outcome=pause.
prior_close = self._tracker.force_close("pause")
if prior_close is not None:
    self._underrun_cycle_closed.emit(prior_close)
self._underrun_dwell_timer.stop()    # cancel pending dwell — main thread, fine to call directly

# NEW — same shape, in stop() body (after line 346)
prior_close = self._tracker.force_close("stop")
if prior_close is not None:
    self._underrun_cycle_closed.emit(prior_close)
self._underrun_dwell_timer.stop()
```

> Both `pause()` and `stop()` run on the main thread, so `_underrun_dwell_timer.stop()` is direct (no Signal needed). The tracker's `force_close` is pure-Python; thread-agnostic.

---

#### 1g. Main-thread slots (cycle-opened, cycle-closed, dwell-elapsed)

**Source pattern:** `musicstreamer/player.py:430-435` (`_clear_recovery_guard` — short main-thread slot) + `player.py:490-500` (`_on_playbin_state_changed` — main-thread queued-Signal target).

**Existing template:**

```python
# Source: musicstreamer/player.py:430-435 — short main-thread slot
def _clear_recovery_guard(self) -> None:
    """Main-thread slot: release the recovery guard after the current
    failover advance is armed. Scheduled by _handle_gst_error_recovery
    via QTimer.singleShot(0, ...) so it runs after any already-queued
    recovery callbacks from the old URL have drained."""
    self._recovery_in_flight = False
```

**Apply:** Add three new main-thread slots in the "Timer helpers — main-thread only" section (around `player.py:502-523`):

```python
# NEW — append in the main-thread helpers section around player.py:520
def _on_underrun_cycle_opened(self) -> None:
    """Main-thread slot (Phase 62 / D-07). Arms the 1500ms dwell QTimer.
    Idempotent — start() on a running timer resets the interval."""
    self._underrun_dwell_timer.start()

def _on_underrun_cycle_closed(self, record) -> None:
    """Main-thread slot (Phase 62 / D-02). Cancels in-flight dwell timer
    (silent recovery, D-07) and writes the structured log line at INFO."""
    self._underrun_dwell_timer.stop()    # idempotent
    _log.info(
        "buffer_underrun "
        "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
        "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
        record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
        record.station_id, record.station_name, record.url,
        record.outcome, record.cause_hint,
    )

def _on_underrun_dwell_elapsed(self) -> None:
    """Main-thread QTimer.timeout slot (Phase 62 / D-07). Cycle has been
    open ≥ 1500ms; notify MainWindow to consider showing the toast (cooldown
    gated there, D-08)."""
    self.underrun_recovery_started.emit()
```

---

#### 1h. Public `shutdown_underrun_tracker()` method (Pitfall 4)

**Source pattern:** No exact precedent in `Player` (the class has no `shutdown()` method today). Closest analog is `MediaKeysBackend.shutdown()` referenced from `MainWindow.closeEvent` at `main_window.py:355`. Public method keeps the test surface clean (asserts `player.shutdown_underrun_tracker()` rather than poking `player._tracker.force_close('shutdown')`).

```python
# NEW — append in the public-API section (after pause/stop, around player.py:358)
def shutdown_underrun_tracker(self) -> None:
    """Phase 62 / D-03: force-close any open underrun cycle as outcome=shutdown.
    Called from MainWindow.closeEvent BEFORE super().closeEvent(event) so
    in-flight cycles still write their log line (Pitfall 4)."""
    prior_close = self._tracker.force_close("shutdown")
    if prior_close is not None:
        # Synchronous log — main thread, safe to call _log directly.
        # Cannot rely on queued Signal here: closeEvent is followed by
        # QApplication shutdown; queued slot may never run.
        _log.info(
            "buffer_underrun "
            "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
            "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
            prior_close.start_ts, prior_close.end_ts, prior_close.duration_ms,
            prior_close.min_percent, prior_close.station_id,
            prior_close.station_name, prior_close.url,
            prior_close.outcome, prior_close.cause_hint,
        )
    self._underrun_dwell_timer.stop()
```

> **Critical detail:** the shutdown path writes the log line **synchronously** rather than via the `_underrun_cycle_closed` queued Signal. Reason: `closeEvent` is followed by `QApplication.quit()`; queued slots may never get scheduled. Same instinct as `_media_keys.shutdown()` running synchronously in `closeEvent`.

---

#### 1i. `_BufferUnderrunTracker` helper class (NEW — pure Python, no Qt)

**Source pattern:** Project convention for module-private helper classes. Exact shape verbatim from RESEARCH §Pattern 1 (~80 lines, dataclass + state machine, injectable clock). Located in `player.py` between the module-level helpers (`_fix_icy_encoding` at line 63) and the `class Player` declaration (line 71).

> The full class shape is in `62-RESEARCH.md` lines 240-345 — copy that verbatim. Tracker has 4 public methods: `bind_url(station_id, station_name, url)`, `observe(percent) → None | "OPENED" | _CycleClose`, `force_close(outcome) → None | _CycleClose`, `note_error_in_cycle()`. Plus internal `_close(outcome) → _CycleClose` and `_reset_per_url()`.

---

### 2. `musicstreamer/ui_qt/main_window.py` — Controller (Signal wiring + cooldown gate)

**Analog:** SELF (`main_window.py:271-296` — 8 existing Player→toast wirings).

#### 2a. Player Signal → MainWindow slot connection

**Source pattern:** `musicstreamer/ui_qt/main_window.py:271-296` — every Player Signal connects to a MainWindow slot or directly to `show_toast`.

**Existing block (verbatim — the pattern to mirror):**

```python
# Source: musicstreamer/ui_qt/main_window.py:271-296 — Player → toast wiring
# Player → now-playing panel
self._player.title_changed.connect(self.now_playing.on_title_changed)
self._player.elapsed_updated.connect(self.now_playing.on_elapsed_updated)
self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)

# Player → toast notifications (D-11)
self._player.failover.connect(self._on_failover)
self._player.offline.connect(self._on_offline)
self._player.playback_error.connect(self._on_playback_error)
self._player.cookies_cleared.connect(self.show_toast)  # Phase 999.7
```

**Apply:** Insert one queued connection adjacent to the existing block (after line 280):

```python
# NEW — append after main_window.py:280 (cookies_cleared connect)
# Phase 62 / D-07-D-08: dwell-elapsed → cooldown-gated toast.
# Queued connection for explicit-policy clarity (Player Signals are queued
# to MainWindow throughout this file). Bound method per QA-05 — no lambda.
self._player.underrun_recovery_started.connect(
    self._on_underrun_recovery_started, Qt.ConnectionType.QueuedConnection
)
```

---

#### 2b. Cooldown bookkeeping (`time.monotonic` float comparison)

**Source pattern:** No prior `time.monotonic()` callsite in the codebase. Closest semantic analog is `Player._recovery_in_flight: bool = False` at `player.py:223` — same intent (suppress duplicate cascading triggers); different mechanism (boolean coalescer vs. wall-clock window).

**`_recovery_in_flight` precedent (boolean coalescer):**

```python
# Source: musicstreamer/player.py:223, 413-415 — coalescer pattern
self._recovery_in_flight: bool = False  # gap-05: coalesce cascading bus errors per URL
# ... later ...
if self._recovery_in_flight:
    return
self._recovery_in_flight = True
```

**Apply:** Cooldown lives on **MainWindow** (not Player) because the toast is a UI concern. Add the bookkeeping field to `__init__` and the gate to a new slot:

```python
# NEW — add at top of MainWindow class body (after the show_toast docstring or as a class-level constant)
import time   # NEW — top of main_window.py module imports

class MainWindow(QMainWindow):
    _UNDERRUN_TOAST_COOLDOWN_S: float = 10.0   # D-08 — wall-clock-based, persists across station changes

    def __init__(self, ...):
        ...
        # NEW — after self._toast = ToastOverlay(self) at main_window.py:255
        # Phase 62 / D-08: cooldown bookkeeping. monotonic clock — immune to NTP.
        self._last_underrun_toast_ts: float = 0.0

    # NEW slot — append in the slots section after _on_playback_error
    def _on_underrun_recovery_started(self) -> None:
        """Phase 62 / D-08 cooldown-gated toast. monotonic-clock based,
        persists across station changes."""
        now = time.monotonic()
        if now - self._last_underrun_toast_ts < self._UNDERRUN_TOAST_COOLDOWN_S:
            return
        self.show_toast("Buffering…")    # D-06 — U+2026 ellipsis, matches "Connecting…"
        self._last_underrun_toast_ts = now
```

> **U+2026 literal:** The codebase uses the `…` escape (see `main_window.py:367`: `self.show_toast("Connecting…")`). Match that spelling exactly — do NOT inline the Unicode glyph in source.

---

#### 2c. `closeEvent` shutdown hook

**Source pattern:** `musicstreamer/ui_qt/main_window.py:352-358` — already calls `self._media_keys.shutdown()` BEFORE `super().closeEvent(event)`.

**Existing template (verbatim):**

```python
# Source: musicstreamer/ui_qt/main_window.py:352-358
def closeEvent(self, event: QCloseEvent) -> None:
    """Unregister the MPRIS2 service cleanly before the window closes (T-41-13)."""
    try:
        self._media_keys.shutdown()
    except Exception as exc:
        _log.warning("media_keys shutdown failed: %s", exc)
    super().closeEvent(event)
```

**Apply:** Add a parallel `try/except` block for `_player.shutdown_underrun_tracker()`:

```python
# NEW — extend closeEvent at main_window.py:352, BEFORE super().closeEvent(event)
def closeEvent(self, event: QCloseEvent) -> None:
    """Unregister the MPRIS2 service cleanly before the window closes (T-41-13).

    Phase 62 / D-03: also force-close any in-flight underrun cycle as
    outcome=shutdown so its log line is written before app exit (Pitfall 4)."""
    try:
        self._player.shutdown_underrun_tracker()
    except Exception as exc:
        _log.warning("player shutdown_underrun_tracker failed: %s", exc)
    try:
        self._media_keys.shutdown()
    except Exception as exc:
        _log.warning("media_keys shutdown failed: %s", exc)
    super().closeEvent(event)
```

---

### 3. `musicstreamer/__main__.py` — Config (per-logger level)

**Analog:** SELF (`__main__.py:222`).

**Existing line:**

```python
# Source: musicstreamer/__main__.py:221-223 — basicConfig
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    argv = list(argv) if argv is not None else list(sys.argv)
```

**Apply:** Add ONE line directly after the existing `basicConfig`. Keep WARNING as global default; bump only `musicstreamer.player` to INFO (Pitfall 5 — global INFO would surface chatter from `aa_import`, `gbs_api`, `mpris2`, etc. that's been silenced for two years):

```python
# NEW — append at main() entry, after __main__.py:222
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)   # Phase 62 / BUG-09
    argv = list(argv) if argv is not None else list(sys.argv)
```

---

### 4. `tests/test_player_underrun_tracker.py` (NEW) — Unit tests, pure logic

**Analog:** `tests/test_stream_ordering.py` (pure-Python helper class, no qtbot fixture).

**Source pattern (header + test shape):**

```python
# Source: tests/test_stream_ordering.py:1-17 — pure-logic test file shape
"""Tests for musicstreamer/stream_ordering.py — Phase 47 failover ordering."""
from __future__ import annotations

import pytest

from musicstreamer.models import StationStream
from musicstreamer.stream_ordering import codec_rank, order_streams, quality_rank


def _s(...):  # local helper factory
    return StationStream(...)


@pytest.mark.parametrize("codec,expected", [...])
def test_codec_rank(codec, expected):
    assert codec_rank(codec) == expected
```

**Apply:** Mirror the file shape — module docstring, `from __future__ import annotations`, plain imports, pytest functions. **No `qtbot` fixture** — `_BufferUnderrunTracker` is pure Python with an injectable clock. Tests use `clock=lambda: next(iter([...]))` for determinism. RESEARCH §Test seam recommendation: this file mirrors `tests/test_stream_ordering.py` exactly (pure-logic test file).

**Verbatim test bodies from RESEARCH §Code Examples Example 8** (lines 668-700):

```python
def test_unarmed_initial_fill_does_not_open_cycle():
    clock = iter([10.0, 11.0, 12.0])
    t = _BufferUnderrunTracker(clock=lambda: next(clock))
    t.bind_url(1, "Test", "http://x/")
    assert t.observe(0) is None
    assert t.observe(50) is None
    assert t.observe(100) is None    # arms here

def test_armed_drop_then_recover_returns_close_record():
    times = [10.0, 11.0, 11.5, 13.0]   # [arm, open, mid-cycle, close]
    it = iter(times)
    t = _BufferUnderrunTracker(clock=lambda: next(it))
    t.bind_url(7, "DI.fm Ambient", "http://prem2.di.fm/ambient")
    t.observe(100)                     # arms
    assert t.observe(80) == "OPENED"   # opens cycle at t=11.0
    assert t.observe(60) is None       # min_percent updates, no transition
    record = t.observe(100)            # closes at t=13.0
    assert record.outcome == "recovered"
    assert record.duration_ms == 2000
    assert record.min_percent == 60
    assert record.station_id == 7
    assert record.url == "http://prem2.di.fm/ambient"

def test_force_close_returns_record_with_outcome():
    t = _BufferUnderrunTracker(clock=iter([10.0, 11.0, 12.5]).__next__)
    t.bind_url(1, "Test", "http://x/")
    t.observe(100)
    t.observe(70)                       # opens
    record = t.force_close("pause")
    assert record.outcome == "pause"
    assert record.duration_ms == 1500
```

**Test list (~7 tests per RESEARCH Wave 0 gap):**

| Test | Validates |
|------|-----------|
| `test_unarmed_initial_fill_does_not_open_cycle` | D-04 unarmed gate |
| `test_armed_drop_opens_cycle` | D-01 / D-04 — `<100` post-arm opens cycle |
| `test_first_100_arms_tracker` | D-04 arm semantics |
| `test_armed_drop_then_recover_returns_close_record` | D-02 record fields + duration_ms + min_percent |
| `test_force_close_returns_record_with_outcome` | D-03 terminator outcomes |
| `test_bind_url_resets_state` | D-04 / Pitfall 3 — per-URL reset |
| `test_cause_hint_network_after_error` | D-02 Discretion — `note_error_in_cycle()` flips cause_hint |

**Import:** `from musicstreamer.player import _BufferUnderrunTracker` — module-private helper, accessed by name.

---

### 5. `tests/test_player_underrun.py` (NEW) — Integration tests, Player + queued Signal + caplog

**Analog:** `tests/test_player_buffering.py` (existing `make_player(qtbot)` + `_fake_buffering_msg(percent)` seam) + `tests/test_media_keys_smtc.py:284-303` (caplog usage pattern).

#### 5a. `make_player` + `_fake_buffering_msg` seam (verbatim copy)

**Source pattern (verbatim — copy these helpers into the new test file or import from a shared conftest):**

```python
# Source: tests/test_player_buffering.py:1-27 — verbatim test seam
"""Tests for GStreamer BUFFERING bus handling in Player (Phase 47.1 D-12/D-14)."""
from unittest.mock import MagicMock, patch

from musicstreamer.models import StationStream
from musicstreamer.player import Player


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


def _fake_buffering_msg(percent, as_tuple=False):
    """Build a fake Gst.Message-like object whose parse_buffering() returns
    either a bare int (PyGObject flattened form) or a 1-tuple (formal binding).
    """
    msg = MagicMock()
    msg.parse_buffering.return_value = (percent,) if as_tuple else percent
    return msg
```

> **Recommendation:** Duplicate these two helpers verbatim into `tests/test_player_underrun.py`. The codebase does not have a shared test-helper module (`conftest.py` or `tests/_helpers.py`); duplication is the established convention. Both `tests/test_player_buffering.py` and `tests/test_player_pause.py` already redefine `make_player` independently.

#### 5b. `qtbot.waitSignal` for queued emission (verbatim from existing buffer test)

**Source pattern:** `tests/test_player_buffering.py:30-36`

```python
# Source: tests/test_player_buffering.py:30-36 — queued Signal assertion
def test_on_gst_buffering_emits_signal(qtbot):
    """A BUFFERING message with percent=42 causes buffer_percent.emit(42)."""
    player = make_player(qtbot)
    msg = _fake_buffering_msg(42)
    with qtbot.waitSignal(player.buffer_percent, timeout=1000) as blocker:
        player._on_gst_buffering(bus=None, msg=msg)
    assert blocker.args == [42]
```

**Apply:** Use `qtbot.waitSignal(player._underrun_cycle_opened, ...)` and `qtbot.waitSignal(player._underrun_cycle_closed, ...)` for the cycle-open/close emission tests.

#### 5c. Synchronous QTimer drive for dwell threshold

**Source pattern:** `tests/test_player.py:54-67` (drive `timeout` synchronously rather than wall-clock-wait).

```python
# Source: tests/test_player.py:54-67 — synchronous QTimer drive
def test_elapsed_timer_emits_seconds_while_playing(qtbot):
    """Timer ticks emit elapsed_updated(1), (2), (3); stop() halts the timer."""
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)

    # Manually drive the timer three times (bypass real wall clock).
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()

    assert emissions == [1, 2, 3]
```

**Apply:** Drive `player._underrun_dwell_timer.timeout.emit()` synchronously to simulate dwell elapse. Assert `player.underrun_recovery_started` was emitted via `qtbot.waitSignal(...)` or a connected list-collector.

#### 5d. `caplog` for log-line assertion

**Source pattern:** `tests/test_media_keys_smtc.py:284-303`

```python
# Source: tests/test_media_keys_smtc.py:284-303 — caplog idiom
def test_unknown_button_logged_no_crash(mock_winrt_modules, qtbot, caplog):
    import logging
    backend = WindowsMediaKeysBackend(None, None)
    args = MagicMock()
    args.button = backend._button_enum.CHANNEL_UP

    caplog.set_level(logging.DEBUG, logger="musicstreamer.media_keys.smtc")

    # ... action that triggers the log ...

    assert any("CHANNEL_UP" in r.message or "not handled" in r.message for r in caplog.records), (
        f"expected DEBUG log about unknown button; got: {[r.message for r in caplog.records]}"
    )
```

**Apply:** Use `caplog.set_level(logging.INFO, logger="musicstreamer.player")` then assert `"buffer_underrun" in r.message` and field substrings (`"outcome=recovered"`, `"min_percent=60"`, etc.).

#### 5e. `_try_next_stream` force-close (existing pattern)

**Source pattern:** `tests/test_player_buffering.py:59-81`

```python
# Source: tests/test_player_buffering.py:59-81 — _try_next_stream test seam
def test_dedup_resets_on_new_stream(qtbot):
    """_try_next_stream resets _last_buffer_percent so new URLs always emit
    their first buffer message (D-14 reset, Pitfall 3)."""
    player = make_player(qtbot)
    player._last_buffer_percent = 50
    fake_stream = StationStream(
        id=1, station_id=1, url="http://example.test/stream",
        codec="MP3", quality="hi", label="test", position=0, bitrate_kbps=128,
    )
    player._streams_queue = [fake_stream]
    player._is_first_attempt = False  # avoid starting elapsed timer in test
    player._try_next_stream()
    assert player._last_buffer_percent == -1
```

**Apply:** Mirror this shape; instead of asserting `_last_buffer_percent == -1`, drive an open cycle first (`player._on_gst_buffering(None, _fake_buffering_msg(100))` then `_fake_buffering_msg(70)`), call `_try_next_stream()`, assert the queued `_underrun_cycle_closed` was emitted with `outcome='failover'` and that the next URL's tracker is freshly bound.

**Test list (~8 tests per RESEARCH Wave 0 gap):**

| Test | Validates |
|------|-----------|
| `test_buffering_drop_emits_cycle_opened` | bus handler emits `_underrun_cycle_opened` |
| `test_buffering_recover_emits_cycle_closed` | bus handler emits `_underrun_cycle_closed` with full record |
| `test_try_next_stream_force_closes_with_failover_outcome` | `_try_next_stream` → outcome=failover |
| `test_pause_force_closes_with_pause_outcome` | `pause()` → outcome=pause |
| `test_stop_force_closes_with_stop_outcome` | `stop()` → outcome=stop |
| `test_cycle_close_writes_structured_log` | INFO log with all 9 fields (caplog) |
| `test_dwell_timer_fires_after_threshold` | `underrun_recovery_started` emits on `timeout.emit()` |
| `test_sub_dwell_recovery_silent` | sub-1500ms recovery cancels timer, no Signal |

---

### 6. `tests/test_main_window_underrun.py` (NEW) — Integration, MainWindow cooldown gate

**Analog:** `tests/test_main_window_integration.py` (FakePlayer + qtbot fixture pattern).

#### 6a. FakePlayer surface (extend existing pattern)

**Source pattern:** `tests/test_main_window_integration.py:31-75` — `FakePlayer(QObject)` with the same Signals as the real Player.

**Existing class shape (excerpt — extend with new Signals):**

```python
# Source: tests/test_main_window_integration.py:31-75
class FakePlayer(QObject):
    """Minimal Player surface — exposes the same Signals as the real Player."""

    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)

    def __init__(self):
        super().__init__()
        self.play_calls: list[Station] = []
        ...
```

**Apply:** Either (a) extend `FakePlayer` in `tests/test_main_window_integration.py` to add `underrun_recovery_started = Signal()` and a no-op `shutdown_underrun_tracker()` method, OR (b) declare a fresh `FakePlayer` in the new test file mirroring this exact shape. Recommendation: **add the new Signal+method to the existing FakePlayer** — it must be available wherever MainWindow is constructed under test, including `test_main_window_integration.py::test_widget_lifetime_no_runtime_error` which constructs/destroys 3x.

```python
# NEW — extend FakePlayer at test_main_window_integration.py:31-40
class FakePlayer(QObject):
    title_changed = Signal(str)
    # ... existing Signals ...
    buffer_percent = Signal(int)
    underrun_recovery_started = Signal()   # NEW — Phase 62 / D-07

    def shutdown_underrun_tracker(self) -> None:    # NEW — Phase 62 / D-03
        """No-op stub for FakePlayer (real method force-closes tracker on shutdown)."""
        pass
```

#### 6b. `time.monotonic` monkeypatch for cooldown determinism

**Source pattern:** No prior `monkeypatch.setattr("...time.monotonic", ...)` in the codebase. Closest analog: `tests/test_main_window_integration.py:194-200` for the `window` fixture; `monkeypatch` is a standard pytest fixture available everywhere.

**Apply:**

```python
# NEW — pattern for test_main_window_underrun.py
def test_first_call_shows_toast(qtbot, fake_player, fake_repo, monkeypatch):
    monkeypatch.setattr("musicstreamer.ui_qt.main_window.time.monotonic", lambda: 1000.0)
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)   # let queued connection deliver
    assert "Buffering" in w._toast.label.text()

def test_second_call_within_cooldown_suppressed(qtbot, fake_player, fake_repo, monkeypatch):
    times = iter([1000.0, 1000.0, 1005.0, 1005.0])   # 1st call, 2nd call (5s later, within 10s)
    monkeypatch.setattr("musicstreamer.ui_qt.main_window.time.monotonic", lambda: next(times))
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    w._toast.hide()    # clear visual state for assertion
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert not w._toast.isVisible()    # cooldown suppressed the 2nd toast
```

#### 6c. Toast assertion via `_toast.label.text()`

**Source pattern:** `tests/test_main_window_integration.py:350-368`

```python
# Source: tests/test_main_window_integration.py:350-367 — toast assertion
def test_playback_error_shows_toast(qtbot, window, fake_player):
    fake_player.playback_error.emit("Pipeline failed")
    assert "Playback error" in window._toast.label.text()
    assert "Pipeline failed" in window._toast.label.text()

def test_show_toast_public_api(qtbot, window):
    window.show_toast("Hello test")
    assert window._toast.label.text() == "Hello test"
```

**Apply:** Assert `"Buffering" in w._toast.label.text()` (the U+2026 ellipsis is a separate codepoint; substring match is robust).

**Test list (~3 tests per RESEARCH Wave 0 gap):**

| Test | Validates |
|------|-----------|
| `test_first_call_shows_toast` | D-06 — first emission shows `Buffering…` |
| `test_second_call_within_cooldown_suppressed` | D-08 — 2nd within 10s suppressed |
| `test_toast_after_cooldown_allowed` | D-08 — after 10s elapses, next emission shows toast |

---

## Shared Patterns

### S-1. Bound-method `Signal.connect(...)` (QA-05)

**Source:** Every `.connect(...)` in `player.py` and `main_window.py` uses a bound method, never a self-capturing lambda.

**Excerpt:**

```python
# Source: musicstreamer/player.py:195-197
self._cancel_timers_requested.connect(
    self._cancel_timers, Qt.ConnectionType.QueuedConnection
)
```

**Apply to:** All four new connections in this phase (3 in Player.__init__, 1 in MainWindow.__init__). No `lambda: self.foo()` — use `self._on_underrun_cycle_opened` etc.

---

### S-2. `Qt.ConnectionType.QueuedConnection` for cross-thread Signal hops (Pitfall 2 — BINDING)

**Source:** 4 existing precedents at `player.py:185-208`. Required for any Signal emitted from `GstBusLoopThread` whose slot does Qt-affined work.

**Excerpt:** see §1b above.

**Apply to:**
- `_underrun_cycle_opened` (bus-loop emit → main slot starts QTimer) — REQUIRED
- `_underrun_cycle_closed` (bus-loop emit → main slot calls `_log.info` + QTimer.stop) — REQUIRED
- `underrun_recovery_started` (main emit → main slot — same thread, but explicit queueing matches the file convention; harmless and clearer)

---

### S-3. Pitfall 1 — `parse_buffering()` tuple-or-int parser

**Source:** `musicstreamer/player.py:455-457`. Already in place — DO NOT add a second parser.

**Excerpt:**

```python
# Source: musicstreamer/player.py:455-457 — Pitfall 1 idiom
result = msg.parse_buffering()
percent = result[0] if isinstance(result, tuple) else int(result)
```

**Apply to:** No change needed. The tracker consumes the already-parsed `int` from the existing handler. New tracker code does NOT touch `parse_buffering` directly.

---

### S-4. Pitfall 3 — per-URL state reset adjacent to existing reset

**Source:** `musicstreamer/player.py:543-545`.

**Apply to:** §1e above. The new `tracker.bind_url(...)` call MUST land in the same block as the existing `_last_buffer_percent = -1` reset. Forgetting this is the documented Pitfall 3 regression mode (spurious toast on every station change).

---

### S-5. `…` literal for ellipsis (UI-SPEC convention)

**Source:** `musicstreamer/ui_qt/main_window.py:367, 393, 280` — `"Connecting…"`, `"Stream failed, trying next…"`, etc.

**Apply to:** New toast text in §2b: `self.show_toast("Buffering…")`. Match the codebase's `…` escape style — do NOT inline the Unicode glyph.

---

### S-6. `try/except` around shutdown calls in `closeEvent`

**Source:** `musicstreamer/ui_qt/main_window.py:354-357`.

**Apply to:** §2c above — wrap `shutdown_underrun_tracker()` in `try/except Exception as exc: _log.warning(...)`. Same belt-and-braces shape as the existing `_media_keys.shutdown()` wrapper. A shutdown crash in any single subsystem must not block app exit.

---

### S-7. Test seam — duplicate `make_player` helper per file (no shared module)

**Source:** `tests/test_player_buffering.py:8-18`, `tests/test_player_pause.py:10-23`, `tests/test_player.py` — three test files each redefine `make_player` independently. The codebase has chosen duplication over a shared helper.

**Apply to:** §5a — copy `make_player` and `_fake_buffering_msg` verbatim into `tests/test_player_underrun.py`. Do NOT extract them to a shared `conftest.py`.

---

### S-8. `caplog.set_level(logging.LEVEL, logger="musicstreamer.MODULE")` for log assertion

**Source:** `tests/test_media_keys_smtc.py:293, 317, 588`. Always passes the explicit logger name (scoped, not global).

**Apply to:** §5d — `caplog.set_level(logging.INFO, logger="musicstreamer.player")` in the test that asserts `buffer_underrun ...` log content.

---

## No Analog Found

No files in this phase fall outside existing precedent. Every new file has at least one role-and-data-flow-exact analog already in the repository.

The only **micro-pattern** without prior usage is `time.monotonic()` (§2b cooldown). It is stdlib-canonical and risk-free. Per RESEARCH Open Questions / Assumption A1, the only consequence is "we set a precedent that future phases might mimic" — that's a feature, not a regression.

---

## Metadata

**Analog search scope:**
- `musicstreamer/player.py` (1004 lines, full file read)
- `musicstreamer/ui_qt/main_window.py` (240-400 + 352-358 closeEvent + signal-wiring block)
- `musicstreamer/__main__.py` (1-30 + 210-240)
- `musicstreamer/aa_import.py` (1-35 — logger pattern)
- `musicstreamer/single_instance.py` (20-35 — logger pattern)
- `musicstreamer/models.py` (1-60 — Station / StationStream dataclass shape)
- `tests/test_player_buffering.py` (full 82 lines)
- `tests/test_player_pause.py` (1-90)
- `tests/test_player.py` (40-130)
- `tests/test_stream_ordering.py` (1-80)
- `tests/test_main_window_integration.py` (1-100, 175-260, 350-388)
- `tests/test_media_keys_smtc.py` (280-330 — caplog pattern)

**Files scanned:** 12 source/test files (all referenced as direct citations in PATTERNS.md sections).

**Pattern extraction date:** 2026-05-07

**Cross-references with RESEARCH:**
- §1c (QTimer pattern) ↔ RESEARCH §Pattern 3
- §1d (queued Signal from bus handler) ↔ RESEARCH §Pattern 2 + Pitfall 2
- §1e (per-URL reset) ↔ RESEARCH Pitfall 3
- §2b (cooldown via `time.monotonic`) ↔ RESEARCH §Pattern 4
- §3 (per-logger level) ↔ RESEARCH Pitfall 5
- §5b (qtbot.waitSignal) ↔ RESEARCH §Validation Architecture / Test seam recommendation
- §5d (caplog idiom) ↔ RESEARCH §Logging Integration / "For tests"
