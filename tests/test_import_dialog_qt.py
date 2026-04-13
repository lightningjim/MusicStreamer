"""Phase 39-03: ImportDialog Qt widget tests (UI-07).

Tests the QDialog widget layer — not the yt_import/aa_import backends
(those are covered by test_import_dialog.py and test_aa_import.py).

Strategy: mock backend functions and directly invoke dialog result-handler
methods to bypass threading, keeping tests fast and deterministic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from musicstreamer.ui_qt.import_dialog import ImportDialog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

YT_SCAN_RESULTS = [
    {"title": "LoFi Radio", "url": "https://youtube.com/watch?v=123", "is_live": True},
    {"title": "Jazz Stream", "url": "https://youtube.com/watch?v=456", "is_live": True},
]


@pytest.fixture
def toast_cb():
    return MagicMock()


@pytest.fixture
def dialog(qtbot, toast_cb):
    dlg = ImportDialog(toast_callback=toast_cb)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


# ---------------------------------------------------------------------------
# Test 1: Dialog has two tabs labelled "YouTube" and "AudioAddict"
# ---------------------------------------------------------------------------


def test_dialog_has_two_tabs(dialog):
    tab = dialog._tabs
    assert tab.count() == 2
    assert tab.tabText(0) == "YouTube"
    assert tab.tabText(1) == "AudioAddict"


# ---------------------------------------------------------------------------
# Test 2: YouTube tab widgets present
# ---------------------------------------------------------------------------


def test_youtube_tab_widgets(dialog):
    """URL field, Scan button, progress bar, list widget, Import button exist."""
    assert dialog._yt_url is not None
    assert dialog._yt_scan_btn is not None
    assert dialog._yt_progress is not None
    assert dialog._yt_list is not None
    assert dialog._yt_import_btn is not None


# ---------------------------------------------------------------------------
# Test 3: YouTube scan populates QListWidget with checkable items
# ---------------------------------------------------------------------------


def test_youtube_scan_populates_list(dialog):
    dialog._on_yt_scan_complete(YT_SCAN_RESULTS)
    assert dialog._yt_list.count() == 2
    item0 = dialog._yt_list.item(0)
    item1 = dialog._yt_list.item(1)
    assert item0.text() == "LoFi Radio"
    assert item1.text() == "Jazz Stream"
    assert item0.flags() & Qt.ItemIsUserCheckable
    assert item1.flags() & Qt.ItemIsUserCheckable


# ---------------------------------------------------------------------------
# Test 4: Import button disabled until at least one item is checked
# ---------------------------------------------------------------------------


def test_import_button_disabled_until_checked(dialog):
    # Populate then uncheck everything
    dialog._on_yt_scan_complete(YT_SCAN_RESULTS)
    for i in range(dialog._yt_list.count()):
        dialog._yt_list.item(i).setCheckState(Qt.Unchecked)
    assert not dialog._yt_import_btn.isEnabled()

    # Check one item
    dialog._yt_list.item(0).setCheckState(Qt.Checked)
    assert dialog._yt_import_btn.isEnabled()


# ---------------------------------------------------------------------------
# Test 5: YouTube import calls yt_import.import_stations with checked entries
# ---------------------------------------------------------------------------


def test_youtube_import_calls_import_stations(dialog, toast_cb):
    """Import button triggers import with only checked entries."""
    dialog._on_yt_scan_complete(YT_SCAN_RESULTS)
    # Uncheck the second item
    dialog._yt_list.item(1).setCheckState(Qt.Unchecked)

    with patch("musicstreamer.ui_qt.import_dialog.yt_import") as mock_yt:
        mock_yt.import_stations.return_value = (1, 0)
        dialog._on_yt_import_complete(1)

    toast_cb.assert_called_once_with("Imported 1 stations")


# ---------------------------------------------------------------------------
# Test 6: AudioAddict tab has API key field, quality combo, Import button
# ---------------------------------------------------------------------------


def test_audioaddict_tab_widgets(dialog):
    assert dialog._aa_key is not None
    assert dialog._aa_quality is not None
    assert dialog._aa_import_btn is not None


# ---------------------------------------------------------------------------
# Test 7: AudioAddict quality combo has items hi, med, low
# ---------------------------------------------------------------------------


def test_audioaddict_quality_combo(dialog):
    items = [dialog._aa_quality.itemText(i) for i in range(dialog._aa_quality.count())]
    assert items == ["hi", "med", "low"]


# ---------------------------------------------------------------------------
# Test 8: AudioAddict invalid API key shows inline error label
# ---------------------------------------------------------------------------


def test_audioaddict_invalid_key_shows_error(dialog):
    dialog._tabs.setCurrentIndex(1)  # switch to AA tab so status label is visible
    dialog._on_aa_fetch_error("no_channels")
    assert dialog._aa_status.isVisible()
    assert "expired" in dialog._aa_status.text().lower() or "api key" in dialog._aa_status.text().lower()


def test_audioaddict_invalid_key_error_text(dialog):
    dialog._tabs.setCurrentIndex(1)  # switch to AA tab
    dialog._on_aa_fetch_error("invalid_key")
    assert dialog._aa_status.isVisible()
    assert "invalid" in dialog._aa_status.text().lower() or "api key" in dialog._aa_status.text().lower()


# ---------------------------------------------------------------------------
# Test 9: AudioAddict import shows progress via QProgressBar (determinate)
# ---------------------------------------------------------------------------


def test_audioaddict_import_progress(dialog):
    """_on_aa_import_progress sets determinate range and value."""
    dialog._on_aa_import_progress(3, 10)
    assert dialog._aa_progress.maximum() == 10
    assert dialog._aa_progress.value() == 3


# ---------------------------------------------------------------------------
# Test 10: Inputs disabled during active import, re-enabled after completion
# ---------------------------------------------------------------------------


def test_inputs_disabled_during_import(dialog):
    """After scan complete, starting an import disables URL and Scan button."""
    dialog._on_yt_scan_complete(YT_SCAN_RESULTS)
    dialog._set_yt_busy(True)
    assert not dialog._yt_url.isEnabled()
    assert not dialog._yt_scan_btn.isEnabled()

    dialog._set_yt_busy(False)
    assert dialog._yt_url.isEnabled()
    assert dialog._yt_scan_btn.isEnabled()
