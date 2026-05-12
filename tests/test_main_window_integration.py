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
    underrun_recovery_started = Signal()  # Phase 62 / D-07 — main→MainWindow toast trigger
    audio_caps_detected = Signal(int, int, int)  # Phase 70 / DS-01: stream_id, rate_hz, bit_depth

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

    def shutdown_underrun_tracker(self) -> None:
        """Phase 62 / D-03: no-op stub — real Player force-closes any open cycle.

        FakePlayer has no tracker so the call is a no-op; MainWindow.closeEvent
        calls this in a try/except, but having it defined avoids the warning log.
        """
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


def test_station_activated_refreshes_recent_list(qtbot, fake_player):
    """Phase 50 / BUG-01: emitting station_activated triggers a recent-list refresh.

    Seeds FakeRepo._recent before MainWindow construction and asserts that the
    panel's QListView reflects the seeded data after the signal fires. Proves
    _on_station_activated calls refresh_recent (D-01, D-04).
    """
    station = _make_station()
    # Start with empty _recent; require refresh_recent (driven by update_last_played → _recent prepend) to populate it.
    fake_repo = FakeRepo(stations=[station], recent=[])

    # Extend update_last_played to mutate _recent so list_recently_played reflects the click.
    original_update = fake_repo.update_last_played
    def update_and_record(station_id: int) -> None:
        original_update(station_id)
        fake_repo._recent = [station] + [s for s in fake_repo._recent if s.id != station_id]
    fake_repo.update_last_played = update_and_record  # type: ignore[assignment]

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    # At construction time _recent is empty → row count is 0.
    assert w.station_panel.recent_view.model().rowCount() == 0

    w.station_panel.station_activated.emit(station)

    # After activation: update_last_played mutated _recent, refresh_recent re-queried, rowCount > 0.
    assert w.station_panel.recent_view.model().rowCount() == 1
    top = w.station_panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert top is not None and top.id == station.id


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
    "Add GBS.FM",          # Phase 60 D-02 (Plan 60-03)
    "Search GBS.FM…",  # Phase 60 D-08a (Plan 60-07; U+2026 ellipsis)
    "Theme",               # Phase 66 D-15 / THEME-01: Theme picker
    "Show similar stations",  # Phase 67 / S-01, M-01: master toggle
    "Accent Color",
    "Accounts",            # Phase 53 D-13: YouTube Cookies entry removed; cookie management consolidated into Accounts dialog
    "Equalizer",           # Phase 47.2 D-07
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
]


def test_hamburger_menu_actions(window):
    """Phase 65 VER-02-C: hamburger menu has 13 named actions plus 1 version footer.

    The first 13 entries are literal text; the 14th is the Phase 65 D-01 version
    footer asserted via regex (text changes every phase via Phase 63 auto-bump,
    so we cannot pin the literal here).

    Updated in Phase 67 to include 'Theme' (Phase 66 D-15) and
    'Show similar stations' (Phase 67 S-01 M-01) in Group 2.
    """
    import re
    menu = window._menu
    actions = [a for a in menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts[:13] == EXPECTED_ACTION_TEXTS
    assert len(actions) == 14, (
        f"Expected 13 named actions + 1 version footer = 14 total, got {len(actions)}: {texts!r}"
    )
    assert re.match(r"^v\d+\.\d+\.\d+$", texts[13]), (
        f"Last menu action must be Phase 65 version footer (D-01), got {texts[13]!r}"
    )


def test_hamburger_menu_separators(window):
    """Phase 65 D-02 / VER-02-E: hamburger menu has 4 separators (was 3).

    Phase 47.1 brought the count to 3 (4 groups: New/Discovery/Import/GBS,
    Settings, Stats, Export/Import-Settings). Phase 65 D-02 adds a 4th
    separator immediately before the version footer.
    """
    menu = window._menu
    separators = [a for a in menu.actions() if a.isSeparator()]
    assert len(separators) == 4


def test_version_action_is_disabled_and_last(window):
    """Phase 65 D-03/D-12 / VER-02-C/D: version footer is disabled and is the
    literal last entry of the menu (regardless of Node-missing presence)."""
    import re
    menu = window._menu
    actions = list(menu.actions())
    assert actions[-1] is window._act_version, (
        "self._act_version must be the literal last menu action "
        "(after the optional Phase 44 Node-missing block)"
    )
    assert window._act_version.isEnabled() is False, (
        "Phase 65 D-12: version footer must be disabled (no click target)"
    )
    assert re.match(r"^v\d+\.\d+\.\d+$", window._act_version.text()), (
        f"Phase 65 D-10: label format must be 'v{{version}}' triple, got {window._act_version.text()!r}"
    )


def test_open_accounts_passes_toast(qtbot, window, monkeypatch):
    """Phase 53 D-14: triggering Accounts passes self.show_toast as toast_callback kwarg."""
    captured: dict = {}

    class FakeAccountsDialog:
        def __init__(self, repo, toast_callback=None, parent=None):
            captured["repo"] = repo
            captured["toast_callback"] = toast_callback
            captured["parent"] = parent

        def exec(self):
            captured["exec_called"] = True
            return 0

    # Patch the symbol bound in main_window's namespace (main_window does
    # `from musicstreamer.ui_qt.accounts_dialog import AccountsDialog` at
    # module top, so this is the canonical patch target — patching
    # accounts_dialog.AccountsDialog would NOT intercept the bound name).
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.AccountsDialog",
        FakeAccountsDialog,
    )

    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    actions["Accounts"].trigger()

    assert captured.get("exec_called") is True
    assert captured["toast_callback"] == window.show_toast
    assert captured["parent"] is window
    assert captured["repo"] is window._repo


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


