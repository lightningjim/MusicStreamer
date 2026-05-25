# Phase 84: BUG-09 Commit B — buffer-tuning behavior fix (reframed) - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 11 new/modified files
**Analogs found:** 11 / 11 (every new file has a 1:1 in-repo precedent — Phase 78 Commit A is the canonical mirror)

---

## File Classification

| New/Modified File | Wave | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `musicstreamer/constants.py` (lines 54-56 edit) | W1 | config (constants module) | static literal | `musicstreamer/constants.py:54-56` itself (Phase 16 baseline) | exact |
| `musicstreamer/player.py` (Signal + state fields + 3 helpers + 2 apply sites) | W1 | service (audio engine) | event-driven + request-response (GStreamer set_property writes + Qt Signal emit) | `musicstreamer/player.py:297, 498, 1133-1134, 1146-1175, 1267-1369` (Phase 78 Commit A wiring + Phase 62 D-04 reset block + Phase 83 preroll handoff) | exact |
| `musicstreamer/ui_qt/main_window.py` (+1 `.connect` after line 390) | W1 | controller (Qt wiring) | request-response (Signal connection) | `musicstreamer/ui_qt/main_window.py:382-390` (Phase 78 Commit A wire) | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` (+1 slot, +1 form.addRow) | W1 | component (Qt widget) | request-response (slot updates label) | `musicstreamer/ui_qt/now_playing_panel.py:1002-1010, 2936-2938` (Phase 78 Commit A row + slot) | exact |
| `tests/_fake_player.py` (+1 Signal mirror line 75) | W0 | test (Player test double) | parity drift-guard | `tests/_fake_player.py:75` (Phase 78 Commit A `underrun_count_changed` mirror) | exact |
| `tests/test_player_buffer.py` (constants literal update) | W0 | test (unit — constants) | static assert | `tests/test_player_buffer.py:30-51` itself (existing test pattern) | exact |
| `tests/test_player_buffer_growth.py` (NEW) | W0 | test (unit — state machine + URI-bind apply) | event-driven (cycle_close → state mutation) | `tests/test_player_underrun_count.py:1-119` (Phase 78 cycle counter tests; `make_player` seam + `_make_record` helper) | exact |
| `tests/test_playbin3_property_hygiene.py` (NEW) | W0 | test (source-grep gate) | static file scan | `tests/test_db_connect_is_sole_connection_factory.py:1-206` (Phase 80 tokenize-blanked source grep) | exact |
| `tests/test_now_playing_panel.py` (+3 tests inside existing file) | W0 | test (Qt widget) | request-response (slot → label text) | existing tests in same file covering `set_underrun_count` / `set_buffer_percent` | exact |
| `tests/test_main_window_underrun.py` (+1 test inside existing file) | W0 | test (Qt integration) | end-to-end Signal wire | existing test covering Player.underrun_count_changed → NowPlayingPanel | exact |
| `.planning/phases/84-…/84-VERIFICATION.md` (NEW) | W2 | docs (closure record) | static markdown | Phase 78 VERIFICATION.md (`.planning/phases/78-…/78-VERIFICATION.md`) — waived-gate + monitor plan precedent | exact |

---

## Pattern Assignments

### `musicstreamer/constants.py` lines 54-56 (D-10 literal-edit)

**Analog:** `musicstreamer/constants.py:54-56` itself (Phase 16 baseline being changed)

**Current state** (file lines 54-56, to be replaced):

```python
# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01)
BUFFER_DURATION_S = 10                    # seconds; applied as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 10 * 1024 * 1024      # 5 MB
```

**Target state per D-10:** Bump both literals AND fix the misleading inline `# 5 MB` comment (which was always wrong — `10 * 1024 * 1024` is 10 MB even pre-change). Optionally extend the header comment to reference Phase 84 / D-10. The comment freshening is a drive-by per D-10 Discretion.

**Notes for planner:**
- Single import site cluster: both names are imported by `musicstreamer/player.py` (line 51 area — verify with `grep -n "BUFFER_DURATION_S\|BUFFER_SIZE_BYTES" musicstreamer/`).
- Zero new construction-site code needed in player.py — the existing `self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)` at `player.py:318` already reads the bumped value.
- `tests/test_player_buffer.py:31, 35` literal assertions need updating in the SAME commit (otherwise CI red).

---

### `musicstreamer/player.py` (Phase 84 / D-11 + D-12 surface)

**Analog:** Phase 78 Commit A wiring at `player.py:297, 498, 1133-1134` (canonical mirror); Phase 62 D-04 reset block at `player.py:1146-1175`; Phase 83 preroll handoff at `player.py:1267-1369`.

