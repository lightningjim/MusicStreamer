"""Tests for Twitch playback via streamlink — URL detection, resolution, offline/error handling."""
from unittest.mock import MagicMock, patch, call
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer.player import Player
from musicstreamer.models import Station, StationStream


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_player_failover.py)
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


def make_twitch_stream(channel="testchannel"):
    return StationStream(
        id=1,
        station_id=1,
        url=f"https://www.twitch.tv/{channel}",
        quality="best",
        position=1,
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
# URL detection tests
# ---------------------------------------------------------------------------

def test_twitch_url_detected():
    """Given a stream with url containing 'twitch.tv', _try_next_stream calls _play_twitch
    (not _set_uri, not _play_youtube)."""
    p = make_player()
    p._pipeline = MagicMock()
    twitch_stream = make_twitch_stream()
    p._streams_queue = [twitch_stream]
    p._current_station_name = "Test Twitch"
    p._on_title = MagicMock()

    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_play_youtube") as mock_play_youtube, \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p._try_next_stream()

    mock_play_twitch.assert_called_once_with(twitch_stream.url)
    mock_set_uri.assert_not_called()
    mock_play_youtube.assert_not_called()


def test_non_twitch_url_not_routed():
    """Given a stream with url 'http://example.com/stream', _play_twitch is NOT called."""
    p = make_player()
    p._pipeline = MagicMock()
    regular_stream = make_stream(1, 1, "hi", url="http://example.com/stream/")
    p._streams_queue = [regular_stream]
    p._current_station_name = "Test Regular"
    p._on_title = MagicMock()

    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_set_uri"), \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p._try_next_stream()

    mock_play_twitch.assert_not_called()


# ---------------------------------------------------------------------------
# streamlink subprocess tests
# ---------------------------------------------------------------------------

def test_streamlink_called_with_correct_args():
    """_play_twitch calls subprocess.run with args ["streamlink", "--stream-url", url, "best"],
    capture_output=True, text=True."""
    p = make_player()
    p._pipeline = MagicMock()
    url = "https://www.twitch.tv/testchannel"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.m3u8\n"

    mock_thread = MagicMock()

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result) as mock_run, \
         patch("musicstreamer.player.threading.Thread") as mock_thread_cls, \
         patch("musicstreamer.player.GLib"):
        # Intercept the thread and run its target directly
        captured_target = []
        def capture_thread(**kwargs):
            captured_target.append(kwargs.get("target"))
            t = MagicMock()
            t.start = lambda: captured_target[0]() if captured_target else None
            return t
        mock_thread_cls.side_effect = capture_thread
        p._play_twitch(url)

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["streamlink", "--stream-url", url, "best"]
    assert call_args[1].get("capture_output") is True
    assert call_args[1].get("text") is True


def test_streamlink_env_includes_local_bin():
    """The env dict passed to subprocess.run has ~/.local/bin in PATH."""
    import os
    p = make_player()
    p._pipeline = MagicMock()
    url = "https://www.twitch.tv/testchannel"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.m3u8\n"

    local_bin = os.path.expanduser("~/.local/bin")

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result) as mock_run, \
         patch("musicstreamer.player.threading.Thread") as mock_thread_cls, \
         patch("musicstreamer.player.GLib"):
        captured_target = []
        def capture_thread(**kwargs):
            captured_target.append(kwargs.get("target"))
            t = MagicMock()
            t.start = lambda: captured_target[0]() if captured_target else None
            return t
        mock_thread_cls.side_effect = capture_thread
        p._play_twitch(url)

    call_args = mock_run.call_args
    env = call_args[1].get("env", {})
    assert local_bin in env.get("PATH", "").split(os.pathsep)


# ---------------------------------------------------------------------------
# Live / offline / error state tests
# ---------------------------------------------------------------------------

def test_live_channel_calls_set_uri():
    """When subprocess.run returns exit 0 with stdout='https://example.m3u8\\n',
    GLib.idle_add is called with _on_twitch_resolved which calls _set_uri."""
    p = make_player()
    p._pipeline = MagicMock()
    p._current_station_name = "Twitch Test"
    p._on_title = MagicMock()
    url = "https://www.twitch.tv/testchannel"
    resolved_url = "https://example.m3u8"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = resolved_url + "\n"

    idle_calls = []

    def fake_idle_add(fn, *args):
        idle_calls.append((fn, args))
        return fn(*args)

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result), \
         patch("musicstreamer.player.threading.Thread") as mock_thread_cls, \
         patch("musicstreamer.player.GLib") as mock_glib, \
         patch.object(p, "_set_uri") as mock_set_uri:
        mock_glib.idle_add.side_effect = fake_idle_add
        captured_target = []
        def capture_thread(**kwargs):
            captured_target.append(kwargs.get("target"))
            t = MagicMock()
            t.start = lambda: captured_target[0]() if captured_target else None
            return t
        mock_thread_cls.side_effect = capture_thread
        p._play_twitch(url)

    # _set_uri should have been called with the resolved URL
    mock_set_uri.assert_called_once_with(resolved_url, p._current_station_name, p._on_title)


