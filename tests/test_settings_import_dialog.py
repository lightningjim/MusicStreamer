"""Phase 42 Plan 02: Tests for SettingsImportDialog widget."""
import pytest
from PySide6.QtCore import Qt
from musicstreamer.settings_export import ImportPreview, ImportDetailRow
from musicstreamer.ui_qt.settings_import_dialog import SettingsImportDialog


@pytest.fixture
def preview():
    return ImportPreview(
        added=3, replaced=1, skipped=0, errors=0,
        detail_rows=[
            ImportDetailRow("Station A", "add"),
            ImportDetailRow("Station B", "add"),
            ImportDetailRow("Station C", "add"),
            ImportDetailRow("Station D", "replace"),
        ],
    )


def test_summary_label_shows_counts(qtbot, preview):
    toasts = []
    dlg = SettingsImportDialog(preview, toasts.append)
    qtbot.addWidget(dlg)
    assert "3 added" in dlg._summary_label.text()
    assert "1 replaced" in dlg._summary_label.text()


def test_merge_is_default_mode(qtbot, preview):
    dlg = SettingsImportDialog(preview, lambda _: None)
    qtbot.addWidget(dlg)
    assert dlg._merge_radio.isChecked()
    assert not dlg._replace_radio.isChecked()


def test_replace_warning_visibility(qtbot, preview):
    dlg = SettingsImportDialog(preview, lambda _: None)
    qtbot.addWidget(dlg)
    # isHidden() reflects the explicit hide/show state independent of parent visibility
    assert dlg._replace_warning.isHidden()
    dlg._replace_radio.setChecked(True)
    assert not dlg._replace_warning.isHidden()


def test_detail_tree_has_rows(qtbot, preview):
    dlg = SettingsImportDialog(preview, lambda _: None)
    qtbot.addWidget(dlg)
    assert dlg._detail_tree.topLevelItemCount() == 4


def test_dialog_title(qtbot, preview):
    dlg = SettingsImportDialog(preview, lambda _: None)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Import Settings"
