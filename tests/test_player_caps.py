"""Phase 70 / Wave 0 RED stubs — Player caps-detection contract (T-06).

Tests cover:
  - test_caps_persists_rate_and_bit_depth (primary caps → signal emission)
  - test_caps_emitted_as_queued_signal (threading invariant per qt-glib-bus-threading.md Rule 2)
  - test_caps_disarm_after_emit (Pitfall 6 one-shot guard)
  - test_caps_ignores_unknown_format (bit_depth_from_format → 0 → early-return)
  - test_caps_ignores_zero_rate (rate 0 → no emit)
  - test_caps_no_double_emit_for_same_stream (Pitfall 6 idempotency)

ALL tests are intentionally RED until Plan 70-04 ships:
  - Player.audio_caps_detected = Signal(int, int, int)
  - Player._on_caps_negotiated(self, pad, _pspec) -> None
  - Player._caps_armed_for_stream_id: int

Phase 62-00 idiom: AttributeError IS the RED state; no pytest.fail() placeholders.

NOTE: Pitfall 4 / Phase 50 D-04 (DB write before UI refresh, main-thread ordering)
is covered by test_main_window.py::test_audio_caps_persists_before_ui_refresh
in Plan 70-05, NOT here. The handler is a pure emitter; slot-level repo.update_stream
call belongs to MainWindow.
"""
from __future__ import annotations

import inspect

from unittest.mock import MagicMock, patch

import pytest

from musicstreamer.player import Player


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Mirrors test_player_tag.py:28-38 pattern exactly (module-local copy for
    isolation — do NOT import from test_player_tag.py).
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


def _fake_caps_pad(rate: int, format_str: str) -> MagicMock:
    """Build a fake GStreamer pad whose get_current_caps() returns a structure
    with the given rate + format.

    Mirrors PATTERNS.md lines 982-996.
    """
    pad = MagicMock()
    structure = MagicMock()
    structure.get_int.return_value = (True, rate)
    structure.get_string.return_value = format_str
    caps = MagicMock()
    caps.get_size.return_value = 1
    caps.get_structure.return_value = structure
    pad.get_current_caps.return_value = caps
    return pad


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_caps_persists_rate_and_bit_depth(qtbot):
    """T-06: _on_caps_negotiated with valid pad (96 kHz / S24LE) emits
    audio_caps_detected(42, 96000, 24) when armed for stream_id=42."""
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42  # RED: AttributeError until Plan 70-04
    pad = _fake_caps_pad(96000, "S24LE")
    with qtbot.waitSignal(player.audio_caps_detected, timeout=1000) as blocker:  # RED: AttributeError
        player._on_caps_negotiated(pad, None)  # RED: AttributeError
    assert blocker.args == [42, 96000, 24]


def test_caps_emitted_as_queued_signal(qtbot):
    """Threading invariant (qt-glib-bus-threading.md Rule 2): audio_caps_detected
    must be a (int, int, int) Signal connected with QueuedConnection.

    Uses grep-style source introspection to assert the invariant at the source
    level — never counts comment lines (per plan critical-rules).
    """
    player = make_player(qtbot)
    import musicstreamer.player as player_module
    src = inspect.getsource(player_module)
    # Strip comment-only lines before checking (Nyquist hygiene — plan line 183)
    lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
    joined = "\n".join(lines)
    # RED: both identifiers absent until Plan 70-04 ships the Signal declaration
    # and QueuedConnection wiring.
    assert "audio_caps_detected" in joined
    assert "QueuedConnection" in joined


def test_caps_disarm_after_emit(qtbot):
    """Pitfall 6 one-shot guard: after _on_caps_negotiated emits,
    _caps_armed_for_stream_id is reset to 0 (per-URL idempotency)."""
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42  # RED: AttributeError until Plan 70-04
    pad = _fake_caps_pad(96000, "S24LE")
    with qtbot.waitSignal(player.audio_caps_detected, timeout=1000):  # RED: AttributeError
        player._on_caps_negotiated(pad, None)  # RED: AttributeError
    assert player._caps_armed_for_stream_id == 0  # RED: AttributeError


