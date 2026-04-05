"""Tests for Player.pause() — pipeline state, yt_proc, and on_title handling."""
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer.player import Player


def make_player():
    """Create a Player with GStreamer pipeline mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    return player


def test_pause_sets_pipeline_null():
    """pause() sets pipeline state to Gst.State.NULL."""
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = MagicMock()
    p.pause()
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)


def test_pause_clears_on_title():
    """pause() sets _on_title to None (stops ICY tag delivery)."""
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = MagicMock()
    p.pause()
    assert p._on_title is None


def test_pause_kills_yt_proc():
    """pause() terminates a running _yt_proc."""
    p = make_player()
    p._pipeline = MagicMock()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process is running
    p._yt_proc = mock_proc
    p.pause()
    mock_proc.terminate.assert_called_once()


def test_stop_after_pause():
    """stop() works identically whether called from playing or paused state."""
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = MagicMock()
    # Simulate paused state
    p.pause()
    assert p._on_title is None
    # Now call stop — should also set NULL and clear on_title
    p._on_title = MagicMock()
    p.stop()
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)
    assert p._on_title is None


def test_pause_does_not_error_when_stopped():
    """Calling pause() when nothing is playing does not raise."""
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = None
    p._yt_proc = None
    # Should not raise
    p.pause()