def test_yt_live_stream_ended_shows_dialog_not_toast(qtbot, window, fake_player, monkeypatch):
    """yt-dlp 'live stream recording is not available' (broadcaster ended the
    stream) routes to a persistent dialog instead of the transient toast."""
    from unittest import mock

    window.show_toast = mock.Mock()
    dialog_calls = mock.Mock()
    monkeypatch.setattr(window, "_show_youtube_stream_ended_dialog", dialog_calls)

    fake_player.playback_error.emit(
        "YouTube resolve failed: ERROR: [youtube] abc123: This live stream recording is not available."
    )

    dialog_calls.assert_called_once()
    window.show_toast.assert_not_called()


def test_yt_live_stream_ended_delete_route_calls_repo(qtbot, window, fake_player, fake_repo, monkeypatch):
    """Clicking 'Delete station' in the dialog → confirm → repo.delete_station."""
    from unittest import mock
    from PySide6.QtWidgets import QMessageBox

    station = _make_station()
    window.now_playing.bind_station(station)

    # First QMessageBox is the warning dialog; clickedButton returns the
    # delete button. Second QMessageBox is the confirmation; exec returns Yes.
    boxes: list = []

    real_qmessagebox = QMessageBox

    class FakeBox:
        # Re-expose the real enums so main_window.py code paths that read
        # QMessageBox.Icon / .ButtonRole / .StandardButton resolve correctly
        # after monkeypatching.
        Icon = real_qmessagebox.Icon
        ButtonRole = real_qmessagebox.ButtonRole
        StandardButton = real_qmessagebox.StandardButton

        def __init__(self, *a, **kw):
            self._buttons: list = []
            self._clicked = None
            self._exec_return = real_qmessagebox.StandardButton.Yes
            boxes.append(self)
        def setIcon(self, *_): pass
        def setWindowTitle(self, *_): pass
        def setText(self, *_): pass
        def addButton(self, label, role):
            btn = mock.Mock()
            btn._label = label
            btn._role = role
            self._buttons.append(btn)
            return btn
        def setDefaultButton(self, *_): pass
        def setStandardButtons(self, *_): pass
        def exec(self):
            if len(boxes) == 1:
                # Warning dialog: simulate clicking the destructive button.
                for b in self._buttons:
                    if b._role == real_qmessagebox.ButtonRole.DestructiveRole:
                        self._clicked = b
                return 0
            return self._exec_return  # confirmation
        def clickedButton(self):
            return self._clicked

    monkeypatch.setattr("musicstreamer.ui_qt.main_window.QMessageBox", FakeBox)

    fake_player.playback_error.emit(
        "YouTube resolve failed: This live stream recording is not available."
    )

    assert station.id in getattr(fake_repo, "_deleted_ids", [])


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


# ---------------------------------------------------------------------------
# Phase 51-05: end-to-end sibling navigation integration test (BUG-02)
# ---------------------------------------------------------------------------


