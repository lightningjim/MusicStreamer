"""Phase 39-02: DiscoveryDialog tests.

Covers UI-06: Radio-Browser.info discovery dialog — search, tag/country filters,
preview playback, save to library, error handling.

Strategy: tests call dialog result-handler methods directly (bypassing threading)
to avoid flaky thread timing. Worker construction/start is verified separately.

Security note: url_resolved preference verified in save test (T-39-04).
"""
from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QProgressBar, QTableView

from musicstreamer.ui_qt.discovery_dialog import DiscoveryDialog


# ---------------------------------------------------------------------------
# Test fixtures / doubles
# ---------------------------------------------------------------------------

FAKE_RESULTS = [
    {
        "name": "Jazz FM",
        "url": "http://jazz.mp3",
        "url_resolved": "http://jazz-resolved.mp3",
        "tags": "jazz,smooth",
        "country": "US",
        "bitrate": 128,
    }
]


class FakePlayer(QObject):
    failover = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.play_calls: List[Any] = []
        self.stop_called: bool = False

    def play(self, station, **kwargs) -> None:
        self.play_calls.append(station)

    def stop(self) -> None:
        self.stop_called = True


class FakeRepo:
    def __init__(self) -> None:
        self.insert_station_calls: List[dict] = []

    def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int:
        self.insert_station_calls.append(
            {"name": name, "url": url, "provider_name": provider_name, "tags": tags}
        )
        return 42


@pytest.fixture
def player():
    return FakePlayer()


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def toast_calls():
    return []


@pytest.fixture
def dialog(qtbot, player, repo, toast_calls):
    dlg = DiscoveryDialog(player=player, repo=repo, toast_callback=lambda msg: toast_calls.append(msg))
    qtbot.addWidget(dlg)
    return dlg


# ---------------------------------------------------------------------------
# Test 1: Dialog opens with required widgets
# ---------------------------------------------------------------------------

def test_dialog_has_search_widgets(dialog):
    """Dialog opens with search bar, tag combo, country combo, search button."""
    assert dialog._search_edit is not None
    assert dialog._tag_combo is not None
    assert dialog._country_combo is not None
    assert dialog._search_btn is not None
    assert dialog._results_table is not None


# ---------------------------------------------------------------------------
# Test 2: Tag combo populated via fetch_tags on open
# ---------------------------------------------------------------------------

def test_tag_combo_populated_on_open(qtbot, player, repo, toast_calls):
    """Tag combo populated from fetch_tags result after dialog show."""
    with patch("musicstreamer.radio_browser.fetch_tags", return_value=["jazz", "rock"]) as mock_ft, \
         patch("musicstreamer.radio_browser.fetch_countries", return_value=[("US", "United States")]):
        dlg = DiscoveryDialog(player=player, repo=repo, toast_callback=lambda msg: toast_calls.append(msg))
        qtbot.addWidget(dlg)
        # Directly call the slot that handles fetch_tags results
        dlg._on_tags_loaded(["jazz", "rock"])
        # First item should be "All Tags" (empty filter), then actual tags
        assert dlg._tag_combo.count() >= 3  # "Loading...", "All Tags", "jazz", "rock" OR just "All Tags", "jazz", "rock"
        texts = [dlg._tag_combo.itemText(i) for i in range(dlg._tag_combo.count())]
        assert "jazz" in texts
        assert "rock" in texts


# ---------------------------------------------------------------------------
# Test 3: Country combo populated via fetch_countries on open
# ---------------------------------------------------------------------------

def test_country_combo_populated_on_open(qtbot, player, repo, toast_calls):
    """Country combo populated from fetch_countries result after dialog show."""
    dlg = DiscoveryDialog(player=player, repo=repo, toast_callback=lambda msg: toast_calls.append(msg))
    qtbot.addWidget(dlg)
    dlg._on_countries_loaded([("US", "United States"), ("GB", "United Kingdom")])
    texts = [dlg._country_combo.itemText(i) for i in range(dlg._country_combo.count())]
    assert "United States" in texts
    assert "United Kingdom" in texts


# ---------------------------------------------------------------------------
# Test 4: Search button calls search_stations via worker; results populate table
# ---------------------------------------------------------------------------