def test_offline_channel_calls_on_offline():
    """When subprocess.run returns exit 1 with stdout containing 'No playable streams found',
    on_offline is called and _try_next_stream is NOT called."""
    p = make_player()
    p._pipeline = MagicMock()
    url = "https://www.twitch.tv/testchannel"
    on_offline = MagicMock()
    p._on_offline = on_offline

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "error: No playable streams found on this URL: https://www.twitch.tv/testchannel"

    idle_calls = []

    def fake_idle_add(fn, *args):
        idle_calls.append((fn, args))
        return fn(*args)

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result), \
         patch("musicstreamer.player.threading.Thread") as mock_thread_cls, \
         patch("musicstreamer.player.GLib") as mock_glib, \
         patch.object(p, "_try_next_stream") as mock_try_next:
        mock_glib.idle_add.side_effect = fake_idle_add
        captured_target = []
        def capture_thread(**kwargs):
            captured_target.append(kwargs.get("target"))
            t = MagicMock()
            t.start = lambda: captured_target[0]() if captured_target else None
            return t
        mock_thread_cls.side_effect = capture_thread
        p._play_twitch(url)

    on_offline.assert_called_once_with("testchannel")
    mock_try_next.assert_not_called()


def test_non_offline_error_calls_try_next():
    """When subprocess.run returns exit 1 with stdout NOT containing 'No playable streams found',
    _try_next_stream IS called."""
    p = make_player()
    p._pipeline = MagicMock()
    url = "https://www.twitch.tv/testchannel"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "error: Failed to open segment 1/1\n"

    idle_calls = []

    def fake_idle_add(fn, *args):
        idle_calls.append((fn, args))
        return fn(*args)

    with patch("musicstreamer.player.subprocess.run", return_value=mock_result), \
         patch("musicstreamer.player.threading.Thread") as mock_thread_cls, \
         patch("musicstreamer.player.GLib") as mock_glib, \
         patch.object(p, "_try_next_stream") as mock_try_next:
        mock_glib.idle_add.side_effect = fake_idle_add
        captured_target = []
        def capture_thread(**kwargs):
            captured_target.append(kwargs.get("target"))
            t = MagicMock()
            t.start = lambda: captured_target[0]() if captured_target else None
            return t
        mock_thread_cls.side_effect = capture_thread
        p._play_twitch(url)

    mock_try_next.assert_called_once()


# ---------------------------------------------------------------------------
# GStreamer error re-resolve tests
# ---------------------------------------------------------------------------

def test_gst_error_twitch_re_resolves():
    """When _on_gst_error fires and _current_stream.url contains 'twitch.tv',
    _play_twitch is called (not _try_next_stream directly)."""
    p = make_player()
    p._pipeline = MagicMock()
    p._current_stream = make_twitch_stream()
    p._twitch_resolve_attempts = 0
    p._streams_queue = []

    mock_msg = MagicMock()
    mock_msg.parse_error.return_value = (Exception("stream error"), "debug")

    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_try_next_stream") as mock_try_next, \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        p._on_gst_error(None, mock_msg)

    mock_play_twitch.assert_called_once_with(p._current_stream.url)
    mock_try_next.assert_not_called()


def test_re_resolve_bounded_to_one():
    """After one re-resolve attempt on the same stream, a second GStreamer error calls
    _try_next_stream instead of re-resolving again."""
    p = make_player()
    p._pipeline = MagicMock()
    p._current_stream = make_twitch_stream()
    p._twitch_resolve_attempts = 1  # already used one attempt
    p._streams_queue = []

    mock_msg = MagicMock()
    mock_msg.parse_error.return_value = (Exception("stream error"), "debug")

    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_try_next_stream") as mock_try_next, \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        p._on_gst_error(None, mock_msg)

    mock_play_twitch.assert_not_called()
    mock_try_next.assert_called_once()


# ---------------------------------------------------------------------------
# Failover timer tests
# ---------------------------------------------------------------------------

def test_failover_timer_not_armed_for_twitch():
    """After _try_next_stream processes a twitch.tv URL, _failover_timer_id remains None."""
    p = make_player()
    p._pipeline = MagicMock()
    twitch_stream = make_twitch_stream()
    p._streams_queue = [twitch_stream]
    p._current_station_name = "Test Twitch"
    p._on_title = MagicMock()

    with patch.object(p, "_play_twitch"), \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.return_value = 99
        p._try_next_stream()

    # timeout_add should NOT have been called for a Twitch URL
    mock_glib.timeout_add.assert_not_called()
    assert p._failover_timer_id is None


# ---------------------------------------------------------------------------
# Station change reset tests
# ---------------------------------------------------------------------------

def test_resolve_counter_resets_on_station_change():
    """After a station change (new play() call), _twitch_resolve_attempts resets to 0."""
    p = make_player()
    p._pipeline = MagicMock()
    p._twitch_resolve_attempts = 1  # simulate previous resolve attempt

    twitch_stream = make_twitch_stream()
    station = make_station_with_streams([twitch_stream])

    with patch.object(p, "_play_twitch"), \
         patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.source_remove = MagicMock()
        mock_glib.timeout_add.return_value = 99
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        p.play(station, MagicMock())

    assert p._twitch_resolve_attempts == 0