def test_phase_51_sibling_navigation_end_to_end(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """Phase 51 SC #1, #2, #3, #4 end-to-end:

    - SC #1: DI.fm Ambient dialog renders 'Also on:' with a ZenRadio link
    - SC #2: Clicking the link opens EditStationDialog for the ZenRadio sibling
    - SC #3: No aa_channel_key column on Station — siblings derived from URL
    - SC #4: Cross-network failover NOT introduced — fake_player.play_calls
              remains empty (FakePlayer.play_calls at line 44 is the canonical
              spy, appended on every play() call at line 53)
    """
    from PySide6.QtWidgets import QDialog
    from musicstreamer.models import Provider
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod

    # ── ARRANGE ────────────────────────────────────────────────────────
    di_station = Station(
        id=1, name="Ambient", provider_id=1, provider_name="DI.fm",
        tags="", station_art_path=None, album_fallback_path=None,
        icy_disabled=False,
        streams=[StationStream(
            id=10, station_id=1,
            url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",
            position=1,
        )],
        last_played_at=None,
    )
    zen_station = Station(
        id=2, name="Ambient", provider_id=2, provider_name="ZenRadio",
        tags="", station_art_path=None, album_fallback_path=None,
        icy_disabled=False,
        streams=[StationStream(
            id=20, station_id=2,
            url="http://prem1.zenradio.com/zrambient?listen_key=abc",
            position=1,
        )],
        last_played_at=None,
    )

    # FakeRepo is a real class (not MagicMock); patch class methods so this
    # test stays consistent with the file's existing monkeypatch.setattr
    # convention (see test_new_station_save_refreshes_and_selects line 623+).
    # Do NOT shadow with MagicMock(...) instance attributes (W5 fix).
    # W5 fix: use monkeypatch.setattr(type(fake_repo), ...) to patch class
    # methods on the real FakeRepo class — consistent with line 623+ idiom.
    monkeypatch.setattr(type(fake_repo), "list_stations", lambda self: [di_station, zen_station])
    monkeypatch.setattr(
        type(fake_repo), "get_station",
        lambda self, sid: {1: di_station, 2: zen_station}.get(sid),
    )
    monkeypatch.setattr(
        type(fake_repo), "list_streams",
        lambda self, sid: {1: di_station.streams, 2: zen_station.streams}.get(sid, []),
    )
    monkeypatch.setattr(
        type(fake_repo), "list_providers",
        lambda self: [Provider(1, "DI.fm"), Provider(2, "ZenRadio")],
    )
    monkeypatch.setattr(
        type(fake_repo), "ensure_provider",
        lambda self, name: 1,
        raising=False,
    )

    # ── MONKEYPATCH EditStationDialog.exec ─────────────────────────────
    exec_calls: list[int] = []
    captured_sibling_label_text: list[str] = []

    def _fake_exec(self):
        exec_calls.append(self._station.id)
        if len(exec_calls) == 1:
            # First exec: this is the DI.fm dialog. Capture sibling-label
            # state and simulate a link click.
            captured_sibling_label_text.append(self._sibling_label.text())
            self._on_sibling_link_activated("sibling://2")
        return QDialog.Accepted

    monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)

    # ── ACT ────────────────────────────────────────────────────────────
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    w._on_edit_requested(di_station)

    # ── ASSERT ─────────────────────────────────────────────────────────
    # SC #2: clicking the link opened the sibling's edit dialog
    assert exec_calls == [1, 2], f"expected [1, 2], got {exec_calls}"

    # SC #1: 'Also on:' rendered with a sibling://2 link to ZenRadio
    assert len(captured_sibling_label_text) == 1
    text = captured_sibling_label_text[0]
    assert "Also on:" in text, f"sibling label missing 'Also on:': {text!r}"
    assert 'href="sibling://2"' in text, f"sibling label missing href: {text!r}"
    assert "ZenRadio" in text, f"sibling label missing ZenRadio: {text!r}"

    # SC #4: assert no playback occurred during sibling navigation.
    # FakePlayer.play_calls (line 44) records every play() call (line 53).
    # Empty list ⇒ navigation did not invoke playback. (B1 fix: replaced
    # the hasattr-guarded MagicMock check that was a silent no-op.)
    assert fake_player.play_calls == [], (
        f"SC #4 violation: player.play was called during sibling navigation; "
        f"play_calls={fake_player.play_calls!r}"
    )

    # SC #3: Station dataclass has NO aa_channel_key field — sibling
    # detection is purely URL-derived (D-01). Verify by inspecting fields.
    from dataclasses import fields as dc_fields
    station_field_names = {f.name for f in dc_fields(Station)}
    assert "aa_channel_key" not in station_field_names, \
        "SC #3 violation: Station gained aa_channel_key field — D-01 says no schema change"


