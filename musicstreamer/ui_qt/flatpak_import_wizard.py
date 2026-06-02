"""Phase 86 Plan 02: FlatpakImportWizard — first-launch settings import dialog.

Reuses the SettingsImportDialog layout + _ImportCommitWorker threading model
(analog: musicstreamer/ui_qt/settings_import_dialog.py) with these additions:

1. Self-building preview: on Open, opens a Repo against the narrow :ro host
   path (_HOST_DATA_DIR), calls settings_export.build_zip to a temp ZIP, then
   settings_export.preview_import to produce the ImportPreview. This reuses the
   Phase 25 import path verbatim (D-04).

2. Import is copy-don't-delete (D-02): the host path is mounted :ro by Flatpak;
   nothing can write back. The original ~/.local/share/musicstreamer/ stays intact.

3. Offer-once (D-03): calls flatpak_first_launch.write_offered_flag() on both
   dismiss and successful completion so the wizard never auto-opens again.

4. Manual entry point: constructor takes no preview argument — the wizard is also
   invokable from a menu for manual re-import ("Import from host settings…").

Security:
    T-86-04: All import routes through settings_export.preview_import +
    commit_import, both of which call _validate_zip_members() internally
    (path-traversal guard, re-validated at commit time for WR-02 TOCTOU).
    No direct zipfile.extractall/extract calls here.

Threading:
    _ImportCommitWorker runs commit_import on a background thread.
    Result signals use Qt.QueuedConnection to reach the main thread.
"""
from __future__ import annotations

import os
import tempfile
from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from musicstreamer import flatpak_first_launch
from musicstreamer.repo import Repo, db_connect
from musicstreamer.settings_export import (
    ImportPreview,
    build_zip,
    commit_import,
    preview_import,
)
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR


# ---------------------------------------------------------------------------
# Background worker (mirrors SettingsImportDialog._ImportCommitWorker)
# ---------------------------------------------------------------------------


class _ImportCommitWorker(QThread):
    """Runs commit_import on a background thread.

    Custom signals named commit_done / commit_error to avoid shadowing
    QThread.finished — same reasoning as SettingsImportDialog._ImportCommitWorker.
    """

    commit_done = Signal()
    commit_error = Signal(str)

    def __init__(self, preview: ImportPreview, mode: str, parent=None):
        super().__init__(parent)
        self._preview = preview
        self._mode = mode

    def run(self) -> None:
        try:
            repo = Repo(db_connect())
            commit_import(self._preview, repo, self._mode)
            self.commit_done.emit()
        except Exception as exc:
            self.commit_error.emit(str(exc))


# ---------------------------------------------------------------------------
# Background worker: builds the import preview from the host :ro path
# ---------------------------------------------------------------------------


