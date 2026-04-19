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

from musicstreamer.ui_qt.import_dialog import ImportDialog, _format_import_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

YT_SCAN_RESULTS = [
    {"title": "LoFi Radio", "url": "https://youtube.com/watch?v=123", "is_live": True},
    {"title": "Jazz Stream", "url": "https://youtube.com/watch?v=456", "is_live": True},
]


class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


@pytest.fixture
def fake_repo():
    return FakeRepo()


@pytest.fixture
def toast_cb():
    return MagicMock()


@pytest.fixture
def dialog(qtbot, toast_cb, fake_repo):
    dlg = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
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
        dialog._on_yt_import_complete(1, 0)

    toast_cb.assert_called_once_with("Imported 1 new")


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


# ---------------------------------------------------------------------------
# Regression (Phase 40.1-01): _YtScanWorker must pass scan_playlist results
# through unchanged. scan_playlist() already filters live entries via
# _entry_is_live() and returns dicts WITHOUT an "is_live" key; a secondary
# `e.get("is_live") is True` filter therefore drops every entry.
# ---------------------------------------------------------------------------


def test_yt_scan_passes_through(qtbot, monkeypatch, dialog):
    """Worker must emit scan_playlist results unchanged — no secondary filter.

    Mirrors real scan_playlist() output shape: dicts with title/url/provider
    only (no "is_live" key). The buggy double-filter drops both entries.
    """
    from musicstreamer.ui_qt.import_dialog import _YtScanWorker

    scan_results = [
        {"title": "Stream A", "url": "https://youtube.com/watch?v=a", "provider": "youtube"},
        {"title": "Stream B", "url": "https://youtube.com/watch?v=b", "provider": "youtube"},
    ]
    monkeypatch.setattr(
        "musicstreamer.yt_import.scan_playlist",
        lambda url: scan_results,
    )

    # Wire worker finished signal to the dialog handler that populates the list
    worker = _YtScanWorker("https://youtube.com/playlist?list=dummy")
    worker.finished.connect(dialog._on_yt_scan_complete)

    with qtbot.waitSignal(worker.finished, timeout=3000):
        worker.start()

    # Both pass-through entries must reach the QListWidget
    assert dialog._yt_list.count() == 2
    titles = {dialog._yt_list.item(i).text() for i in range(dialog._yt_list.count())}
    assert titles == {"Stream A", "Stream B"}


# ---------------------------------------------------------------------------
# Regression (Phase 40.1-03): _format_import_summary + (imported, skipped)
# signal signatures for AA and YT import workers.
# ---------------------------------------------------------------------------


def test_format_import_summary_imported_only():
    assert _format_import_summary(5, 0) == "Imported 5 new"


def test_format_import_summary_skipped_only():
    assert _format_import_summary(0, 12) == "All 12 already in library"


def test_format_import_summary_mixed():
    assert _format_import_summary(3, 2) == "Imported 3 new, 2 skipped (already in library)"


def test_aa_import_emits_imported_and_skipped(dialog, toast_cb):
    """AA handler renders mixed-case wording to inline label + toast."""
    dialog._tabs.setCurrentIndex(1)
    dialog._on_aa_import_complete(3, 7)
    assert dialog._aa_status.text() == "Imported 3 new, 7 skipped (already in library)"
    assert dialog._aa_status.isVisible() is True
    toast_cb.assert_called_once_with("Imported 3 new, 7 skipped (already in library)")


def test_aa_import_all_deduped(dialog, toast_cb):
    """AA handler renders skipped-only wording with no 'Imported 0' framing."""
    dialog._tabs.setCurrentIndex(1)
    dialog._on_aa_import_complete(0, 12)
    assert dialog._aa_status.text() == "All 12 already in library"
    assert "Imported 0" not in dialog._aa_status.text()
    toast_cb.assert_called_once_with("All 12 already in library")


def test_yt_import_emits_imported_and_skipped(dialog, toast_cb):
    """YT handler renders mixed-case wording to inline label + toast."""
    dialog._on_yt_import_complete(4, 1)
    assert dialog._yt_status.text() == "Imported 4 new, 1 skipped (already in library)"
    assert dialog._yt_status.isVisible() is True
    toast_cb.assert_called_once_with("Imported 4 new, 1 skipped (already in library)")


def test_yt_import_new_only_no_skip_clause(dialog, toast_cb):
    """YT handler renders imported-only wording without 'skipped' clause."""
    dialog._on_yt_import_complete(5, 0)
    assert dialog._yt_status.text() == "Imported 5 new"
    assert "skipped" not in dialog._yt_status.text()
    toast_cb.assert_called_once_with("Imported 5 new")