# ---------------------------------------------------------------------------
# Phase 64 / SC #2 / D-02: sibling click switches active playback via the
# canonical _on_station_activated chain (delegating slot)
# ---------------------------------------------------------------------------


def test_sibling_click_switches_playback_via_main_window(qtbot, monkeypatch):
    """Phase 64 / SC #2: clicking an 'Also on:' link in NowPlayingPanel
    triggers Player.play(sibling) and Repo.update_last_played(sibling.id).

    Inverts the Phase 51 SC #4 assertion at lines 920-993 of this file:
    Phase 51's navigate-to-sibling test asserts fake_player.play_calls == []
    (dialog flow does NOT touch playback). Phase 64's panel flow DOES change
    playback — that is the entire point of the phase per ROADMAP SC #2.
    """
    # Two AA stations with the same channel key on different networks.
    di_station = Station(
        id=1,
        name="Ambient",
        provider_id=1,
        provider_name="DI.fm",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=10,
                station_id=1,
                url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",
                position=1,
            )
        ],
    )
    zen_station = Station(
        id=2,
        name="Ambient",
        provider_id=2,
        provider_name="ZenRadio",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=20,
                station_id=2,
                url="http://prem1.zenradio.com/zrambient?listen_key=abc",
                position=1,
            )
        ],
    )

    fake_player = FakePlayer()
    fake_repo = FakeRepo(stations=[di_station, zen_station])

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    # Bind to DI.fm first (simulates the user activating it from the list).
    w._on_station_activated(di_station)
    # Reset spies to isolate the sibling click's effects.
    fake_player.play_calls.clear()
    fake_repo._last_played_ids = []

    # Drive the panel-side click handler directly. The Plan 02 panel test
    # already asserts that this emits sibling_activated(zen_station). This
    # integration test asserts the MainWindow handler picks up the signal
    # and runs the canonical activation chain.
    w.now_playing._on_sibling_link_activated("sibling://2")

    # Phase 64 / SC #2: playback DID switch. (Inverts Phase 51 SC #4.)
    assert fake_player.play_calls == [zen_station]
    # update_last_played was called with the sibling id.
    assert fake_repo._last_played_ids == [2]
    # Bound station is now the sibling (delegates through bind_station).
    assert w.now_playing._station is zen_station


# ----------------------------------------------------------------------
# Phase 67 / SIM-01..SIM-12: Similar Stations integration
# ----------------------------------------------------------------------


def test_show_similar_action_is_checkable(qtbot, fake_player, fake_repo):
    """Phase 67 / SIM-01 / S-01 / M-01: hamburger 'Show similar stations'
    QAction exists, is checkable, and initial checked state reflects
    repo setting (default '0' -> False). Mirrors
    test_stats_action_is_checkable at line 568."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert hasattr(w, "_act_show_similar")
    assert w._act_show_similar.isCheckable() is True
    assert w._act_show_similar.isChecked() is False


def test_show_similar_action_initial_checked_when_setting_is_1(qtbot, fake_player):
    """Phase 67 / SIM-01 / S-01: if repo has 'show_similar_stations' = '1',
    action starts checked. Mirrors
    test_stats_action_initial_checked_when_setting_is_1 at line 577."""
    repo = FakeRepo(stations=[_make_station()], settings={"show_similar_stations": "1"})
    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)
    assert w._act_show_similar.isChecked() is True


def test_show_similar_toggle_persists_and_toggles_panel(qtbot, fake_player, fake_repo):
    """Phase 67 / SIM-01 + SIM-02 / S-01, M-01: triggering the action persists
    '1'/'0' AND flips the panel's _similar_container visibility accordingly.

    CRITICAL invariant (Pitfall 4): after each trigger,
    w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden()).

    Mirrors test_stats_toggle_persists_and_toggles_panel at line 587.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Initial: unchecked, container hidden
    assert w._act_show_similar.isChecked() is False
    assert w.now_playing._similar_container.isHidden() is True

    # Trigger ON
    w._act_show_similar.trigger()
    assert w._act_show_similar.isChecked() is True
    assert fake_repo.get_setting("show_similar_stations", "0") == "1"
    assert w.now_playing._similar_container.isHidden() is False
    # Invariant: action checked state matches container visibility
    assert w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden())

    # Trigger OFF
    w._act_show_similar.trigger()
    assert w._act_show_similar.isChecked() is False
    assert fake_repo.get_setting("show_similar_stations", "0") == "0"
    assert w.now_playing._similar_container.isHidden() is True
    # Invariant: action checked state matches container visibility
    assert w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden())


