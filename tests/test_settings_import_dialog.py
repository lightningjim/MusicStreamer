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


def test_commit_error_shows_toast_and_reenables_button(qtbot, preview, monkeypatch):
    """UI-REVIEW fix #3: when commit_import raises, the worker must surface
    the failure via toast and the Import button must re-enable so the user
    can retry. Previously the worker's except branch was marked
    `# pragma: no cover`; this test exercises that path end-to-end."""
    toasts: list[str] = []

    def _boom(*_args, **_kwargs):
        raise RuntimeError("disk full")

    # Patch at the location the worker resolves the symbol.
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.commit_import", _boom
    )

    dlg = SettingsImportDialog(preview, toasts.append)
    qtbot.addWidget(dlg)
    assert dlg._import_btn.isEnabled()

    # _on_import constructs and starts the commit worker (merge mode: no modal).
    dlg._on_import()
    # Wait for the worker thread to finish so both error and (native QThread)
    # finished signals have been delivered.
    dlg._commit_worker.wait(3000)
    qtbot.waitUntil(
        lambda: any(t.startswith("Import failed") for t in toasts),
        timeout=2000,
    )

    error_toasts = [t for t in toasts if t.startswith("Import failed")]
    assert error_toasts, f"expected 'Import failed' toast, got {toasts!r}"
    assert "disk full" in error_toasts[0]
    assert dlg._import_btn.isEnabled()