#### Pattern 1: Class-level Signal declaration (D-12)

**Analog excerpt** (`musicstreamer/player.py:285-302`):

```python
    # Phase 62 / BUG-09: buffer-underrun cycle Signals.
    # _underrun_cycle_opened / _underrun_cycle_closed are bus-loop → main
    # queued (Pitfall 2 — bus handlers may only emit Signals).
    # underrun_recovery_started is main → MainWindow (D-07 dwell elapsed).
    _underrun_cycle_opened    = Signal()         # bus-loop → main: arm dwell timer
    _underrun_cycle_closed    = Signal(object)   # bus-loop → main: log + cancel dwell (object = _CycleClose)
    underrun_recovery_started = Signal()         # main → MainWindow: show_toast (D-07)
    # Phase 78 / BUG-09 Commit A: cumulative cycle counter for stats-for-nerds row.
    # Emitted from _on_underrun_cycle_closed (main-thread slot — the receiving end
    # of the queued _underrun_cycle_closed connection above). Both emitter and
    # receiver (MainWindow → NowPlayingPanel) are on the main thread, so the wire
    # uses DirectConnection (default) — qt-glib-bus-threading.md Pitfall 2 satisfied.
    underrun_count_changed    = Signal(int)      # main → MainWindow → NowPlayingPanel.set_underrun_count
```

**Apply to:** Add `buffer_duration_changed = Signal(int)` immediately after line 297 with a comment block that mirrors the Phase 78 docstring AND cites RESEARCH.md Pattern 3 / Pitfall 2. Same emission thread (main), same DirectConnection wire shape, same `_MutedLabel` UI sink shape. RESEARCH.md A5 verifies no name collision.

#### Pattern 2: Instance-field state init in `__init__` (D-11)

**Analog excerpt** (`musicstreamer/player.py:490-498`):

```python
        # Tracker mirrors Phase 47.1 D-14 sentinel reset lifecycle (Pitfall 3 —
        # bind_url is called from _try_next_stream alongside _last_buffer_percent reset).
        # _current_station_id mirrors _current_station_name for log-line context.
        self._tracker = _BufferUnderrunTracker()
        self._current_station_id: int = 0
        # Phase 78 / BUG-09 Commit A: cumulative cycle count (resets per launch,
        # CONTEXT.md Discretion — the file sink from Plan 78-01 is the persistent record).
        # Type-annotated zero — Pitfall 3 (never rely on set-on-first-write semantics).
        self._underrun_event_count: int = 0
```

**Apply to:** Immediately after line 498, add three new instance fields per RESEARCH.md Example 2:

```python
        # Phase 84 / D-11 / BUG-09 Commit B: adaptive buffer-duration growth state.
        # Per playbin3 source inspection (84-RESEARCH §D-11), mid-session writes to
        # buffer-duration are silent no-ops; this state is staged at cycle_close and
        # applied to the pipeline at the next URI bind (in _try_next_stream and
        # _on_preroll_about_to_finish, BEFORE the set_property("uri", ...) call).
        self._growth_step: int = 0                                     # 0 = baseline, 1 = 60s, 2 = 120s (cap)
        self._current_buffer_duration_s: int = BUFFER_DURATION_S       # mirrors stats-for-nerds row
        self._pending_buffer_duration_s: int | None = None             # staged for next URI bind
```

**Type-annotated init invariant carried forward from Phase 78** (Pitfall 3 — never rely on set-on-first-write semantics).

#### Pattern 3: Cycle-close slot extension — increment + Signal emit (D-11)

**Analog excerpt** (`musicstreamer/player.py:1113-1134`):

```python
    def _on_underrun_cycle_closed(self, record) -> None:
        """Main-thread slot (Phase 62 / D-02). Cancels in-flight dwell timer
        (silent recovery, D-07) and writes the structured log line at INFO.

        T-62-01 mitigation: station_name and url are %r-quoted, so embedded
        newlines / control chars / quotes from library data cannot inject
        spurious log lines or break grep-based diagnosis.
        """
        self._underrun_dwell_timer.stop()    # idempotent
        _log.info(
            "buffer_underrun "
            "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
            "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
            record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
            record.station_id, record.station_name, record.url,
            record.outcome, record.cause_hint,
        )
        # Phase 78 / BUG-09 Commit A: increment + emit on EVERY cycle close
        # (every outcome — recovered / failover / stop / pause / shutdown —
        # mirrors the file-sink one-line-per-cycle semantics per CONTEXT <specifics>).
        self._underrun_event_count += 1
        self.underrun_count_changed.emit(self._underrun_event_count)
```