def test_show_similar_default_off_hides_container(qtbot, fake_player, fake_repo):
    """Phase 67 / SIM-02 / S-01: default settings (no 'show_similar_stations') →
    _similar_container hidden after MainWindow.__init__ completes.

    Initial-state push at __init__ time must run during construction.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.now_playing._similar_container.isHidden() is True


def test_similar_link_switches_playback_via_main_window(qtbot):
    """Phase 67 / SIM-08: clicking a similar-station link triggers Player.play(B)
    and Repo.update_last_played(B.id), and bound station switches to B.

    Mirrors test_sibling_click_switches_playback_via_main_window at line 1055.
    Uses same-provider stations (not AA cross-network siblings) — Phase 67 uses
    provider/tag matching, not AA channel keys.
    """
    station_a = Station(
        id=1,
        name="Station A",
        provider_id=1,
        provider_name="P1",
        tags="rock",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=10,
                station_id=1,
                url="http://example.com/station_a",
                position=1,
            )
        ],
    )
    station_b = Station(
        id=2,
        name="Station B",
        provider_id=1,
        provider_name="P1",
        tags="rock",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=20,
                station_id=2,
                url="http://example.com/station_b",
                position=1,
            )
        ],
    )

    fake_player = FakePlayer()
    fake_repo = FakeRepo(stations=[station_a, station_b])

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    # Bind to station A first (simulates user activating it from list).
    w._on_station_activated(station_a)
    # Reset spies to isolate the similar-link click's effects.
    fake_player.play_calls.clear()
    fake_repo._last_played_ids = []

    # Drive the panel-side click handler directly (similar:// prefix, not sibling://).
    w.now_playing._on_similar_link_activated("similar://2")

    # Phase 67 / SIM-08: playback DID switch to station B.
    assert fake_player.play_calls == [station_b]
    # update_last_played was called with station B's id.
    assert fake_repo._last_played_ids == [2]
    # Bound station is now station B (delegates through bind_station).
    assert w.now_playing._station is station_b


def test_no_lambda_on_similar_signal_connections(qtbot):
    """Phase 67 / QA-05: similar_activated and _act_show_similar.toggled
    connections must use bound methods (no self-capturing lambdas).

    Structural: greps the MainWindow source for the literal text 'lambda'
    on each Phase 67 .connect line. Mirrors
    test_buffer_percent_bound_method_connect_no_lambda at line 609-628."""
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod

    src = inspect.getsource(mw_mod.MainWindow)

    targets = ["similar_activated.connect", "_act_show_similar.toggled.connect"]
    found = {t: False for t in targets}
    for line in src.splitlines():
        for target in targets:
            if target in line:
                found[target] = True
                assert "lambda" not in line, (
                    f"QA-05 violated — lambda found on {target} line: {line!r}"
                )
    for target, was_found in found.items():
        assert was_found, f"{target} not found in MainWindow source"


# === Phase 68: Live Stream Detection (DI.fm) ===


def test_aa_poll_loop_started_in_init_when_key_present(qtbot, fake_player, fake_repo):
    """Phase 68 / B-03: MainWindow.__init__ starts AA poll loop when listen key is saved."""
    fake_repo._settings["audioaddict_listen_key"] = "testkey"
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.now_playing.is_aa_poll_active() is True


def test_aa_poll_loop_not_started_in_init_without_key(qtbot, fake_player, fake_repo):
    """Phase 68 / B-03 / N-01: MainWindow.__init__ does NOT start poll when key absent."""
    # fake_repo has no audioaddict_listen_key by default
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.now_playing.is_aa_poll_active() is False


def test_check_and_start_aa_poll_after_dialog_close(qtbot, fake_player, fake_repo):
    """Phase 68 / B-04: _check_and_start_aa_poll starts poll after key is saved."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.now_playing.is_aa_poll_active() is False
    fake_repo._settings["audioaddict_listen_key"] = "newkey"
    w._check_and_start_aa_poll()
    assert w.now_playing.is_aa_poll_active() is True


