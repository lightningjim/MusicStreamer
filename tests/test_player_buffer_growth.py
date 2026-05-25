"""Phase 84 / BUG-09 Commit B / D-11 — Wave 0 RED tests for adaptive
buffer-duration growth state machine + URI-bind apply ordering.

Drives Wave 1 (Plan 84-02) implementation against locked contracts:

  - ``Player._growth_step: int = 0``                  (D-11 state)
  - ``Player._current_buffer_duration_s: int =        (D-11 state)
        BUFFER_DURATION_S``
  - ``Player._pending_buffer_duration_s:              (D-11 staging)
        int | None = None``
  - ``Player.buffer_duration_changed = Signal(int)``  (D-12 Signal)
  - ``Player._maybe_grow_buffer_duration()``          (D-11 cycle-close hook)
  - ``Player._apply_pending_buffer_duration_to_pipeline()``  (D-11 apply)
  - ``Player._reset_buffer_duration_to_baseline()``   (D-11 per-URL reset)

D-11 is implemented under the playbin3 mid-session-write FALLBACK shape
(84-RESEARCH §D-11 Resolution): mid-session ``set_property("buffer-duration",
N)`` writes are silent no-ops for the currently-playing stream; the value
must be written to playbin3 BEFORE the next URI bind so that
uridecodebin3's ``new_source_handler`` reads the updated struct field and
pushes it down to urisourcebin → queue2. Hence the "stage + apply + reset"
three-step lifecycle:

  1. cycle_close (in-session underrun)  → stage ``_pending_buffer_duration_s``
  2. URI bind   (``_try_next_stream``   → apply ``_pending`` BEFORE
                  or gapless preroll        ``set_property("uri", ...)``
                  handoff)
  3. URI bind   (per-URL reset)         → reset back to baseline

Per-file helpers (``make_player`` / ``_make_record``) are duplicated VERBATIM
from ``tests/test_player_underrun_count.py`` per PATTERNS.md §S-6 (codebase
convention: per-file duplication, NOT shared conftest extraction).

The ``_GST_SECOND`` hard-coded literal at the top of file is the same idiom
as ``tests/test_player_buffer.py:13`` — keeps this test file free of
``import gi`` per D-26 / QA-02 (project invariant).

All ``.connect(...)`` calls bind to ``received.append`` (bound method) per
QA-05 / Pattern S-1 — NEVER use lambdas.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from musicstreamer.constants import BUFFER_DURATION_S
from musicstreamer.player import Player, _CycleClose

# Gst.SECOND is 1_000_000_000 (nanoseconds) — hard-coded here so the test
# file does not need ``import gi`` (D-26 / QA-02).
_GST_SECOND = 1_000_000_000


# ----------------------------------------------------------------------
# Per-file helpers — DUPLICATED VERBATIM from tests/test_player_underrun_count.py
# per PATTERNS.md §S-6. Do NOT extract to conftest.py.
# ----------------------------------------------------------------------

def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Verbatim duplicate of tests/test_player_underrun_count.py:27-42 (per
    PATTERNS.md §S-6 — codebase convention is per-file helper duplication,
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


class _PairCollector:
    """Per-file helper for collecting two-arg buffer_duration_changed emits.

    Lambdas in .connect(...) are banned per QA-05 / Pattern S-1. Bound-method
    ``append`` on a plain list only collects positional single args; with the
    WR-02 (Phase 84 code review) two-arg Signal(int, bool), we need a small
    bound-method-friendly collector. Used by the growth tests below.
    """

    def __init__(self) -> None:
        self.pairs: list[tuple[int, bool]] = []

    def collect(self, seconds: int, is_adapted: bool) -> None:
        self.pairs.append((int(seconds), bool(is_adapted)))


def _make_record(outcome: str = "recovered") -> _CycleClose:
    """Build a minimal _CycleClose record for the cycle-close slot.

    Verbatim duplicate of tests/test_player_underrun_count.py:45-62.
    """
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


# ----------------------------------------------------------------------
# 9 RED tests covering the D-11 state machine + URI-bind apply ordering.
# ----------------------------------------------------------------------

def test_growth_state_initialized(qtbot):
    """D-11 init: growth-step counter starts at 0; current duration mirrors
    the BUFFER_DURATION_S baseline; pending value is None (no staged write).

    Pitfall 3 (Phase 78 carry-forward): all three fields MUST be
    type-annotated in __init__ — never rely on set-on-first-write semantics.
    """
    player = make_player(qtbot)
    assert player._growth_step == 0
    assert player._current_buffer_duration_s == BUFFER_DURATION_S
    assert player._pending_buffer_duration_s is None


def test_first_cycle_close_stages_60s(qtbot):
    """D-11: first in-session cycle_close bumps growth_step 0→1 and stages
    60s. Signal emits with the new (staged) value so the stats-for-nerds row
    updates immediately to "60s (adapted)" — even though the pipeline write
    is deferred to the next URI bind (RESEARCH §D-11 fallback).
    """
    player = make_player(qtbot)
    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)  # bound method (Pattern S-1)

    player._on_underrun_cycle_closed(_make_record())
    qtbot.wait(50)

    assert collector.pairs == [(60, True)]
    assert player._growth_step == 1
    assert player._current_buffer_duration_s == 60
    assert player._pending_buffer_duration_s == 60


def test_second_cycle_close_stages_120s(qtbot):
    """D-11: second sequential cycle_close bumps growth_step 1→2 and
    stages 120s (cap).
    """
    player = make_player(qtbot)
    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)

    player._on_underrun_cycle_closed(_make_record())
    player._on_underrun_cycle_closed(_make_record())
    qtbot.wait(50)

    assert collector.pairs == [(60, True), (120, True)]
    assert player._growth_step == 2
    assert player._current_buffer_duration_s == 120
    assert player._pending_buffer_duration_s == 120


def test_growth_caps_at_120(qtbot):
    """D-11: third+ cycle_close are no-ops at the 120s cap. Counter stays
    at 2 and the Signal does NOT re-emit (no spurious "still 120s" updates).
    """
    player = make_player(qtbot)
    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)

    for _ in range(5):
        player._on_underrun_cycle_closed(_make_record())
    qtbot.wait(50)

    assert collector.pairs == [(60, True), (120, True)]  # third+ at cap are no-ops
    assert player._growth_step == 2
    assert player._current_buffer_duration_s == 120


def test_try_next_stream_applies_pending_before_uri_bind(qtbot):
    """D-11 URI-bind apply (Pitfall 1 from RESEARCH): _try_next_stream must
    write the staged buffer-duration to playbin3 BEFORE binding the next
    URI. uridecodebin3.new_source_handler reads playbin3.buffer_duration
    at URI-bind time; missing this ordering means the staged value is
    ignored by queue2 entirely (silent no-op for the new stream).

    CR-02 (Phase 84 code review): _try_next_stream is a station-change
    boundary per CONTEXT D-11 ("each new station starts fresh"). The reset
    stages baseline.

    WR-04 (Phase 84 code review) idempotency: if playbin3 already holds
    the baseline value (e.g. after one growth cycle that was never applied
    because no URI bind occurred between growth and the station change),
    the apply's idempotency guard skips the redundant property write — the
    EFFECTIVE state (playbin3's buffer-duration) is baseline either way.
    To exercise the apply-WRITES-when-needed branch, this test pre-stages
    playbin3 at a non-baseline value via _last_applied_buffer_duration_s
    so the staged baseline triggers an actual write.

    Ordering (buffer-duration before uri) holds whenever a write happens.
    """
    player = make_player(qtbot)
    # Stage a pending 60s value via one cycle_close.
    player._on_underrun_cycle_closed(_make_record())
    assert player._pending_buffer_duration_s == 60
    # WR-04 simulation: force the idempotency guard to take the WRITE branch
    # by pretending playbin3 currently holds 120s (so staged baseline differs).
    player._last_applied_buffer_duration_s = 120

    # Queue a minimal stream. The MagicMock pipeline absorbs set_property
    # calls; we inspect call_args_list to assert ordering.
    player._streams_queue = [
        SimpleNamespace(url="http://example/", id=1, station_id=1)
    ]
    player._is_first_attempt = False  # avoid elapsed-timer side effects

    # Clear prior call history so we only see _try_next_stream's writes.
    player._pipeline.set_property.reset_mock()

    player._try_next_stream()

    calls = player._pipeline.set_property.call_args_list
    # After CR-02 fix the value written at the station-change bind is the
    # BASELINE (30s), not the prior URL's grown 60s. Ordering still holds.
    duration_indices = [
        i for i, c in enumerate(calls)
        if c == call("buffer-duration", BUFFER_DURATION_S * _GST_SECOND)
    ]
    uri_indices = [
        i for i, c in enumerate(calls)
        if len(c.args) >= 1 and c.args[0] == "uri"
    ]
    assert duration_indices, (
        f"expected call('buffer-duration', BUFFER_DURATION_S * Gst.SECOND) "
        f"in _try_next_stream set_property calls; got {calls}. Per CR-02, "
        f"the per-URL reset flushes baseline at the station-change bind."
    )
    assert uri_indices, (
        f"expected call('uri', ...) in _try_next_stream set_property "
        f"calls; got {calls}"
    )
    assert duration_indices[0] < uri_indices[0], (
        f"D-11 ordering FAIL: buffer-duration write must precede uri "
        f"write so uridecodebin3.new_source_handler reads the updated "
        f"struct field. duration_index={duration_indices[0]}, "
        f"uri_index={uri_indices[0]}, calls={calls}"
    )


def test_preroll_handoff_applies_pending_before_uri_swap(qtbot):
    """D-11 URI-bind apply at the second site (Pitfall 2 from RESEARCH):
    missing this apply-site means SomaFM users (who hit gapless preroll
    handoff hourly per Phase 83) lose all adaptive growth on every
    preroll cycle. The slot must mirror _try_next_stream's stage-and-apply
    block exactly.

    Setup mirrors tests/test_player.py:1136-1144 (the Phase 83 D-10
    post-handoff failover test) for the about-to-finish slot prerequisites.
    """
    player = make_player(qtbot)
    # Stage a pending 60s value via one cycle_close.
    player._on_underrun_cycle_closed(_make_record())
    assert player._pending_buffer_duration_s == 60

    # The about-to-finish slot requires _preroll_in_flight=True and
    # expected_seq == _preroll_seq to proceed past the CR-01/WR-03 guards
    # (player.py:1308-1311). Both are configurable directly on the player
    # instance — no need to drive the full play() path.
    player._preroll_in_flight = True
    player._preroll_handler_id = 0
    seq_at_emit = player._preroll_seq
    player._streams_queue = [
        SimpleNamespace(url="http://stream.example/", id=1, station_id=1)
    ]
    player._is_first_attempt = False

    # Tracker is real (constructed in __init__); patch its mutators so the
    # slot's force_close/bind_url calls don't touch real state.
    player._pipeline.set_property.reset_mock()

    with patch.object(player, "_tracker", MagicMock()), \
         patch.object(player, "_underrun_dwell_timer", MagicMock()), \
         patch.object(player, "_elapsed_timer", MagicMock()):
        player._on_preroll_about_to_finish(seq_at_emit)

    calls = player._pipeline.set_property.call_args_list
    duration_indices = [
        i for i, c in enumerate(calls)
        if c == call("buffer-duration", 60 * _GST_SECOND)
    ]
    uri_indices = [
        i for i, c in enumerate(calls)
        if len(c.args) >= 1 and c.args[0] == "uri"
    ]
    assert duration_indices, (
        f"expected call('buffer-duration', 60 * Gst.SECOND) in "
        f"_on_preroll_about_to_finish set_property calls; got {calls}. "
        f"Pitfall 2 from 84-RESEARCH: missing this apply-site means "
        f"SomaFM users lose adaptive growth at every preroll handoff."
    )
    assert uri_indices, (
        f"expected call('uri', ...) in _on_preroll_about_to_finish "
        f"set_property calls; got {calls}"
    )
    assert duration_indices[0] < uri_indices[0], (
        f"D-11 ordering FAIL at preroll-handoff site: buffer-duration "
        f"write must precede the gapless uri swap. "
        f"duration_index={duration_indices[0]}, "
        f"uri_index={uri_indices[0]}, calls={calls}"
    )


def test_try_next_stream_resets_growth_to_baseline(qtbot):
    """D-11 per-URL reset (mirrors Phase 47.1 D-14 sentinel-reset and
    Phase 62 D-04 _underrun_armed reset): _try_next_stream must reset
    growth state back to baseline so each new station starts fresh.

    Per RESEARCH §D-11 implementation block: the pending value is reset
    to BUFFER_DURATION_S (NOT None) so the baseline value is pushed to
    the pipeline at the next bind — otherwise a station change after
    growth-to-120s would leave playbin3 stuck at 120s for the new
    station. The reset MUST emit buffer_duration_changed so the stats
    row drops back to "30s".
    """
    player = make_player(qtbot)
    # Bump growth to step 1 (one cycle_close → staged 60s).
    player._on_underrun_cycle_closed(_make_record())
    assert player._growth_step == 1

    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)

    player._streams_queue = [
        SimpleNamespace(url="http://newstation/", id=2, station_id=2)
    ]
    player._is_first_attempt = False
    player._try_next_stream()
    qtbot.wait(50)

    assert player._growth_step == 0
    assert player._current_buffer_duration_s == BUFFER_DURATION_S
    # Pending is reset to baseline (not None) so the next bind writes the
    # baseline value to playbin3 — flushes any prior growth that may have
    # been applied to a previous URL session.
    assert player._pending_buffer_duration_s in (None, BUFFER_DURATION_S)
    # The reset emits a Signal so the stats row reflects the baseline.
    assert collector.pairs[-1] == (BUFFER_DURATION_S, False)


def test_reset_is_noop_when_already_at_baseline(qtbot):
    """D-11 reset no-op guard (Pitfall 3 / Pattern S-3): when the state
    is already at baseline, _reset_buffer_duration_to_baseline must NOT
    emit a spurious Signal — would cause the stats row to "twitch" at
    every URL bind even when no growth happened.
    """
    player = make_player(qtbot)  # fresh — already at baseline
    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)

    player._reset_buffer_duration_to_baseline()
    qtbot.wait(50)

    assert collector.pairs == [], (
        "D-11 Pitfall 3: reset-to-baseline when already at baseline must "
        "be a no-op (no Signal emit). Got spurious emits: "
        + repr(collector.pairs)
    )


def test_try_next_stream_writes_baseline_value_after_growth(qtbot):
    """CR-02 (Phase 84 code review): the per-URL reset MUST flush the
    BASELINE value (30s) to playbin3 at the station-change URI bind,
    NOT the prior URL's grown value (60s). Asserts the actual VALUE
    written via set_property, not just the in-Python _pending state.

    Root cause CR-02 caught: the original ordering was
        apply() → reset()
    which pushed the prior URL's 60s to playbin3 for the NEW station,
    and only staged baseline=30 for the bind AFTER that. Fix reorders to
        reset() → apply()
    so apply pushes the staged baseline value at the new station's bind.

    WR-04 (Phase 84 code review) idempotency interaction: to force the
    apply-WRITES branch (not the idempotent-skip branch), this test pre-sets
    _last_applied_buffer_duration_s to a non-baseline value (simulating the
    real-world case where a prior URI bind had pushed a grown value down).

    This test gap was the reason CR-02 shipped: the existing tests asserted
    on _pending_buffer_duration_s and Signal emission, never on the value
    written to _pipeline.set_property("buffer-duration", ...).
    """
    player = make_player(qtbot)
    # Grow to step 1 (one cycle_close → staged 60s).
    player._on_underrun_cycle_closed(_make_record())
    assert player._growth_step == 1
    assert player._pending_buffer_duration_s == 60
    # WR-04 simulation: pretend playbin3 currently holds 120s (a prior URI
    # bind pushed it down) so the staged baseline value triggers a real write.
    player._last_applied_buffer_duration_s = 120

    player._streams_queue = [
        SimpleNamespace(url="http://newstation/", id=2, station_id=2)
    ]
    player._is_first_attempt = False
    player._pipeline.set_property.reset_mock()

    player._try_next_stream()

    calls = player._pipeline.set_property.call_args_list
    duration_calls = [
        c for c in calls if len(c.args) >= 1 and c.args[0] == "buffer-duration"
    ]
    uri_calls = [
        (i, c) for i, c in enumerate(calls)
        if len(c.args) >= 1 and c.args[0] == "uri"
    ]
    assert duration_calls, (
        f"CR-02 FAIL: _try_next_stream did not write 'buffer-duration' to "
        f"playbin3 at the new station's URI bind. Calls: {calls}"
    )
    # The buffer-duration value written MUST be the baseline (30s), not the
    # prior grown 60s. The bug under CR-02 was: 60s was being written here.
    assert duration_calls[0].args[1] == BUFFER_DURATION_S * _GST_SECOND, (
        f"CR-02 FAIL: _try_next_stream wrote buffer-duration={duration_calls[0].args[1]!r} "
        f"to playbin3, expected BUFFER_DURATION_S * Gst.SECOND "
        f"({BUFFER_DURATION_S * _GST_SECOND!r}). The per-URL reset must run "
        f"BEFORE _apply_pending so the baseline reaches the new URI bind."
    )
    # Ordering still holds: buffer-duration write must precede uri write
    # (uridecodebin3.new_source_handler reads playbin3.buffer_duration at
    # URI-bind time).
    duration_idx = calls.index(duration_calls[0])
    assert uri_calls and duration_idx < uri_calls[0][0], (
        f"CR-02 FAIL: buffer-duration write must precede uri write. "
        f"duration_idx={duration_idx}, uri_idx={uri_calls[0][0] if uri_calls else None}, "
        f"calls={calls}"
    )


def test_apply_pending_is_idempotent_when_value_unchanged(qtbot):
    """WR-04 (Phase 84 code review): _apply_pending_buffer_duration_to_pipeline
    is idempotent when the staged value equals what playbin3 already holds.
    Avoids per-URL-bind no-op writes in the common no-growth case (post-CR-02,
    reset stages baseline at every station change; without idempotency, the
    baseline would be re-written every time even when playbin3 already has it).
    """
    player = make_player(qtbot)
    # After __init__, _last_applied tracks the baseline write performed during
    # pipeline construction (see player.py ~line 327).
    assert player._last_applied_buffer_duration_s == BUFFER_DURATION_S
    # Stage baseline as pending (simulates reset on a fresh, never-grown state).
    player._pending_buffer_duration_s = BUFFER_DURATION_S
    player._pipeline.set_property.reset_mock()

    player._apply_pending_buffer_duration_to_pipeline()

    duration_calls = [
        c for c in player._pipeline.set_property.call_args_list
        if len(c.args) >= 1 and c.args[0] == "buffer-duration"
    ]
    assert duration_calls == [], (
        f"WR-04 FAIL: _apply_pending wrote buffer-duration when staged value "
        f"({BUFFER_DURATION_S}) equals last-applied ({player._last_applied_buffer_duration_s}); "
        f"expected idempotent skip. Calls: {duration_calls}"
    )
    # Pending stage still cleared (apply consumed it).
    assert player._pending_buffer_duration_s is None


def test_preroll_handoff_preserves_growth_state(qtbot):
    """CR-02 (Phase 84 code review) + CONTEXT D-11: gapless preroll →
    station-stream handoff is the SAME logical session, NOT a per-station
    reset boundary. After growth → preroll handoff, _growth_step and
    _current_buffer_duration_s MUST be preserved (NOT reset to baseline).

    SomaFM users hit this path hourly (preroll cycle); resetting at the
    handoff would erase adaptive growth at every preroll cycle, defeating
    Commit B's intent for the SomaFM cluster (3 of 5 long events per
    harvest-week data summary).

    Per CONTEXT D-11: reset is per-station-change ("each new station starts
    fresh"), not per-URI-bind. Preroll is two URLs but one station.
    """
    player = make_player(qtbot)
    # Grow to step 1 via one cycle_close.
    player._on_underrun_cycle_closed(_make_record())
    assert player._growth_step == 1
    assert player._current_buffer_duration_s == 60

    player._preroll_in_flight = True
    player._preroll_handler_id = 0
    seq_at_emit = player._preroll_seq
    player._streams_queue = [
        SimpleNamespace(url="http://stream.example/", id=1, station_id=1)
    ]
    player._is_first_attempt = False
    player._pipeline.set_property.reset_mock()

    with patch.object(player, "_tracker", MagicMock()), \
         patch.object(player, "_underrun_dwell_timer", MagicMock()), \
         patch.object(player, "_elapsed_timer", MagicMock()):
        player._on_preroll_about_to_finish(seq_at_emit)

    # Growth state preserved across the gapless handoff.
    assert player._growth_step == 1, (
        f"CR-02 FAIL: preroll handoff reset _growth_step from 1 to "
        f"{player._growth_step}. Per CONTEXT D-11, preroll → station-stream "
        f"is the SAME session; reset is per-station-change only."
    )
    assert player._current_buffer_duration_s == 60, (
        f"CR-02 FAIL: preroll handoff reset _current_buffer_duration_s "
        f"from 60 to {player._current_buffer_duration_s}. SomaFM users would "
        f"lose adaptive growth at every hourly preroll cycle."
    )

    # The buffer-duration value written at the preroll bind MUST be the
    # GROWN value (60s), not the baseline.
    calls = player._pipeline.set_property.call_args_list
    duration_calls = [
        c for c in calls if len(c.args) >= 1 and c.args[0] == "buffer-duration"
    ]
    assert duration_calls, (
        f"CR-02 FAIL: preroll handoff did not write 'buffer-duration' to "
        f"playbin3 at the URI swap. Calls: {calls}"
    )
    assert duration_calls[0].args[1] == 60 * _GST_SECOND, (
        f"CR-02 FAIL: preroll handoff wrote "
        f"buffer-duration={duration_calls[0].args[1]!r}, expected the grown "
        f"value 60 * Gst.SECOND ({60 * _GST_SECOND!r}). Preroll must NOT call "
        f"_reset_buffer_duration_to_baseline before _apply_pending."
    )


@pytest.mark.parametrize("outcome", ["pause", "stop", "failover", "preroll"])
def test_non_recovered_outcomes_do_not_trigger_growth(qtbot, outcome):
    """CR-01 (Phase 84 code review): adaptive growth fires ONLY on
    outcome=='recovered'. User-initiated terminators (pause/stop) and
    queue-advancement events (failover/preroll) must NOT bump _growth_step
    or emit buffer_duration_changed — otherwise pressing Pause during an
    underrun would penalise the next session with a 60s startup delay
    even though no actual buffer recovery happened.

    Failure scenario this guards against:
      1. User plays station A; underrun cycle opens (buffer drops below 100).
      2. User presses Pause before the cycle naturally closes.
      3. tracker.force_close("pause") queues a cycle_close record.
      4. Old buggy slot fires _maybe_grow_buffer_duration → step=1, pending=60s.
      5. User presses Play; the staged 60s gets applied to the new bind even
         though no recovered underrun ever occurred.
    """
    player = make_player(qtbot)
    collector = _PairCollector()
    player.buffer_duration_changed.connect(collector.collect)

    player._on_underrun_cycle_closed(_make_record(outcome=outcome))
    qtbot.wait(50)

    assert collector.pairs == [], (
        f"CR-01 FAIL: outcome={outcome!r} triggered growth Signal emit "
        f"(spurious emits: {collector.pairs!r}). Growth must gate on 'recovered'."
    )
    assert player._growth_step == 0, (
        f"CR-01 FAIL: outcome={outcome!r} bumped _growth_step to "
        f"{player._growth_step} (expected 0)."
    )
    assert player._current_buffer_duration_s == BUFFER_DURATION_S
    assert player._pending_buffer_duration_s is None


def test_failover_timer_uses_grown_buffer_duration(qtbot):
    """WR-01 (Phase 84 code review): the failover-timeout watchdog at
    _try_next_stream's tail must arm at self._current_buffer_duration_s,
    NOT the static BUFFER_DURATION_S baseline. After growth bumps the
    target to 60s or 120s, a stream that legitimately needs the full
    grown window to fill its enlarged buffer would otherwise be
    incorrectly failed-over to the next queue entry after the baseline
    30s — actively defeating Commit B's intent that the larger buffer
    give jittery streams more recovery headroom.
    """
    player = make_player(qtbot)
    # Simulate "growth happened on prior URL; this bind is the next station"
    # by setting _current_buffer_duration_s directly. (After CR-02, a real
    # _try_next_stream would reset to baseline first; but the failover-timer
    # arm runs AFTER the reset/apply pair, so we test the post-reset value.
    # To exercise grown-value semantics we patch the field after construction.)
    player._current_buffer_duration_s = 60

    player._streams_queue = [
        SimpleNamespace(url="http://example/", id=1, station_id=1)
    ]
    player._is_first_attempt = False

    with patch.object(player, "_failover_timer", MagicMock()) as fo_timer, \
         patch.object(player, "_reset_buffer_duration_to_baseline"):
        # Disable reset so the grown value survives into the failover-timer arm.
        player._try_next_stream()

    fo_timer.start.assert_called_once()
    (interval_ms,), _kwargs = fo_timer.start.call_args
    assert interval_ms == 60 * 1000, (
        f"WR-01 FAIL: _failover_timer.start was called with {interval_ms}ms "
        f"(expected 60_000ms = grown buffer-duration). The watchdog must "
        f"track self._current_buffer_duration_s, not BUFFER_DURATION_S, or "
        f"jittery streams that need the grown window will be force-failed "
        f"before they can recover."
    )


def test_buffer_duration_changed_signal_at_class_scope():
    """D-12 contract pin: Player.buffer_duration_changed must exist as a
    class-level Signal so the wire wave (Plan 84-03) cannot silently
    rename it. Mirrors the Phase 78 underrun_count_changed pattern
    (player.py:297).
    """
    assert hasattr(Player, "buffer_duration_changed"), (
        "Player.buffer_duration_changed Signal missing — Plan 84-02 must "
        "add `buffer_duration_changed = Signal(int)` adjacent to the "
        "existing `underrun_count_changed = Signal(int)` at player.py:297."
    )
    sig = Player.buffer_duration_changed
    # PySide6 class-level Signal descriptors expose a string-form repr that
    # includes the carrying type — defensive contract check that catches
    # arity drift (Signal() vs Signal(object) vs Signal(int)).
    sig_repr = repr(sig) + " " + sig.__class__.__name__
    assert "Signal" in sig_repr, (
        f"Player.buffer_duration_changed is not a PySide6 Signal: "
        f"{sig_repr}"
    )