class _BuildPreviewWorker(QThread):
    """Opens a Repo against the host path, builds a temp ZIP, produces ImportPreview.

    D-04: routes through build_zip + preview_import — the Phase 25 path verbatim.
    _validate_zip_members is called internally by preview_import (T-86-04).
    """

    preview_ready = Signal(object)  # ImportPreview
    preview_error = Signal(str)

    def __init__(self, host_data_dir: str, sandbox_db_path: str, parent=None):
        super().__init__(parent)
        self._host_data_dir = host_data_dir
        self._sandbox_db_path = sandbox_db_path

    def run(self) -> None:
        tmp_zip: Optional[str] = None
        try:
            # Open a Repo against the :ro host data dir to read existing data.
            host_db = os.path.join(self._host_data_dir, "musicstreamer.sqlite3")
            import sqlite3

            host_con = sqlite3.connect(host_db)
            host_con.row_factory = sqlite3.Row
            host_repo = Repo(host_con)

            # Export to a temp ZIP (Phase 25 build_zip path, D-04).
            tmp_fd, tmp_zip = tempfile.mkstemp(suffix=".zip", prefix="musicstreamer-fp-import-")
            os.close(tmp_fd)
            build_zip(host_repo, tmp_zip)
            host_con.close()

            # Open the sandbox Repo for preview (to detect add/replace splits).
            sandbox_con = sqlite3.connect(self._sandbox_db_path)
            sandbox_con.row_factory = sqlite3.Row
            sandbox_repo = Repo(sandbox_con)

            # preview_import calls _validate_zip_members internally (T-86-04).
            preview = preview_import(tmp_zip, sandbox_repo)
            sandbox_con.close()

            self.preview_ready.emit(preview)
        except Exception as exc:
            self.preview_error.emit(str(exc))
        finally:
            # Do NOT delete the temp ZIP yet — commit_import will read it.
            # The wizard stores tmp_zip and deletes it after commit.
            pass


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class FlatpakImportWizard(QDialog):
    """First-launch import wizard: reuses Phase 25 settings-export ZIP flow.

    Constructor takes no preview argument.  On show(), it builds the preview
    from the host :ro mount via a background worker, then displays the standard
    summary + mode selector UI.

    offer-once (D-03): write_offered_flag() is called on any dismiss path
    (cancel, X button, successful import) so the wizard never auto-prompts again.

    Manual access: the dialog is fully functional when opened from a menu item
    in addition to the automatic first-launch path.
    """

    import_complete = Signal()

    def __init__(
        self,
        sandbox_db_path: str,
        toast_callback: Optional[Callable[[str], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._sandbox_db_path = sandbox_db_path
        self._toast: Callable[[str], None] = toast_callback or (lambda _: None)
        self._preview: Optional[ImportPreview] = None
        self._tmp_zip: Optional[str] = None
        self._commit_worker: Optional[_ImportCommitWorker] = None
        self._build_worker: Optional[_BuildPreviewWorker] = None

        self.setWindowTitle("Import Settings from Host")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(16)

        # Show a loading indicator until the preview is ready.
        self._loading_label = QLabel("Scanning host settings…")
        self._loading_label.setTextFormat(Qt.PlainText)
        self._layout.addWidget(self._loading_label)

        # Build the import UI (hidden until preview ready).
        self._build_import_ui()

        # Button box is always visible; OK disabled until preview loads.
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._btn_box.button(QDialogButtonBox.Ok).setText("Import")
        self._import_btn = self._btn_box.button(QDialogButtonBox.Ok)
        self._import_btn.setEnabled(False)
        self._btn_box.accepted.connect(self._on_import)
        self._btn_box.rejected.connect(self._on_cancel)
        self._layout.addWidget(self._btn_box)

        # Start background preview build.
        self._start_preview_build()

    # ------------------------------------------------------------------
    # Import UI construction (mirrors SettingsImportDialog layout)
    # ------------------------------------------------------------------

    def _build_import_ui(self) -> None:
        """Build the mode selector, summary label, detail tree (hidden until preview)."""
        # Section 1: Mode selector
        mode_label = QLabel("Import mode:")
        mode_label.setTextFormat(Qt.PlainText)
        font_10 = QFont()
        font_10.setPointSize(10)
        mode_label.setFont(font_10)
        mode_label.setVisible(False)
        self._mode_label = mode_label
        self._layout.addWidget(mode_label)

        self._merge_radio = QRadioButton(
            "Merge — add new stations and update matches"
        )
        self._replace_radio = QRadioButton(
            "Replace All — wipe library and restore from host settings"
        )
        self._merge_radio.setChecked(True)
        self._merge_radio.setVisible(False)
        self._replace_radio.setVisible(False)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._merge_radio, 0)
        self._mode_group.addButton(self._replace_radio, 1)

        self._layout.addWidget(self._merge_radio)
        self._layout.addWidget(self._replace_radio)

        self._replace_warning = QLabel(
            "This will replace all stations, streams, and favorites."
        )
        self._replace_warning.setTextFormat(Qt.PlainText)
        self._replace_warning.setStyleSheet(
            f"color: {ERROR_COLOR_HEX}; font-size: 9pt;"
        )
        self._replace_warning.setVisible(False)
        self._replace_radio.toggled.connect(
            lambda checked: self._replace_warning.setVisible(checked)
        )
        self._layout.addWidget(self._replace_warning)

        # Section 2: Summary counts + detail tree
        self._summary_label = QLabel("")
        self._summary_label.setTextFormat(Qt.PlainText)
        summary_font = QFont()
        summary_font.setPointSize(13)
        summary_font.setWeight(QFont.Weight.DemiBold)
        self._summary_label.setFont(summary_font)
        self._summary_label.setVisible(False)
        self._layout.addWidget(self._summary_label)

        self._toggle_btn = QPushButton("Show details")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet("border: none;")
        self._toggle_btn.clicked.connect(self._toggle_details)
        self._toggle_btn.setVisible(False)
        self._layout.addWidget(self._toggle_btn)

        self._detail_tree = QTreeWidget()
        self._detail_tree.setColumnCount(2)
        self._detail_tree.setHeaderLabels(["Station", "Action"])
        self._detail_tree.setMaximumHeight(200)
        self._detail_tree.setVisible(False)
        self._layout.addWidget(self._detail_tree)

    # ------------------------------------------------------------------
    # Background preview build
    # ------------------------------------------------------------------

    def _start_preview_build(self) -> None:
        """Launch the background worker to build the ImportPreview."""
        self._build_worker = _BuildPreviewWorker(
            flatpak_first_launch._HOST_DATA_DIR,
            self._sandbox_db_path,
            parent=self,
        )
        self._build_worker.preview_ready.connect(
            self._on_preview_ready, Qt.QueuedConnection
        )
        self._build_worker.preview_error.connect(
            self._on_preview_error, Qt.QueuedConnection
        )
        self._build_worker.start()

    def _on_preview_ready(self, preview: ImportPreview) -> None:
        """Called on main thread when preview build succeeds."""
        self._preview = preview
        # Stash the temp ZIP path so commit_import can read it and cleanup can delete it.
        self._tmp_zip = preview.zip_path

        # Populate the UI with preview data.
        self._loading_label.setVisible(False)

        self._mode_label.setVisible(True)
        self._merge_radio.setVisible(True)
        self._replace_radio.setVisible(True)

        self._summary_label.setText(
            f"{preview.added} added, {preview.replaced} replaced, "
            f"{preview.skipped} skipped, {preview.errors} errors"
        )
        self._summary_label.setVisible(True)

        self._toggle_btn.setVisible(True)

        error_icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        for row in preview.detail_rows:
            item = QTreeWidgetItem([row.name, row.action.title()])
            if row.action == "error":
                item.setForeground(0, ERROR_COLOR_QCOLOR)
                item.setForeground(1, ERROR_COLOR_QCOLOR)
                item.setIcon(0, error_icon)
            self._detail_tree.addTopLevelItem(item)

        # Show tree by default only if there are errors.
        has_errors = preview.errors > 0
        self._detail_tree.setVisible(has_errors)
        if has_errors:
            self._toggle_btn.setText("Hide details")

        self._import_btn.setEnabled(True)
        self.adjustSize()

    def _on_preview_error(self, msg: str) -> None:
        """Called on main thread when preview build fails."""
        self._loading_label.setText(f"Could not read host settings: {msg}")
        self._import_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_details(self) -> None:
        visible = not self._detail_tree.isVisible()
        self._detail_tree.setVisible(visible)
        self._toggle_btn.setText("Hide details" if visible else "Show details")

    def _on_import(self) -> None:
        if self._preview is None:
            return

        mode = "replace_all" if self._replace_radio.isChecked() else "merge"

        if mode == "replace_all":
            result = QMessageBox.warning(
                self,
                "Replace All",
                "This will erase your entire station library and replace it with the "
                "imported host settings. Continue?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if result != QMessageBox.Yes:
                return

        self._import_btn.setEnabled(False)
        self._commit_worker = _ImportCommitWorker(self._preview, mode, parent=self)
        self._commit_worker.commit_done.connect(
            self._on_commit_done, Qt.QueuedConnection
        )
        self._commit_worker.commit_error.connect(
            self._on_commit_error, Qt.QueuedConnection
        )
        self._commit_worker.start()

    def _on_commit_done(self) -> None:
        # Offer-once: write flag on successful import (D-03).
        flatpak_first_launch.write_offered_flag()
        self._cleanup_tmp_zip()
        self._toast(
            f"Import complete — {self._preview.added} added, "
            f"{self._preview.replaced} replaced"
        )
        self.import_complete.emit()
        self.accept()

    def _on_commit_error(self, msg: str) -> None:
        self._import_btn.setEnabled(True)
        self._toast(f"Import failed — {msg}")

    def _on_cancel(self) -> None:
        """Dismiss without importing — still writes offer-once flag (D-03)."""
        flatpak_first_launch.write_offered_flag()
        self._cleanup_tmp_zip()
        self.reject()

    def reject(self) -> None:
        """Override reject() to ensure offer-once flag is always written on any close."""
        flatpak_first_launch.write_offered_flag()
        self._cleanup_tmp_zip()
        super().reject()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_tmp_zip(self) -> None:
        """Remove the temp ZIP file created by _BuildPreviewWorker."""
        if self._tmp_zip and os.path.isfile(self._tmp_zip):
            try:
                os.unlink(self._tmp_zip)
            except OSError:
                pass
            self._tmp_zip = None
