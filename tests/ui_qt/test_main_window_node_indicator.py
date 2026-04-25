"""Tests for the hamburger-menu Node-missing indicator (Phase 44, RUNTIME-01 D-13.3).

When MainWindow is constructed with node_runtime.available=False, the hamburger
menu must include a "Node.js: Missing" QAction (D-13 part 3 — persistent
indicator). When node_runtime.available=True, the menu must not include any
Node-related entry.

RED until Plan 02 lands musicstreamer/runtime_check.py (NodeRuntime dataclass)
AND Plan 03 wires the conditional QAction into MainWindow.__init__.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
from PySide6.QtCore import QObject, Signal

from musicstreamer.models import Station
from musicstreamer.ui_qt.main_window import MainWindow

# Lazy import: musicstreamer.runtime_check lands in Plan 02 (Wave 1).
# Tests are RED at execution (NodeRuntime missing AND MainWindow doesn't yet
# accept node_runtime kwarg) but collection stays green so Plan 01 verification
# passes. Plan 02 + Plan 03 turn these GREEN.
NodeRuntime: Any  # populated lazily inside each test


# ---------------------------------------------------------------------------
# Test doubles — minimal versions of the FakePlayer/FakeRepo from
# tests/test_main_window_integration.py. Kept in-file so this module is
# self-contained (no cross-test fixture coupling).
# ---------------------------------------------------------------------------


class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.volume: Optional[float] = None

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self, station: Station, **kwargs) -> None:
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


def _make_window(qtbot, *, node_runtime) -> MainWindow:
    w = MainWindow(_FakePlayer(), _FakeRepo(), node_runtime=node_runtime)
    qtbot.addWidget(w)
    return w


def test_hamburger_indicator_absent_when_node_available(qtbot):
    """No "Node.js" entry in the hamburger menu when Node is detected."""
    from musicstreamer.runtime_check import NodeRuntime  # lazy: Plan 02 dependency
    window = _make_window(
        qtbot, node_runtime=NodeRuntime(available=True, path="/usr/bin/node")
    )
    actions = [a.text() for a in window._menu.actions()]
    assert not any("Node.js" in t for t in actions), (
        f"unexpected Node.js entry in menu: {actions!r}"
    )


def test_hamburger_indicator_present_when_node_missing(qtbot):
    """Persistent "Node.js: Missing" entry appears when Node is absent."""
    from musicstreamer.runtime_check import NodeRuntime  # lazy: Plan 02 dependency
    window = _make_window(
        qtbot, node_runtime=NodeRuntime(available=False, path=None)
    )
    actions = [a.text() for a in window._menu.actions()]
    assert any("Node.js: Missing" in t for t in actions), (
        f"missing Node.js indicator in menu: {actions!r}"
    )