# ---------------------------------------------------------------------------
# Phase 48: AudioAddict listen-key persistence (D-01, D-03, D-08, D-09, D-11)
# ---------------------------------------------------------------------------


AA_SUCCESS_CHANNELS = [
    {"key": "jazz", "name": "Jazz", "asset_url": None},
]


def dlg_mode(dialog):
    return dialog._aa_key.echoMode()


def test_aa_key_field_masked_by_default(qtbot, toast_cb, fake_repo):
    """D-08: field uses EchoMode.Password on open — empty and prefilled both."""
    from PySide6.QtWidgets import QLineEdit

    # Empty repo
    dlg = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg)
    assert dlg._aa_key.echoMode() == QLineEdit.EchoMode.Password

    # Prefilled repo
    fake_repo.set_setting("audioaddict_listen_key", "pre-saved")
    dlg2 = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg2)
    assert dlg2._aa_key.echoMode() == QLineEdit.EchoMode.Password


def test_aa_key_prefills_from_repo_on_open(qtbot, toast_cb, fake_repo):
    """D-03: ImportDialog.__init__ reads audioaddict_listen_key into the field."""
    fake_repo.set_setting("audioaddict_listen_key", "prefilled-value")

    dlg = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg)

    assert dlg._aa_key.text() == "prefilled-value"


def test_aa_key_show_toggle_flips_echo_mode(dialog):
    """D-09 / D-10: Show toggle flips echoMode and tooltip."""
    from PySide6.QtWidgets import QLineEdit

    assert dlg_mode(dialog) == QLineEdit.EchoMode.Password
    assert dialog._aa_show_btn.toolTip() == "Show key"

    dialog._aa_show_btn.toggle()
    assert dlg_mode(dialog) == QLineEdit.EchoMode.Normal
    assert dialog._aa_show_btn.toolTip() == "Hide key"

    dialog._aa_show_btn.toggle()
    assert dlg_mode(dialog) == QLineEdit.EchoMode.Password
    assert dialog._aa_show_btn.toolTip() == "Show key"


def test_aa_key_persists_on_successful_fetch(qtbot, toast_cb, fake_repo):
    """D-01: _on_aa_fetch_complete with non-empty channels writes the setting."""
    dlg = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg)
    dlg._aa_key.setText("test-key-abc")

    # Stub _AaImportWorker construction so the slot doesn't spawn a real thread
    with patch("musicstreamer.ui_qt.import_dialog._AaImportWorker") as MockWorker:
        MockWorker.return_value = MagicMock()
        dlg._on_aa_fetch_complete(AA_SUCCESS_CHANNELS)

    assert fake_repo.get_setting("audioaddict_listen_key", "") == "test-key-abc"


def test_aa_key_does_not_persist_on_failed_fetch(qtbot, toast_cb, fake_repo):
    """D-01 negative: error slot never persists."""
    dlg = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg)
    dlg._aa_key.setText("should-not-save")

    dlg._on_aa_fetch_error("invalid_key")

    assert fake_repo.get_setting("audioaddict_listen_key", "") == ""

    # Also confirm the empty-channels defensive guard
    dlg._aa_key.setText("still-should-not-save")
    with patch("musicstreamer.ui_qt.import_dialog._AaImportWorker") as MockWorker:
        MockWorker.return_value = MagicMock()
        dlg._on_aa_fetch_complete([])  # empty list should skip the write

    assert fake_repo.get_setting("audioaddict_listen_key", "") == ""


def test_aa_key_save_reopen_readback(qtbot, toast_cb, fake_repo):
    """D-11 (primary integration): set -> persist -> close -> reopen -> readback."""
    # Dialog A
    dlg_a = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg_a)
    dlg_a._aa_key.setText("test-key-abc")

    with patch("musicstreamer.ui_qt.import_dialog._AaImportWorker") as MockWorker:
        MockWorker.return_value = MagicMock()
        dlg_a._on_aa_fetch_complete(AA_SUCCESS_CHANNELS)

    assert fake_repo.get_setting("audioaddict_listen_key", "") == "test-key-abc"
    dlg_a.close()

    # Dialog B — same repo, should see the value
    dlg_b = ImportDialog(toast_callback=toast_cb, repo=fake_repo)
    qtbot.addWidget(dlg_b)
    assert dlg_b._aa_key.text() == "test-key-abc"