**Apply to:** Add ONE new line at the end of this slot calling `self._maybe_grow_buffer_duration()` (RESEARCH.md Example 4). Do NOT inline the growth logic in the slot — keep it factored out for testability per RESEARCH §S-7 convention.

#### Pattern 4: Three new helper methods on Player (D-11)

Per RESEARCH.md Examples 4-5 / §D-11 Resolution. Method bodies should land near `_on_underrun_cycle_closed` (line 1113) and `_try_next_stream` (line 1146) — co-located with their callsites:

- `_maybe_grow_buffer_duration()` — bump 0→1→2 cap, stage `_pending_buffer_duration_s`, emit `buffer_duration_changed`.
- `_apply_pending_buffer_duration_to_pipeline()` — write staged value to `self._pipeline.set_property("buffer-duration", N * Gst.SECOND)`; clear `_pending`.
- `_reset_buffer_duration_to_baseline()` — early-return when already at baseline (Pitfall 3 — no spurious Signal); else reset all three fields and emit `buffer_duration_changed(BUFFER_DURATION_S)`.

#### Pattern 5: Per-URL reset block in `_try_next_stream` (D-11)

**Analog excerpt** (`musicstreamer/player.py:1146-1175`):

```python
    def _try_next_stream(self) -> None:
        """Pop next stream from queue and attempt playback. On empty queue,
        emit failover(None)."""
        self._pipeline.set_state(Gst.State.NULL)
        # Wait for NULL to complete so playbin3's internal streamsynchronizer
        # fully resets before we reconfigure.  Without this, rapid
        # teardown→replay (e.g. YouTube resolve failure → failover) can leave
        # duplicate pad names in streamsynchronizer, triggering GStreamer
        # CRITICAL assertions that abort the process.
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        if not self._streams_queue:
            # All streams exhausted
            self.failover.emit(None)
            return
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        self._last_buffer_percent = -1  # 47.1 D-14: reset so new URL's first buffer emits (Pitfall 3)
        # Phase 62 / D-03 + T-62-02: force-close any cycle on the OUTGOING URL
        # with outcome=failover BEFORE binding the tracker to the NEW URL.
        # Ordering is load-bearing: the close record must carry the OLD url.
        prior_close = self._tracker.force_close("failover")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)   # queued → main: log + cancel dwell
        # Phase 62 / D-04: bind tracker to NEW URL (mirror of D-14 sentinel reset, Pitfall 3).
        self._tracker.bind_url(
            station_id=self._current_station_id,
            station_name=self._current_station_name,
            url=stream.url,
        )
```

**Apply to:** Insert TWO calls immediately AFTER `self._last_buffer_percent = -1` (line 1162) and BEFORE `prior_close = self._tracker.force_close(...)`:

```python
        self._last_buffer_percent = -1  # EXISTING — Phase 47.1 D-14
        # Phase 84 / D-11: apply staged buffer-duration to playbin3 BEFORE binding
        # the new URI. uridecodebin3.new_source_handler will read playbin3.buffer_duration
        # at URI-bind time and push it to urisourcebin → queue2.
        self._apply_pending_buffer_duration_to_pipeline()
        # Phase 84 / D-11 per-URL reset (mirrors Phase 47.1 D-14 sentinel reset
        # at _last_buffer_percent above and tracker.bind_url below).
        self._reset_buffer_duration_to_baseline()
```

**Ordering load-bearing:** Apply BEFORE the eventual `_set_uri(url)` call at line 1191 (which itself does `set_property("uri", ...)` at line 1199). The `_apply_pending_*` write must precede the URI write per RESEARCH §D-11 (uridecodebin3 reads playbin3.buffer_duration during `new_source_handler` which fires on URI write).

#### Pattern 6: Per-URI-bind apply in `_on_preroll_about_to_finish` (D-11 — Phase 83 gapless handoff site)

**Analog excerpt** (`musicstreamer/player.py:1338-1369` — Phase 83 gapless handoff):

```python
        stream = self._streams_queue.pop(0)
        self._current_stream = stream
        self._last_buffer_percent = -1  # Pitfall 3 — mirror _try_next_stream:1056
        # Force-close any cycle on the OUTGOING URL with a "preroll" outcome ...
        prior_close = self._tracker.force_close("preroll")
        if prior_close is not None:
            self._underrun_cycle_closed.emit(prior_close)
        self._tracker.bind_url(
            station_id=self._current_station_id,
            station_name=self._current_station_name,
            url=stream.url,
        )
        self._underrun_dwell_timer.stop()
        # ... elapsed-timer seeding (lines 1354-1362, UNCHANGED) ...
        # Gapless: set URI on the still-PLAYING pipeline. NO set_state(NULL),
        # NO set_state(PLAYING) — playbin3 transitions to the new URI at the
        # preroll's EOS automatically. ...
        self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))   # line 1369
```

