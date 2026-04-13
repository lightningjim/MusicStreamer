"""Phase 40 Plan 03: CookieImportDialog — YouTube cookie import.

UI-09 feature: import YouTube cookies via file picker, paste, or Google login.

Constructor: CookieImportDialog(toast_callback: Callable[[str], None], parent=None)
  toast_callback: forwarded to main-window toast overlay on success.

Three tabs:
  "File"         — QFileDialog picker for Netscape cookie file
  "Paste"        — QTextEdit for pasting cookie text
  "Google Login" — launches subprocess oauth_helper.py --mode google

All paths write to paths.cookies_path() with 0o600 permissions.

Security:
  T-40-07: Validate Netscape format + .youtube.com domain before writing.
  T-40-08: 0o600 permissions immediately after write.
  T-40-09: sys.executable as QProcess program — no PATH injection.
  T-40-10: setTextFormat(Qt.PlainText) on all QLabel instances.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import paths


# ---------------------------------------------------------------------------
# Module-level validation helper (exported for testing)
# ---------------------------------------------------------------------------

def _validate_youtube_cookies(text: str) -> bool:
    """Return True if text contains at least one .youtube.com domain line.

    Expects Netscape-format tab-separated lines; lines starting with '#'
    and blank lines are skipped.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) >= 6 and ".youtube.com" in parts[0]:
            return True
    return False


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class CookieImportDialog(QDialog):
    """Three-tab dialog for importing YouTube cookies.

    Tabs: File | Paste | Google Login
    All paths call _write_cookies() which enforces 0o600 permissions.
    """

    def __init__(
        self,
        toast_callback: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._toast = toast_callback
        self._selected_file_path: str | None = None
        self._google_process: QProcess | None = None

        self.setWindowTitle("YouTube Cookies")
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_file_tab(), "File")
        self._tabs.addTab(self._build_paste_tab(), "Paste")
        self._tabs.addTab(self._build_google_tab(), "Google Login")
        root.addWidget(self._tabs)

        # Inline error label (shared across tabs, shown below tab widget)
        self._error_label = QLabel()
        self._error_label.setTextFormat(Qt.PlainText)
        error_font = QFont()
        error_font.setPointSize(9)
        self._error_label.setFont(error_font)
        self._error_label.setStyleSheet("color: #c0392b;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_file_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        choose_btn = QPushButton("Choose File...")
        choose_btn.clicked.connect(self._on_choose_file)
        layout.addWidget(choose_btn)

        self._file_label = QLabel("No file selected")
        self._file_label.setTextFormat(Qt.PlainText)
        muted_font = QFont()
        muted_font.setPointSize(9)
        self._file_label.setFont(muted_font)
        self._file_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._file_label)

        self._file_import_btn = QPushButton("Import")
        self._file_import_btn.setVisible(False)
        self._file_import_btn.clicked.connect(self._on_file_import)
        layout.addWidget(self._file_import_btn)

        layout.addStretch()
        return tab

    def _build_paste_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._paste_edit = QTextEdit()
        self._paste_edit.setPlaceholderText("Paste Netscape cookie text here...")
        self._paste_edit.textChanged.connect(self._on_paste_changed)
        layout.addWidget(self._paste_edit)

        self._paste_import_btn = QPushButton("Import")
        self._paste_import_btn.setEnabled(False)
        self._paste_import_btn.clicked.connect(self._on_paste_import)
        layout.addWidget(self._paste_import_btn)

        return tab

    def _build_google_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        info_label = QLabel("Opens Google login in a browser window.")
        info_label.setTextFormat(Qt.PlainText)
        layout.addWidget(info_label)

        self._google_btn = QPushButton("Open Google Login")
        self._google_btn.clicked.connect(self._on_google_login)
        layout.addWidget(self._google_btn)

        self._google_status_label = QLabel()
        self._google_status_label.setTextFormat(Qt.PlainText)
        self._google_status_label.setVisible(False)
        layout.addWidget(self._google_status_label)

        layout.addStretch()
        return tab

    # ------------------------------------------------------------------
    # Slot: paste tab text changed
    # ------------------------------------------------------------------

    def _on_paste_changed(self) -> None:
        has_text = bool(self._paste_edit.toPlainText().strip())
        self._paste_import_btn.setEnabled(has_text)

    # ------------------------------------------------------------------
    # Slot: paste import
    # ------------------------------------------------------------------

    def _on_paste_import(self) -> None:
        self._hide_error()
        text = self._paste_edit.toPlainText()
        if not _validate_youtube_cookies(text):
            self._show_error("Invalid cookies: no .youtube.com entries found.")
            return
        self._write_cookies(text)

    # ------------------------------------------------------------------
    # Slot: file chooser
    # ------------------------------------------------------------------

    def _on_choose_file(self) -> None:
        self._hide_error()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cookie File",
            "",
            "Cookie files (*.txt);;All files (*)",
        )
        if not file_path:
            return

        self._selected_file_path = file_path
        # Truncate display name to 40 chars (per UI-SPEC)
        display = os.path.basename(file_path)[:40]
        self._file_label.setText(display)
        self._file_import_btn.setVisible(True)

    # ------------------------------------------------------------------
    # Slot: file import
    # ------------------------------------------------------------------

    def _on_file_import(self) -> None:
        self._hide_error()
        if not self._selected_file_path:
            return

        try:
            with open(self._selected_file_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self._show_error(f"Could not read file: {exc}")
            return

        if not text.strip():
            self._show_error("File is empty.")
            return

        if not _validate_youtube_cookies(text):
            self._show_error("Invalid cookies: no .youtube.com entries found.")
            return

        self._write_cookies(text)

    # ------------------------------------------------------------------
    # Slot: Google login
    # ------------------------------------------------------------------

    def _on_google_login(self) -> None:
        self._hide_error()
        self._google_btn.setEnabled(False)
        self._google_status_label.setText("Logging in...")
        self._google_status_label.setVisible(True)

        process = QProcess(self)
        self._google_process = process
        process.finished.connect(self._on_google_process_finished)
        process.start(
            sys.executable,
            ["-m", "musicstreamer.oauth_helper", "--mode", "google"],
        )

    def _on_google_process_finished(self, exit_code: int, exit_status: object) -> None:
        proc = self._google_process   # capture before clearing
        self._google_process = None   # clear immediately to avoid stale reference
        self._google_btn.setEnabled(True)
        self._google_status_label.setVisible(False)

        if exit_code != 0 or proc is None:
            QMessageBox.warning(self, "Google Login", "Google login failed.")
            return

        stdout_bytes = proc.readAllStandardOutput().data()
        text = stdout_bytes.decode("utf-8", errors="replace").strip()

        if not text:
            QMessageBox.warning(self, "Google Login", "Google login failed.")
            return

        if not _validate_youtube_cookies(text):
            self._show_error("Invalid cookies: no .youtube.com entries found.")
            return

        self._write_cookies(text)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _write_cookies(self, text: str) -> None:
        """Write cookie text to cookies_path() with 0o600 permissions."""
        dest = paths.cookies_path()
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(dest, 0o600)
        self._toast("YouTube cookies imported.")
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)
        self._error_label.setText("")
