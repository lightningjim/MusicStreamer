"""Tests for Player buffer property configuration.

Phase 35 port: uses pytest-qt ``qtbot`` instead of GTK / GLib imports.
The real GStreamer pipeline factory is mocked so buffer property calls
land on a MagicMock we can inspect directly.
"""
from unittest.mock import MagicMock, patch

from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES

# Gst.SECOND is 1_000_000_000 (nanoseconds) — hard-coded here so the test
# file does not need ``import gi`` (D-26 / QA-02).
_GST_SECOND = 1_000_000_000


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
    return player


def test_buffer_duration_constant():
    assert BUFFER_DURATION_S == 10


def test_buffer_size_constant():
    assert BUFFER_SIZE_BYTES == 10 * 1024 * 1024


def test_init_sets_buffer_duration(qtbot):
    p = make_player(qtbot)
    calls = {
        c[0][0]: c[0][1] for c in p._pipeline.set_property.call_args_list
    }
    assert calls["buffer-duration"] == BUFFER_DURATION_S * _GST_SECOND


def test_init_sets_buffer_size(qtbot):
    p = make_player(qtbot)
    calls = {
        c[0][0]: c[0][1] for c in p._pipeline.set_property.call_args_list
    }
    assert calls["buffer-size"] == BUFFER_SIZE_BYTES
