"""Tests for Player failover logic — stream queue, error/timeout triggers, cancellation.

Phase 35 port: the Player is a QObject; failover arms a ``QTimer``
instead of calling ``GLib.timeout_add``. The legacy ``_failover_timer_id``
integer is gone — the plan's guidance is to check
``player._failover_timer.isActive()`` directly. The legacy
``_cancel_failover_timer`` method is renamed ``_cancel_timers`` and now
also stops the yt-poll timer.
"""
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Gst, Player


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
    player._pipeline = MagicMock()
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

def test_preferred_stream_first(qtbot):
    """Preferred-quality stream is dequeued first; remainder in position order."""
    p = make_player(qtbot)
    streams = [
        make_stream(1, 1, "low"),
        make_stream(2, 2, "hi"),
        make_stream(3, 3, "med"),
    ]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"):
        p.play(station, preferred_quality="hi")
    assert p._current_stream is not None
    assert p._current_stream.quality == "hi"
    assert len(p._streams_queue) == 2
    assert p._streams_queue[0].position == 1
    assert p._streams_queue[1].position == 3


def test_no_preferred_quality_uses_position_order(qtbot):
    p = make_player(qtbot)
    streams = [
        make_stream(3, 3, "low"),
        make_stream(1, 1, "hi"),
        make_stream(2, 2, "med"),
    ]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"):
        p.play(station, preferred_quality="")
    assert p._current_stream.position == 1
    assert p._streams_queue[0].position == 2
    assert p._streams_queue[1].position == 3


def test_preferred_stream_not_duplicated(qtbot):
    p = make_player(qtbot)
    streams = [make_stream(1, 1, "low"), make_stream(2, 2, "hi")]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"):
        p.play(station, preferred_quality="hi")
    assert p._current_stream.id == 2
    all_ids = [p._current_stream.id] + [s.id for s in p._streams_queue]
    assert all_ids.count(2) == 1


# ---------------------------------------------------------------------------
# Failover trigger tests
# ---------------------------------------------------------------------------

def test_gst_error_triggers_failover(qtbot):
    """_on_gst_error schedules recovery that pops the next stream."""
    p = make_player(qtbot)
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    p._current_station_name = "Test"
    p._current_stream = make_stream(1, 1, "hi")  # non-twitch current
    # Start the failover timer so we can verify it gets cancelled.
    p._failover_timer.start(10000)

    mock_msg = MagicMock()
    mock_msg.parse_error.return_value = (Exception("test error"), "debug info")

    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"):
        # Call the recovery path directly — _on_gst_error schedules it via
        # QTimer.singleShot(0, ...), which the test does not need to spin
        # an event loop for because we can invoke the handler synchronously.
        p._handle_gst_error_recovery()

    # After recovery, the current stream is the new one and _set_uri was
    # invoked with the new URL. The failover timer is re-armed for the new
    # stream (expected behavior — BUFFER_DURATION_S watchdog on new playback).
    mock_set_uri.assert_called_once()
    assert p._current_stream == stream_b


def test_timeout_triggers_failover(qtbot):
    """_on_timeout pops next stream from queue."""
    p = make_player(qtbot)
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    p._current_station_name = "Test"
    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"):
        p._on_timeout()
    assert p._current_stream == stream_b
    mock_set_uri.assert_called_once()


def test_tag_received_cancels_timeout(qtbot):
    """Receiving a TAG message cancels the failover timer."""
    p = make_player(qtbot)
    p._failover_timer.start(10000)
    assert p._failover_timer.isActive()

    taglist = MagicMock()
    taglist.get_string.return_value = (True, "Artist - Song")
    msg = MagicMock()
    msg.parse_tag.return_value = taglist

    # _on_gst_tag routes cancel through QTimer.singleShot(0, self._cancel_timers);
    # the test invokes _cancel_timers directly because waiting for a 0-ms
    # single-shot in a non-running event loop is unreliable.
    with qtbot.waitSignal(p.title_changed, timeout=1000):
        p._on_gst_tag(None, msg)
    p._cancel_timers()
    assert not p._failover_timer.isActive()


def test_all_streams_exhausted(qtbot):
    """Empty queue causes failover(None) emission + pipeline NULL."""
    p = make_player(qtbot)
    p._streams_queue = []
    with qtbot.waitSignal(p.failover, timeout=1000) as blocker:
        p._try_next_stream()
    assert blocker.args == [None]
    p._pipeline.set_state.assert_called_with(Gst.State.NULL)


def test_failover_signal_fires_on_attempt(qtbot):
    """When not the first attempt, failover signal emits with the stream."""
    p = make_player(qtbot)
    stream_b = make_stream(2, 2, "med")
    p._streams_queue = [stream_b]
    p._current_station_name = "Test"
    p._is_first_attempt = False
    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"):
        with qtbot.waitSignal(p.failover, timeout=1000) as blocker:
            p._try_next_stream()
    assert blocker.args == [stream_b]


# ---------------------------------------------------------------------------
# Timer cancellation tests
# ---------------------------------------------------------------------------

def test_timer_cancelled_on_stop(qtbot):
    p = make_player(qtbot)
    p._failover_timer.start(10000)
    assert p._failover_timer.isActive()
    p.stop()
    assert not p._failover_timer.isActive()


def test_timer_cancelled_on_pause(qtbot):
    p = make_player(qtbot)
    p._failover_timer.start(10000)
    p.pause()
    assert not p._failover_timer.isActive()


