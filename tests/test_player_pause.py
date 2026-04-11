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