**Apply to:** Insert the SAME two `_apply_pending_buffer_duration_to_pipeline()` + `_reset_buffer_duration_to_baseline()` calls immediately BEFORE line 1369 (`set_property("uri", ...)`). Per RESEARCH Pitfall 2: missing this site means SomaFM users (who hit gapless preroll handoff hourly) lose all adaptive growth on every preroll cycle. Must mirror the `_try_next_stream` block exactly.

**Implementation invariant (Pitfall 7 — DO NOT TOUCH):** Lines 320-325 `flags | 0x100` (`GST_PLAY_FLAG_BUFFERING`) is load-bearing. Without it, ALL Phase 84 work is invisible. The Pattern 4 grep gate (`tests/test_playbin3_property_hygiene.py`) regression-locks this.

---

### `musicstreamer/ui_qt/main_window.py` (+1 `.connect` after line 390)

**Analog:** `musicstreamer/ui_qt/main_window.py:382-390` (Phase 78 Commit A wire)

**Analog excerpt** (lines 380-390):

```python
        self._player.elapsed_updated.connect(self.now_playing.on_elapsed_updated)
        self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)
        # Phase 78 / BUG-09 Commit A: cumulative underrun cycle count → stats-for-nerds row.
        # Bound method per QA-05 / §S-3 (no lambda). DirectConnection (default — no
        # Qt.ConnectionType.QueuedConnection argument) is correct because the emit
        # site is Player._on_underrun_cycle_closed (main-thread slot, RESEARCH A3) and
        # the receiver NowPlayingPanel.set_underrun_count is a QWidget slot also on
        # the main thread (Pitfall 2 satisfied). This differs from the Phase 62
        # underrun_recovery_started connection below, which uses QueuedConnection
        # defensively for unrelated reasons — do NOT harmonize the two wires.
        self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)
```

**Apply to:** Add ONE new line immediately after line 390 (per RESEARCH Example 7). Bound method per QA-05 (no lambda). DirectConnection (default — both ends main-thread). Comment block must cite RESEARCH §Pattern 3 / Pitfall 2 and warn against harmonizing with QueuedConnection.

```python
        # Phase 84 / D-12 / BUG-09 Commit B: live buffer-duration → stats-for-nerds "Buf duration" row.
        # ... [comment block mirroring above] ...
        self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)
```

---

### `musicstreamer/ui_qt/now_playing_panel.py` (+1 slot near line 1010, +1 form.addRow in `_build_stats_widget`)

**Analog:** `musicstreamer/ui_qt/now_playing_panel.py:1002-1010` (slot) + lines 2930-2941 (stats widget rows).

#### Slot pattern (line 1002-1010 analog)

```python
    def set_underrun_count(self, count: int) -> None:
        """Phase 78 / BUG-09 Commit A: receiver for Player.underrun_count_changed.

        Updates the Underruns stats-for-nerds row text to the new cumulative
        cycle count. The int() coercion is defensive (mirrors set_buffer_percent's
        pattern); the wrapper-level set_stats_visible governs visibility for
        both this row and the Buffer row above.
        """
        self._underrun_count_label.setText(str(int(count)))
```

**Apply to:** Add `set_buffer_duration(self, seconds: int) -> None:` slot immediately after `set_underrun_count` per RESEARCH Example 8. `int()` coercion defensive (mirrors `set_underrun_count` + `set_buffer_percent`). Label format: `"{s}s"` when at baseline `BUFFER_DURATION_S`; `"{s}s (adapted)"` otherwise. Import `BUFFER_DURATION_S` locally inside the method (function-local import — minor convention, but matches RESEARCH guidance to keep the constant in one place).

#### Stats row pattern (lines 2930-2941 analog)

**Analog excerpt** (`musicstreamer/ui_qt/now_playing_panel.py:2930-2942`):

```python
        form.addRow(buffer_row_label, value_row)
        # Phase 78 / BUG-09 Commit A: cumulative underrun cycle count row.
        # Two-column shape mirrors the Buffer row above (RESEARCH Open Q2);
        # _MutedLabel preserves theme-flip readability per Phase 47.1 D-10;
        # the wrapper-level setVisible(False) below applies to BOTH rows —
        # no per-row visibility code is needed (set_stats_visible governs both).
        underrun_row_label = _MutedLabel("Underruns", wrapper)
        self._underrun_count_label = _MutedLabel("0", wrapper)
        form.addRow(underrun_row_label, self._underrun_count_label)
        # D-05: default hidden. MainWindow drives visibility from the QAction's
        # checked state after construction (WR-02: single source of truth).
        wrapper.setVisible(False)
        return wrapper
```

