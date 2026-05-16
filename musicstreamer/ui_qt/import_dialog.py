"""Phase 39-03: ImportDialog — YouTube + AudioAddict import tabs.

UI-07 feature-parity port of the v1.5 import dialog to PySide6.

Constructor: ImportDialog(toast_callback, parent=None)
  toast_callback: Callable[[str], None] — forwarded to main-window toast overlay.

Signals:
  import_complete() — emitted after any successful import (for station-list refresh).

Threading discipline (Pitfall 3):
  All blocking I/O runs on daemon QThread workers.
  yt_import.import_stations and aa_import.import_stations_multi both need a
  thread-local Repo(db_connect()) — instantiated inside QThread.run(), never
  passed from the main thread.

Security:
  YouTube URL validated by is_yt_playlist_url() before scan (T-39-07).
  QListWidget items are plain text — no rich-text injection (T-39-10).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import yt_import, aa_import
from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.yt_import import is_yt_playlist_url
from musicstreamer.repo import Repo, db_connect
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX


# ---------------------------------------------------------------------------
# Import summary formatter (Phase 40.1-03 D-10)
# ---------------------------------------------------------------------------


def _format_import_summary(imported: int, skipped: int) -> str:
    """Context-sensitive wording for AA/YT import results.

    - imported>0, skipped==0 → "Imported N new"
    - imported==0, skipped>0 → "All M already in library"
    - otherwise              → "Imported N new, M skipped (already in library)"
    """
    if imported > 0 and skipped == 0:
        return f"Imported {imported} new"
    if imported == 0 and skipped > 0:
        return f"All {skipped} already in library"
    return f"Imported {imported} new, {skipped} skipped (already in library)"


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------


class _YtScanWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        url: str,
        toast_callback: Optional[Callable[[str], None]] = None,
        *,
        node_runtime: "NodeRuntime | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._url = url
        self._toast = toast_callback
        self._node_runtime = node_runtime

    def run(self):
        try:
            results = yt_import.scan_playlist(
                self._url,
                toast_callback=self._toast,
                node_runtime=self._node_runtime,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class _YtImportWorker(QThread):
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, entries: list, parent=None):
        super().__init__(parent)
        self._entries = entries

    def run(self):
        try:
            repo = Repo(db_connect())
            result = yt_import.import_stations(self._entries, repo)
            # import_stations returns (imported, skipped) tuple
            if isinstance(result, tuple):
                imported, skipped = int(result[0]), int(result[1])
            else:
                imported, skipped = int(result), 0
            self.finished.emit(imported, skipped)
        except Exception as exc:
            self.error.emit(str(exc))


class _AaFetchWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key

    def run(self):
        try:
            channels = aa_import.fetch_channels_multi(self._api_key)
            self.finished.emit(channels)
        except ValueError as ve:
            self.error.emit(str(ve))
        except Exception as exc:
            self.error.emit(str(exc))


class _AaImportWorker(QThread):
    progress = Signal(int, int)  # current, total
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, channels: list, api_key: str, parent=None):
        super().__init__(parent)
        self._channels = channels
        self._api_key = api_key

    def run(self):
        try:
            repo = Repo(db_connect())
            result = aa_import.import_stations_multi(
                self._channels,
                repo,
                on_progress=lambda cur, tot: self.progress.emit(cur, tot),
            )
            if isinstance(result, tuple):
                imported, skipped = int(result[0]), int(result[1])
            else:
                imported, skipped = int(result), 0
            self.finished.emit(imported, skipped)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class ImportDialog(QDialog):
    """Modal dialog for importing stations from YouTube playlists or AudioAddict."""

    import_complete = Signal()

    def __init__(self, toast_callback: Callable[[str], None], repo, parent=None, *, node_runtime: "NodeRuntime | None" = None):
        super().__init__(parent)
        self._toast = toast_callback
        self._repo = repo
        self._node_runtime = node_runtime
        self.setWindowTitle("Import Stations")
        self.setMinimumSize(600, 440)
        self.setModal(True)

        self._yt_scan_worker: Optional[QThread] = None
        self._yt_import_worker: Optional[QThread] = None
        self._aa_fetch_worker: Optional[QThread] = None
        self._aa_import_worker: Optional[QThread] = None
        self._aa_channels: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget(self)
        root.addWidget(self._tabs)

        self._tabs.addTab(self._build_yt_tab(), "YouTube")
        self._tabs.addTab(self._build_aa_tab(), "AudioAddict")

    # ------------------------------------------------------------------
    # YouTube tab
    # ------------------------------------------------------------------

    def _build_yt_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # URL row
        url_row = QHBoxLayout()
        self._yt_url = QLineEdit()
        self._yt_url.setPlaceholderText("YouTube playlist URL")
        url_row.addWidget(self._yt_url, 1)
        self._yt_scan_btn = QPushButton("Scan Playlist")
        self._yt_scan_btn.clicked.connect(self._on_yt_scan_clicked)
        url_row.addWidget(self._yt_scan_btn)
        layout.addLayout(url_row)

        # Progress bar (hidden initially)
        self._yt_progress = QProgressBar()
        self._yt_progress.setVisible(False)
        layout.addWidget(self._yt_progress)

        # Status label (hidden initially)
        self._yt_status = QLabel()
        self._yt_status.setVisible(False)
        layout.addWidget(self._yt_status)

        # List widget (hidden until scan completes)
        self._yt_list = QListWidget()
        self._yt_list.setVisible(False)
        self._yt_list.itemChanged.connect(self._on_yt_item_changed)
        layout.addWidget(self._yt_list, 1)

        # Import button row
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._yt_import_btn = QPushButton("Import Selected")
        self._yt_import_btn.setEnabled(False)
        self._yt_import_btn.clicked.connect(self._on_yt_import_clicked)
        btn_row.addWidget(self._yt_import_btn)
        layout.addLayout(btn_row)

        return w

    # ------------------------------------------------------------------
    # AudioAddict tab
    # ------------------------------------------------------------------

    def _build_aa_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Form
        form = QFormLayout()
        form.setSpacing(8)
        # Phase 48: AA listen-key row — masked by default, with Show toggle
        self._aa_key = QLineEdit()
        self._aa_key.setPlaceholderText("AudioAddict listen key")
        self._aa_key.setEchoMode(QLineEdit.EchoMode.Password)  # D-08

        # D-03: prefill from DB
        saved_aa_key = self._repo.get_setting("audioaddict_listen_key", "")
        if saved_aa_key:
            self._aa_key.setText(saved_aa_key)

        # D-09: Show/hide toggle
        self._aa_show_btn = QToolButton()
        self._aa_show_btn.setCheckable(True)
        self._aa_show_btn.setChecked(False)
        self._aa_show_btn.setIcon(
            QIcon.fromTheme(
                "view-reveal-symbolic",
                QIcon.fromTheme("document-properties"),
            )
        )
        self._aa_show_btn.setToolTip("Show key")  # D-10
        self._aa_show_btn.toggled.connect(self._on_aa_show_toggled)

        # Wrap field + toggle in an HBox container so QFormLayout can addRow a single widget
        aa_key_container = QWidget()
        aa_key_row = QHBoxLayout(aa_key_container)
        aa_key_row.setContentsMargins(0, 0, 0, 0)
        aa_key_row.addWidget(self._aa_key, 1)
        aa_key_row.addWidget(self._aa_show_btn)

        form.addRow("API Key:", aa_key_container)
        layout.addLayout(form)

        # Progress bar (hidden initially)
        self._aa_progress = QProgressBar()
        self._aa_progress.setVisible(False)
        layout.addWidget(self._aa_progress)

        # Status / error label (hidden initially)
        self._aa_status = QLabel()
        self._aa_status.setVisible(False)
        self._aa_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._aa_status.setWordWrap(True)
        layout.addWidget(self._aa_status)

        layout.addStretch(1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._aa_import_btn = QPushButton("Import Channels")
        self._aa_import_btn.clicked.connect(self._on_aa_import_clicked)
        btn_row.addWidget(self._aa_import_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        return w

    # ------------------------------------------------------------------
    # YouTube flow
    # ------------------------------------------------------------------

    def _on_yt_scan_clicked(self):
        url = self._yt_url.text().strip()
        if not url:
            return
        if not is_yt_playlist_url(url):
            self._yt_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
            self._yt_status.setText("Not a valid YouTube playlist URL.")
            self._yt_status.setVisible(True)
            return
        self._set_yt_busy(True)
        self._yt_list.clear()
        self._yt_list.setVisible(False)
        self._yt_status.setText("Scanning playlist…")
        self._yt_status.setVisible(True)
        self._yt_progress.setRange(0, 0)  # indeterminate
        self._yt_progress.setVisible(True)

        self._yt_scan_worker = _YtScanWorker(
            url,
            toast_callback=self._toast,
            node_runtime=self._node_runtime,
            parent=self,
        )
        self._yt_scan_worker.finished.connect(self._on_yt_scan_complete, Qt.QueuedConnection)
        self._yt_scan_worker.error.connect(self._on_yt_scan_error, Qt.QueuedConnection)
        self._yt_scan_worker.start()

    def _on_yt_scan_complete(self, results: list):
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)

        if not results:
            self._yt_status.setText("No live streams found in this playlist.")
            self._yt_status.setVisible(True)
            self._yt_import_btn.setEnabled(False)
            return

        self._yt_status.setText(f"{len(results)} streams found")
        self._yt_status.setVisible(True)

        # Populate list — block itemChanged during bulk insert
        self._yt_list.blockSignals(True)
        self._yt_list.clear()
        for entry in results:
            item = QListWidgetItem(entry.get("title", "Untitled"))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, entry)
            self._yt_list.addItem(item)
        self._yt_list.blockSignals(False)

        self._yt_list.setVisible(True)
        self._yt_import_btn.setEnabled(True)

    def _on_yt_scan_error(self, msg: str):
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)
        self._yt_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._yt_status.setText(f"Scan failed: {msg}")
        self._yt_status.setVisible(True)

    def _on_yt_item_changed(self, _item: QListWidgetItem):
        checked = any(
            self._yt_list.item(i).checkState() == Qt.Checked
            for i in range(self._yt_list.count())
        )
        self._yt_import_btn.setEnabled(checked)

    def _on_yt_import_clicked(self):
        entries = []
        for i in range(self._yt_list.count()):
            item = self._yt_list.item(i)
            if item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if data:
                    entries.append(data)
        if not entries:
            return

        self._set_yt_busy(True)
        self._yt_progress.setRange(0, len(entries))
        self._yt_progress.setValue(0)
        self._yt_progress.setVisible(True)

        self._yt_import_worker = _YtImportWorker(entries, parent=self)
        self._yt_import_worker.finished.connect(self._on_yt_import_complete, Qt.QueuedConnection)
        self._yt_import_worker.error.connect(self._on_yt_import_error, Qt.QueuedConnection)
        self._yt_import_worker.start()

    def _on_yt_import_complete(self, imported: int, skipped: int) -> None:
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)
        msg = _format_import_summary(imported, skipped)
        self._yt_status.setStyleSheet("")
        self._yt_status.setText(msg)
        self._yt_status.setVisible(True)
        self._toast(msg)
        self.import_complete.emit()

    def _on_yt_import_error(self, msg: str):
        self._yt_progress.setVisible(False)
        self._set_yt_busy(False)
        self._toast(f"Import error: {msg}")

    def _set_yt_busy(self, busy: bool):
        self._yt_url.setEnabled(not busy)
        self._yt_scan_btn.setEnabled(not busy)
        if busy:
            self._yt_import_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # AudioAddict flow
    # ------------------------------------------------------------------

    def _on_aa_show_toggled(self, checked: bool) -> None:
        """Phase 48 D-09/D-10: toggle EchoMode + tooltip on Show button."""
        if checked:
            self._aa_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self._aa_show_btn.setToolTip("Hide key")
        else:
            self._aa_key.setEchoMode(QLineEdit.EchoMode.Password)
            self._aa_show_btn.setToolTip("Show key")

    def _on_aa_import_clicked(self):
        key = self._aa_key.text().strip()
        if not key:
            return
        self._set_aa_busy(True)
        self._aa_status.setVisible(False)
        self._aa_progress.setRange(0, 0)  # indeterminate during fetch
        self._aa_progress.setVisible(True)
        self._aa_status.setText("Fetching channels…")
        self._aa_status.setStyleSheet("")
        self._aa_status.setVisible(True)

        self._aa_fetch_worker = _AaFetchWorker(key, parent=self)
        self._aa_fetch_worker.finished.connect(self._on_aa_fetch_complete, Qt.QueuedConnection)
        self._aa_fetch_worker.error.connect(self._on_aa_fetch_error, Qt.QueuedConnection)
        self._aa_fetch_worker.start()

    def _on_aa_fetch_complete(self, channels: list):
        # Phase 48 D-01: persist ONLY on successful fetch, before UI updates.
        key = self._aa_key.text().strip()
        if key and channels:
            self._repo.set_setting("audioaddict_listen_key", key)
        self._aa_channels = channels
        total = len(channels)
        self._aa_progress.setRange(0, total)  # switch to determinate
        self._aa_progress.setValue(0)
        self._aa_status.setText(f"Importing 0 of {total}…")
        self._aa_status.setStyleSheet("")
        self._aa_status.setVisible(True)

        self._aa_import_worker = _AaImportWorker(
            channels, self._aa_key.text().strip(), parent=self
        )
        self._aa_import_worker.progress.connect(self._on_aa_import_progress, Qt.QueuedConnection)
        self._aa_import_worker.finished.connect(self._on_aa_import_complete, Qt.QueuedConnection)
        self._aa_import_worker.error.connect(self._on_aa_import_error, Qt.QueuedConnection)
        self._aa_import_worker.start()

    def _on_aa_fetch_error(self, msg: str):
        self._aa_progress.setVisible(False)
        self._set_aa_busy(False)
        self._aa_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")

        if msg == "no_channels":
            self._aa_status.setText("No channels returned. API key may have expired.")
        elif msg == "invalid_key" or "invalid" in msg.lower() or "401" in msg or "403" in msg:
            self._aa_status.setText("Invalid API key. Check your AudioAddict account settings.")
        else:
            # Network error — show toast + inline message
            self._aa_status.setText(f"Error: {msg}")
            self._toast("Network error — check your connection")

        self._aa_status.setVisible(True)

    def _on_aa_import_progress(self, current: int, total: int):
        self._aa_progress.setRange(0, total)
        self._aa_progress.setValue(current)
        self._aa_status.setText(f"Importing {current} of {total}…")
        self._aa_status.setStyleSheet("")
        self._aa_status.setVisible(True)

    def _on_aa_import_complete(self, imported: int, skipped: int) -> None:
        self._aa_progress.setVisible(False)
        self._set_aa_busy(False)
        msg = _format_import_summary(imported, skipped)
        self._aa_status.setStyleSheet("")
        self._aa_status.setText(msg)
        self._aa_status.setVisible(True)
        self._toast(msg)
        self.import_complete.emit()

    def _on_aa_import_error(self, msg: str):
        self._aa_progress.setVisible(False)
        self._set_aa_busy(False)
        self._aa_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._aa_status.setText(f"Import error: {msg}")
        self._aa_status.setVisible(True)
        self._toast("Network error — check your connection")

    def _set_aa_busy(self, busy: bool):
        self._aa_key.setEnabled(not busy)
        self._aa_import_btn.setEnabled(not busy)
