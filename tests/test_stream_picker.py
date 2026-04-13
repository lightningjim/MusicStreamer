"""Phase 39-04 TDD: NowPlayingPanel edit button + stream picker (UI-13).

Tests:
  1. Edit button exists and is initially disabled.
  2. Edit button becomes enabled after bind_station + on_playing_state_changed(True).
  3. Edit button becomes disabled after on_playing_state_changed(False).
  4. Stream picker is hidden when station has 1 stream.
  5. Stream picker is visible when station has 2+ streams.
  6. Stream picker populated with label "quality — codec" format.
  7. Changing stream picker selection calls player.play_stream with correct StationStream.
  8. Failover signal sync updates combo without triggering play_stream (blockSignals).
"""
from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    elapsed_updated = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._current_station_name: str = ""
        self.play_stream = MagicMock()
        self.set_volume_calls: List[float] = []
        self.stop_called: bool = False
        self.pause_called: bool = False
        self.play_calls: List[Station] = []

    def set_volume(self, v: float) -> None:
        self.set_volume_calls.append(v)

    def stop(self) -> None:
        self.stop_called = True

    def pause(self) -> None:
        self.pause_called = True

    def play(self, station, **kwargs) -> None:
        self.play_calls.append(station)


class FakeRepo:
    def __init__(self, streams_by_station_id=None, settings=None) -> None:
        self._streams: dict = dict(streams_by_station_id or {})
        self._settings: dict = dict(settings or {})
        self._favorites: list = []

    def list_streams(self, station_id: int) -> List[StationStream]:
        return self._streams.get(station_id, [])

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return any(f == (station_name, track_title) for f in self._favorites)

    def add_favorite(self, station_name: str, provider_name: str, track_title: str, genre: str) -> None:
        key = (station_name, track_title)
        if key not in self._favorites:
            self._favorites.append(key)

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        key = (station_name, track_title)
        if key in self._favorites:
            self._favorites.remove(key)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

single_stream_station = Station(
    id=1, name="FM1", provider_id=1, provider_name="P",
    tags="", station_art_path=None, album_fallback_path=None,
)

multi_stream_station = Station(
    id=2, name="FM2", provider_id=1, provider_name="P",
    tags="", station_art_path=None, album_fallback_path=None,
)

SINGLE_STREAMS = [
    StationStream(id=10, station_id=1, url="http://s1", quality="hi", codec="MP3", position=1),
]
MULTI_STREAMS = [
    StationStream(id=20, station_id=2, url="http://s1", quality="hi", codec="AAC", position=1),
    StationStream(id=21, station_id=2, url="http://s2", quality="med", codec="MP3", position=2),
]


@pytest.fixture
def app(qtbot):
    """Ensure QApplication exists."""
    return QApplication.instance()


@pytest.fixture
def player():
    return FakePlayer()


@pytest.fixture
def repo():
    return FakeRepo(
        streams_by_station_id={
            1: SINGLE_STREAMS,
            2: MULTI_STREAMS,
        }
    )


@pytest.fixture
def panel(qtbot, player, repo):
    w = NowPlayingPanel(player, repo)
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_edit_btn_exists_and_disabled_initially(panel):
    """Test 1: edit_btn exists and is initially disabled."""
    assert hasattr(panel, "edit_btn"), "NowPlayingPanel must have edit_btn attribute"
    assert not panel.edit_btn.isEnabled(), "edit_btn must be disabled before any station is bound"


def test_edit_btn_enabled_when_playing(panel):
    """Test 2: edit_btn enabled after bind_station + on_playing_state_changed(True)."""
    panel.bind_station(single_stream_station)
    panel.on_playing_state_changed(True)
    assert panel.edit_btn.isEnabled(), "edit_btn must be enabled when a station is playing"


def test_edit_btn_disabled_when_stopped(panel):
    """Test 3: edit_btn disabled after on_playing_state_changed(False)."""
    panel.bind_station(single_stream_station)
    panel.on_playing_state_changed(True)
    panel.on_playing_state_changed(False)
    assert not panel.edit_btn.isEnabled(), "edit_btn must be disabled when playback stops"


def test_stream_combo_hidden_for_single_stream(panel):
    """Test 4: stream_combo is hidden when station has only 1 stream."""
    assert hasattr(panel, "stream_combo"), "NowPlayingPanel must have stream_combo attribute"
    panel.bind_station(single_stream_station)
    # isHidden() checks the explicit hide flag regardless of parent visibility
    assert panel.stream_combo.isHidden(), "stream_combo must be hidden for single-stream station"


def test_stream_combo_visible_for_multi_stream(panel):
    """Test 5: stream_combo is visible when station has 2+ streams."""
    panel.bind_station(multi_stream_station)
    # isHidden() is False when setVisible(True) was called, even in offscreen tests
    assert not panel.stream_combo.isHidden(), "stream_combo must not be hidden for multi-stream station"


def test_stream_combo_populated_with_labels(panel):
    """Test 6: stream_combo populated with 'quality — codec' labels."""
    panel.bind_station(multi_stream_station)
    assert panel.stream_combo.count() == 2
    label_0 = panel.stream_combo.itemText(0)
    label_1 = panel.stream_combo.itemText(1)
    assert "hi" in label_0 and "AAC" in label_0, f"Expected 'hi — AAC' in '{label_0}'"
    assert "med" in label_1 and "MP3" in label_1, f"Expected 'med — MP3' in '{label_1}'"


def test_stream_selection_calls_play_stream(qtbot, player, repo):
    """Test 7: Changing stream picker selection calls player.play_stream with correct StationStream."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)

    player.play_stream.reset_mock()
    # Select index 1 (second stream)
    panel.stream_combo.setCurrentIndex(1)

    player.play_stream.assert_called_once()
    called_with = player.play_stream.call_args[0][0]
    assert called_with.id == MULTI_STREAMS[1].id, (
        f"Expected play_stream called with stream id={MULTI_STREAMS[1].id}, got {called_with.id}"
    )


def test_failover_sync_does_not_call_play_stream(qtbot, player, repo):
    """Test 8: _sync_stream_picker updates combo selection without triggering play_stream."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)

    player.play_stream.reset_mock()
    # Simulate failover sync to the second stream
    panel._sync_stream_picker(MULTI_STREAMS[1])

    # Combo selection must have updated
    assert panel.stream_combo.currentIndex() == 1, (
        "stream_combo must reflect the failed-over stream"
    )
    # play_stream must NOT have been called (blockSignals prevented it)
    player.play_stream.assert_not_called()