**Apply to:** Add THREE new lines immediately AFTER `form.addRow(underrun_row_label, self._underrun_count_label)` (line 2938) and BEFORE `wrapper.setVisible(False)` (line 2941). Use the RESEARCH-recommended label string `"Buf duration"` (NOT `"Buffer"` — would shadow the existing progressbar row label). Initial value: `f"{BUFFER_DURATION_S}s"`. `_MutedLabel` preserves theme-flip readability. Inherit wrapper visibility — DO NOT add per-row `setVisible()` (Pitfall 8).

```python
        # Phase 84 / D-12 / BUG-09 Commit B: always-visible adaptive buffer-duration row.
        # [comment block — see RESEARCH Example 8]
        buffer_duration_row_label = _MutedLabel("Buf duration", wrapper)
        self._buffer_duration_label = _MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)
        form.addRow(buffer_duration_row_label, self._buffer_duration_label)
        wrapper.setVisible(False)                                       # EXISTING — line 2941
```

---

### `tests/_fake_player.py` (parity edit — INFRA-01 drift-guard)

**Analog:** `tests/_fake_player.py:72-78` (Phase 78 Commit A `underrun_count_changed` mirror entry).

**Analog excerpt** (lines 67-78):

```python
    _cancel_timers_requested           = Signal()
    _error_recovery_requested          = Signal()
    _try_next_stream_requested         = Signal()
    _preroll_about_to_finish_requested = Signal(int)  # Phase 83 D-05 — preroll about-to-finish handoff (int = preroll_seq for CR-01/WR-03 guard)
    _playbin_playing_state_reached     = Signal()
    _underrun_cycle_opened         = Signal()
    _underrun_cycle_closed         = Signal(object)
    underrun_recovery_started      = Signal()
    underrun_count_changed         = Signal(int)  # Phase 78 / BUG-09 Commit A

    # Phase 70 / DS-01 caps signal (1)
    audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth
```

**Apply to:** Add ONE line immediately after line 75 (`underrun_count_changed`) per RESEARCH Example 9:

```python
    underrun_count_changed         = Signal(int)  # Phase 78 / BUG-09 Commit A
    buffer_duration_changed        = Signal(int)  # Phase 84 / BUG-09 Commit B / D-12
```

**Drift-guard side effect:** Update the class docstring "20 signals, D-16 invariant" → "21 signals" if the parity gate's count assertion is strict. Verify by running `pytest tests/test_fake_player_signal_parity.py -v` — if it fails on count, also update the docstring + any count-based assertion in the parity test file. (RESEARCH A6 indicates the existing pattern is well-established.)

---

### `tests/test_player_buffer.py` (constants literal update)

**Analog:** the file itself (Phase 35 port — see `tests/test_player_buffer.py:30-51`).

**Lines to edit:**
- Line 31: `assert BUFFER_DURATION_S == 10` → `assert BUFFER_DURATION_S == 30`
- Line 35: `assert BUFFER_SIZE_BYTES == 10 * 1024 * 1024` → `assert BUFFER_SIZE_BYTES == 20 * 1024 * 1024`

Lines 43 (`assert calls["buffer-duration"] == BUFFER_DURATION_S * _GST_SECOND`) and 51 (`assert calls["buffer-size"] == BUFFER_SIZE_BYTES`) need NO change — they reference the imported constant symbolically.

No new test functions. No new helpers. Literal-only.

---

### `tests/test_player_buffer_growth.py` (NEW)

**Analog:** `tests/test_player_underrun_count.py:1-119` (Phase 78 Commit A cycle counter tests — exact same `make_player` seam + `_make_record` helper shape).

**Test seam to reuse verbatim** (from `tests/test_player_underrun_count.py:27-42`):

```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Verbatim duplicate of tests/test_player_underrun.py:16-31 (per
    PATTERNS.md §S-7 — codebase convention is per-file helper duplication,
    not shared conftest extraction).
    """
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player
```

**Record-builder helper to reuse verbatim** (from `tests/test_player_underrun_count.py:45-62`):

```python
def _make_record(outcome: str = "recovered") -> _CycleClose:
    return _CycleClose(
        start_ts=10.0,
        end_ts=11.5,
        duration_ms=1500,
        min_percent=60,
        station_id=7,
        station_name="Test",
        url="http://x/",
        outcome=outcome,
        cause_hint="unknown",
    )
```

**Test pattern to mirror** (from `tests/test_player_underrun_count.py:97-118` — signal emission pattern):

