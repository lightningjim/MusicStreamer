"""Phase 37-04: MainWindow integration tests.

Tests that StationListPanel, NowPlayingPanel, and ToastOverlay are correctly
wired inside MainWindow. Uses FakePlayer(QObject) — no real GStreamer pipeline.

Covers:
  - UI-01: station list present and visible
  - UI-02: now-playing panel present and visible
  - UI-12: toast overlay wired to Player signals
  - QA-05: widget lifetime safe over 3 construct/destroy cycles
"""
from __future__ import annotations

from typing import Optional

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QSplitter

from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt.main_window import MainWindow
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.ui_qt.toast import ToastOverlay


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakePlayer(QObject):
    """Minimal Player surface — exposes the same Signals as the real Player."""

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
    """Minimal repo surface."""

    def __init__(self, stations=None, recent=None, settings=None):
        self._stations = stations or []
        self._recent = recent or []
        self._settings = settings or {}

    def list_stations(self) -> list:
        return list(self._stations)

    def list_recently_played(self, n: int = 3) -> list:
        return list(self._recent[:n])

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def update_last_played(self, station_id: int) -> None:
        self._last_played_ids: list = getattr(self, "_last_played_ids", [])
        self._last_played_ids.append(station_id)

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
        for s in self._stations:
            if s.id == station_id:
                return s
        return None


def _make_station(name="Test Station", provider="TestFM") -> Station:
    return Station(
        id=1,
        name=name,
        provider_id=None,
        provider_name=provider,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
        last_played_at=None,
    )


@pytest.fixture
def fake_player():
    return FakePlayer()


@pytest.fixture
def fake_repo():
    return FakeRepo(stations=[_make_station()])


@pytest.fixture
def window(qtbot, fake_player, fake_repo):
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Structure tests (UI-01, UI-02)
# ---------------------------------------------------------------------------

def test_central_widget_is_splitter(window):
    assert isinstance(window.centralWidget(), QSplitter)


def test_station_panel_present(window):
    assert isinstance(window.station_panel, StationListPanel)


def test_now_playing_panel_present(window):
    assert isinstance(window.now_playing, NowPlayingPanel)


def test_splitter_orientation_horizontal(window):
    assert window.centralWidget().orientation() == Qt.Horizontal


def test_station_panel_min_width(window):
    assert window.station_panel.minimumWidth() >= 280


def test_now_playing_min_width(window):
    assert window.now_playing.minimumWidth() >= 560


def test_window_title(window):
    assert window.windowTitle() == "MusicStreamer"


def test_window_default_size(qtbot, fake_player, fake_repo):
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.width() >= 800
    assert w.height() >= 600


# ---------------------------------------------------------------------------
# Signal wiring — Player → NowPlayingPanel (UI-02)
# ---------------------------------------------------------------------------

def test_title_changed_updates_icy_label(qtbot, window, fake_player):
    fake_player.title_changed.emit("Artist - Track")
    assert window.now_playing.icy_label.text() == "Artist - Track"


def test_elapsed_updated_updates_elapsed_label(qtbot, window, fake_player):
    fake_player.elapsed_updated.emit(125)
    assert window.now_playing.elapsed_label.text() == "2:05"


# ---------------------------------------------------------------------------
# Station activation (UI-01)
# ---------------------------------------------------------------------------

def test_station_activated_calls_player_play(qtbot, window, fake_player):
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert len(fake_player.play_calls) == 1
    assert fake_player.play_calls[0] is station


def test_station_activated_binds_now_playing(qtbot, window):
    station = _make_station("Drone Zone", "SomaFM")
    window.station_panel.station_activated.emit(station)
    assert "Drone Zone" in window.now_playing.name_provider_label.text()


def test_station_activated_sets_playing_state(qtbot, window):
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert window.now_playing._is_playing is True


def test_station_activated_updates_last_played(qtbot, window, fake_repo):
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert fake_repo._last_played_ids == [station.id]


# ---------------------------------------------------------------------------
# Toast wiring (UI-12)
# ---------------------------------------------------------------------------

def test_station_activated_shows_connecting_toast(qtbot, window):
    station = _make_station()
    window.station_panel.station_activated.emit(station)
    assert window._toast.label.text() == "Connecting\u2026"


def test_failover_with_stream_shows_toast(qtbot, window, fake_player):
    stream = StationStream(id=1, station_id=1, url="http://backup.example.com", quality="hi")
    fake_player.failover.emit(stream)
    assert "trying next" in window._toast.label.text()


def test_failover_none_shows_exhausted_toast(qtbot, window, fake_player):
    fake_player.failover.emit(None)
    assert window._toast.label.text() == "Stream exhausted"


