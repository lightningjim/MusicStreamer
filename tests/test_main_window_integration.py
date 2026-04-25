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
    cookies_cleared = Signal(str)  # Phase 999.7
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)  # Phase 47.1 D-12

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

    # Phase 47.2: EQ API stubs — MainWindow calls restore_eq_from_settings
    # from __init__; the other methods are referenced by EqualizerDialog
    # and included here for completeness.
    def restore_eq_from_settings(self, repo) -> None:
        pass

    def set_eq_enabled(self, enabled: bool) -> None:
        pass

    def set_eq_profile(self, profile) -> None:
        pass

    def set_eq_preamp(self, db: float) -> None:
        pass


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

    def list_providers(self) -> list:
        # Phase 999.1 Plan 03: EditStationDialog._populate enumerates providers;
        # an empty list is sufficient for the new-station flow since no
        # provider pre-selection is exercised by these integration tests.
        return []

    def get_station(self, station_id: int):
        for s in self._stations:
            if s.id == station_id:
                return s
        # Fall back to the Phase 999.1 placeholder path: if a new id was handed
        # out by create_station() but not yet pushed into _stations, return a
        # freshly-constructed placeholder Station. Plan 01/02/03 tests exercise
        # this path when they rehydrate the dialog from a just-created id.
        if station_id in getattr(self, "_created_ids", []):
            return Station(
                id=station_id,
                name="New Station",
                provider_id=None,
                provider_name=None,
                tags="",
                station_art_path=None,
                album_fallback_path=None,
                icy_disabled=False,
                streams=[],
                last_played_at=None,
            )
        return None

    # ------------------------------------------------------------------
    # Phase 999.1 Wave 0 — create/delete hooks required by Plan 03 tests.
    # ------------------------------------------------------------------

    def create_station(self) -> int:
        self._created_ids: list = getattr(self, "_created_ids", [])
        self._next_station_id: int = getattr(self, "_next_station_id", 100)
        new_id = self._next_station_id
        self._next_station_id += 1
        self._created_ids.append(new_id)
        return new_id

    def delete_station(self, station_id: int) -> None:
        self._deleted_ids: list = getattr(self, "_deleted_ids", [])
        self._deleted_ids.append(station_id)


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
    "New Station",         # Phase 999.1 D-01 (Plan 03)
    "Discover Stations",
    "Import Stations",
    "Accent Color",
    "YouTube Cookies",
    "Accounts",
    "Equalizer",           # Phase 47.2 D-07
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
]


