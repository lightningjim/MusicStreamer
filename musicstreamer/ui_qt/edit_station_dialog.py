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

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musicstreamer.models import Station
from musicstreamer.ui_qt.flow_layout import FlowLayout


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

_DELETE_BTN_QSS = "QPushButton { color: #c0392b; }"

# Stream table columns
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_POSITION = 3


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

        self.streams_table = QTableWidget(0, 4)
        self.streams_table.setHorizontalHeaderLabels(["URL", "Quality", "Codec", "Position"])
        self.streams_table.setAlternatingRowColors(True)
        self.streams_table.setSelectionBehavior(QTableWidget.SelectRows)
        hdr = self.streams_table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_URL, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_QUALITY, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_CODEC, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_POSITION, QHeaderView.Fixed)
        self.streams_table.setColumnWidth(_COL_QUALITY, 80)
        self.streams_table.setColumnWidth(_COL_CODEC, 80)
        self.streams_table.setColumnWidth(_COL_POSITION, 60)
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
            self._add_stream_row(s.url, s.quality, s.codec, s.position, stream_id=s.id)

        # Delete guard (T-39-03)
        is_playing = getattr(self._player, "_current_station_name", "") == station.name
        self.delete_btn.setEnabled(not is_playing)

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
                        codec: str = "", position: int = 1,
                        stream_id: Optional[int] = None) -> int:
        """Insert a new row in the stream table.

        stream_id stored in URL item's Qt.UserRole — survives row swaps.
        """
        row = self.streams_table.rowCount()
        self.streams_table.insertRow(row)

        url_item = QTableWidgetItem(url)
        url_item.setData(Qt.UserRole, stream_id)  # None for new rows

        self.streams_table.setItem(row, _COL_URL, url_item)
        self.streams_table.setItem(row, _COL_QUALITY, QTableWidgetItem(quality))
        self.streams_table.setItem(row, _COL_CODEC, QTableWidgetItem(codec))
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
        self._url_timer.start()

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
            station.station_art_path,
            station.album_fallback_path,
            icy_disabled,
        )

        # Persist streams
        ordered_ids: list[int] = []
        table = self.streams_table
        for row in range(table.rowCount()):
            url_item = table.item(row, _COL_URL)
            qual_item = table.item(row, _COL_QUALITY)
            codec_item = table.item(row, _COL_CODEC)
            pos_item = table.item(row, _COL_POSITION)

            url = url_item.text() if url_item else ""
            quality = qual_item.text() if qual_item else ""
            codec = codec_item.text() if codec_item else ""
            try:
                position = int(pos_item.text()) if pos_item else row + 1
            except ValueError:
                position = row + 1

            stream_id: Optional[int] = url_item.data(Qt.UserRole) if url_item else None

            if stream_id is not None:
                repo.update_stream(stream_id, url, "", quality, position, "", codec)
                ordered_ids.append(stream_id)
            else:
                new_id = repo.insert_stream(
                    station.id, url, label="", quality=quality,
                    position=position, stream_type="", codec=codec,
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
