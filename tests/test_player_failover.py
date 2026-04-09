"""Tests for Player failover logic — stream queue, error/timeout triggers, cancellation."""
from unittest.mock import MagicMock, patch, call
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer.player import Player
from musicstreamer.models import Station, StationStream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player():
    """Create a Player with GStreamer pipeline mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    return player


def make_stream(id_, position, quality, url="http://stream.test/"):
    return StationStream(
        id=id_,
        station_id=1,
        url=f"{url}{id_}",
        quality=quality,
        position=position,
    )


def make_station_with_streams(streams):
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=streams,
    )


# ---------------------------------------------------------------------------
# Queue construction tests
# ---------------------------------------------------------------------------

def test_preferred_stream_first():
    """Given streams [pos1/low, pos2/hi, pos3/med] and preferred_quality='hi',
    the first stream attempted should be pos2/hi."""
    p = make_player()
    p._pipeline = MagicMock()
    streams = [
        make_stream(1, 1, "low"),
        make_stream(2, 2, "hi"),
        make_stream(3, 3, "med"),
    ]
    station = make_station_with_streams(streams)
    on_title = MagicMock()

    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play(station, on_title, preferred_quality="hi")

    # After calling play(), the first stream popped must be hi (id=2)
    assert p._current_stream is not None
    assert p._current_stream.quality == "hi"
    # Remaining queue should have 2 entries (pos1/low and pos3/med), NOT including hi again
    assert len(p._streams_queue) == 2
    # They should be in position order: pos1 then pos3
    assert p._streams_queue[0].position == 1
    assert p._streams_queue[1].position == 3


def test_no_preferred_quality_uses_position_order():
    """When no preferred_quality, streams are tried in position order."""
    p = make_player()
    p._pipeline = MagicMock()
    streams = [
        make_stream(3, 3, "low"),
        make_stream(1, 1, "hi"),
        make_stream(2, 2, "med"),
    ]
    station = make_station_with_streams(streams)
    on_title = MagicMock()

    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play(station, on_title, preferred_quality="")

    # First stream should be position 1
    assert p._current_stream is not None
    assert p._current_stream.position == 1
    # Remaining queue: positions 2 and 3
    assert p._streams_queue[0].position == 2
    assert p._streams_queue[1].position == 3


def test_preferred_stream_not_duplicated():
    """The preferred stream appears exactly once in the queue — not in both preferred slot
    and its natural position."""
    p = make_player()
    p._pipeline = MagicMock()
    streams = [
        make_stream(1, 1, "low"),
        make_stream(2, 2, "hi"),
    ]
    station = make_station_with_streams(streams)
    on_title = MagicMock()

    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play(station, on_title, preferred_quality="hi")

    # Current stream = hi (id=2), queue = [low (id=1)]
    assert p._current_stream.id == 2
    all_ids = [p._current_stream.id] + [s.id for s in p._streams_queue]
    # hi stream should appear exactly once
    assert all_ids.count(2) == 1


# ---------------------------------------------------------------------------
# Failover trigger tests
# ---------------------------------------------------------------------------

def test_gst_error_triggers_failover():
    """Calling _on_gst_error pops next stream from queue and plays it."""
    p = make_player()
    p._pipeline = MagicMock()
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    p._failover_timer_id = 42
    p._on_failover = MagicMock()
    p._current_station_name = "Test"
    p._on_title = MagicMock()

    mock_msg = MagicMock()
    mock_msg.parse_error.return_value = (Exception("test error"), "debug info")

    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        mock_glib.source_remove = MagicMock()
        p._on_gst_error(None, mock_msg)

    # Timer should have been cancelled
    mock_glib.source_remove.assert_called_with(42)
    # _set_uri called with stream_b's url
    mock_set_uri.assert_called_once()
    assert p._current_stream == stream_b


def test_timeout_triggers_failover():
    """When _on_timeout_cb fires (simulating 10s with no audio), it triggers _try_next_stream."""
    p = make_player()
    p._pipeline = MagicMock()
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    p._failover_timer_id = 55
    p._on_failover = None
    p._current_station_name = "Test"
    p._on_title = MagicMock()

    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 77
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        result = p._on_timeout_cb()

    # Must return False so GLib does not repeat the callback
    assert result is False
    # Stream popped and played
    assert p._current_stream == stream_b
    mock_set_uri.assert_called_once()


def test_tag_received_cancels_timeout():
    """Calling _on_gst_tag (ICY metadata received) cancels the failover timer."""
    p = make_player()
    p._pipeline = MagicMock()
    p._failover_timer_id = 33
    p._on_title = MagicMock()

    mock_msg = MagicMock()
    mock_taglist = MagicMock()
    mock_taglist.get_string.return_value = (True, "Artist - Song")
    mock_msg.parse_tag.return_value = mock_taglist

    with patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        mock_glib.source_remove = MagicMock()
        p._on_gst_tag(None, mock_msg)

    mock_glib.source_remove.assert_called_with(33)
    assert p._failover_timer_id is None


def test_all_streams_exhausted():
    """When _streams_queue is empty and _try_next_stream is called, on_failover is called
    with None and pipeline is set to NULL."""
    p = make_player()
    p._pipeline = MagicMock()
    p._streams_queue = []
    on_failover = MagicMock()
    p._on_failover = on_failover

    with patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p._try_next_stream()

    # Pipeline set to NULL
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)
    # on_failover called with None
    on_failover.assert_called_once_with(None)


def test_failover_callback_called_on_attempt():
    """When failover occurs (not first play, not exhaustion), on_failover is called with
    the failed stream info."""
    p = make_player()
    p._pipeline = MagicMock()
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    on_failover = MagicMock()
    p._on_failover = on_failover
    p._current_station_name = "Test"
    p._on_title = MagicMock()
    p._is_first_attempt = False  # Not first — this is a failover

    with patch.object(p, "_set_uri"), \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p._try_next_stream()

    # on_failover called with the stream that just failed (stream_b being tried as failover)
    on_failover.assert_called_once_with(stream_b)


# ---------------------------------------------------------------------------
# Timer cancellation tests
# ---------------------------------------------------------------------------

def test_timer_cancelled_on_stop():
    """stop() cancels any pending failover timer."""
    p = make_player()
    p._pipeline = MagicMock()
    p._failover_timer_id = 11

    with patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        p.stop()

    mock_glib.source_remove.assert_called_with(11)
    assert p._failover_timer_id is None


def test_timer_cancelled_on_pause():
    """pause() cancels any pending failover timer."""
    p = make_player()
    p._pipeline = MagicMock()
    p._failover_timer_id = 22

    with patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        p.pause()

    mock_glib.source_remove.assert_called_with(22)
    assert p._failover_timer_id is None


def test_new_play_cancels_previous_failover():
    """Calling play() while failover is in progress clears _streams_queue and cancels timer."""
    p = make_player()
    p._pipeline = MagicMock()
    p._failover_timer_id = 77
    p._streams_queue = [make_stream(9, 9, "low")]
    streams = [make_stream(1, 1, "hi")]
    station = make_station_with_streams(streams)
    on_title = MagicMock()

    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        mock_glib.timeout_add.return_value = 88
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play(station, on_title)

    # Old timer cancelled at start of play()
    mock_glib.source_remove.assert_any_call(77)
    # Queue rebuilt from new station (old stale stream gone)
    assert p._current_stream is not None
    assert p._current_stream.id == 1


# ---------------------------------------------------------------------------
# Manual stream selection
# ---------------------------------------------------------------------------

def test_play_stream_bypasses_queue():
    """Calling play_stream(stream) clears the queue and plays that specific stream."""
    p = make_player()
    p._pipeline = MagicMock()
    # Pre-populate queue with other streams
    p._streams_queue = [make_stream(2, 2, "med"), make_stream(3, 3, "low")]
    p._on_title = MagicMock()
    p._current_station_name = "Test"

    target_stream = make_stream(5, 5, "hi")

    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play_stream(target_stream, p._on_title)

    # Queue cleared (only target was in it, now consumed)
    assert p._current_stream == target_stream
    assert len(p._streams_queue) == 0
    mock_set_uri.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube failover
# ---------------------------------------------------------------------------

def test_youtube_failover_polling():
    """For YouTube streams, failover is detected via GLib.timeout_add polling of
    _yt_proc.poll() rather than GStreamer bus error."""
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = MagicMock()

    # Simulate a YouTube stream and a second stream to failover to
    yt_stream = StationStream(id=1, station_id=1, url="https://www.youtube.com/watch?v=test",
                              quality="hi", position=1)
    backup_stream = make_stream(2, 2, "med")
    station = make_station_with_streams([yt_stream, backup_stream])

    mock_yt_proc = MagicMock()
    # Simulate mpv exiting with error (non-zero)
    mock_yt_proc.poll.return_value = 1

    yt_poll_callbacks = []

    def capture_timeout(ms, cb):
        yt_poll_callbacks.append(cb)
        return 100 + len(yt_poll_callbacks)

    with patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.subprocess.Popen", return_value=mock_yt_proc), \
         patch("musicstreamer.player.time") as mock_time, \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.side_effect = capture_timeout
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        mock_glib.source_remove = MagicMock()
        mock_time.sleep = MagicMock()  # don't actually sleep
        p.play(station, p._on_title)

    # A poll timer should have been registered
    assert len(yt_poll_callbacks) >= 1
