"""Phase 42 Plan 02: SettingsImportDialog — import summary dialog.

Shows import counts, merge/replace-all mode toggle, expandable detail tree,
and commits on OK via a background QThread worker.

Constructor: SettingsImportDialog(preview, toast_callback, parent=None)
  preview: ImportPreview dataclass from settings_export.preview_import
  toast_callback: Callable[[str], None] — forwarded to main-window toast overlay.

Signals:
  import_complete() — emitted after a successful import (for station-list refresh).

Threading:
  _ImportCommitWorker runs commit_import on a background thread (T-42-06).
  Result signals are emitted via Qt.QueuedConnection to the main thread.

Security:
  T-42-05: Replace All mode shows QMessageBox.warning confirmation before commit.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QVBoxLayout,
    QPushButton,
)

from musicstreamer.settings_export import ImportPreview, commit_import
from musicstreamer.repo import Repo, db_connect
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------


class _ImportCommitWorker(QThread):
    """Runs commit_import on a background thread (T-42-06).

    Custom signals are named ``commit_done`` and ``commit_error`` to avoid
    shadowing ``QThread.finished`` — PySide6 emits the C++ ``QThread::finished``
    unconditionally on thread exit, so a Python ``finished = Signal()`` class
    attribute would collide and route thread-exit to slots intended for the
    success path. See ``.planning/debug/settings-import-silent-fail-on-readonly-db.md``.
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
# Import summary dialog
# ---------------------------------------------------------------------------


class SettingsImportDialog(QDialog):
    """Import summary dialog: counts, mode toggle, expandable detail list."""

    import_complete = Signal()

    def __init__(
        self,
        preview: ImportPreview,
        toast_callback: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._preview = preview
        self._toast = toast_callback
        self._commit_worker: Optional[QThread] = None

        self.setWindowTitle("Import Settings")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ------------------------------------------------------------------
        # Section 1: Mode selector
        # ------------------------------------------------------------------
        mode_label = QLabel("Import mode:")
        mode_label.setTextFormat(Qt.PlainText)
        font_10 = QFont()
        font_10.setPointSize(10)
        mode_label.setFont(font_10)
        layout.addWidget(mode_label)

        self._merge_radio = QRadioButton(
            "Merge \u2014 add new stations and update matches"
        )
        self._replace_radio = QRadioButton(
            "Replace All \u2014 wipe library and restore from ZIP"
        )
        self._merge_radio.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._merge_radio, 0)
        self._mode_group.addButton(self._replace_radio, 1)

        layout.addWidget(self._merge_radio)
        layout.addWidget(self._replace_radio)

        self._replace_warning = QLabel(
            "This will replace all stations, streams, and favorites."
        )
        self._replace_warning.setTextFormat(Qt.PlainText)
        self._replace_warning.setStyleSheet(
            f"color: {ERROR_COLOR_HEX}; font-size: 9pt;"
        )
        self._replace_warning.setVisible(False)
        self._replace_radio.toggled.connect(self._replace_warning.setVisible)
        layout.addWidget(self._replace_warning)

        # ------------------------------------------------------------------
        # Section 2: Summary counts + detail tree
        # ------------------------------------------------------------------
        self._summary_label = QLabel(
            f"{preview.added} added, {preview.replaced} replaced, "
            f"{preview.skipped} skipped, {preview.errors} errors"
        )
        self._summary_label.setTextFormat(Qt.PlainText)
        summary_font = QFont()
        summary_font.setPointSize(13)
        summary_font.setWeight(QFont.Weight.DemiBold)
        self._summary_label.setFont(summary_font)
        layout.addWidget(self._summary_label)

        self._toggle_btn = QPushButton("Show details")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet("border: none;")
        self._toggle_btn.clicked.connect(self._toggle_details)
        layout.addWidget(self._toggle_btn)

        self._detail_tree = QTreeWidget()
        self._detail_tree.setColumnCount(2)
        self._detail_tree.setHeaderLabels(["Station", "Action"])
        self._detail_tree.setMaximumHeight(200)

        # UI-REVIEW follow-up: add a standard warning glyph to error rows so
        # users who cannot perceive the red foreground still get an
        # unambiguous status indicator (a11y, color-vision deficiency).
        error_icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)

        for row in preview.detail_rows:
            item = QTreeWidgetItem([row.name, row.action.title()])
            if row.action == "error":
                item.setForeground(0, ERROR_COLOR_QCOLOR)
                item.setForeground(1, ERROR_COLOR_QCOLOR)
                item.setIcon(0, error_icon)
            self._detail_tree.addTopLevelItem(item)

        # Show tree by default only if there are errors
        self._detail_tree.setVisible(preview.errors > 0)
        if preview.errors > 0:
            self._toggle_btn.setText("Hide details")

        layout.addWidget(self._detail_tree)

        # ------------------------------------------------------------------
        # Section 3: Button box
        # ------------------------------------------------------------------
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.button(QDialogButtonBox.Ok).setText("Import")
        self._import_btn = btn_box.button(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self._on_import)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_details(self) -> None:
        visible = not self._detail_tree.isVisible()
        self._detail_tree.setVisible(visible)
        self._toggle_btn.setText("Hide details" if visible else "Show details")

    def _on_import(self) -> None:
        mode = "replace_all" if self._replace_radio.isChecked() else "merge"

        if mode == "replace_all":
            result = QMessageBox.warning(
                self,
                "Replace All",
                "This will erase your entire station library and replace it with the import. Continue?",
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
        self._toast(
            f"Import complete \u2014 {self._preview.added} added, "
            f"{self._preview.replaced} replaced"
        )
        self.import_complete.emit()
        self.accept()

    def _on_commit_error(self, msg: str) -> None:
        self._import_btn.setEnabled(True)
        self._toast(f"Import failed \u2014 {msg}")