def test_live_status_toast_wired_to_show_toast(qtbot, fake_player, fake_repo):
    """Phase 68 / T-01 / QA-05: live_status_toast signal must route to MainWindow.show_toast."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    toasts = []
    original = w.show_toast
    w.show_toast = lambda t, d=3000: toasts.append(t) or original(t, d)  # type: ignore[method-assign]
    w.now_playing.live_status_toast.emit("Test live message")
    assert toasts == ["Test live message"]


def test_no_lambda_on_live_status_toast_connection(qtbot, fake_player, fake_repo):
    """Phase 68 / QA-05 structural: live_status_toast must use bound method, not lambda."""
    from pathlib import Path
    import musicstreamer.ui_qt.main_window as mw_mod
    src = Path(mw_mod.__file__).read_text()
    assert "live_status_toast.connect(self.show_toast)" in src
    assert "live_status_toast.connect(lambda" not in src


def test_aa_poll_stopped_in_close_event(qtbot, fake_player, fake_repo):
    """Phase 68 / B-03 closeEvent: closing MainWindow stops the AA poll loop."""
    fake_repo._settings["audioaddict_listen_key"] = "k"
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w.now_playing.is_aa_poll_active() is True
    w.close()
    assert w.now_playing.is_aa_poll_active() is False


# === Phase 70: Hi-Res Audio Caps Fan-Out ===


def _make_repo_with_stream():
    """Return a (Repo, stream_id, station_id) tuple backed by an in-memory SQLite DB.

    Used by Phase 70 tests that need a real repo.con.execute for the stream lookup.
    """
    import sqlite3
    from musicstreamer.repo import Repo, db_init

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    repo = Repo(con)

    # Insert a station with one FLAC stream.
    con.execute(
        "INSERT INTO stations(id, name, provider_id, tags, station_art_path, album_fallback_path,"
        " icy_disabled, last_played_at, is_favorite) VALUES (?,?,?,?,?,?,?,?,?)",
        (1, "Test Station", None, "", None, None, 0, None, 0),
    )
    con.commit()
    stream_id = repo.insert_stream(
        station_id=1,
        url="http://test.example.com/stream",
        label="FLAC 1411",
        quality="hi",
        position=1,
        stream_type="icecast",
        codec="FLAC",
        bitrate_kbps=1411,
        sample_rate_hz=0,
        bit_depth=0,
    )
    return repo, stream_id, 1


def test_quality_map_changed_signal_exists_on_class():
    """Phase 70 / DS-01: MainWindow must declare quality_map_changed at class scope."""
    from musicstreamer.ui_qt.main_window import MainWindow as MW
    assert hasattr(MW, "quality_map_changed"), "quality_map_changed Signal missing from MainWindow class"


def test_audio_caps_detected_connect_wired(qtbot, fake_player, fake_repo):
    """Phase 70 / DS-01: audio_caps_detected must be connected in MainWindow.__init__.

    Verifies via source inspection that the literal 'audio_caps_detected.connect' is
    present in MainWindow's __init__ — the Phase 70-00 grep gate requirement.
    """
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod
    src = inspect.getsource(mw_mod.MainWindow.__init__)
    assert "audio_caps_detected.connect" in src, (
        "audio_caps_detected.connect must appear in MainWindow.__init__"
    )
    assert "QueuedConnection" in src, (
        "Explicit QueuedConnection must appear near audio_caps_detected.connect in __init__"
    )


def test_on_audio_caps_detected_db_write_before_fanout():
    """Phase 70 / Pitfall 4 / D-04: in _on_audio_caps_detected, repo.update_stream
    reference must appear LEXICALLY BEFORE quality_map_changed.emit and
    _refresh_quality_badge and update_quality_map.

    This is the DB-write-first / fan-out-second invariant.
    """
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod

    lines = inspect.getsourcelines(mw_mod.MainWindow._on_audio_caps_detected)[0]
    line_texts = [ln.rstrip() for ln in lines]

    # Find the update_stream call line and the first fan-out line.
    update_idx = next(
        (i for i, ln in enumerate(line_texts) if "update_stream(" in ln),
        None,
    )
    fanout_idx = next(
        (i for i, ln in enumerate(line_texts)
         if "quality_map_changed.emit" in ln
         or "_refresh_quality_badge" in ln
         or "update_quality_map" in ln),
        None,
    )

    assert update_idx is not None, "update_stream call not found in _on_audio_caps_detected"
    assert fanout_idx is not None, "fan-out call not found in _on_audio_caps_detected"
    assert update_idx < fanout_idx, (
        f"DB write (line {update_idx}) must precede fan-out (line {fanout_idx})"
    )


def test_on_audio_caps_detected_writes_db_and_emits_quality_map(qtbot, fake_player):
    """Phase 70 / DS-01: _on_audio_caps_detected writes sample_rate_hz/bit_depth to DB
    and then emits quality_map_changed with a non-empty dict.

    Uses a real in-memory Repo so repo.con.execute, list_streams, update_stream,
    and list_stations are all exercised end-to-end (DB-write-first invariant).
    """
    repo, stream_id, station_id = _make_repo_with_stream()

    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)

    received_maps: list[dict] = []
    w.quality_map_changed.connect(lambda m: received_maps.append(m))

    # Fire the slot directly (no cross-thread queuing needed in test).
    w._on_audio_caps_detected(stream_id, 96000, 24)

    # DB must have been updated.
    updated = repo.list_streams(station_id)
    assert len(updated) == 1
    assert updated[0].sample_rate_hz == 96000
    assert updated[0].bit_depth == 24

    # quality_map_changed must have fired.
    assert len(received_maps) == 1
    assert station_id in received_maps[0]
    assert received_maps[0][station_id] == "hires"


def test_on_audio_caps_detected_idempotent(qtbot, fake_player):
    """Phase 70 / DS-01: second emit with same stream_id + rate + depth is a no-op
    (idempotency cache prevents redundant DB writes).
    """
    repo, stream_id, station_id = _make_repo_with_stream()

    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)

    # Spy on update_stream to count calls.
    original_update = repo.update_stream
    call_count = [0]
    def counting_update(*args, **kwargs):
        call_count[0] += 1
        return original_update(*args, **kwargs)
    repo.update_stream = counting_update  # type: ignore[method-assign]

    # First emit — should call update_stream once.
    w._on_audio_caps_detected(stream_id, 96000, 24)
    assert call_count[0] == 1

    # Second emit with same args — must NOT call update_stream (idempotency cache).
    w._on_audio_caps_detected(stream_id, 96000, 24)
    assert call_count[0] == 1, "Second emit with same args must be a no-op (idempotency)"


def test_on_audio_caps_detected_stream_deleted_race(qtbot, fake_player):
    """Phase 70 / T-70-14: if stream is deleted between caps-emit and slot-fire,
    the slot must NOT raise and must NOT update the cache.
    """
    repo, stream_id, station_id = _make_repo_with_stream()

    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)

    # Delete the stream to simulate the race.
    repo.delete_stream(stream_id)

    # Should be a silent no-op — no exception.
    w._on_audio_caps_detected(stream_id, 96000, 24)

    # Cache must NOT have been updated (stream was absent).
    assert stream_id not in w._last_quality_payload


def test_on_audio_caps_detected_fanout_guarded_pre_70_06(qtbot, fake_player):
    """Phase 70 / forward-compat: slot does NOT raise if NowPlayingPanel lacks
    _refresh_quality_badge (pre-Plan 70-06 state).
    """
    repo, stream_id, station_id = _make_repo_with_stream()
    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)

    # Confirm NowPlayingPanel does NOT yet have _refresh_quality_badge (pre-70-06).
    assert not hasattr(w.now_playing, "_refresh_quality_badge"), (
        "If NowPlayingPanel already has _refresh_quality_badge, "
        "this test is no longer relevant (Plan 70-06 has shipped)"
    )

    # Must not raise even without the method present.
    w._on_audio_caps_detected(stream_id, 44100, 16)


def test_last_quality_payload_initialized_in_init(qtbot, fake_player, fake_repo):
    """Phase 70 / DS-01: _last_quality_payload must be initialized as empty dict in __init__."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert hasattr(w, "_last_quality_payload")
    assert isinstance(w._last_quality_payload, dict)
    assert w._last_quality_payload == {}
