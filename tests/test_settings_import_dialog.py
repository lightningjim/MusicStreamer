"""Phase 42 Plan 02: Tests for SettingsImportDialog widget."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
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


# ---------------------------------------------------------------------------
# IN-03: Import-click / replace_all confirm / import_complete emission
# ---------------------------------------------------------------------------


def test_import_click_merge_emits_import_complete(qtbot, preview, monkeypatch):
    """Clicking Import in merge mode runs the worker and emits import_complete.

    Uses a fake commit_import that succeeds silently so we can assert the
    signal without needing a real Repo/DB.
    """
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.commit_import",
        lambda *_a, **_kw: None,
    )
    # Skip the real Repo(db_connect()) call inside the worker — patch the
    # Repo constructor to a no-op sentinel so the worker thread doesn't hit
    # the filesystem.
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.Repo",
        lambda *_a, **_kw: object(),
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.db_connect",
        lambda *_a, **_kw: None,
    )

    toasts: list[str] = []
    dlg = SettingsImportDialog(preview, toasts.append)
    qtbot.addWidget(dlg)

    completed: list[bool] = []
    dlg.import_complete.connect(lambda: completed.append(True))

    dlg._on_import()
    dlg._commit_worker.wait(3000)
    qtbot.waitUntil(lambda: bool(completed), timeout=2000)

    assert completed, "import_complete signal did not fire"
    assert any(t.startswith("Import complete") for t in toasts)


def test_replace_all_confirm_cancel_does_not_start_worker(qtbot, preview, monkeypatch):
    """Replace All + user picks Cancel on the confirmation modal must NOT
    start the commit worker. The dialog stays open and the Import button
    remains enabled so the user can switch modes or retry."""
    # If commit_import is ever called, raise loudly to fail the test.
    def _should_not_be_called(*_a, **_kw):
        raise AssertionError("commit_import should not run when user cancels")

    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.commit_import",
        _should_not_be_called,
    )
    # Force the modal to return Cancel without displaying.
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.QMessageBox.warning",
        lambda *_a, **_kw: QMessageBox.Cancel,
    )

    dlg = SettingsImportDialog(preview, lambda _msg: None)
    qtbot.addWidget(dlg)
    dlg._replace_radio.setChecked(True)

    dlg._on_import()

    assert dlg._commit_worker is None, "worker should not be created on cancel"
    assert dlg._import_btn.isEnabled()


def test_replace_all_confirm_yes_starts_worker(qtbot, preview, monkeypatch):
    """Replace All + user picks Yes on the confirmation modal starts the
    commit worker. Uses a fake commit_import so the test does not touch a
    real database."""
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.commit_import",
        lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.Repo",
        lambda *_a, **_kw: object(),
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.db_connect",
        lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.QMessageBox.warning",
        lambda *_a, **_kw: QMessageBox.Yes,
    )

    toasts: list[str] = []
    dlg = SettingsImportDialog(preview, toasts.append)
    qtbot.addWidget(dlg)
    dlg._replace_radio.setChecked(True)

    dlg._on_import()
    assert dlg._commit_worker is not None
    dlg._commit_worker.wait(3000)
    qtbot.waitUntil(
        lambda: any(t.startswith("Import complete") for t in toasts),
        timeout=2000,
    )


def test_import_button_disabled_during_commit(qtbot, preview, monkeypatch):
    """While the commit worker is running, the Import button is disabled to
    prevent double-submits."""
    # Block the fake commit_import on an event so the test can observe the
    # mid-flight state before the worker completes.
    import threading
    release = threading.Event()

    def _blocking_commit(*_a, **_kw):
        release.wait(timeout=5.0)

    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.commit_import",
        _blocking_commit,
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.Repo",
        lambda *_a, **_kw: object(),
    )
    monkeypatch.setattr(
        "musicstreamer.ui_qt.settings_import_dialog.db_connect",
        lambda *_a, **_kw: None,
    )

    dlg = SettingsImportDialog(preview, lambda _msg: None)
    qtbot.addWidget(dlg)
    assert dlg._import_btn.isEnabled()

    dlg._on_import()
    # Worker is running — button should be disabled.
    assert not dlg._import_btn.isEnabled()

    # Release the worker so the test can tear down cleanly.
    release.set()
    dlg._commit_worker.wait(3000)
