"""Tests for Player.set_volume() — clamping and GStreamer property set.

Phase 35 port: uses pytest-qt ``qtbot`` to anchor Qt object creation on
the main thread. No GTK / GLib imports.
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
    # Replace the cached pipeline with a fresh mock so tests can assert
    # directly on set_property without init-time noise.
    player._pipeline = MagicMock()
    return player


def test_set_volume_normal(qtbot):
    """set_volume(0.8) sets pipeline volume to 0.8."""
    p = make_player(qtbot)
    p.set_volume(0.8)
    p._pipeline.set_property.assert_called_with("volume", 0.8)


def test_set_volume_clamps_high(qtbot):
    """set_volume(1.5) clamps to 1.0."""
    p = make_player(qtbot)
    p.set_volume(1.5)
    p._pipeline.set_property.assert_called_with("volume", 1.0)


def test_set_volume_clamps_low(qtbot):
    """set_volume(-0.5) clamps to 0.0."""
    p = make_player(qtbot)
    p.set_volume(-0.5)
    p._pipeline.set_property.assert_called_with("volume", 0.0)


def test_set_volume_stores_for_mpv(qtbot):
    """After set_volume(0.6), _volume attribute equals 0.6."""
    p = make_player(qtbot)
    p.set_volume(0.6)
    assert p._volume == 0.6