```python
def test_signal_emits_with_count_value(qtbot):
    player = make_player(qtbot)
    rec = _make_record()
    received: list[int] = []
    player.underrun_count_changed.connect(received.append)
    player._on_underrun_cycle_closed(rec)
    qtbot.wait(50)
    assert received == [1]
```

**Apply to:** Per RESEARCH Example 10, ~10 test functions covering:
- `test_growth_state_initialized` — init: `_growth_step==0`, `_current==BUFFER_DURATION_S`, `_pending is None`.
- `test_first_cycle_close_bumps_to_60` — `qtbot.waitSignal(p.buffer_duration_changed)` blocker pattern.
- `test_second_cycle_close_bumps_to_120` — sequential cycle_close calls.
- `test_growth_caps_at_120` — loop 5 calls, assert stays at 2/120.
- `test_try_next_stream_applies_pending_before_uri_bind` — call ordering assertion on `_pipeline.set_property.call_args_list` (the dash-form `"buffer-duration"` arg precedes the `"uri"` arg).
- `test_preroll_handoff_applies_pending_before_uri_swap` — same call-ordering assertion for the `_on_preroll_about_to_finish` site (Pitfall 2 — this is the test that catches the SomaFM gapless regression).
- `test_try_next_stream_resets_growth_to_baseline` — state machine reset after URL bind.
- `test_reset_is_noop_when_at_baseline` — `qtbot.assertNotEmitted(p.buffer_duration_changed, wait=100)` (Pitfall 3 — no spurious Signal).
- `test_buffer_duration_changed_signal_class_scope` — source-level assertion `hasattr(Player, 'buffer_duration_changed')` and the Signal arity.

**Imports** (file header):

```python
from unittest.mock import MagicMock, call, patch
import pytest
from musicstreamer.constants import BUFFER_DURATION_S
from musicstreamer.player import Player, _CycleClose

_GST_SECOND = 1_000_000_000  # avoid `import gi` (D-26 / QA-02)
```

**Note on `_GST_SECOND`:** `tests/test_player_buffer.py:13` already hard-codes this for the same reason ("test file does not need `import gi` (D-26 / QA-02)"). Copy that convention here verbatim.

---

### `tests/test_playbin3_property_hygiene.py` (NEW — source-grep gate)

**Analog:** `tests/test_db_connect_is_sole_connection_factory.py:1-206` (Phase 80 tokenize-blanked source grep — canonical project pattern).

#### Imports + module-scope constants (analog lines 45-56)

```python
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

_MUSICSTREAMER_PKG = Path(__file__).resolve().parent.parent / "musicstreamer"
```

#### Tokenize-blanking scan helper (analog lines 67-99)

```python
def _scan_file(path: Path) -> list[int]:
    """Return 1-based line numbers in ``path`` whose executable code
    matches :data:`_PATTERN`. STRING and COMMENT token ranges are blanked
    before scanning so that docstring / comment mentions of
    ``sqlite3.connect(...)`` are intentionally ignored.

    If the file cannot be tokenized (e.g. a syntax error in a vendored
    chunk), fall back to a raw line scan — better to over-report than
    silently miss a real callsite.
    """
    src = path.read_text(encoding="utf-8")
    rows = [list(line) for line in src.splitlines()]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        return [
            i for i, line in enumerate(src.splitlines(), 1) if _PATTERN.search(line)
        ]
    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        (start_row, start_col), (end_row, end_col) = tok.start, tok.end
        for ln in range(start_row, end_row + 1):
            if ln - 1 >= len(rows):
                continue
            row = rows[ln - 1]
            lo = start_col if ln == start_row else 0
            hi = end_col if ln == end_row else len(row)
            for j in range(lo, min(hi, len(row))):
                row[j] = " "
    return [i for i, row in enumerate(rows, 1) if _PATTERN.search("".join(row))]
```

**Apply to:** Adapt the helper to scan `musicstreamer/player.py` specifically (single file, not the whole tree), capturing the first string argument to `self._pipeline.set_property(...)`. RESEARCH Pattern 4 provides the regex and the allowlist:

```python
_PLAYER_PATH = _MUSICSTREAMER_PKG / "player.py"

_ALLOWED_PIPELINE_PROPERTIES = {
    "video-sink", "audio-sink", "buffer-duration", "buffer-size",
    "flags", "audio-filter", "uri", "volume",
}
_BANNED_SPELLINGS = {
    "buffer_duration", "buffer_size", "connection_speed",
    "low-percent", "high-percent",        # Phase 78/84 DEFERRED — must not land
}
_SETPROPERTY_RE = re.compile(
    r"""self\._pipeline\.set_property\(\s*["']([^"']+)["']"""
)
```

#### Test function pattern (analog lines 126-165 — grep-friendly failure messages)

