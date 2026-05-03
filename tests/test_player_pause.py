"""Tests for Player.pause() — pipeline state and timer handling.

Plan 35-06: all subprocess-related pause paths are gone. pause() now
only cancels timers, clears the failover queue, and sets the pipeline
to NULL. No more mpv / yt_proc termination.
"""
from unittest.mock import MagicMock, patch


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    # Swap in a clean pipeline mock for assertions.
    player._pipeline = MagicMock()
    return player


def test_pause_sets_pipeline_null(qtbot):
    """pause() sets pipeline state to NULL.

    Phase 57 / WIN-03 D-15: pause() now arms the volume fade-down ramp;
    set_state(NULL) is called inside the final tick of _on_pause_volume_ramp_tick.
    We drive all ticks synchronously to verify the contract that pause()
    eventually transitions to NULL."""
    from musicstreamer.player import Player
    p = make_player(qtbot)
    p._pipeline.get_property.return_value = 1.0
    p.pause()
    # Drain all ramp ticks synchronously (QTimer wait would be flaky).
    for _ in range(Player._PAUSE_VOLUME_RAMP_TICKS):
        p._on_pause_volume_ramp_tick()
    p._pipeline.set_state.assert_called()
    # The last set_state should have been with the NULL enum.
    from musicstreamer.player import Gst
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)


def test_pause_stops_failover_timer(qtbot):
    """pause() cancels the failover timer (no legacy _on_title state)."""
    p = make_player(qtbot)
    p._failover_timer.start(5000)
    p.pause()
    assert not p._failover_timer.isActive()


def test_pause_clears_streams_queue(qtbot):
    """pause() clears the failover streams queue (D-04)."""
    p = make_player(qtbot)
    from musicstreamer.models import StationStream
    p._streams_queue = [
        StationStream(id=1, station_id=1, url="http://a/", quality="hi", position=1),
        StationStream(id=2, station_id=2, url="http://b/", quality="med", position=2),
    ]
    p.pause()
    assert p._streams_queue == []


def test_stop_after_pause(qtbot):
    """stop() works identically whether called from playing or paused."""
    p = make_player(qtbot)
    p.pause()
    p.stop()
    from musicstreamer.player import Gst
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)


def test_pause_does_not_error_when_stopped(qtbot):
    """Calling pause() when nothing is playing does not raise."""
    p = make_player(qtbot)
    p.pause()  # should not raise


# ---------------------------------------------------------------------------
# Phase 57 / WIN-03 D-15: pause-volume fade-down ramp structural guard
# ---------------------------------------------------------------------------
# Perceptual no-pop verification is the Plan 57-05 Win11 VM UAT scope; this
# block locks the structural invariants that the ramp wrapper exists, targets
# 0 volume, and does NOT mutate self._volume (so Plan 57-03's bus-message
# re-apply lands at the user's slider position post-resume).


def test_pause_starts_volume_ramp(qtbot):
    """WIN-03 D-15: pause() arms the new pause-volume ramp timer.

    Locks the structural invariant: pause() body calls _start_pause_volume_ramp,
    which seeds the ramp state and starts the QTimer. The actual fade is not
    observable in unit tests (QTimer ticks would require qtbot.wait or an
    event-loop spin); we only assert that the ramp was armed."""
    p = make_player(qtbot)
    # Make get_property return a real float so _start_pause_volume_ramp's
    # try/except float() succeeds.
    p._pipeline.get_property.return_value = 0.5
    p.pause()
    assert p._pause_volume_ramp_timer.isActive()
    assert p._pause_volume_ramp_state is not None


def test_pause_volume_ramp_state_targets_zero(qtbot):
    """WIN-03 D-15: ramp state targets 0 (silence) and starts from the live
    playbin3.volume readback. Locks the fade-DOWN direction and the
    reverse-from-current behavior (D-05 mirror of Phase 52 EQ ramp)."""
    p = make_player(qtbot)
    p.set_volume(0.5)
    # Mock playbin3.volume readback: pretend it's currently at 0.5.
    p._pipeline.get_property.return_value = 0.5
    p.pause()
    assert p._pause_volume_ramp_state["target_volume"] == 0.0
    assert p._pause_volume_ramp_state["start_volume"] == 0.5
    assert p._pause_volume_ramp_state["tick_index"] == 0


def test_pause_does_not_modify_self_volume(qtbot):
    """WIN-03 D-15 + D-13: the ramp writes to playbin3.volume only — never
    to self._volume. This is the composition contract with Plan 57-03's
    bus-message re-apply: post-resume, the bus-message handler reads
    self._volume to write the user's slider position back to playbin3.

    Drives all _PAUSE_VOLUME_RAMP_TICKS ticks synchronously (no QTimer
    wait) by directly invoking _on_pause_volume_ramp_tick — mirrors the
    Phase 52 EQ ramp test pattern."""
    from musicstreamer.player import Player
    p = make_player(qtbot)
    p.set_volume(0.5)
    p._pipeline.get_property.return_value = 0.5
    p.pause()
    # Simulate the QTimer firing _PAUSE_VOLUME_RAMP_TICKS times.
    for _ in range(Player._PAUSE_VOLUME_RAMP_TICKS):
        p._on_pause_volume_ramp_tick()
    # self._volume is the cached slider position; ramp NEVER mutates it.
    assert p._volume == 0.5
    # State cleared on final tick (mirror Phase 52 EQ ramp completion).
    assert p._pause_volume_ramp_state is None
    # Final tick is what calls set_state(NULL) — preserves the existing
    # test_pause_sets_pipeline_null contract.
    from musicstreamer.player import Gst
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)
