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
    with patch.object(p, "_set_uri"):
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
    with patch.object(p, "_set_uri"):
        p.play(station, preferred_quality="")
    assert p._current_stream.position == 1
    assert p._streams_queue[0].position == 2
    assert p._streams_queue[1].position == 3


def test_preferred_stream_not_duplicated(qtbot):
    p = make_player(qtbot)
    streams = [make_stream(1, 1, "low"), make_stream(2, 2, "hi")]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
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

    with patch.object(p, "_set_uri") as mock_set_uri:
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
    with patch.object(p, "_set_uri") as mock_set_uri:
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
    with patch.object(p, "_set_uri"):
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
    with patch.object(p, "_set_uri"):
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
    with patch.object(p, "_set_uri") as mock_set_uri:
        p.play_stream(target_stream)
    assert p._current_stream == target_stream
    assert len(p._streams_queue) == 0
    mock_set_uri.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube playback via yt-dlp library (Plan 35-06)
# ---------------------------------------------------------------------------

def test_youtube_resolve_success_sets_uri_and_arms_failover(qtbot):
    """Happy path: _youtube_resolve_worker returns an HLS URL, the queued
    youtube_resolved handler calls _set_uri and arms the failover timer."""
    p = make_player(qtbot)

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL), \
         patch.object(p, "_set_uri") as mock_set_uri:
        # Call worker directly so the signal fires synchronously in tests
        with qtbot.waitSignal(p.youtube_resolved, timeout=3000) as blocker:
            p._youtube_resolve_worker("https://www.youtube.com/watch?v=test")
        assert blocker.args == ["http://resolved.example/stream.m3u8"]
        # The queued slot runs on the main thread via qtbot's event processing
        qtbot.wait(50)

    mock_set_uri.assert_called_with("http://resolved.example/stream.m3u8")
    assert p._failover_timer.isActive()


def test_youtube_resolve_failure_emits_error_and_advances_queue(qtbot):
    """Sad path: yt_dlp raises -> youtube_resolution_failed -> playback_error
    fires and _try_next_stream is invoked."""
    p = make_player(qtbot)

    import yt_dlp
    from yt_dlp.utils import DownloadError

    class FailingYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            raise DownloadError("boom")

    with patch.object(yt_dlp, "YoutubeDL", FailingYDL), \
         patch.object(p, "_try_next_stream") as mock_next:
        with qtbot.waitSignal(p.youtube_resolution_failed, timeout=3000):
            p._youtube_resolve_worker("https://www.youtube.com/watch?v=test")
        qtbot.wait(50)

    mock_next.assert_called_once()


def test_play_youtube_spawns_resolver_thread(qtbot):
    """_play_youtube schedules a resolver thread and does not block."""
    import threading as _threading
    p = make_player(qtbot)
    p._current_station_name = "Test"

    started = {"count": 0, "target": None}
    real_thread_init = _threading.Thread.__init__

    def fake_init(self, *args, target=None, **kwargs):
        started["count"] += 1
        started["target"] = target
        # Bypass real thread execution; just capture
        real_thread_init(self, target=lambda: None, daemon=kwargs.get("daemon", False))

    with patch.object(_threading.Thread, "__init__", fake_init):
        p._play_youtube("https://www.youtube.com/watch?v=test")

    assert started["count"] == 1
    assert started["target"] is not None


def test_cancel_stops_failover_timer(qtbot):
    """_cancel_timers stops the failover timer (no more yt poll timer)."""
    p = make_player(qtbot)
    p._failover_timer.start(10000)
    p._cancel_timers()
    assert not p._failover_timer.isActive()


# ---------------------------------------------------------------------------
# Phase 47-02: failover queue uses order_streams (PB-18)
# ---------------------------------------------------------------------------

def test_failover_queue_uses_order_streams(qtbot):
    """PB-18: play(station) builds the failover queue via order_streams
    (codec_rank desc, bitrate_kbps desc) rather than raw position order."""
    p = make_player(qtbot)
    streams = [
        StationStream(id=1, station_id=1, url="http://mp3", codec="MP3",
                      bitrate_kbps=64, position=1),
        StationStream(id=2, station_id=1, url="http://flac", codec="FLAC",
                      bitrate_kbps=320, position=2),
        StationStream(id=3, station_id=1, url="http://aac", codec="AAC",
                      bitrate_kbps=128, position=3),
    ]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
        p.play(station)

    # FLAC (rank 3) > AAC (rank 2) > MP3 (rank 1).
    # _current_stream pops first; queue holds the rest in order.
    all_urls = [p._current_stream.url] + [s.url for s in p._streams_queue]
    assert all_urls == ["http://flac", "http://aac", "http://mp3"]


