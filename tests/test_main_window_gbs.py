"""Phase 60 / GBS-01a UI: hamburger menu wiring + worker flow + idempotent toasts.

Mirrors tests/ui_qt/test_main_window_node_indicator.py shape — direct MainWindow
construction with FakePlayer + FakeRepo doubles (no qtbot-injected monkeypatching
on the constructor itself). Tests exercise the GBS.FM handler methods directly
after the widget is up.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock
from typing import Optional

import pytest
from PySide6.QtCore import QObject, Signal

from musicstreamer.ui_qt.main_window import MainWindow, _GbsImportWorker


# ---------------------------------------------------------------------------
# Test doubles — minimal versions sufficient for MainWindow construction.
# Modeled on tests/ui_qt/test_main_window_node_indicator.py _FakePlayer/_FakeRepo.
# ---------------------------------------------------------------------------

class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)
    underrun_recovery_started = Signal()   # Phase 62 BUG-09
    audio_caps_detected = Signal(object)   # Phase 70 DS-01

    def __init__(self) -> None:
        super().__init__()
        self.volume: Optional[float] = None

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self, station, **kwargs) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def restore_eq_from_settings(self, repo) -> None:
        pass

    def set_eq_enabled(self, enabled: bool) -> None:
        pass

    def set_eq_profile(self, profile) -> None:
        pass

    def set_eq_preamp(self, db: float) -> None:
        pass


class _FakeRepo:
    def __init__(self) -> None:
        self._settings: dict = {}

    def list_stations(self) -> list:
        return []

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

    def add_favorite(self, *args, **kwargs) -> None:
        pass

    def remove_favorite(self, *args, **kwargs) -> None:
        pass

    def list_streams(self, station_id: int) -> list:
        return []

    def list_providers(self) -> list:
        return []

    def get_station(self, station_id: int):
        return None

    def create_station(self) -> int:
        return 1

    def delete_station(self, station_id: int) -> None:
        pass


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def main_window(qtbot):
    """Construct a MainWindow with FakePlayer + FakeRepo doubles."""
    w = MainWindow(_FakePlayer(), _FakeRepo())
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_action(window, text: str):
    for action in window._menu.actions():
        if action.text() == text:
            return action
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_add_gbs_menu_entry_exists(main_window):
    """D-02: 'Add GBS.FM' menu entry is rendered in the hamburger menu."""
    action = _find_action(main_window, "Add GBS.FM")
    assert action is not None, "Expected 'Add GBS.FM' menu entry"
    assert action.isEnabled(), "D-02b: menu entry must always be enabled"


def test_add_gbs_triggers_worker_start(main_window, monkeypatch):
    """D-02: click should start a _GbsImportWorker."""
    started = {"flag": False}
    real_init = _GbsImportWorker.__init__

    def fake_init(self, parent=None):
        real_init(self, parent=parent)

    def fake_start(self):
        started["flag"] = True

    monkeypatch.setattr(_GbsImportWorker, "__init__", fake_init)
    monkeypatch.setattr(_GbsImportWorker, "start", fake_start)
    main_window._on_gbs_add_clicked()
    assert started["flag"] is True
    assert main_window._gbs_import_worker is not None


def test_import_finished_toasts_added_on_first_call(main_window, monkeypatch):
    """D-02a: finished(1, 0) -> 'GBS.FM added' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(1, 0)
    assert captured["text"] == "GBS.FM added"
    assert main_window._gbs_import_worker is None


def test_import_finished_toasts_updated_on_refresh(main_window, monkeypatch):
    """D-02a: finished(0, 1) -> 'GBS.FM streams updated' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(0, 1)
    assert captured["text"] == "GBS.FM streams updated"


def test_import_error_auth_expired_toasts_reconnect_prompt(main_window, monkeypatch):
    """Pitfall 3: error('auth_expired') -> reconnect-via-Accounts toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("auth_expired")
    assert "session expired" in captured["text"].lower()
    assert "Accounts" in captured["text"]
    assert main_window._gbs_import_worker is None


def test_import_error_generic_toasts_failure(main_window, monkeypatch):
    """Generic error -> 'GBS.FM import failed: {msg}' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("Connection refused")
    assert "GBS.FM import failed" in captured["text"]
    assert "Connection refused" in captured["text"]


def test_import_error_long_message_truncated(main_window, monkeypatch):
    """T-60-15: long error messages are truncated to 80 chars before display."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    long_msg = "very long error " * 20  # 320 chars
    main_window._on_gbs_import_error(long_msg)
    assert "GBS.FM import failed" in captured["text"]
    # The toast text must contain the ellipsis truncation marker
    assert "…" in captured["text"]


def test_no_self_capturing_lambda_in_gbs_action():
    """QA-05 / Pitfall 10: act_gbs_add must use a bound method, not a lambda."""
    src = open(
        "musicstreamer/ui_qt/main_window.py", encoding="utf-8"
    ).read()
    # The connection line must look like:
    #   act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
    matches = re.findall(r"act_gbs_add\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_gbs_add.triggered.connect(...) line"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: {m!r}"
        assert m.strip().startswith("self."), \
            f"QA-05 expects bound method starting with 'self.', got: {m!r}"
