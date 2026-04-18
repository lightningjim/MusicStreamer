"""Tests for GStreamer BUFFERING bus handling in Player (Phase 47.1 D-12/D-14)."""
from unittest.mock import MagicMock, patch

from musicstreamer.models import StationStream
from musicstreamer.player import Player


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


def _fake_buffering_msg(percent, as_tuple=False):
    """Build a fake Gst.Message-like object whose parse_buffering() returns
    either a bare int (PyGObject flattened form) or a 1-tuple (formal binding).
    """
    msg = MagicMock()
    msg.parse_buffering.return_value = (percent,) if as_tuple else percent
    return msg


def test_on_gst_buffering_emits_signal(qtbot):
    """A BUFFERING message with percent=42 causes buffer_percent.emit(42)."""
    player = make_player(qtbot)
    msg = _fake_buffering_msg(42)
    with qtbot.waitSignal(player.buffer_percent, timeout=1000) as blocker:
        player._on_gst_buffering(bus=None, msg=msg)
    assert blocker.args == [42]


def test_on_gst_buffering_handles_tuple_return(qtbot):
    """Defensive Pitfall 1: tuple return from parse_buffering is unpacked."""
    player = make_player(qtbot)
    msg = _fake_buffering_msg(75, as_tuple=True)
    with qtbot.waitSignal(player.buffer_percent, timeout=1000) as blocker:
        player._on_gst_buffering(bus=None, msg=msg)
    assert blocker.args == [75]


def test_on_gst_buffering_dedups_unchanged(qtbot):
    """Repeated identical percents only emit once (D-14 de-dup)."""
    player = make_player(qtbot)
    # First emission fires (sentinel is -1)
    with qtbot.waitSignal(player.buffer_percent, timeout=1000):
        player._on_gst_buffering(None, _fake_buffering_msg(50))
    # Second emission at same percent is a no-op
    with qtbot.assertNotEmitted(player.buffer_percent, wait=200):
        player._on_gst_buffering(None, _fake_buffering_msg(50))


def test_dedup_resets_on_new_stream(qtbot):
    """_try_next_stream resets _last_buffer_percent so new URLs always emit
    their first buffer message (D-14 reset, Pitfall 3)."""
    player = make_player(qtbot)
    # Seed the sentinel as if a previous stream ended at 50%
    player._last_buffer_percent = 50
    # Queue a minimal fake stream and advance
    fake_stream = StationStream(
        id=1,
        station_id=1,
        url="http://example.test/stream",
        codec="MP3",
        quality="hi",
        label="test",
        position=0,
        bitrate_kbps=128,
    )
    player._streams_queue = [fake_stream]
    player._is_first_attempt = False  # avoid starting elapsed timer in test
    # _try_next_stream touches the pipeline; the MagicMock pipeline absorbs it
    player._try_next_stream()
    # Sentinel must be reset so another 50% would re-emit
    assert player._last_buffer_percent == -1