def test_hamburger_menu_actions(window):
    """Hamburger menu contains exactly 9 non-separator actions with correct text."""
    menu = window._menu
    actions = [a for a in menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts == EXPECTED_ACTION_TEXTS


def test_hamburger_menu_separators(window):
    """Hamburger menu has exactly 3 separators (4 groups; Phase 47.1 adds Stats group)."""
    menu = window._menu
    separators = [a for a in menu.actions() if a.isSeparator()]
    assert len(separators) == 3


def test_sync_actions_enabled(window):
    """Export Settings and Import Settings are enabled (Phase 42)."""
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    assert actions["Export Settings"].isEnabled() is True
    assert actions["Import Settings"].isEnabled() is True


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


# ---------------------------------------------------------------------------
# Phase 47.1 — Stats for Nerds integration (D-03, D-04, D-13)
# ---------------------------------------------------------------------------

def test_stats_action_is_checkable(qtbot, fake_player, fake_repo):
    """D-03: hamburger 'Stats for Nerds' QAction exists, is checkable, and
    initial checked state reflects repo setting (default '0' -> False)."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert hasattr(w, "_act_stats")
    assert w._act_stats.isCheckable() is True
    # Default repo has no setting -> get_setting returns default "0" -> unchecked
    assert w._act_stats.isChecked() is False


def test_stats_action_initial_checked_when_setting_is_1(qtbot, fake_player):
    """D-04: if repo has 'show_stats_for_nerds' = '1', action starts checked."""
    repo = FakeRepo(stations=[_make_station()], settings={"show_stats_for_nerds": "1"})
    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)
    assert w._act_stats.isChecked() is True


def test_stats_toggle_persists_and_toggles_panel(qtbot, fake_player, fake_repo):
    """D-04 + D-07: triggering the action persists '1'/'0' AND flips the
    panel's _stats_widget visibility accordingly."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Initial: unchecked, widget hidden
    assert w._act_stats.isChecked() is False
    assert w.now_playing._stats_widget.isHidden() is True

    # Trigger ON
    w._act_stats.trigger()
    assert w._act_stats.isChecked() is True
    assert fake_repo.get_setting("show_stats_for_nerds", "0") == "1"
    assert w.now_playing._stats_widget.isHidden() is False

    # Trigger OFF
    w._act_stats.trigger()
    assert w._act_stats.isChecked() is False
    assert fake_repo.get_setting("show_stats_for_nerds", "0") == "0"
    assert w.now_playing._stats_widget.isHidden() is True


def test_buffer_percent_bound_method_connect_no_lambda(qtbot, window, fake_player):
    """D-13 + QA-05: emitting Player.buffer_percent updates both bar and
    label on the now-playing panel via a bound-method connect (no lambda)."""
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod

    # Functional: emit -> slot fires -> both widgets update atomically (D-11 also)
    fake_player.buffer_percent.emit(42)
    assert window.now_playing.buffer_bar.value() == 42
    assert window.now_playing.buffer_pct_label.text() == "42%"

    # Structural: no 'lambda' appears on the buffer_percent.connect line
    src = inspect.getsource(mw_mod.MainWindow)
    # Find the buffer_percent.connect line and verify no lambda on it
    for line in src.splitlines():
        if "buffer_percent.connect" in line:
            assert "lambda" not in line, (
                f"D-13 violated — lambda found on buffer_percent.connect line: {line!r}"
            )
            break
    else:
        raise AssertionError("buffer_percent.connect line not found in MainWindow source")


# ---------------------------------------------------------------------------
# Phase 999.1 Wave 0 — Add-New-Station menu wiring integration tests (RED).
# These tests cover MainWindow's "New Station" hamburger-menu action added
# by Plan 03. Expected to FAIL until Plan 03 lands.
# ---------------------------------------------------------------------------


def test_hamburger_menu_has_new_station_first_in_group1(qtbot, fake_player, fake_repo):
    """D-01: 'New Station' is the first item in the hamburger menu's Group 1
    (precedes Discover Stations and Import Stations)."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    action_texts = [
        a.text() for a in w._menu.actions() if not a.isSeparator()
    ]
    assert "New Station" in action_texts, \
        f"Expected 'New Station' action in hamburger menu; got {action_texts!r}"

    idx_new = action_texts.index("New Station")
    idx_discover = action_texts.index("Discover Stations")
    idx_import = action_texts.index("Import Stations")
    assert idx_new < idx_discover
    assert idx_new < idx_import


def test_new_station_menu_creates_placeholder_and_opens_dialog(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """D-03a: triggering the 'New Station' action calls repo.create_station()
    and opens EditStationDialog; on dialog reject, repo.delete_station(new_id)
    must be called to clean up the placeholder row (ties D-04a into the
    menu-triggered flow)."""
    from PySide6.QtWidgets import QDialog
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod

    # Simulate user clicking Cancel: invoke the dialog's own reject() override
    # so the Plan-01 is_new delete-on-reject path fires (Pitfall 3). Returning
    # Rejected alone bypasses the override and leaves the placeholder orphaned.
    def _fake_exec_reject(self):
        self.reject()
        return QDialog.Rejected

    monkeypatch.setattr(
        esd_mod.EditStationDialog, "exec", _fake_exec_reject
    )

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    action = next(
        (a for a in w._menu.actions() if a.text() == "New Station"), None
    )
    assert action is not None, "New Station action must exist on hamburger menu"
    action.trigger()

    # FakeRepo tracked exactly one create_station() call.
    created = getattr(fake_repo, "_created_ids", [])
    assert len(created) == 1, \
        f"expected exactly one create_station call, got {created!r}"
    new_id = created[0]

    # Because the dialog was rejected, the placeholder must be cleaned up.
    deleted = getattr(fake_repo, "_deleted_ids", [])
    assert new_id in deleted, \
        f"expected delete_station({new_id}) after dialog reject; deleted={deleted!r}"


def test_new_station_save_refreshes_and_selects(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """D-07a: after a successful save in the New Station flow, MainWindow
    refreshes the station panel model and selects the newly-created row."""
    from PySide6.QtWidgets import QDialog
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod
    from musicstreamer.ui_qt import station_list_panel as slp_mod

    def _fake_exec(self):
        # Simulate "user hit Save" — emit station_saved, then accept.
        self.station_saved.emit()
        return QDialog.Accepted

    monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)

    select_calls: list = []
    refresh_calls: list = []

    def _record_select(self, station_id):
        select_calls.append(station_id)

    def _record_refresh(self, *args, **kwargs):
        refresh_calls.append((args, kwargs))

    monkeypatch.setattr(
        slp_mod.StationListPanel, "select_station", _record_select, raising=False
    )
    monkeypatch.setattr(
        slp_mod.StationListPanel, "refresh_model", _record_refresh, raising=False
    )

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    action = next(
        (a for a in w._menu.actions() if a.text() == "New Station"), None
    )
    assert action is not None
    action.trigger()

    created = getattr(fake_repo, "_created_ids", [])
    assert len(created) == 1
    new_id = created[0]

    assert select_calls == [new_id], \
        f"expected select_station({new_id}) exactly once; got {select_calls!r}"
    assert len(refresh_calls) >= 1, \
        "expected at least one refresh_model() call after successful save"


def test_new_station_save_does_not_auto_play(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """D-07c: the New Station save path must never auto-play the new station
    or call _sync_now_playing_station for it."""
    from PySide6.QtWidgets import QDialog
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod

    def _fake_exec(self):
        self.station_saved.emit()
        return QDialog.Accepted

    monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)

    sync_calls: list = []
    from musicstreamer.ui_qt.main_window import MainWindow as _MW

    orig_sync = _MW._sync_now_playing_station

    def _spy_sync(self, station_id):
        sync_calls.append(station_id)
        return orig_sync(self, station_id)

    monkeypatch.setattr(_MW, "_sync_now_playing_station", _spy_sync)

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    action = next(
        (a for a in w._menu.actions() if a.text() == "New Station"), None
    )
    assert action is not None
    action.trigger()

    created = getattr(fake_repo, "_created_ids", [])
    assert len(created) == 1
    new_id = created[0]

    # The new placeholder must NOT have been auto-played.
    assert not any(s.id == new_id for s in fake_player.play_calls), \
        f"new station (id={new_id}) must not auto-play; play_calls={fake_player.play_calls!r}"
    assert new_id not in sync_calls, \
        f"_sync_now_playing_station must not fire for new id={new_id}; sync_calls={sync_calls!r}"


# ---------------------------------------------------------------------------
# Phase 44 Plan 03 — Node-missing YT-fail toast branch (D-13 part 2)
# ---------------------------------------------------------------------------


def test_yt_fail_toast_when_node_missing(qtbot, fake_player, fake_repo):
    """D-13 part 2: when node_runtime is missing AND Player emits a
    'YouTube resolve failed: ...' message, MainWindow surfaces the
    install-Node toast instead of the generic Playback-error toast."""
    from unittest import mock
    from musicstreamer.runtime_check import NodeRuntime

    w = MainWindow(
        fake_player, fake_repo,
        node_runtime=NodeRuntime(available=False, path=None),
    )
    qtbot.addWidget(w)

    w.show_toast = mock.Mock()
    fake_player.playback_error.emit("YouTube resolve failed: nodejs not on PATH")

    w.show_toast.assert_called_with("Install Node.js for YouTube playback")


def test_yt_fail_toast_uses_generic_when_node_present(qtbot, fake_player, fake_repo):
    """Inverse of test_yt_fail_toast_when_node_missing: when Node IS available,
    a 'YouTube resolve failed' message falls through to the generic
    'Playback error: ...' toast (no Node-install nudge)."""
    from unittest import mock
    from musicstreamer.runtime_check import NodeRuntime

    w = MainWindow(
        fake_player, fake_repo,
        node_runtime=NodeRuntime(available=True, path="/usr/bin/node"),
    )
    qtbot.addWidget(w)

    w.show_toast = mock.Mock()
    fake_player.playback_error.emit("YouTube resolve failed: transient")

    args, _ = w.show_toast.call_args
    assert "Install Node.js" not in args[0]
    assert "Playback error" in args[0]


def test_player_emits_expected_yt_failure_prefix():
    """Plan 03 issue 4 regression guard. MainWindow._on_playback_error
    matches the literal substring 'YouTube resolve failed' in the message
    string. If musicstreamer/player.py drifts to a different prefix
    ('YT resolve failed:', 'YouTube playback failed:', etc.), the
    Node-missing toast branch silently stops firing — this pinning test
    fails fast on that drift."""
    import re
    import pathlib
    src = pathlib.Path("musicstreamer/player.py").read_text()
    assert re.search(r'playback_error\.emit\(\s*f?["\']YouTube resolve failed:', src), \
        "player.py drifted — MainWindow Node-missing toast branch will silently break (Plan 03 issue 4 regression guard)"
