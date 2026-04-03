"""Tests for Player buffer property configuration."""
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.player import Player


def make_player():
    """Create a Player with GStreamer pipeline mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    return player


def test_buffer_duration_constant():
    assert BUFFER_DURATION_S == 5


def test_buffer_size_constant():
    assert BUFFER_SIZE_BYTES == 5 * 1024 * 1024


def test_init_sets_buffer_duration():
    p = make_player()
    calls = {c[0][0]: c[0][1] for c in p._pipeline.set_property.call_args_list}
    assert calls["buffer-duration"] == BUFFER_DURATION_S * Gst.SECOND


def test_init_sets_buffer_size():
    p = make_player()
    calls = {c[0][0]: c[0][1] for c in p._pipeline.set_property.call_args_list}
    assert calls["buffer-size"] == BUFFER_SIZE_BYTES
