"""Phase 39-01: EditStationDialog — modal QDialog for station CRUD.

UI-05 feature-parity port of the v1.5 station editor to PySide6.

Constructor: EditStationDialog(station, player, repo, parent=None)

Signals:
    station_saved   — emitted after successful save
    station_deleted — emitted with station_id after delete

Security: all QLabel instances use Qt.PlainText to prevent rich-text
injection from untrusted station metadata (T-39-01).

Delete guard: delete_btn is disabled when
player._current_station_name == station.name (T-39-03).
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QCursor, QIntValidator, QPixmap, QPixmapCache
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import assets
from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import abs_art_path
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX
from musicstreamer.ui_qt.flow_layout import FlowLayout


class _LogoFetchWorker(QThread):
    """Background thumbnail fetcher for station URL. Handles YT and AudioAddict.

    Emits finished(tmp_path, token, classification) where tmp_path is a temp
    file path or "" on failure/unsupported URL. The token mirrors
    NowPlayingPanel._cover_fetch_token so the slot can discard stale responses
    (and unlink their tmp files). The 3rd arg carries classification:
    "" (default) or "aa_no_key" when an AudioAddict URL is recognized but
    slug/channel_key could not be derived. Phase 46-02 / D-07 / D-08.
    """
    finished = Signal(str, int, str)

    def __init__(self, url: str, token: int, parent=None):
        super().__init__(parent)
        self._url = url
        self._token = token

    def run(self):
        token = self._token
        try:
            url = self._url or ""
            if "youtube.com" in url or "youtu.be" in url:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                thumb = info.get("thumbnail") if info else None
                if thumb:
                    import urllib.request
                    fd, tmp = tempfile.mkstemp(suffix=".jpg")
                    os.close(fd)
                    urllib.request.urlretrieve(thumb, tmp)
                    self.finished.emit(tmp, token, "")
                    return
                self.finished.emit("", token, "")
                return

            from musicstreamer.url_helpers import (
                _is_aa_url, _aa_slug_from_url, _aa_channel_key_from_url,
            )
            if _is_aa_url(url):
                slug = _aa_slug_from_url(url)
                channel_key = _aa_channel_key_from_url(url, slug=slug)
                if not slug or not channel_key:
                    # D-07 / D-08: AA URL recognized but key not derivable.
                    # Classify distinctly so the slot can show the AA-specific
                    # message. Emit BEFORE importing _fetch_image_map so this
                    # branch does not depend on aa_import being importable.
                    self.finished.emit("", token, "aa_no_key")
                    return
                from musicstreamer.aa_import import _fetch_image_map
                import urllib.request
                img_map = _fetch_image_map(slug)
                image_url = img_map.get(channel_key)
                if not image_url:
                    # Network/map failure — generic "Fetch failed" for an
                    # otherwise-parseable AA URL. Not aa_no_key.
                    self.finished.emit("", token, "")
                    return
                ext = os.path.splitext(image_url.split("?")[0])[1] or ".png"
                fd, tmp = tempfile.mkstemp(suffix=ext)
                os.close(fd)
                urllib.request.urlretrieve(image_url, tmp)
                self.finished.emit(tmp, token, "")
                return

            self.finished.emit("", token, "")
        except Exception:
            self.finished.emit("", token, "")


# ---------------------------------------------------------------------------
# Chip QSS (verbatim from station_list_panel._CHIP_QSS)
# ---------------------------------------------------------------------------

_CHIP_QSS = """
QPushButton[chipState="unselected"] {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 12px;
    padding: 4px 8px;
}
QPushButton[chipState="selected"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
    border-radius: 12px;
    padding: 4px 8px;
}
"""

# Phase 46-01 / 46-02: centralized error-red token from musicstreamer.ui_qt._theme.
# f-string with doubled braces so QSS selector braces survive formatting.
_DELETE_BTN_QSS = f"QPushButton {{ color: {ERROR_COLOR_HEX}; }}"

# Stream table columns
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_BITRATE = 3
_COL_POSITION = 4


class _BitrateDelegate(QStyledItemDelegate):
    """Numeric-only editor for the bitrate column (D-12/D-13, P-5).

    Default QTableWidget delegate edits via a plain QLineEdit with no
    validator; subclassing is the minimal way to attach QIntValidator(0, 9999)
    per D-13. The save-path also coerces via ``int(text or "0")`` so pasted
    / malformed values are neutralized at the save boundary (D-14).
    """

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QIntValidator(0, 9999, parent))
        editor.setPlaceholderText("e.g. 128")
        return editor


class EditStationDialog(QDialog):
    """Modal dialog for editing station properties and managing streams."""

    station_saved = Signal()
    station_deleted = Signal(int)

    def __init__(self, station: Station, player, repo, parent=None) -> None:
        super().__init__(parent)
        self._station = station
        self._player = player
        self._repo = repo

        # Map tag name -> QPushButton chip
        self._tag_chips: dict[str, QPushButton] = {}

        self.setWindowTitle("Edit Station")
        self.setMinimumSize(640, 480)
        self.setModal(True)

        self._build_ui()
        self._populate()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Logo row (Plan 40.1-04): 64x64 preview + Choose File + Clear, above form.
        self._logo_path: Optional[str] = self._station.station_art_path
        self._logo_fetch_worker: Optional[_LogoFetchWorker] = None
        # Monotonic token so stale worker emissions can be discarded / cleaned up
        # (mirrors NowPlayingPanel._cover_fetch_token). See WR-01/WR-02/IN-01.
        self._logo_fetch_token: int = 0
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.setSpacing(8)
        self._logo_preview = QLabel(self)
        self._logo_preview.setFixedSize(64, 64)
        self._logo_preview.setAlignment(Qt.AlignCenter)
        self._choose_logo_btn = QPushButton("Choose File\u2026", self)
        self._clear_logo_btn = QPushButton("Clear", self)
        self._fetch_logo_btn = QPushButton("Fetch from URL", self)
        self._logo_status = QLabel("", self)
        logo_row.addWidget(self._logo_preview)
        logo_row.addWidget(self._choose_logo_btn)
        logo_row.addWidget(self._clear_logo_btn)
        logo_row.addWidget(self._fetch_logo_btn)
        logo_row.addWidget(self._logo_status)
        logo_row.addStretch(1)
        outer.addLayout(logo_row)
        self._choose_logo_btn.clicked.connect(self._on_choose_logo)
        self._clear_logo_btn.clicked.connect(self._on_clear_logo)
        self._fetch_logo_btn.clicked.connect(self._on_fetch_logo_clicked)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        outer.addLayout(form)

        # Name
        self.name_edit = QLineEdit()
        form.addRow("Name:", self.name_edit)

        # URL (primary stream convenience field; debounced thumbnail auto-fetch D-07)
        self.url_edit = QLineEdit()
        self._url_timer = QTimer()
        self._url_timer.setSingleShot(True)
        self._url_timer.setInterval(500)
        self.url_edit.textChanged.connect(self._on_url_text_changed)
        self._url_timer.timeout.connect(self._on_url_timer_timeout)
        # Auto-clear timer for _logo_status (D-09). 3s after a terminal status
        # is set, clear the label. Cancelled/restarted via _on_url_text_changed
        # (which also clears the label immediately).
        self._logo_status_clear_timer = QTimer(self)    # parented — G-1 safety
        self._logo_status_clear_timer.setSingleShot(True)
        self._logo_status_clear_timer.setInterval(3000)
        self._logo_status_clear_timer.timeout.connect(self._logo_status.clear)
        form.addRow("URL:", self.url_edit)

        # Provider
        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(True)
        form.addRow("Provider:", self.provider_combo)

        # Tags
        tags_container = QWidget()
        tags_vbox = QVBoxLayout(tags_container)
        tags_vbox.setContentsMargins(0, 0, 0, 0)
        tags_vbox.setSpacing(4)

        self._chips_widget = QWidget()
        self._chips_layout = FlowLayout(self._chips_widget, h_spacing=4, v_spacing=4)
        self._chips_widget.setStyleSheet(_CHIP_QSS)
        tags_vbox.addWidget(self._chips_widget)

        tag_input_row = QHBoxLayout()
        tag_input_row.setContentsMargins(0, 0, 0, 0)
        tag_input_row.setSpacing(4)
        self.new_tag_edit = QLineEdit()
        self.new_tag_edit.setPlaceholderText("New tag...")
        self.add_tag_btn = QPushButton("Add Tag")
        self.add_tag_btn.clicked.connect(self._on_add_tag)
        tag_input_row.addWidget(self.new_tag_edit)
        tag_input_row.addWidget(self.add_tag_btn)
        tags_vbox.addLayout(tag_input_row)

        form.addRow("Tags:", tags_container)

        # ICY
        self.icy_checkbox = QCheckBox("Disable ICY metadata")
        form.addRow("ICY metadata:", self.icy_checkbox)

        # Streams table
        streams_container = QWidget()
        streams_vbox = QVBoxLayout(streams_container)
        streams_vbox.setContentsMargins(0, 0, 0, 0)
        streams_vbox.setSpacing(4)

        self.streams_table = QTableWidget(0, 5)
        self.streams_table.setHorizontalHeaderLabels(
            ["URL", "Quality", "Codec", "Bitrate (kbps)", "Position"]
        )
        self.streams_table.setAlternatingRowColors(True)
        self.streams_table.setSelectionBehavior(QTableWidget.SelectRows)
        hdr = self.streams_table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_URL, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_QUALITY, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_CODEC, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_BITRATE, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_POSITION, QHeaderView.Fixed)
        self.streams_table.setColumnWidth(_COL_QUALITY, 80)
        self.streams_table.setColumnWidth(_COL_CODEC, 80)
        self.streams_table.setColumnWidth(_COL_BITRATE, 95)
        self.streams_table.setColumnWidth(_COL_POSITION, 60)
        self.streams_table.setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
        streams_vbox.addWidget(self.streams_table)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)
        self.add_stream_btn = QPushButton("Add")
        self.remove_stream_btn = QPushButton("Remove")
        self.move_up_btn = QPushButton("Move Up")
        self.move_down_btn = QPushButton("Move Down")
        for btn in (self.add_stream_btn, self.remove_stream_btn,
                    self.move_up_btn, self.move_down_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch()
        streams_vbox.addLayout(btn_row)
        form.addRow("Streams:", streams_container)

        self.add_stream_btn.clicked.connect(self._on_add_stream)
        self.remove_stream_btn.clicked.connect(self._on_remove_stream)
        self.move_up_btn.clicked.connect(self._on_move_up)
        self.move_down_btn.clicked.connect(self._on_move_down)

        # Button box — Save (AcceptRole), Discard (RejectRole), Delete (DestructiveRole)
        self.button_box = QDialogButtonBox()
        save_btn = self.button_box.addButton("Save Station", QDialogButtonBox.AcceptRole)
        save_btn.setDefault(True)
        self.button_box.addButton("Discard", QDialogButtonBox.RejectRole)

        self.delete_btn = QPushButton("Delete Station")
        self.delete_btn.setStyleSheet(_DELETE_BTN_QSS)
        self.delete_btn.setToolTip("Stop playback before deleting")
        self.button_box.addButton(self.delete_btn, QDialogButtonBox.DestructiveRole)

        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        self.delete_btn.clicked.connect(self._on_delete)

        outer.addWidget(self.button_box)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        station = self._station

        # Name (Qt.PlainText enforced — T-39-01; QLineEdit always plain)
        self.name_edit.setText(station.name)

        # URL from first stream
        streams = self._repo.list_streams(station.id)
        if streams:
            self.url_edit.setText(streams[0].url)

        # Provider combo
        for p in self._repo.list_providers():
            self.provider_combo.addItem(p.name)
        self.provider_combo.setCurrentText(station.provider_name or "")

        # Tag chips
        if station.tags:
            for tag in (t.strip() for t in station.tags.split(",") if t.strip()):
                self._make_chip(tag, selected=True)

        # ICY
        self.icy_checkbox.setChecked(bool(station.icy_disabled))

        # Streams
        for s in streams:
            self._add_stream_row(s.url, s.quality, s.codec, s.bitrate_kbps, s.position, stream_id=s.id)

        # Delete guard (T-39-03)
        is_playing = getattr(self._player, "_current_station_name", "") == station.name
        self.delete_btn.setEnabled(not is_playing)

        # Logo preview (Plan 40.1-04)
        self._refresh_logo_preview()

    # ------------------------------------------------------------------
    # Chip helpers
    # ------------------------------------------------------------------

    def _make_chip(self, tag: str, selected: bool = True) -> QPushButton:
        chip = QPushButton(tag)
        state = "selected" if selected else "unselected"
        chip.setProperty("chipState", state)
        chip.setStyleSheet(_CHIP_QSS)
        chip.style().polish(chip)
        chip.clicked.connect(self._make_chip_toggle(chip))
        self._chips_layout.addWidget(chip)
        self._tag_chips[tag] = chip
        return chip

    @staticmethod
    def _make_chip_toggle(chip: QPushButton):
        def _toggle():
            current = chip.property("chipState")
            new_state = "unselected" if current == "selected" else "selected"
            chip.setProperty("chipState", new_state)
            chip.style().polish(chip)
        return _toggle

    def _on_add_tag(self) -> None:
        tag = self.new_tag_edit.text().strip()
        if not tag or tag in self._tag_chips:
            return
        self._make_chip(tag, selected=True)
        self.new_tag_edit.clear()

    # ------------------------------------------------------------------
    # Stream table helpers
    # ------------------------------------------------------------------

    def _add_stream_row(self, url: str = "", quality: str = "",
                        codec: str = "", bitrate_kbps: int = 0,
                        position: int = 1,
                        stream_id: Optional[int] = None) -> int:
        """Insert a new row in the stream table.

        stream_id stored in URL item's Qt.UserRole — survives row swaps.
        bitrate_kbps=0 renders as empty string (D-12/G-5).
        """
        row = self.streams_table.rowCount()
        self.streams_table.insertRow(row)

        url_item = QTableWidgetItem(url)
        url_item.setData(Qt.UserRole, stream_id)  # None for new rows

        self.streams_table.setItem(row, _COL_URL, url_item)
        self.streams_table.setItem(row, _COL_QUALITY, QTableWidgetItem(quality))
        self.streams_table.setItem(row, _COL_CODEC, QTableWidgetItem(codec))
        self.streams_table.setItem(
            row, _COL_BITRATE,
            QTableWidgetItem(str(bitrate_kbps) if bitrate_kbps else ""),
        )
        self.streams_table.setItem(row, _COL_POSITION, QTableWidgetItem(str(position)))
        return row

    def _on_add_stream(self) -> None:
        self._add_stream_row()

    def _on_remove_stream(self) -> None:
        selected = self.streams_table.selectedItems()
        if not selected:
            return
        for row in sorted({item.row() for item in selected}, reverse=True):
            self.streams_table.removeRow(row)

    def _on_move_up(self) -> None:
        row = self.streams_table.currentRow()
        if row <= 0:
            return
        self._swap_rows(row - 1, row)
        self.streams_table.selectRow(row - 1)

    def _on_move_down(self) -> None:
        row = self.streams_table.currentRow()
        if row < 0 or row >= self.streams_table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self.streams_table.selectRow(row + 1)

    def _swap_rows(self, r1: int, r2: int) -> None:
        table = self.streams_table
        for col in range(table.columnCount()):
            item1 = table.takeItem(r1, col) or QTableWidgetItem("")
            item2 = table.takeItem(r2, col) or QTableWidgetItem("")
            table.setItem(r1, col, item2)
            table.setItem(r2, col, item1)

    # ------------------------------------------------------------------
    # URL auto-fetch debounce (D-07)
    # ------------------------------------------------------------------

    def _on_url_text_changed(self) -> None:
        # Debounce fetch (existing behavior).
        self._url_timer.start()
        # D-09: clear pending auto-clear timer + clear status label immediately.
        # QLabel.clear is idempotent — safe when label is already empty.
        self._logo_status_clear_timer.stop()
        self._logo_status.clear()

    def _on_url_timer_timeout(self) -> None:
        """Debounced: kick off a _LogoFetchWorker for the current URL.

        Uses a monotonic token so any prior in-flight worker's emission is
        recognized as stale by _on_logo_fetched (which unlinks its tmp file).
        No disconnect needed — the slot always runs.
        """
        url = self.url_edit.text().strip()
        if not url:
            return
        self._logo_fetch_token += 1
        token = self._logo_fetch_token
        self._logo_status.setText("Fetching\u2026")
        self._fetch_logo_btn.setEnabled(False)
        self._logo_fetch_worker = _LogoFetchWorker(url, token, self)
        self._logo_fetch_worker.finished.connect(self._on_logo_fetched)
        # D-10: wait cursor during fetch. Restored exactly once at the top of
        # _on_logo_fetched (covers success, failure, unsupported, aa_no_key,
        # and stale-token branches — see RESEARCH Pitfall P-1).
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self._logo_fetch_worker.start()

    def _on_fetch_logo_clicked(self) -> None:
        """Manual trigger — bypass debounce and fetch now."""
        self._url_timer.stop()
        url = self.url_edit.text().strip()
        if not url:
            self._logo_status.setText("Enter a URL first")
            # D-09: also auto-clear this terminal status after 3s.
            self._logo_status_clear_timer.start()
            return
        self._on_url_timer_timeout()

    # ------------------------------------------------------------------
    # Logo row (Plan 40.1-04)
    # ------------------------------------------------------------------

    def _refresh_logo_preview(self) -> None:
        resolved = abs_art_path(self._logo_path)
        if resolved and os.path.exists(resolved):
            pix = QPixmap(resolved)
            if not pix.isNull():
                self._logo_preview.setPixmap(
                    pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self._logo_preview.clear()

    def _on_choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose station logo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.svg)",
        )
        if not path:
            return
        old_path = self._logo_path
        rel = assets.copy_asset_for_station(self._station.id, path, "station_art")
        self._logo_path = rel
        self._refresh_logo_preview()
        self._invalidate_cache_for(old_path)

    def _on_clear_logo(self) -> None:
        old_path = self._logo_path
        self._logo_path = None
        self._refresh_logo_preview()
        self._invalidate_cache_for(old_path)

    def _on_logo_fetched(
        self,
        tmp_path: str,
        token: int = 0,
        classification: str = "",
    ) -> None:
        # D-10/D-11 + P-1: restore cursor BEFORE the stale-token check so that
        # every setOverrideCursor call has exactly one matching restore,
        # regardless of token freshness. _on_logo_fetched is the sole slot for
        # _LogoFetchWorker.finished — there is no separate error signal (G-7).
        QApplication.restoreOverrideCursor()

        # Stale response: a newer fetch has been started. Unlink the stale tmp
        # file (if any) so we do not leak temp files under rapid URL typing.
        # See WR-01.
        if token and token != self._logo_fetch_token:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return

        self._fetch_logo_btn.setEnabled(True)
        if not tmp_path or not os.path.exists(tmp_path):
            if classification == "aa_no_key":
                # D-07: AA URL recognized but slug/channel_key not derivable.
                # Tell the user to use Choose File instead of a generic "not
                # supported" message.
                self._logo_status.setText(
                    "AudioAddict station \u2014 use Choose File to supply a logo"
                )
            else:
                from musicstreamer.url_helpers import _is_aa_url
                url = self.url_edit.text().strip()
                lower = url.lower()
                if "youtube.com" in lower or "youtu.be" in lower or _is_aa_url(url):
                    # YT/AA recognized URL that failed mid-fetch (e.g. network
                    # error, image_url missing from map).
                    self._logo_status.setText("Fetch failed")
                else:
                    self._logo_status.setText("Fetch not supported for this URL")
            # D-09: arm the 3s auto-clear timer for this terminal status.
            self._logo_status_clear_timer.start()
            # Defensive: truthy-but-missing tmp_path shouldn't happen, but
            # attempt cleanup in case of race / external deletion. See WR-03.
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return
        try:
            old_path = self._logo_path
            rel = assets.copy_asset_for_station(self._station.id, tmp_path, "station_art")
            self._logo_path = rel
            self._refresh_logo_preview()
            self._invalidate_cache_for(old_path)
            self._logo_status.setText("Fetched")
            # D-09: arm the 3s auto-clear timer for the success terminal status.
            self._logo_status_clear_timer.start()
        finally:
            # Always unlink the tmp file — even on exception from copy_asset.
            # See WR-03.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _invalidate_cache_for(self, rel_path: Optional[str]) -> None:
        if not rel_path:
            return
        resolved = abs_art_path(rel_path)
        QPixmapCache.remove(f"station-logo:{resolved}")

    def _shutdown_logo_fetch_worker(self) -> None:
        """Bound-wait for the logo fetch worker so tmp files are cleaned up.

        Capped at 2s to keep UI close snappy. If the worker completes during
        the wait, its queued emission will not be delivered (the dialog is
        tearing down); we rely on stale-token branch logic in the next fetch
        to avoid leaks when the dialog is reused. See WR-02.
        """
        worker = self._logo_fetch_worker
        if worker is None or not worker.isRunning():
            return
        try:
            worker.finished.disconnect()
        except Exception:
            pass
        worker.wait(2000)

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self._shutdown_logo_fetch_worker()
        super().closeEvent(event)

    def reject(self) -> None:
        self._shutdown_logo_fetch_worker()
        super().reject()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        station = self._station
        repo = self._repo

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Station name cannot be empty.")
            return
        provider_name = self.provider_combo.currentText().strip()
        icy_disabled = self.icy_checkbox.isChecked()

        selected_tags = [
            tag for tag, chip in self._tag_chips.items()
            if chip.property("chipState") == "selected"
        ]
        tags_csv = ",".join(selected_tags)

        # D-02: currentText() on save — ensure_provider handles blank → None
        provider_id = repo.ensure_provider(provider_name)

        repo.update_station(
            station.id,
            name,
            provider_id,
            tags_csv,
            self._logo_path,
            station.album_fallback_path,
            icy_disabled,
        )
        # Keep in-memory Station consistent for any station_saved consumers.
        station.station_art_path = self._logo_path

        # Persist streams
        ordered_ids: list[int] = []
        table = self.streams_table
        for row in range(table.rowCount()):
            url_item = table.item(row, _COL_URL)
            qual_item = table.item(row, _COL_QUALITY)
            codec_item = table.item(row, _COL_CODEC)
            bitrate_item = table.item(row, _COL_BITRATE)
            pos_item = table.item(row, _COL_POSITION)

            url = url_item.text() if url_item else ""
            quality = qual_item.text() if qual_item else ""
            codec = codec_item.text() if codec_item else ""
            bitrate_text = bitrate_item.text() if bitrate_item else ""
            try:
                bitrate_kbps = int(bitrate_text or "0")  # D-14 + P-4
            except ValueError:
                bitrate_kbps = 0
            try:
                position = int(pos_item.text()) if pos_item else row + 1
            except ValueError:
                position = row + 1

            stream_id: Optional[int] = url_item.data(Qt.UserRole) if url_item else None

            if stream_id is not None:
                repo.update_stream(stream_id, url, "", quality, position, "", codec,
                                   bitrate_kbps=bitrate_kbps)
                ordered_ids.append(stream_id)
            else:
                new_id = repo.insert_stream(
                    station.id, url, label="", quality=quality,
                    position=position, stream_type="", codec=codec,
                    bitrate_kbps=bitrate_kbps,
                )
                if isinstance(new_id, int):
                    ordered_ids.append(new_id)

        if ordered_ids:
            repo.reorder_streams(station.id, ordered_ids)

        self.station_saved.emit()
        self.accept()

    # ------------------------------------------------------------------
    # Delete (T-39-03)
    # ------------------------------------------------------------------

    def _on_delete(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Station",
            f"Delete '{self._station.name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            self._repo.delete_station(self._station.id)
            self.station_deleted.emit(self._station.id)
            self.accept()
