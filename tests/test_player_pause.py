"""Tests for Player.pause() — pipeline state, yt_proc, and timer handling.

Phase 35 port: the pre-rewrite ``_on_title`` callback attribute is gone
(replaced by the ``title_changed`` Qt Signal and a legacy shim attribute
``_on_title_cb``). ``pause()`` now calls ``_cancel_timers()`` and routes
subprocess termination through ``_stop_yt_proc``. No GTK / GLib imports.
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
    """pause() sets pipeline state to NULL."""
    p = make_player(qtbot)
    p.pause()
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


def test_pause_kills_yt_proc(qtbot):
    """pause() terminates a running _yt_proc."""
    p = make_player(qtbot)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process is running
    p._yt_proc = mock_proc
    p.pause()
    mock_proc.terminate.assert_called_once()


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
    p._yt_proc = None
    p.pause()  # should not raise
