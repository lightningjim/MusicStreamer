"""Phase 41-03: MainWindow media-keys wiring integration tests.

Tests that MainWindow correctly:
  - Constructs a MediaKeysBackend via the factory after Player + Repo exist
  - Bridges Player.title_changed -> backend.publish_metadata
  - Bridges backend.play_pause_requested / stop_requested -> Player
  - Calls set_playback_state on playback state transitions
  - Calls backend.shutdown() on closeEvent

All tests use a _SpyBackend (NoOpMediaKeysBackend subclass) injected via
monkeypatching media_keys.create so no real D-Bus is needed.
"""
from __future__ import annotations

from typing import Optional
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject, Signal

from musicstreamer.media_keys.base import NoOpMediaKeysBackend
from musicstreamer.models import Station
from musicstreamer.ui_qt.main_window import MainWindow


# ---------------------------------------------------------------------------
# Spy backend
# ---------------------------------------------------------------------------

class _SpyBackend(NoOpMediaKeysBackend):
    """Records all method calls for assertion in tests."""

    def __init__(self):
        super().__init__()
        self.metadata_calls: list[tuple] = []
        self.state_calls: list[str] = []
        self.shutdown_count: int = 0

    def publish_metadata(self, station, title, cover_pixmap):
        self.metadata_calls.append((station, title, cover_pixmap))

    def set_playback_state(self, state):
        super().set_playback_state(state)  # base validation
        self.state_calls.append(state)

    def shutdown(self):
        self.shutdown_count += 1


# ---------------------------------------------------------------------------
# Test doubles (mirrors test_main_window_integration.py)
# ---------------------------------------------------------------------------

class FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    elapsed_updated = Signal(int)

    def __init__(self):
        super().__init__()
        self.play_calls: list[Station] = []
        self.pause_calls: int = 0
        self.stop_calls: int = 0
        self.volume: Optional[float] = None

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self, station: Station, **kwargs) -> None:
        self.play_calls.append(station)

    def pause(self) -> None:
        self.pause_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


class FakeRepo:
    def __init__(self):
        self._stations: list = []
        self._settings: dict = {}

    def list_stations(self) -> list:
        return list(self._stations)

    def list_recently_played(self, n: int = 3) -> list:
        return []

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def update_last_played(self, station_id: int) -> None:
        pass

    def set_station_favorite(self, station_id: int, is_favorite: bool) -> None:
        pass

    def is_favorite_station(self, station_id: int) -> bool:
        return False

    def list_favorite_stations(self) -> list:
        return []

    def list_favorites(self) -> list:
        return []

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return False

    def add_favorite(self, station_name: str, provider_name: str, track_title: str, genre: str) -> None:
        pass

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        pass

    def list_streams(self, station_id: int) -> list:
        return []

    def get_station(self, station_id: int):
        return None


def _make_station(name="Test Station", sid=1) -> Station:
    return Station(
        id=sid,
        name=name,
        provider_id=None,
        provider_name="TestFM",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
        last_played_at=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spy():
    return _SpyBackend()


@pytest.fixture
def player():
    return FakePlayer()


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def window(qtbot, player, repo, spy, monkeypatch):
    """MainWindow with media_keys.create monkeypatched to return the spy."""
    monkeypatch.setattr("musicstreamer.media_keys.create", lambda p, r: spy)
    w = MainWindow(player, repo)
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Test 1: backend constructed and signals wired
# ---------------------------------------------------------------------------

def test_media_keys_backend_constructed(window, spy):
    """MainWindow sets self._media_keys to the backend returned by the factory."""
    assert window._media_keys is spy


# ---------------------------------------------------------------------------
# Test 2: title_changed fires publish_metadata
# ---------------------------------------------------------------------------

def test_title_changed_fires_publish_metadata(window, player, spy):
    """Player.title_changed -> _on_title_changed_for_media_keys -> publish_metadata."""
    station = _make_station()
    # Bind a station first so there's a current station in NowPlayingPanel
    window.now_playing.bind_station(station)

    player.title_changed.emit("Test Track")

    assert len(spy.metadata_calls) >= 1
    _, title, _ = spy.metadata_calls[-1]
    assert title == "Test Track"


# ---------------------------------------------------------------------------
# Test 3: _on_station_activated calls set_playback_state("playing")
# ---------------------------------------------------------------------------

def test_station_activated_sets_playing_state(window, spy):
    """_on_station_activated -> set_playback_state("playing")."""
    station = _make_station()
    window._on_station_activated(station)

    assert "playing" in spy.state_calls


# ---------------------------------------------------------------------------
# Test 4: failover(None) calls set_playback_state("stopped")
# ---------------------------------------------------------------------------

def test_failover_none_sets_stopped_state(window, player, spy):
    """Player.failover(None) -> set_playback_state("stopped")."""
    player.failover.emit(None)

    assert "stopped" in spy.state_calls


# ---------------------------------------------------------------------------
# Test 5: play_pause_requested signal toggles playback (with station bound)
# ---------------------------------------------------------------------------

def test_play_pause_requested_toggles_playback(window, player, spy):
    """backend.play_pause_requested -> _on_media_key_play_pause -> Player action."""
    station = _make_station()
    # Bind station and set playing state
    window._on_station_activated(station)
    # After activation, now_playing._is_playing should be True
    # Emitting play_pause_requested from the spy should trigger pause
    spy.play_pause_requested.emit()

    # Either pause was called (if playing) or play was called (if not playing)
    # After _on_station_activated, _is_playing is True so pause should be called
    assert player.pause_calls >= 1 or len(player.play_calls) >= 2


# ---------------------------------------------------------------------------
# Test 6: stop_requested calls stop on the player
# ---------------------------------------------------------------------------

def test_stop_requested_stops_player(window, player, spy):
    """backend.stop_requested -> _on_media_key_stop -> Player.stop()."""
    station = _make_station()
    window._on_station_activated(station)
    spy.stop_requested.emit()

    assert player.stop_calls >= 1


# ---------------------------------------------------------------------------
# Test 7: close() calls backend.shutdown()
# ---------------------------------------------------------------------------

def test_close_calls_backend_shutdown(qtbot, player, repo, spy, monkeypatch):
    """closeEvent calls backend.shutdown() before delegating to super()."""
    monkeypatch.setattr("musicstreamer.media_keys.create", lambda p, r: spy)
    w = MainWindow(player, repo)
    qtbot.addWidget(w)
    w.close()

    assert spy.shutdown_count >= 1


# ---------------------------------------------------------------------------
# Test 8: Factory raises -> MainWindow still constructs cleanly
# ---------------------------------------------------------------------------

def test_factory_exception_does_not_crash_startup(qtbot, player, repo, monkeypatch):
    """If media_keys.create raises, MainWindow wraps it and uses NoOp fallback."""
    from musicstreamer.media_keys.base import NoOpMediaKeysBackend

    def _raising_factory(p, r):
        raise RuntimeError("D-Bus not available in test")

    monkeypatch.setattr("musicstreamer.media_keys.create", _raising_factory)
    # Should not raise
    w = MainWindow(player, repo)
    qtbot.addWidget(w)
    assert isinstance(w._media_keys, NoOpMediaKeysBackend)
    w.close()
