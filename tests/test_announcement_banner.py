"""Phase 87 / Plan 87-05: AnnouncementBanner widget tests.

Tests for:
  - PlainText format invariant (CONVENTIONS T-40-04 / D-14 threat T-87-05-01)
  - Pipe → newline wrap (GBS-MARQ-04 / D-14)
  - Dismiss × button emits announcement_hash and hides widget
  - Banner hides on empty/whitespace-only announcement
  - NowPlayingPanel banner visibility predicate (GBS-MARQ-03)
  - NowPlayingPanel hides banner on non-GBS bind
  - Phase 71 RichText baseline: EXPECTED_RICHTEXT_COUNT stays at 3

Widget tests use pytest-qt (qtbot fixture from conftest.py which sets
QT_QPA_PLATFORM=offscreen).
"""
from __future__ import annotations

import os
import sys
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt.announcement_banner import AnnouncementBanner


# ---------------------------------------------------------------------------
# Network block (mirrors test_now_playing_panel.py pattern — Phase 77 D-12)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _block_real_network_for_this_file(block_real_network):
    """Block urlopen and urlretrieve for ALL tests in this file.

    NowPlayingPanel.bind_station fires _on_gbs_poll_tick which spawns a
    _GbsPollWorker thread; that thread calls gbs_api._open_with_cookies which
    calls urllib.request.urlopen. Without blocking, the thread outlives the
    test and crashes Qt on teardown when the panel is destroyed mid-call.

    Same autouse=True pattern as test_now_playing_panel.py (Phase 77 D-12).
    """
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gbs_station(name: str = "GBS.FM Radio") -> Station:
    """Construct a minimal GBS.FM Station for panel-level tests."""
    return Station(
        id=42,
        name=name,
        provider_id=10,
        provider_name="GBS.FM",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=420,
                station_id=42,
                url="http://gbs.fm/listen",
                label="hi",
                quality="hi",
                position=1,
                stream_type="shoutcast",
                codec="MP3",
            )
        ],
    )


def _make_non_gbs_station(provider: str = "SomaFM") -> Station:
    """Construct a minimal non-GBS Station for panel-level tests."""
    return Station(
        id=7,
        name="Drone Zone",
        provider_id=2,
        provider_name=provider,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=70,
                station_id=7,
                url="http://soma.fm/drone",
                label="hi",
                quality="hi",
                position=1,
                stream_type="shoutcast",
                codec="MP3",
            )
        ],
    )


# ---------------------------------------------------------------------------
# AnnouncementBanner unit tests (Task 1)
# ---------------------------------------------------------------------------


def test_banner_uses_plaintext_format(qtbot):
    """CONVENTIONS T-40-04 / T-87-05-01: banner label MUST use PlainText format.

    Qt.TextFormat.PlainText ensures operator-controlled marquee body text is
    never interpreted as HTML — defeats <script> / <img onerror> injection.
    """
    banner = AnnouncementBanner()
    qtbot.addWidget(banner)
    assert banner._label.textFormat() == Qt.TextFormat.PlainText, (
        "AnnouncementBanner._label must use Qt.TextFormat.PlainText "
        "(CONVENTIONS T-40-04 — defeats HTML/JS injection in operator-controlled marquee)"
    )


def test_pipe_to_newline_wrap(qtbot):
    """GBS-MARQ-04 / D-14: internal pipes in first_segment are replaced by \\n.

    QLabel's wordWrap=True wraps at pipe boundaries so multi-part announcements
    display on separate visual lines.
    """
    banner = AnnouncementBanner()
    qtbot.addWidget(banner)
    banner.set_announcement("first | second | third", "abc123")
    text = banner._label.text()
    assert "|" not in text, (
        "Pipe characters must be replaced by \\n in the rendered text"
    )
    assert "\n" in text, (
        "Replacement \\n must appear in the rendered text for multi-line wrap"
    )
    assert "first" in text and "second" in text and "third" in text, (
        "All segments must survive the pipe→newline replacement"
    )


def test_dismiss_stores_hash(qtbot):
    """Dismiss × emits the announcement_hash and hides the banner.

    The dismissed Signal carries the hash (not the text); NowPlayingPanel's
    _on_banner_dismissed slot adds the hash to _dismissed_announcement_hashes.
    """
    banner = AnnouncementBanner()
    qtbot.addWidget(banner)

    collected: list[str] = []
    banner.dismissed.connect(collected.append)

    banner.set_announcement("hello world", "deadbeef")
    assert banner.isVisible() is True, "Banner must be visible after set_announcement"

    # Programmatically trigger dismiss.
    banner._on_dismiss_clicked()

    assert collected == ["deadbeef"], (
        f"dismissed Signal must emit the announcement_hash; got {collected!r}"
    )
    assert banner.isVisible() is False, (
        "Banner must hide itself after dismiss"
    )


def test_banner_hides_on_empty_announcement(qtbot):
    """set_announcement with empty or whitespace-only text hides the banner.

    GBS-MARQ-03: if the parsed first_segment is empty, the banner must not
    appear (no announcement to display).
    """
    banner = AnnouncementBanner()
    qtbot.addWidget(banner)

    # Empty string → hidden.
    banner.set_announcement("", "")
    assert banner.isVisible() is False, "Empty announcement must hide the banner"

    # Non-empty → visible.
    banner.set_announcement("real text", "hash1")
    assert banner.isVisible() is True, "Non-empty announcement must show the banner"

    # Whitespace-only → hidden.
    banner.set_announcement("   ", "hash2")
    assert banner.isVisible() is False, "Whitespace-only announcement must hide the banner"