```python
def test_only_one_sqlite_connect_callsite_in_production(
    production_callsites: dict[Path, list[int]],
) -> None:
    """Phase 80 / BUG-10 / D-09 / D-12: the production tree must contain
    exactly one ``sqlite3.connect(`` ...
    """
    total = sum(len(line_numbers) for line_numbers in production_callsites.values())
    assert total == 1, (
        "Phase 80 / BUG-10 / D-09 / D-12 drift-guard FAIL: expected "
        f"exactly 1 `sqlite3.connect(` callsite ... found {total}. "
        f"Offending files and line numbers: ..."
    )
```

**Apply to:** Three test functions per RESEARCH §Test Map row 17-19:

1. `test_pipeline_setproperty_uses_only_allowed_names` — allowlist enforcement (RESEARCH Pattern 4 reference body).
2. `test_pipeline_setproperty_no_banned_legacy_spellings` — banned-set rejection (separate assertion for cleaner failure messages).
3. `test_flags_buffering_bit_preserved` — literal `flags | 0x100` regression lock (Pitfall 7 — load-bearing for ALL Phase 84 work to have effect).

Failure messages must be grep-friendly with file path + line numbers + remediation hint (cite `84-RESEARCH §Pattern 4` and `MEMORY feedback_gstreamer_mock_blind_spot`).

---

### `tests/test_now_playing_panel.py` (+3 tests inside existing file)

**Analog:** existing tests in same file covering `set_underrun_count` / `set_buffer_percent` slot behavior + `_build_stats_widget` row presence. Locate via `grep -n "set_underrun_count\|set_buffer_percent\|_build_stats_widget\|Underruns" tests/test_now_playing_panel.py`.

**Apply to:** Three new tests added inline per RESEARCH §Test Map rows 13-15:

- `test_buffer_duration_row_present` — `_build_stats_widget` produces a row with label `"Buf duration"` and initial value `"30s"`.
- `test_set_buffer_duration_baseline_format` — `set_buffer_duration(30)` → label text `"30s"` (no `(adapted)` suffix).
- `test_set_buffer_duration_adapted_format` — `set_buffer_duration(60)` → `"60s (adapted)"`; `set_buffer_duration(120)` → `"120s (adapted)"`. Parametrize over both values.

All three use the existing test infrastructure (`qtbot` fixture, `FakePlayer` test double for any Player references).

---

### `tests/test_main_window_underrun.py` (+1 test inside existing file)

**Analog:** existing tests in same file covering the Player.underrun_count_changed → NowPlayingPanel wire (Phase 78 Commit A).

**Apply to:** ONE new integration test per RESEARCH §Test Map row 16:

- `test_buffer_duration_changed_updates_stats_row` — emit `player.buffer_duration_changed.emit(60)` → assert `now_playing._buffer_duration_label.text() == "60s (adapted)"`. End-to-end Signal wire verification.

Use `FakePlayer` from `tests/_fake_player.py` (the parity edit in this wave gives it the new `buffer_duration_changed` Signal).

---

### `.planning/phases/84-…/84-VERIFICATION.md` (NEW — closure record)

**Analog:** Phase 78 VERIFICATION.md at `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-VERIFICATION.md` — same shape: waived-gate language + monitor plan + follow-up trigger thresholds.

**Apply to:** Write per D-13 verbatim:

1. Waived-gate statement — Phase 78 D-06 `M < N AND median lower` gate explicitly waived under harvest-week reframe (12 events / 7 days = insufficient sample for marginal-effect detection).
2. Monitor plan — 2-week post-ship window comparing `~/.local/share/musicstreamer/buffer-events.log` against the harvest-week baseline documented in 84-CONTEXT.md `<data-summary>`.
3. Follow-up trigger thresholds — ≥3 long events (>1s) with `min_percent=0` in 2-week window, OR any `recovered` event >10s, OR ≥1 `cause_hint=network` event → open follow-up phase for reconnect-on-stall evaluation.
4. BUG-09 SC #3 closes on the Phase 84 ship commit; monitor window is forward-looking guidance, NOT a closure prerequisite.

---

## Shared Patterns

### Pattern S-1: Bound-method Signal.connect (no lambdas) — QA-05 carry-forward

**Source:** `musicstreamer/ui_qt/main_window.py:380-390` (project-wide convention)

**Apply to:** Every `.connect(...)` line in Phase 84 (one new line in `main_window.py` after line 390).

```python
self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)
```

NEVER use `lambda x: self.now_playing.set_buffer_duration(x)` — breaks Qt reference-counting and bypasses QA-05.

### Pattern S-2: DirectConnection (default) for main-thread → main-thread Signals; document the choice

**Source:** `musicstreamer/ui_qt/main_window.py:382-390` (Phase 78 Commit A precedent — comment block explicitly cites RESEARCH A3 + Pitfall 2)

**Apply to:** The new `buffer_duration_changed.connect(...)` line. Comment block MUST cite RESEARCH §Pattern 3 / Pitfall 2 and warn against harmonizing with the nearby QueuedConnection on `underrun_recovery_started`.

### Pattern S-3: Type-annotated instance-field init in `__init__` (Pitfall 3)

**Source:** `musicstreamer/player.py:498` (Phase 78 — `self._underrun_event_count: int = 0`)

**Apply to:** All three new D-11 state fields:

```python
self._growth_step: int = 0
self._current_buffer_duration_s: int = BUFFER_DURATION_S
self._pending_buffer_duration_s: int | None = None
```

Never rely on set-on-first-write semantics — explicit annotation prevents the "field exists only after first growth bump" footgun.

### Pattern S-4: `_MutedLabel` for theme-flip-safe stats rows (Phase 47.1 D-10)

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:176` (definition) + lines 2912, 2925, 2936-2937 (usage).

**Apply to:** Both new label widgets in `_build_stats_widget` row: `buffer_duration_row_label = _MutedLabel("Buf duration", wrapper)` and `self._buffer_duration_label = _MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)`.

### Pattern S-5: `int()` defensive coercion in Qt slot signatures

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:999, 1010` (existing `set_buffer_percent`, `set_underrun_count`)

