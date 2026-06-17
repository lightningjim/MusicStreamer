"""Phase 87.1 Plan 03: NowPlayingPanel — inline GBS session-expiry prompt tests.

Five tests exercising the inline _gbs_expiry_widget show/hide lifecycle:
  - GBS-AUTH-EXP-01: prompt shows on auth_expired, hides on relogin success
  - GBS-AUTH-EXP-01/D-04: poll timer resumes after successful relogin
  - GBS-AUTH-EXP-03/D-02: prompt stays visible on cancel (non-dismissive)
  - GBS-AUTH-EXP-01/D-02: prompt hides when user navigates away from GBS station

All tests are RED at creation time (Wave 0) — _gbs_expiry_widget, _gbs_relogin_btn,
_on_gbs_relogin_succeeded, and _on_gbs_relogin_failed do not yet exist in
now_playing_panel.py.
"""
from __future__ import annotations

import os

from unittest.mock import MagicMock

import pytest
from musicstreamer import paths


# ---------------------------------------------------------------------------
# Test helpers — copied verbatim from tests/test_now_playing_panel.py:1304 and :1327
# so this file can run independently without importing module-private symbols.
# ---------------------------------------------------------------------------

def _make_gbs_station(provider_name: str = "GBS.FM", name: str = "GBS.FM"):
    """Lightweight Station-shaped object for GBS bind_station tests.

    Source: tests/test_now_playing_panel.py:1304 (_make_gbs_station)
    """
    s = MagicMock()
    s.id = 99
    s.name = name
    s.provider_name = provider_name
    s.tags = ""
    s.streams = []
    s.icy_disabled = False
    return s


class _FakeRepo:
    """Minimal repo double — mirrors FakeRepo from tests/test_now_playing_panel.py:38."""

    def __init__(self):
        self._settings = {"volume": "80"}
        self._favorites = []
        self._stations = []

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value

    def is_favorited(self, station_name, track_title):
        return False

    def add_favorite(self, station_name, provider_name, track_title, genre):
        pass

    def remove_favorite(self, station_name, track_title):
        pass

    def list_streams(self, station_id):
        return []

    def list_stations(self):
        return list(self._stations)

    def get_station(self, station_id):
        raise ValueError("Station not found")

    def list_sibling_links(self, station_id):
        return []

    def set_preferred_stream(self, station_id, stream_id):
        pass


def _construct_gbs_panel(qtbot):
    """Construct NowPlayingPanel using FakePlayer/_FakeRepo.

    Source: tests/test_now_playing_panel.py:1327 (_construct_gbs_panel)
    """
    from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
    from tests._fake_player import FakePlayer

    panel = NowPlayingPanel(FakePlayer(), _FakeRepo())
    qtbot.addWidget(panel)
    return panel


# ---------------------------------------------------------------------------
# Canonical GBS setup helper — monkeypatches worker.start and gbs_api.load_auth_context
# so bind_station does not hit the network.
# Source pattern: tests/test_now_playing_panel.py:1484-1488
# ---------------------------------------------------------------------------

def _setup_gbs_panel(qtbot, tmp_path, monkeypatch):
    """Write a fake cookie, construct the panel, stub network paths."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")

    panel = _construct_gbs_panel(qtbot)

    monkeypatch.setattr(
        "musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
        lambda self: None,
    )
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())

    panel.bind_station(_make_gbs_station())
    # Ensure token is known so _on_gbs_playlist_error passes the guard
    panel._gbs_poll_token = 5
    panel._gbs_playlist_widget.setVisible(True)
    panel._gbs_poll_timer.start()
    return panel


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_gbs_auth_expired_shows_expiry_prompt(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01: auth_expired shows _gbs_expiry_widget and hides _gbs_playlist_widget.

    Also verifies poll timer is stopped (D-04).
    Fails RED because _gbs_expiry_widget does not yet exist on the panel.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")

    assert panel._gbs_playlist_widget.isVisible() is False
    assert panel._gbs_poll_timer.isActive() is False
    assert panel._gbs_expiry_widget.isVisible() is True


def test_gbs_relogin_succeeded_hides_prompt(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01: _on_gbs_relogin_succeeded hides the expiry prompt.

    Fails RED because _on_gbs_relogin_succeeded does not yet exist.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_expiry_widget.isVisible() is True

    panel._on_gbs_relogin_succeeded()
    assert panel._gbs_expiry_widget.isVisible() is False


def test_gbs_relogin_succeeded_resumes_timer(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01/D-04: successful relogin resumes poll and resets _gbs_ajax_disabled.

    The timer should be active (or an immediate tick was kicked) after
    _on_gbs_relogin_succeeded because _refresh_gbs_visibility() re-checks
    cookies and restarts the poll.

    Fails RED because _on_gbs_relogin_succeeded does not yet exist.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_poll_timer.isActive() is False
    assert panel._gbs_ajax_disabled is True

    panel._on_gbs_relogin_succeeded()

    # Poll should resume via _refresh_gbs_visibility (timer active or immediate tick fired)
    assert panel._gbs_poll_timer.isActive() is True or not panel._gbs_ajax_disabled
    assert panel._gbs_ajax_disabled is False


def test_gbs_expiry_prompt_stays_on_cancel(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-03/D-02: relogin_failed keeps prompt visible (non-dismissive).

    Timer stays stopped. Button re-enabled for retry.
    Fails RED because _on_gbs_relogin_failed does not yet exist.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_expiry_widget.isVisible() is True

    panel._on_gbs_relogin_failed("Login was cancelled or failed")

    assert panel._gbs_expiry_widget.isVisible() is True
    assert panel._gbs_poll_timer.isActive() is False
    assert panel._gbs_relogin_btn.isEnabled() is True


def test_gbs_expiry_prompt_hides_on_station_change(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01/D-02: expiry prompt hides when user navigates to a non-GBS station.

    After expiry, bind a SomaFM station — _refresh_gbs_visibility should
    set should_show=False and hide _gbs_expiry_widget.

    Fails RED because _gbs_expiry_widget does not yet exist.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_expiry_widget.isVisible() is True

    # Navigate away — bind a non-GBS station
    panel.bind_station(_make_gbs_station(provider_name="SomaFM", name="Drone Zone"))

    assert panel._gbs_expiry_widget.isVisible() is False