def test_failover_none_clears_playing_state(qtbot, window, fake_player):
    # First, set playing state
    window.now_playing.on_playing_state_changed(True)
    fake_player.failover.emit(None)
    assert window.now_playing._is_playing is False


def test_offline_shows_toast(qtbot, window, fake_player):
    fake_player.offline.emit("somechannel")
    assert window._toast.label.text() == "Channel offline"


def test_playback_error_shows_toast(qtbot, window, fake_player):
    fake_player.playback_error.emit("Pipeline failed")
    assert "Playback error" in window._toast.label.text()
    assert "Pipeline failed" in window._toast.label.text()


def test_playback_error_long_message_truncated(qtbot, window, fake_player):
    long_msg = "x" * 100
    fake_player.playback_error.emit(long_msg)
    text = window._toast.label.text()
    # Should be truncated to 80 chars + ellipsis
    assert text.endswith("\u2026")
    assert len(text) < len(long_msg) + 20  # definitely shorter


def test_show_toast_public_api(qtbot, window):
    window.show_toast("Hello test")
    assert window._toast.label.text() == "Hello test"


# ---------------------------------------------------------------------------
# QA-05: widget lifetime over 3 construct/destroy cycles
# ---------------------------------------------------------------------------

def test_widget_lifetime_no_runtime_error(qtbot):
    """Construct and destroy MainWindow 3 times — no RuntimeError on C++ object."""
    for _ in range(3):
        player = FakePlayer()
        repo = FakeRepo(stations=[_make_station()])
        w = MainWindow(player, repo)
        qtbot.addWidget(w)
        w.show()
        # Emit signals while alive — no crash
        player.title_changed.emit("Test Title")
        player.elapsed_updated.emit(42)
        player.failover.emit(None)
        # Clean up — triggers Qt object deletion
        w.close()
        w.deleteLater()


# ---------------------------------------------------------------------------
# Phase 40-04: Hamburger menu wiring + accent startup load
# ---------------------------------------------------------------------------

EXPECTED_ACTION_TEXTS = [
    "Discover Stations",
    "Import Stations",
    "Accent Color",
    "YouTube Cookies",
    "Accounts",
    "Export Settings",
    "Import Settings",
]


def test_hamburger_menu_actions(window):
    """Hamburger menu contains exactly 7 non-separator actions with correct text."""
    menu = window._menu
    actions = [a for a in menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts == EXPECTED_ACTION_TEXTS


def test_hamburger_menu_separators(window):
    """Hamburger menu has exactly 2 separators (3 groups)."""
    menu = window._menu
    separators = [a for a in menu.actions() if a.isSeparator()]
    assert len(separators) == 2


def test_sync_actions_disabled(window):
    """Export Settings and Import Settings are disabled."""
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    assert actions["Export Settings"].isEnabled() is False
    assert actions["Import Settings"].isEnabled() is False


def test_sync_actions_tooltip(window):
    """Disabled sync actions have the expected tooltip."""
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    assert actions["Export Settings"].toolTip() == "Coming in a future update"
    assert actions["Import Settings"].toolTip() == "Coming in a future update"


def test_accent_loaded_on_startup(qtbot, fake_player):
    """When repo has saved accent_color, MainWindow applies it on startup."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor

    accent_hex = "#e62d42"
    repo = FakeRepo(settings={"accent_color": accent_hex})
    app = QApplication.instance()
    # Reset to default palette before test
    default_palette = app.palette()

    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)

    highlight = app.palette().color(app.palette().ColorRole.Highlight)
    assert highlight == QColor(accent_hex)

    # Restore default palette to avoid polluting other tests
    app.setPalette(default_palette)
    app.setStyleSheet("")


def test_discover_action_opens_dialog(qtbot, window, monkeypatch):
    """Triggering Discover Stations opens DiscoveryDialog."""
    from musicstreamer.ui_qt import discovery_dialog
    called = []

    def fake_exec(self):
        called.append(True)
        return 0

    monkeypatch.setattr(discovery_dialog.DiscoveryDialog, "exec", fake_exec)
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    actions["Discover Stations"].trigger()
    assert called == [True]


def test_import_action_opens_dialog(qtbot, window, monkeypatch):
    """Triggering Import Stations opens ImportDialog."""
    from musicstreamer.ui_qt import import_dialog
    called = []

    def fake_exec(self):
        called.append(True)
        return 0

    monkeypatch.setattr(import_dialog.ImportDialog, "exec", fake_exec)
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    actions["Import Stations"].trigger()
    assert called == [True]