**Apply to:** New `set_buffer_duration(self, seconds: int) -> None:` slot — `s = int(seconds)` first line. Mirrors precedent.

### Pattern S-6: Per-file helper duplication (NOT shared conftest extraction)

**Source:** `tests/test_player_underrun_count.py:16-18` ("PATTERNS.md §S-7 — codebase convention is per-file helper duplication, not shared conftest extraction")

**Apply to:** `tests/test_player_buffer_growth.py` — copy `make_player(qtbot)` and `_make_record(outcome="recovered")` verbatim from `tests/test_player_underrun_count.py:27-62` rather than extracting to `conftest.py`.

### Pattern S-7: Hard-code `_GST_SECOND = 1_000_000_000` in test files to avoid `import gi` (D-26 / QA-02)

**Source:** `tests/test_player_buffer.py:11-13`

**Apply to:** `tests/test_player_buffer_growth.py` — top-of-file constant `_GST_SECOND = 1_000_000_000`. Used in the URI-bind ordering assertion: `call("buffer-duration", 60 * _GST_SECOND)`.

### Pattern S-8: Grep-friendly source-grep gate failure messages (Phase 80 precedent)

**Source:** `tests/test_db_connect_is_sole_connection_factory.py:152-165` (failure-message structure: "Phase X / FEATURE / D-NN drift-guard FAIL: expected ... found ... Offending files and line numbers: ... Either ... or ...")

**Apply to:** All three test functions in `tests/test_playbin3_property_hygiene.py`. Each failure message must cite Phase 84 / D-11 / Pattern 4, the offending file + line numbers, the relevant allowlist/banned-set, and a remediation hint (e.g., "Add to `_ALLOWED_PIPELINE_PROPERTIES` in the same commit that introduces the callsite").

---

## No Analog Found

**All 11 new/modified files have direct in-repo analogs.** No files in this phase require fallback to RESEARCH.md-only patterns (no novel external library introductions, no new architectural patterns — Phase 84 is a deliberate copy-edit of Phase 78 Commit A's wiring patterns plus a Phase 80-style source-grep gate).

---

## Metadata

**Analog search scope:** `musicstreamer/`, `tests/`, `.planning/phases/78-*/`
**Files scanned (top-level reads):** 8
- `musicstreamer/constants.py` (existing values)
- `musicstreamer/player.py` (Signal block, __init__, cycle_close slot, _try_next_stream, _on_preroll_about_to_finish)
- `musicstreamer/ui_qt/main_window.py` (wire site)
- `musicstreamer/ui_qt/now_playing_panel.py` (slot + stats widget)
- `tests/_fake_player.py` (parity site)
- `tests/test_player_buffer.py` (constants assertion site)
- `tests/test_player_underrun_count.py` (test seam canonical mirror)
- `tests/test_db_connect_is_sole_connection_factory.py` (source-grep gate template)

**Pattern extraction date:** 2026-05-24

**Cross-phase canonical mirror:** Phase 78 Commit A is the structural mirror for D-12 (Signal + wire + slot + stats row). Phase 80 is the structural mirror for the new source-grep gate. Phase 62 D-04 is the structural mirror for per-URL reset. Phase 83 is the structural mirror for the second URI-bind apply site.