def test_search_populates_table(dialog, qtbot):
    """Search results are populated in the table via the result handler."""
    # Directly call the result handler (bypasses thread)
    dialog._on_search_finished(FAKE_RESULTS)
    assert dialog._results_table.model().rowCount() == 1


# ---------------------------------------------------------------------------
# Test 5: Results table shows correct columns
# ---------------------------------------------------------------------------

def test_results_table_columns(dialog):
    """Results table shows Name, Tags, Country, Bitrate columns."""
    model = dialog._results_table.model()
    headers = [model.horizontalHeaderItem(i).text() for i in range(model.columnCount())]
    assert "Name" in headers
    assert "Tags" in headers
    assert "Country" in headers
    assert "Bitrate" in headers


# ---------------------------------------------------------------------------
# Test 6: Save action uses url_resolved (not url)
# ---------------------------------------------------------------------------

def test_save_uses_url_resolved(dialog, repo, qtbot):
    """Save action calls repo.insert_station with url_resolved, not url."""
    dialog._on_search_finished(FAKE_RESULTS)
    dialog._on_save_row(0)
    assert len(repo.insert_station_calls) == 1
    saved = repo.insert_station_calls[0]
    assert saved["url"] == "http://jazz-resolved.mp3"
    assert saved["url"] != "http://jazz.mp3"


# ---------------------------------------------------------------------------
# Test 7: Save button disabled after save (no duplicate adds)
# ---------------------------------------------------------------------------

def test_save_button_disabled_after_save(dialog, repo, qtbot):
    """Save button for a row is disabled after the first save."""
    dialog._on_search_finished(FAKE_RESULTS)
    # Get the save button for row 0
    save_btn = dialog._get_save_button(0)
    assert save_btn is not None
    assert save_btn.isEnabled()
    dialog._on_save_row(0)
    assert not save_btn.isEnabled()


# ---------------------------------------------------------------------------
# Test 8: Preview play calls player.play with a temporary Station
# ---------------------------------------------------------------------------

def test_preview_play_calls_player(dialog, player, qtbot):
    """Clicking play on a row calls player.play with a temporary Station object."""
    from musicstreamer.models import Station
    dialog._on_search_finished(FAKE_RESULTS)
    dialog._on_play_row(0)
    assert len(player.play_calls) == 1
    played_station = player.play_calls[0]
    assert isinstance(played_station, Station)
    assert played_station.id == -1
    assert played_station.name == "Jazz FM"
    # Stream URL should use url_resolved
    assert played_station.streams[0].url == "http://jazz-resolved.mp3"


# ---------------------------------------------------------------------------
# Test 9: Search error shows toast feedback
# ---------------------------------------------------------------------------

def test_search_error_shows_toast(dialog, toast_calls, qtbot):
    """Search error triggers toast_callback with error message."""
    dialog._on_search_error("Connection refused")
    assert len(toast_calls) == 1
    assert "Connection refused" in toast_calls[0] or "error" in toast_calls[0].lower()


# ---------------------------------------------------------------------------
# Phase 40.1-02: Play buttons use icons (D-03/D-04/D-05)
# ---------------------------------------------------------------------------

def test_play_button_uses_icon(dialog, qtbot):
    """Play button in results table is icon-only (no text) with accessibleName."""
    dialog._on_search_finished(FAKE_RESULTS)
    btn = dialog._play_buttons[0]
    assert btn.text() == ""
    assert not btn.icon().isNull()
    assert btn.accessibleName() == "Play preview"


def test_play_button_toggles_icon_on_click(dialog, qtbot):
    """Clicking play toggles icon + accessibleName between Play/Stop preview."""
    dialog._on_search_finished(FAKE_RESULTS)
    btn = dialog._play_buttons[0]
    key0 = btn.icon().cacheKey()

    # Start preview
    dialog._on_play_row(0)
    assert dialog._previewing_row == 0
    assert btn.icon().cacheKey() != key0
    assert btn.accessibleName() == "Stop preview"

    # Stop preview
    dialog._on_play_row(0)
    assert dialog._previewing_row == -1
    assert btn.accessibleName() == "Play preview"