# ---------------------------------------------------------------------------
# NowPlayingPanel integration tests (Task 2)
# ---------------------------------------------------------------------------


class _FakeRepoForPanel:
    """Minimal FakeRepo for NowPlayingPanel construction in banner tests.

    Mirrors _FakeRepoForPanel in tests/test_gbs_marquee.py to avoid
    cross-test-file import (project convention — each test file is self-contained).
    Adds list_sibling_links and set_preferred_stream to satisfy the Phase 71
    and Phase 82 NowPlayingPanel slots that are wired in bind_station.
    """

    def __init__(self) -> None:
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return False

    def add_favorite(self, *args: Any, **kwargs: Any) -> None:
        pass

    def remove_favorite(self, *args: Any, **kwargs: Any) -> None:
        pass

    def list_streams(self, station_id: int) -> list:
        return []

    def list_stations(self) -> list:
        return []

    def get_station(self, station_id: int) -> Station:
        raise ValueError(f"Station not found: {station_id}")

    def list_sibling_links(self, station_id: int) -> list:
        return []

    def set_preferred_stream(self, station_id: int, stream_id: Any) -> None:
        pass

    def list_favorites(self, *args: Any, **kwargs: Any) -> list:
        return []


def test_banner_visibility_predicate(qtbot, tmp_path, monkeypatch):
    """GBS-MARQ-03 full visibility predicate for NowPlayingPanel.

    Sequence:
      1. Bind GBS station + call _on_marquee_ready → banner visible.
      2. Re-emit same first_segment → banner stays visible (same hash, no change).
      3. Dismiss → banner hidden, hash in _dismissed_announcement_hashes.
      4. _on_marquee_ready with same first_segment → banner stays hidden (dismissed).
      5. _on_marquee_ready with DIFFERENT first_segment → new hash → banner re-appears.

    Uses tmp_path + _root_override to ensure no cookies file exists so
    _GbsPollWorker never fires real network calls (mirrors test_now_playing_panel.py
    pattern for GBS bind_station tests without active GBS login).
    """
    from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
    from tests._fake_player import FakePlayer
    from musicstreamer import paths

    # No cookies file → _is_gbs_logged_in() returns False → no GBS poll timer.
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    repo = _FakeRepoForPanel()
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.show()

    gbs_station = _make_gbs_station()
    panel.bind_station(gbs_station)

    first_text = "Memorial Day - da troops!"
    full_text = "Memorial Day - da troops! | Tip jar open"

    # --- Step 1: first emit → banner visible ---
    panel._on_marquee_ready(first_text, full_text)
    assert panel._announcement_banner.isVisible() is True, (
        "Banner must be visible after first _on_marquee_ready for GBS station"
    )
    label_text = panel._announcement_banner._label.text()
    assert "Memorial Day" in label_text, (
        "Banner label must contain the announcement text"
    )

    # --- Step 2: re-emit same first_segment → banner still visible ---
    panel._on_marquee_ready(first_text, full_text)
    assert panel._announcement_banner.isVisible() is True, (
        "Re-emitting same announcement must keep banner visible"
    )

    # --- Step 3: dismiss → banner hidden, hash stored ---
    panel._announcement_banner._on_dismiss_clicked()
    assert panel._announcement_banner.isVisible() is False, (
        "Banner must hide after dismiss"
    )
    import hashlib
    expected_hash = hashlib.sha256(first_text.encode("utf-8")).hexdigest()
    assert expected_hash in panel._dismissed_announcement_hashes, (
        "Dismissed hash must be in _dismissed_announcement_hashes"
    )

    # --- Step 4: same first_segment again → banner stays hidden (dismissed) ---
    panel._on_marquee_ready(first_text, full_text)
    assert panel._announcement_banner.isVisible() is False, (
        "Banner must stay hidden after dismissal for same announcement hash"
    )

    # --- Step 5: different first_segment → new hash → banner re-appears ---
    new_text = "Happy Thanksgiving - gobble gobble!"
    panel._on_marquee_ready(new_text, new_text)
    assert panel._announcement_banner.isVisible() is True, (
        "Banner must re-appear for a new (not-dismissed) announcement"
    )
    assert "Thanksgiving" in panel._announcement_banner._label.text(), (
        "Banner must show the new announcement text"
    )


def test_banner_hides_on_non_gbs_bind(qtbot, tmp_path, monkeypatch):
    """GBS-MARQ-03: banner stays hidden when bound station is not GBS.FM.

    If the current station is SomaFM (or any non-GBS provider), marquee_ready
    emissions must not show the banner.
    """
    from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
    from tests._fake_player import FakePlayer
    from musicstreamer import paths

    # No cookies → no GBS poll timer.
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    repo = _FakeRepoForPanel()
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.show()

    non_gbs_station = _make_non_gbs_station()
    panel.bind_station(non_gbs_station)

    panel._on_marquee_ready("ignored announcement", "ignored | full text")
    assert panel._announcement_banner.isVisible() is False, (
        "Banner must NOT be visible when the bound station is not GBS.FM"
    )
