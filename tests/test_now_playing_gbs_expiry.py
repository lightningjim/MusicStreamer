"""Phase 87.1 Plan 03: NowPlayingPanel — inline GBS session-expiry prompt tests.

Five tests exercising the inline _gbs_expiry_widget show/hide lifecycle:
  - GBS-AUTH-EXP-01: prompt shows on auth_expired, hides on relogin success
  - GBS-AUTH-EXP-01/D-04: poll timer resumes after successful relogin
  - GBS-AUTH-EXP-03/D-02: prompt stays visible on cancel (non-dismissive)
  - GBS-AUTH-EXP-01/D-02: prompt hides when user navigates away from GBS station

Phase 87.1 Plan 05 (RED, Task 1): three additional regression tests asserting that
detection events (playlist error + marquee) reveal the prompt but do NOT start any
QProcess subprocess, and that the button click is the sole launch trigger.
  - GBS-AUTH-EXP-01: no auto-launch on playlist auth_expired detection
  - GBS-AUTH-EXP-02: no auto-launch on marquee auth_expired detection (USER DECISION 2026-06-17)
  - GBS-AUTH-EXP-01: button click launches exactly one subprocess after detection

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
    # isHidden() is used instead of isVisible() for unrealized-window widgets
    # per the existing test pattern (test_now_playing_panel.py:1367).
    assert panel._gbs_expiry_widget.isHidden() is False


def test_gbs_relogin_succeeded_hides_prompt(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01: _on_gbs_relogin_succeeded hides the expiry prompt.

    Fails RED because _on_gbs_relogin_succeeded does not yet exist.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_expiry_widget.isHidden() is False

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
    assert panel._gbs_expiry_widget.isHidden() is False

    panel._on_gbs_relogin_failed("Login was cancelled or failed")

    assert panel._gbs_expiry_widget.isHidden() is False  # still shown (non-dismissive)
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
    assert panel._gbs_expiry_widget.isHidden() is False

    # Navigate away — bind a non-GBS station
    panel.bind_station(_make_gbs_station(provider_name="SomaFM", name="Drone Zone"))

    assert panel._gbs_expiry_widget.isVisible() is False


# ---------------------------------------------------------------------------
# Phase 87.1 Plan 05 — Task 1 (RED): dual-path no-auto-launch regression tests
#
# These three tests assert the detection-vs-launch separation required by
# D-01 (GBS-AUTH-EXP-01), GBS-AUTH-EXP-02, and the USER DECISION 2026-06-17.
#
# RED at Task 1 commit time because:
#   - test_playlist_auth_expired_shows_prompt_no_auto_launch fails:
#       _on_gbs_playlist_error still calls notify_expiry_detected() → start_calls == 1
#   - test_marquee_auth_expired_shows_prompt_no_auto_launch fails:
#       attach_gbs_marquee_worker wires auth_expired → notify_expiry_detected → start_calls == 1
# ---------------------------------------------------------------------------

def _make_qprocess_patcher(monkeypatch):
    """Return start_calls list after patching QProcess.start and _make_oauth_launch_args.

    Patches QProcess.start to append to start_calls (no real subprocess).
    Patches musicstreamer.subprocess_utils._make_oauth_launch_args to return fake args.
    Mirrors the pattern from tests/test_gbs_relogin_handler.py lines 44-49.
    """
    from PySide6.QtCore import QProcess
    start_calls: list[int] = []
    monkeypatch.setattr(QProcess, "start", lambda self, prog, args: start_calls.append(1))
    monkeypatch.setattr(
        "musicstreamer.subprocess_utils._make_oauth_launch_args",
        lambda mode: ("fake_prog", ["--mode", mode]),
    )
    return start_calls


def test_playlist_auth_expired_shows_prompt_no_auto_launch(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01: playlist auth_expired reveals the prompt but starts ZERO subprocesses.

    Detection must not auto-launch the oauth_helper. The launch is user-gated on
    _on_gbs_relogin_clicked (D-01 / GBS-AUTH-EXP-01).

    RED reason: _on_gbs_playlist_error auth_expired branch still calls
    notify_expiry_detected() → start_calls == 1.
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    start_calls = _make_qprocess_patcher(monkeypatch)

    panel._on_gbs_playlist_error(5, "auth_expired")

    assert panel._gbs_expiry_widget.isHidden() is False, (
        "_gbs_expiry_widget must be revealed after auth_expired detection"
    )
    assert len(start_calls) == 0, (
        f"Expected ZERO QProcess.start calls on detection; got {len(start_calls)}. "
        "Detection must not auto-launch the oauth_helper (D-01 / GBS-AUTH-EXP-01)."
    )


def test_marquee_auth_expired_shows_prompt_no_auto_launch(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-02: marquee auth_expired reveals the prompt but starts ZERO subprocesses.

    USER DECISION 2026-06-17: the marquee surfaces the inline prompt (does NOT no-op,
    does NOT auto-launch). Gap closure for 87.1-HUMAN-UAT.md Test 1 (major, GBS-AUTH-EXP-02).

    RED reason: attach_gbs_marquee_worker wires worker.auth_expired directly to
    handler.notify_expiry_detected → start_calls == 1 on signal emit.
    """
    # USER DECISION 2026-06-17 / GBS-AUTH-EXP-02: marquee surfaces prompt, does not auto-launch
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    start_calls = _make_qprocess_patcher(monkeypatch)

    # Build a minimal marquee worker double exposing the signals that
    # attach_gbs_marquee_worker expects to connect. Using a real GbsMarqueeWorker
    # is lightest since __init__ touches no network.
    from musicstreamer.gbs_marquee import GbsMarqueeWorker
    from PySide6.QtWidgets import QApplication

    worker = GbsMarqueeWorker()
    panel.attach_gbs_marquee_worker(worker)

    # Emit auth_expired from the worker (same-thread here; QueuedConnection still
    # delivers via the event loop — processEvents() drains the queue).
    worker.auth_expired.emit()
    QApplication.processEvents()

    assert panel._gbs_expiry_widget.isHidden() is False, (
        "_gbs_expiry_widget must be revealed after marquee auth_expired signal "
        "(USER DECISION 2026-06-17 / GBS-AUTH-EXP-02)"
    )
    assert len(start_calls) == 0, (
        f"Expected ZERO QProcess.start calls on marquee detection; got {len(start_calls)}. "
        "Marquee must surface prompt only, not auto-launch (USER DECISION 2026-06-17)."
    )


def test_relogin_button_click_launches_after_detection(qtbot, tmp_path, monkeypatch):
    """GBS-AUTH-EXP-01: after detection (zero starts), button click launches exactly one subprocess.

    Proves the launch is user-gated and still works after the detection-vs-launch separation.
    _on_gbs_relogin_clicked must remain the sole caller of notify_expiry_detected (D-01).
    """
    panel = _setup_gbs_panel(qtbot, tmp_path, monkeypatch)
    start_calls = _make_qprocess_patcher(monkeypatch)

    # Detection: prompt reveals, zero subprocess starts
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert len(start_calls) == 0  # detection must not launch

    # User-gated launch: button click triggers the sole notify_expiry_detected call
    panel._on_gbs_relogin_clicked()

    assert len(start_calls) == 1, (
        f"Expected exactly 1 QProcess.start call after button click; got {len(start_calls)}. "
        "_on_gbs_relogin_clicked must remain the sole caller of notify_expiry_detected."
    )
    assert panel._gbs_relogin_btn.isEnabled() is False, (
        "_gbs_relogin_btn must be disabled while in-flight (Pitfall 5 / GBS-AUTH-EXP-01)"
    )