def test_caps_ignores_unknown_format(qtbot):
    """bit_depth_from_format("GIBBERISH") → 0 → early-return without emitting.

    Ensures the handler does NOT emit audio_caps_detected for unrecognized
    format strings (Pattern 1 lines 302-303).
    """
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42  # RED: AttributeError until Plan 70-04
    pad = _fake_caps_pad(96000, "GIBBERISH")
    with qtbot.assertNotEmitted(player.audio_caps_detected, wait=200):  # RED: AttributeError
        player._on_caps_negotiated(pad, None)  # RED: AttributeError


def test_caps_ignores_zero_rate(qtbot):
    """rate == 0 → handler returns WITHOUT emitting audio_caps_detected.

    Zero rate indicates no valid caps negotiation result.
    """
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42  # RED: AttributeError until Plan 70-04
    pad = _fake_caps_pad(0, "S24LE")
    with qtbot.assertNotEmitted(player.audio_caps_detected, wait=200):  # RED: AttributeError
        player._on_caps_negotiated(pad, None)  # RED: AttributeError


def test_caps_no_double_emit_for_same_stream(qtbot):
    """Pitfall 6: after first emit the guard disarms; calling handler again
    does NOT emit a second audio_caps_detected for the same stream_id."""
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42  # RED: AttributeError until Plan 70-04
    pad = _fake_caps_pad(96000, "S24LE")

    # First call — should emit once
    emission_count = []

    def _on_caps(*args):
        emission_count.append(args)

    player.audio_caps_detected.connect(_on_caps)  # RED: AttributeError

    player._on_caps_negotiated(pad, None)  # RED: AttributeError
    # After first emit, _caps_armed_for_stream_id == 0, so second call must not emit
    player._on_caps_negotiated(pad, None)  # RED: AttributeError

    # Process Qt events so any queued emissions are delivered
    qtbot.waitUntil(lambda: True, timeout=200)
    assert len(emission_count) == 1, (
        f"expected exactly 1 emission, got {len(emission_count)} "
        "(Pitfall 6 one-shot guard failure)"
    )


# ---------------------------------------------------------------------------
# Regression: playbin3 pad-extraction must not call get-audio-pad
# (legacy playbin 1.x action signal; absent on GstPlayBin3 — discovered
# via live UAT 2026-05-12)
# ---------------------------------------------------------------------------


def test_arm_caps_watch_uses_audio_sink_pad_not_get_audio_pad_signal(qtbot):
    """Phase 70 / UAT-fix: _arm_caps_watch_for_current_stream must NOT call
    `pipeline.emit("get-audio-pad", ...)`. That action signal exists on legacy
    `playbin` but is absent on `playbin3` (which the project uses since
    Phase 57 / WIN-03), raising `TypeError: unknown signal name: get-audio-pad`
    on live playback.

    The correct path is to read `pipeline.get_property("audio-sink")` and
    probe that element's static sink pad — works on both playbin and playbin3.
    """
    import inspect as _inspect
    from musicstreamer.player import Player
    src = _inspect.getsource(Player._arm_caps_watch_for_current_stream)
    # The legacy action signal MUST NOT appear in code (comments OK but
    # strip them before grep so a documentation reference doesn't fail).
    code_only = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert 'emit("get-audio-pad"' not in code_only, (
        "playbin3 has no get-audio-pad action signal — use "
        "pipeline.get_property('audio-sink').get_static_pad('sink') instead"
    )
    # Positive lock: the audio-sink property approach is present.
    assert 'get_property("audio-sink")' in code_only, (
        "expected pipeline.get_property('audio-sink') in pad extraction"
    )


def test_arm_caps_watch_survives_missing_audio_sink(qtbot):
    """Defensive: if pipeline.get_property('audio-sink') returns None (or
    raises), arming must not raise — UI falls back to D-03 cold-start defaults.
    """
    player = make_player(qtbot)
    # Force the path: audio-sink returns None
    player._pipeline.get_property = MagicMock(return_value=None)
    # Set up a current stream so the early-return on _current_stream is None
    # doesn't short-circuit before we exercise the audio-sink path.
    fake_stream = MagicMock()
    fake_stream.id = 7
    player._current_stream = fake_stream

    # Must not raise
    player._arm_caps_watch_for_current_stream()

    # Verify the get_audio_pad signal was NOT called
    assert not any(
        call.args == ("get-audio-pad", 0)
        for call in player._pipeline.emit.call_args_list
    ), "Player must not call pipeline.emit('get-audio-pad', ...) — that signal does not exist on playbin3"