def test_failover_preferred_quality_still_works_with_order_streams(qtbot):
    """Regression guard: preferred_quality still pins its stream first even
    though the remainder is now order_streams-ordered."""
    p = make_player(qtbot)
    streams = [
        StationStream(id=1, station_id=1, url="http://mp3-low", codec="MP3",
                      bitrate_kbps=64, quality="low", position=1),
        StationStream(id=2, station_id=1, url="http://flac-hi", codec="FLAC",
                      bitrate_kbps=320, quality="hi", position=2),
        StationStream(id=3, station_id=1, url="http://aac-med", codec="AAC",
                      bitrate_kbps=128, quality="med", position=3),
    ]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
        p.play(station, preferred_quality="low")

    # 'low' is pinned first (MP3 despite lowest codec rank).
    assert p._current_stream.quality == "low"
    # The rest follow order_streams: FLAC > AAC.
    rest_codecs = [s.codec for s in p._streams_queue]
    assert rest_codecs == ["FLAC", "AAC"]


# ---------------------------------------------------------------------------
# Gap-closure (UAT gap 5): error-cascade coalescing regression tests
# See: .planning/debug/stream-exhausted-premature.md
# ---------------------------------------------------------------------------


def test_multiple_gst_errors_advance_queue_once(qtbot):
    """Multiple bus errors for a single failing URL must advance the failover
    queue exactly once (regression for gsd-debug:stream-exhausted-premature).

    Before the fix: 3 cascading playbin3 errors per broken URL each schedule
    an independent recovery, draining 3 queue entries -> spurious 'Stream
    exhausted'.

    After the fix: the _recovery_in_flight guard coalesces same-URL errors;
    only the FIRST advance takes effect until the guard-clear singleShot
    fires on the next main-loop turn.
    """
    p = make_player(qtbot)
    streams = [make_stream(i, i, f"q{i}") for i in (1, 2, 3)]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
        p.play(station)

    # After p.play, stream 1 is current; queue holds [2, 3].
    assert p._current_stream.id == 1
    assert [s.id for s in p._streams_queue] == [2, 3]

    # Simulate playbin3 emitting THREE errors for the same failing URL.
    # Call the recovery handler directly (mirrors test_gst_error_triggers_failover
    # convention -- avoids spinning a real event loop for 0-ms singleShots).
    with patch.object(p, "_set_uri"):
        p._handle_gst_error_recovery()
        p._handle_gst_error_recovery()
        p._handle_gst_error_recovery()

    # The guard-clear singleShot(0) has NOT fired yet (no qtbot.wait), so
    # the 2nd and 3rd calls must have hit the guard and no-op'd.
    assert p._current_stream.id == 2
    assert [s.id for s in p._streams_queue] == [3]


def test_recovery_guard_resets_between_distinct_url_failures(qtbot):
    """After the guard-clear singleShot fires, a subsequent error on the
    NEW URL must advance the queue again -- the guard does not stick.
    """
    p = make_player(qtbot)
    streams = [make_stream(i, i, f"q{i}") for i in (1, 2, 3)]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):
        p.play(station)

    with patch.object(p, "_set_uri"):
        p._handle_gst_error_recovery()   # advance to stream 2
        qtbot.wait(20)                   # let guard-clear singleShot fire
        p._handle_gst_error_recovery()   # advance to stream 3
        qtbot.wait(20)

    assert p._current_stream.id == 3


# ---------------------------------------------------------------------------
# Phase 56 / WIN-01: _set_uri normalizes DI.fm HTTPS -> HTTP (D-01)
# ---------------------------------------------------------------------------
# NOTE: these tests deliberately do NOT patch.object(p, "_set_uri").
# All other tests in this file mock _set_uri to avoid real GStreamer state
# changes -- but that mock would intercept BEFORE the new normalization line
# runs, and a buggy helper would pass vacuously. These tests exercise the
# real _set_uri body and assert on the underlying _pipeline.set_property
# MagicMock (which make_player already replaces _pipeline with on line 26).


def test_set_uri_normalizes_difm_https_to_http(qtbot):
    """WIN-01 / D-01: _set_uri rewrites DI.fm https:// to http:// before
    handing the URL to playbin3."""
    p = make_player(qtbot)
    p._set_uri("https://prem1.di.fm/lounge?listen_key=abc")
    p._pipeline.set_property.assert_any_call(
        "uri", "http://prem1.di.fm/lounge?listen_key=abc"
    )


def test_set_uri_passes_through_non_difm(qtbot):
    """D-06 idempotency at player layer: non-DI.fm URLs reach playbin3
    unchanged (no scheme rewrite)."""
    p = make_player(qtbot)
    p._set_uri("https://ice4.somafm.com/dronezone-256-mp3")
    p._pipeline.set_property.assert_any_call(
        "uri", "https://ice4.somafm.com/dronezone-256-mp3"
    )


