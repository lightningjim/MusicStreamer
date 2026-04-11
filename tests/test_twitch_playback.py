"""Tests for Twitch playback via the streamlink library API.

Phase 35 port: ``_play_twitch`` spawns a worker thread that calls
``streamlink.session.Streamlink().streams(url)``. On success the worker
emits the queued ``twitch_resolved`` Qt signal, which is connected to
``_on_twitch_resolved`` on the main thread. Tests drive the worker
directly (bypassing the Thread start) so assertions are synchronous.
"""
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Player


def make_player(qtbot):
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
# URL detection — routing path
# ---------------------------------------------------------------------------

def test_twitch_url_detected(qtbot):
    """A stream with 'twitch.tv' routes to _play_twitch, not _set_uri/_play_youtube."""
    p = make_player(qtbot)
    twitch_stream = make_twitch_stream()
    p._streams_queue = [twitch_stream]
    p._current_station_name = "Test Twitch"
    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_set_uri") as mock_set_uri, \
         patch.object(p, "_play_youtube") as mock_play_youtube:
        p._try_next_stream()
    mock_play_twitch.assert_called_once_with(twitch_stream.url)
    mock_set_uri.assert_not_called()
    mock_play_youtube.assert_not_called()


def test_non_twitch_url_not_routed(qtbot):
    p = make_player(qtbot)
    regular_stream = make_stream(1, 1, "hi", url="http://example.com/stream/")
    p._streams_queue = [regular_stream]
    p._current_station_name = "Test Regular"
    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_set_uri"):
        p._try_next_stream()
    mock_play_twitch.assert_not_called()


# ---------------------------------------------------------------------------
# streamlink library API — success path
# ---------------------------------------------------------------------------

class _FakeStream:
    def __init__(self, url):
        self.url = url


def _fake_session_with_streams(streams_dict):
    """Build a MagicMock streamlink Session that returns ``streams_dict``."""
    session = MagicMock()
    session.streams.return_value = streams_dict
    return session


def test_twitch_resolves_via_library(qtbot, tmp_path, monkeypatch):
    """Worker calls Streamlink().streams(url) and emits twitch_resolved."""
    monkeypatch.setattr(
        "musicstreamer.paths.twitch_token_path",
        lambda: str(tmp_path / "nonexistent-token"),
    )
    p = make_player(qtbot)
    session = _fake_session_with_streams(
        {"best": _FakeStream("https://example.m3u8")}
    )
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000) as blocker:
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")
    assert blocker.args == ["https://example.m3u8"]
    session.streams.assert_called_once_with("https://www.twitch.tv/testchannel")


def test_twitch_offline_emits_offline_signal(qtbot, tmp_path, monkeypatch):
    """Empty streams dict (channel offline) emits the offline signal."""
    monkeypatch.setattr(
        "musicstreamer.paths.twitch_token_path",
        lambda: str(tmp_path / "nonexistent-token"),
    )
    p = make_player(qtbot)
    session = _fake_session_with_streams({})
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.offline, timeout=2000) as blocker:
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")
    assert blocker.args == ["testchannel"]


def test_twitch_plugin_error_offline_emits_offline(qtbot, tmp_path, monkeypatch):
    """streamlink PluginError whose message contains 'offline' → offline signal."""
    from streamlink.exceptions import PluginError
    monkeypatch.setattr(
        "musicstreamer.paths.twitch_token_path",
        lambda: str(tmp_path / "nonexistent-token"),
    )
    p = make_player(qtbot)
    session = MagicMock()
    session.streams.side_effect = PluginError("channel is offline")
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.offline, timeout=2000) as blocker:
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")
    assert blocker.args == ["testchannel"]


def test_twitch_plugin_error_other_emits_playback_error(qtbot, tmp_path, monkeypatch):
    """streamlink PluginError with a non-offline message → playback_error."""
    from streamlink.exceptions import PluginError
    monkeypatch.setattr(
        "musicstreamer.paths.twitch_token_path",
        lambda: str(tmp_path / "nonexistent-token"),
    )
    p = make_player(qtbot)
    session = MagicMock()
    session.streams.side_effect = PluginError("bogus stream error")
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.playback_error, timeout=2000) as blocker:
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")
    assert "bogus stream error" in blocker.args[0]


def test_twitch_no_plugin_emits_playback_error(qtbot, tmp_path, monkeypatch):
    """NoPluginError → playback_error signal."""
    from streamlink.exceptions import NoPluginError
    monkeypatch.setattr(
        "musicstreamer.paths.twitch_token_path",
        lambda: str(tmp_path / "nonexistent-token"),
    )
    p = make_player(qtbot)
    session = MagicMock()
    session.streams.side_effect = NoPluginError("no plugin")
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.playback_error, timeout=2000) as blocker:
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")
    assert "no plugin" in blocker.args[0]


# ---------------------------------------------------------------------------
# GStreamer error re-resolve tests (rebuilt against new API)
# ---------------------------------------------------------------------------

def test_gst_error_twitch_re_resolves(qtbot):
    """On GStreamer error with a Twitch current stream, _play_twitch is re-invoked."""
    p = make_player(qtbot)
    p._current_stream = make_twitch_stream()
    p._twitch_resolve_attempts = 0
    p._streams_queue = []
    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_try_next_stream") as mock_try_next:
        p._handle_gst_error_recovery()
    mock_play_twitch.assert_called_once_with(p._current_stream.url)
    mock_try_next.assert_not_called()


def test_re_resolve_bounded_to_one(qtbot):
    """After one re-resolve, a second error falls through to _try_next_stream."""
    p = make_player(qtbot)
    p._current_stream = make_twitch_stream()
    p._twitch_resolve_attempts = 1
    p._streams_queue = []
    with patch.object(p, "_play_twitch") as mock_play_twitch, \
         patch.object(p, "_try_next_stream") as mock_try_next:
        p._handle_gst_error_recovery()
    mock_play_twitch.assert_not_called()
    mock_try_next.assert_called_once()


# ---------------------------------------------------------------------------
# Failover timer not armed for Twitch (resolver handles its own timing)
# ---------------------------------------------------------------------------

def test_failover_timer_not_armed_for_twitch(qtbot):
    """After _try_next_stream routes a Twitch URL, _failover_timer is NOT active."""
    p = make_player(qtbot)
    twitch_stream = make_twitch_stream()
    p._streams_queue = [twitch_stream]
    p._current_station_name = "Test Twitch"
    with patch.object(p, "_play_twitch"):
        p._try_next_stream()
    assert not p._failover_timer.isActive()


# ---------------------------------------------------------------------------
# Station change reset
# ---------------------------------------------------------------------------

def test_resolve_counter_resets_on_station_change(qtbot):
    """Starting a new station resets _twitch_resolve_attempts to 0."""
    p = make_player(qtbot)
    p._twitch_resolve_attempts = 1
    twitch_stream = make_twitch_stream()
    station = make_station_with_streams([twitch_stream])
    with patch.object(p, "_play_twitch"):
        p.play(station)
    assert p._twitch_resolve_attempts == 0