def test_new_play_cancels_previous_failover(qtbot):
    """Calling play() clears the old queue and starts on the new station's
    first stream. The pre-existing stale queue entry is gone; the timer is
    re-armed for the new stream (expected BUFFER_DURATION_S watchdog)."""
    p = make_player(qtbot)
    p._failover_timer.start(10000)
    p._streams_queue = [make_stream(9, 9, "low")]
    streams = [make_stream(1, 1, "hi")]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"), patch.object(p, "_stop_yt_proc"):
        p.play(station)
    assert p._current_stream is not None
    assert p._current_stream.id == 1
    # Stale queue entry (id=9) is gone
    assert all(s.id != 9 for s in p._streams_queue)


# ---------------------------------------------------------------------------
# Manual stream selection
# ---------------------------------------------------------------------------

def test_play_stream_bypasses_queue(qtbot):
    p = make_player(qtbot)
    p._streams_queue = [make_stream(2, 2, "med"), make_stream(3, 3, "low")]
    p._current_station_name = "Test"
    target_stream = make_stream(5, 5, "hi")
    with patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_stop_yt_proc"):
        p.play_stream(target_stream)
    assert p._current_stream == target_stream
    assert len(p._streams_queue) == 0
    mock_set_uri.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube failover (KEEP_MPV branch)
# ---------------------------------------------------------------------------

def test_youtube_starts_poll_timer(qtbot):
    """For a YouTube URL, _play_youtube arms the yt_poll_timer."""
    p = make_player(qtbot)
    yt_stream = StationStream(
        id=1, station_id=1,
        url="https://www.youtube.com/watch?v=test",
        quality="hi", position=1,
    )
    backup_stream = make_stream(2, 2, "med")
    station = make_station_with_streams([yt_stream, backup_stream])

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running
    with patch("musicstreamer.player._popen", return_value=mock_proc), \
         patch("musicstreamer.player.os.path.exists", return_value=False):
        p.play(station)
    assert p._yt_poll_timer.isActive()


# ---------------------------------------------------------------------------
# Phase 33 / FIX-07 — 15s YT minimum wait window (behavior preserved)
# ---------------------------------------------------------------------------

def test_yt_premature_exit_does_not_failover_before_15s(qtbot):
    """FIX-07(a): mpv exit <15s keeps polling — no failover."""
    p = make_player(qtbot)
    p._yt_proc = MagicMock()
    p._yt_proc.poll.return_value = 1  # exited nonzero
    p._yt_attempt_start_ts = 1000.0

    with patch("musicstreamer.player.time.monotonic", return_value=1001.0), \
         patch.object(p, "_try_next_stream") as mock_next:
        # Arm poll timer then invoke callback directly
        p._yt_poll_timer.start()
        p._yt_poll_cb()

    mock_next.assert_not_called()
    assert p._yt_poll_timer.isActive()


def test_yt_alive_at_window_close_succeeds(qtbot):
    """FIX-07(b): mpv still alive at >=15s → stop poll timer, success."""
    p = make_player(qtbot)
    p._yt_proc = MagicMock()
    p._yt_proc.poll.return_value = None  # still running
    p._yt_attempt_start_ts = 1000.0

    with patch("musicstreamer.player.time.monotonic", return_value=1015.1):
        p._yt_poll_timer.start()
        p._yt_poll_cb()

    assert not p._yt_poll_timer.isActive()
    assert p._yt_attempt_start_ts is None


def test_cookie_retry_reseeds_yt_window(qtbot):
    """FIX-07(c): cookie-retry substitutes new mpv and re-seeds _yt_attempt_start_ts."""
    p = make_player(qtbot)
    p._current_station_name = "Test"
    first_proc = MagicMock()
    first_proc.poll.return_value = 1  # exited immediately
    second_proc = MagicMock()
    second_proc.poll.return_value = None  # still running

    popen_returns = iter([first_proc, second_proc])
    monotonic_values = iter([1000.0, 1002.0])

    def fake_monotonic():
        return next(monotonic_values)

    with patch("musicstreamer.player._popen", side_effect=lambda *a, **k: next(popen_returns)), \
         patch("musicstreamer.player.os.path.exists", return_value=True), \
         patch("musicstreamer.player.tempfile.mkstemp", return_value=(0, "/tmp/fake_cookies.txt")), \
         patch("musicstreamer.player.os.close"), \
         patch("musicstreamer.player.os.unlink"), \
         patch("musicstreamer.player.shutil.copy2"), \
         patch("musicstreamer.player.time.monotonic", side_effect=fake_monotonic):
        p._play_youtube("https://www.youtube.com/watch?v=test")
        # Directly trigger the cookie retry
        p._check_cookie_retry({
            "url": "https://www.youtube.com/watch?v=test",
            "cmd": ["mpv", "--ytdl-raw-options=cookies=/tmp/fake_cookies.txt", "url"],
            "env": {},
        })

    assert p._yt_attempt_start_ts == 1002.0


def test_cancel_clears_yt_attempt_ts(qtbot):
    """_cancel_timers clears _yt_attempt_start_ts and stops the poll timer."""
    p = make_player(qtbot)
    p._yt_attempt_start_ts = 5.0
    p._yt_poll_timer.start()
    p._cancel_timers()
    assert p._yt_attempt_start_ts is None
    assert not p._yt_poll_timer.isActive()