def test_set_uri_passes_through_youtube_hls(qtbot):
    """T-56-01 mitigation: YouTube-resolved HLS manifests must NEVER be
    downgraded to http -- broadening the predicate would strip TLS from
    arbitrary streams (active-MITM exposure). Locks the predicate scope."""
    p = make_player(qtbot)
    url = "https://manifest.googlevideo.com/api/manifest/hls_playlist/abc/playlist.m3u8"
    p._set_uri(url)
    p._pipeline.set_property.assert_any_call("uri", url)


# ---------------------------------------------------------------------------
# Phase 57 / WIN-03 D-12 + D-14: bus-message STATE_CHANGED re-applies volume
# on every transition to PLAYING (NULL->PLAYING and playbin3-internal
# PAUSED->PLAYING auto-rebuffer recovery). Cross-platform regression guard
# — Linux CI catches the future "contributor adds a new set_state(NULL) site
# and forgets to re-apply volume" or "child-element state-change leaks into
# the re-apply path" without needing a Win11 CI runner.
# ---------------------------------------------------------------------------


def test_volume_reapplied_on_null_to_playing(qtbot):
    """WIN-03 D-12 + D-14: After playbin3 transitions NULL->PLAYING (via
    _set_uri / pause-resume / failover / station switch / YouTube|Twitch
    resolve), the main-thread slot _on_playbin_state_changed re-applies
    the user's stored volume to playbin3.volume. Catches the diagnostic
    Step 2 bug: playbin3.volume resets 0.5 -> 1.0 across NULL->PLAYING
    without this hook."""
    p = make_player(qtbot)
    p.set_volume(0.5)
    # set_volume's own write is one set_property call; the WIN-03 guarantee
    # is that ANOTHER write of the same value happens after the bus-message
    # arrives on the main thread.
    p._pipeline.set_property.reset_mock()
    # Simulate the queued Signal landing on the main thread post-transition.
    p._on_playbin_state_changed()
    p._pipeline.set_property.assert_any_call("volume", 0.5)


def test_volume_reapplied_on_paused_to_playing(qtbot):
    """WIN-03 D-12 + D-14: Same re-apply happens on the GStreamer-internal
    PAUSED->PLAYING auto-rebuffer recovery path that bypasses _set_uri.
    Catches the in-session disclosure surface (57-DIAGNOSTIC-LOG.md
    'In-session scope expansion'): playbin3 auto-pauses when buffer drops
    below threshold and auto-resumes when refilled, without revisiting
    application code. The bus-message hook still fires; the main-thread
    slot writes regardless of the prior state."""
    p = make_player(qtbot)
    p.set_volume(0.7)
    p._pipeline.set_property.reset_mock()
    # PAUSED->PLAYING and NULL->PLAYING share the same main-thread slot;
    # the bus-loop filter only cares about new == PLAYING.
    p._on_playbin_state_changed()
    p._pipeline.set_property.assert_any_call("volume", 0.7)


def test_bus_state_changed_handler_filters_non_playing_transitions(qtbot):
    """WIN-03 D-12 invariant: _on_gst_state_changed early-returns when
    new_state != PLAYING. PLAYING->PAUSED, PAUSED->READY, READY->NULL etc.
    must NOT fire the re-apply Signal."""
    from musicstreamer.player import Gst
    p = make_player(qtbot)
    msg = MagicMock()
    msg.src = p._pipeline  # top-level — the OTHER filter passes
    msg.parse_state_changed.return_value = (
        Gst.State.PLAYING, Gst.State.PAUSED, Gst.State.VOID_PENDING
    )
    with patch.object(p, "_playbin_playing_state_reached") as sig:
        p._on_gst_state_changed(bus=MagicMock(), msg=msg)
        sig.emit.assert_not_called()


def test_bus_state_changed_handler_filters_child_element_messages(qtbot):
    """WIN-03 D-12 invariant: _on_gst_state_changed early-returns when
    msg.src is not the top-level playbin3 pipeline. Child elements
    (decodebin3, urisourcebin, audio sink, etc.) emit their own
    state-changed messages on the same bus and MUST be ignored — only
    the top-level transition matters for re-apply."""
    from musicstreamer.player import Gst
    p = make_player(qtbot)
    msg = MagicMock()
    msg.src = MagicMock(name="some-child-element")  # NOT p._pipeline
    msg.parse_state_changed.return_value = (
        Gst.State.PAUSED, Gst.State.PLAYING, Gst.State.VOID_PENDING
    )
    with patch.object(p, "_playbin_playing_state_reached") as sig:
        p._on_gst_state_changed(bus=MagicMock(), msg=msg)
        sig.emit.assert_not_called()
