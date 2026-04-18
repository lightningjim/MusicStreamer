"""Phase 39-02: DiscoveryDialog — Radio-Browser.info search, preview, save.

Non-modal QDialog for UI-06. Key behaviors:
  D-09: Search bar with tag/country filter combos.
  D-10: Filters populated on open via daemon threads (started in showEvent).
  D-11: Per-row play/stop preview via main Player instance.
  D-12: Per-row save to library using url_resolved preference.
  D-13: Search runs on daemon thread with indeterminate progress bar.

Security:
  T-39-04: QStandardItem cells are plain-text by default — no markup injection.
  T-39-06: limit=50 caps result set size.

Lifetime: all signal connections use bound methods (no self-capturing lambdas)
per QA-05. Filter workers are started lazily in showEvent to avoid emitting
signals onto unshown (or already-closed) widgets.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import radio_browser
from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt import icons_rc  # noqa: F401  # register :/icons/* resources


# ---------------------------------------------------------------------------
# Icon helpers (Phase 40.1-02: D-03/D-04/D-05 icon-only play toggle)
# ---------------------------------------------------------------------------


def _play_icon() -> QIcon:
    return QIcon.fromTheme(
        "media-playback-start-symbolic",
        QIcon(":/icons/media-playback-start-symbolic.svg"),
    )


def _stop_icon() -> QIcon:
    return QIcon.fromTheme(
        "media-playback-stop-symbolic",
        QIcon(":/icons/media-playback-stop-symbolic.svg"),
    )


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------


class _TagWorker(QThread):
    """Fetch tag list from Radio-Browser on a worker thread."""

    finished = Signal(list)
    error = Signal(str)

    def run(self) -> None:
        try:
            tags = radio_browser.fetch_tags()
            self.finished.emit(tags)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _CountryWorker(QThread):
    """Fetch country list from Radio-Browser on a worker thread."""

    finished = Signal(list)
    error = Signal(str)

    def run(self) -> None:
        try:
            countries = radio_browser.fetch_countries()
            self.finished.emit(countries)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _SearchWorker(QThread):
    """Search Radio-Browser stations on a worker thread."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        name: str,
        tag: str,
        countrycode: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._tag = tag
        self._countrycode = countrycode

    def run(self) -> None:
        try:
            results = radio_browser.search_stations(
                name=self._name,
                tag=self._tag,
                countrycode=self._countrycode,
                limit=50,
            )
            self.finished.emit(results)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------

_COL_NAME = 0
_COL_TAGS = 1
_COL_COUNTRY = 2
_COL_BITRATE = 3
_COL_PLAY = 4
_COL_SAVE = 5
_TOTAL_COLS = 6


# ---------------------------------------------------------------------------
# DiscoveryDialog
# ---------------------------------------------------------------------------


class DiscoveryDialog(QDialog):
    """Non-modal dialog for Radio-Browser.info station discovery.

    Args:
        player: Main application Player instance.
        repo:   Application Repo instance.
        toast_callback: ``Callable[[str], None]`` — typically
            ``main_window.show_toast``.
        parent: Optional parent widget.
    """

    # Emitted after a successful save (lets StationListPanel refresh).
    station_saved = Signal()

    def __init__(
        self,
        player,
        repo,
        toast_callback: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._player = player
        self._repo = repo
        self._toast_callback = toast_callback
        self._results: List[dict] = []
        self._previewing_row: int = -1
        self._save_buttons: List[QPushButton] = []
        self._play_buttons: List[QPushButton] = []
        self._filter_load_started: bool = False

        # Workers stored as instance attrs for lifetime safety
        self._tag_worker: Optional[_TagWorker] = None
        self._country_worker: Optional[_CountryWorker] = None
        self._search_worker: Optional[_SearchWorker] = None

        self.setWindowTitle("Discover Stations")
        self.setMinimumSize(720, 520)
        self.setModal(False)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Search bar row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search stations...")
        self._search_edit.returnPressed.connect(self._start_search)
        search_row.addWidget(self._search_edit, 1)

        self._tag_combo = QComboBox(self)
        self._tag_combo.addItem("Loading...")
        self._tag_combo.setMinimumWidth(140)
        search_row.addWidget(self._tag_combo)

        self._country_combo = QComboBox(self)
        self._country_combo.addItem("Loading...")
        self._country_combo.setMinimumWidth(140)
        search_row.addWidget(self._country_combo)

        self._search_btn = QPushButton("Search Stations", self)
        self._search_btn.setDefault(True)
        self._search_btn.clicked.connect(self._start_search)
        search_row.addWidget(self._search_btn)

        root.addLayout(search_row)

        # Progress bar (indeterminate; hidden when idle)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(4)
        root.addWidget(self._progress_bar)

        # Results table
        self._model = QStandardItemModel(0, _TOTAL_COLS, self)
        self._model.setHorizontalHeaderLabels(
            ["Name", "Tags", "Country", "Bitrate", "Play", "Save"]
        )

        self._results_table = QTableView(self)
        self._results_table.setModel(self._model)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.setSelectionBehavior(QTableView.SelectRows)
        self._results_table.setSelectionMode(QTableView.SingleSelection)
        self._results_table.setEditTriggers(QTableView.NoEditTriggers)
        self._results_table.setShowGrid(False)

        hdr = self._results_table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_TAGS, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_COUNTRY, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_BITRATE, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_PLAY, QHeaderView.Fixed)
        hdr.setSectionResizeMode(_COL_SAVE, QHeaderView.Fixed)
        self._results_table.setColumnWidth(_COL_TAGS, 160)
        self._results_table.setColumnWidth(_COL_COUNTRY, 80)
        self._results_table.setColumnWidth(_COL_BITRATE, 80)
        self._results_table.setColumnWidth(_COL_PLAY, 60)
        self._results_table.setColumnWidth(_COL_SAVE, 60)

        root.addWidget(self._results_table, 1)

        # Button box — Close
        btn_box = QDialogButtonBox(QDialogButtonBox.Close, self)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # showEvent: start filter workers once on first show
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._filter_load_started:
            self._filter_load_started = True
            self._start_filter_load()

    # ------------------------------------------------------------------
    # Filter population (worker threads)
    # ------------------------------------------------------------------

    def _start_filter_load(self) -> None:
        self._tag_worker = _TagWorker(self)
        self._tag_worker.finished.connect(self._on_tags_loaded)
        self._tag_worker.error.connect(self._on_filter_load_error)
        self._tag_worker.start()

        self._country_worker = _CountryWorker(self)
        self._country_worker.finished.connect(self._on_countries_loaded)
        self._country_worker.error.connect(self._on_filter_load_error)
        self._country_worker.start()

    def _on_tags_loaded(self, tags: list) -> None:
        self._tag_combo.clear()
        self._tag_combo.addItem("All Tags", "")
        for tag in tags:
            self._tag_combo.addItem(tag, tag)

    def _on_countries_loaded(self, countries: list) -> None:
        self._country_combo.clear()
        self._country_combo.addItem("All Countries", "")
        for item in countries:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                code, name = item
                self._country_combo.addItem(name, code)
            else:
                # Plain string fallback
                self._country_combo.addItem(str(item), str(item))

    def _on_filter_load_error(self, _msg: str) -> None:
        # Non-critical — combos keep placeholder text.
        pass

    # ------------------------------------------------------------------
    # Search flow (D-13)
    # ------------------------------------------------------------------

    def _start_search(self) -> None:
        name = self._search_edit.text().strip()
        tag = self._tag_combo.currentData() or ""
        countrycode = self._country_combo.currentData() or ""

        self._search_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)
        self._clear_table()

        self._search_worker = _SearchWorker(name, tag, countrycode, self)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _clear_table(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._save_buttons.clear()
        self._play_buttons.clear()
        self._results = []
        self._previewing_row = -1

    def _on_search_finished(self, results: list) -> None:
        self._progress_bar.setVisible(False)
        self._search_btn.setEnabled(True)
        self._results = list(results)
        self._save_buttons = []
        self._play_buttons = []

        self._model.removeRows(0, self._model.rowCount())

        for row_idx, result in enumerate(results):
            name_item = QStandardItem(result.get("name", ""))
            tags_item = QStandardItem(result.get("tags", ""))
            country_item = QStandardItem(
                result.get("country", "") or result.get("countrycode", "")
            )
            bitrate_val = result.get("bitrate", 0)
            bitrate_item = QStandardItem(str(bitrate_val) if bitrate_val else "")

            # Play/Save placeholder items (widgets set via setIndexWidget below)
            play_placeholder = QStandardItem()
            save_placeholder = QStandardItem()

            self._model.appendRow(
                [name_item, tags_item, country_item, bitrate_item,
                 play_placeholder, save_placeholder]
            )

            play_btn = QPushButton(self._results_table)
            play_btn.setIcon(_play_icon())
            play_btn.setAccessibleName("Play preview")
            play_btn.setToolTip("Play preview")
            play_btn.clicked.connect(self._make_play_slot(row_idx))
            self._play_buttons.append(play_btn)

            save_btn = QPushButton("Save", self._results_table)
            save_btn.clicked.connect(self._make_save_slot(row_idx))
            self._save_buttons.append(save_btn)

            self._results_table.setIndexWidget(
                self._model.index(row_idx, _COL_PLAY), play_btn
            )
            self._results_table.setIndexWidget(
                self._model.index(row_idx, _COL_SAVE), save_btn
            )

    def _on_search_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._search_btn.setEnabled(True)
        self._toast_callback(f"Search error: {msg}")

    # ------------------------------------------------------------------
    # Per-row action closure helpers (D-11, D-12)
    # ------------------------------------------------------------------

    def _make_play_slot(self, row_index: int):
        def _slot():
            self._on_play_row(row_index)
        return _slot

    def _make_save_slot(self, row_index: int):
        def _slot():
            self._on_save_row(row_index)
        return _slot

    def _get_save_button(self, row_index: int) -> Optional[QPushButton]:
        """Return the save button for ``row_index`` (used in tests)."""
        if 0 <= row_index < len(self._save_buttons):
            return self._save_buttons[row_index]
        return None

    def _get_play_button(self, row_index: int) -> Optional[QPushButton]:
        """Return the play button for ``row_index``."""
        if 0 <= row_index < len(self._play_buttons):
            return self._play_buttons[row_index]
        return None

    # ------------------------------------------------------------------
    # Save flow (D-12)
    # ------------------------------------------------------------------

    def _on_save_row(self, row_index: int) -> None:
        if row_index >= len(self._results):
            return
        result = self._results[row_index]
        stream_url = result.get("url_resolved") or result.get("url", "")
        if not stream_url:
            return
        station_id = self._repo.insert_station(
            name=result.get("name", "Unknown"),
            url=stream_url,
            provider_name="Radio-Browser",
            tags=result.get("tags", ""),
        )
        # D-11 + G-2 Option 1: persist RadioBrowser bitrate via post-insert fix-up.
        # insert_station auto-created a stream at position=1 via insert_stream(station_id, url);
        # update it with bitrate_kbps. Mirrors aa_import.import_stations_multi:188-196.
        bitrate_val = int(result.get("bitrate", 0) or 0)
        if bitrate_val:
            streams = self._repo.list_streams(station_id)
            if streams:
                s = streams[0]
                self._repo.update_stream(
                    s.id, s.url, s.label, s.quality, s.position,
                    s.stream_type, s.codec,
                    bitrate_kbps=bitrate_val,
                )
        self._toast_callback(f"Saved '{result.get('name', 'station')}' to library")
        if row_index < len(self._save_buttons):
            self._save_buttons[row_index].setEnabled(False)
        self.station_saved.emit()

    # ------------------------------------------------------------------
    # Preview play flow (D-11)
    # ------------------------------------------------------------------

    def _on_play_row(self, row_index: int) -> None:
        if row_index >= len(self._results):
            return
        result = self._results[row_index]

        if self._previewing_row == row_index:
            self._player.stop()
            self._previewing_row = -1
            if row_index < len(self._play_buttons):
                btn = self._play_buttons[row_index]
                btn.setIcon(_play_icon())
                btn.setAccessibleName("Play preview")
                btn.setToolTip("Play preview")
        else:
            # Reset icon on previously-previewing row
            if self._previewing_row >= 0 and self._previewing_row < len(self._play_buttons):
                prev_btn = self._play_buttons[self._previewing_row]
                prev_btn.setIcon(_play_icon())
                prev_btn.setAccessibleName("Play preview")
                prev_btn.setToolTip("Play preview")

            stream_url = result.get("url_resolved") or result.get("url", "")
            temp_station = Station(
                id=-1,
                name=result["name"],
                provider_id=None,
                provider_name="Radio-Browser",
                tags=result.get("tags", ""),
                station_art_path=None,
                album_fallback_path=None,
            )
            temp_station.streams = [
                StationStream(id=-1, station_id=-1, url=stream_url)
            ]
            self._player.play(temp_station)
            self._previewing_row = row_index
            if row_index < len(self._play_buttons):
                btn = self._play_buttons[row_index]
                btn.setIcon(_stop_icon())
                btn.setAccessibleName("Stop preview")
                btn.setToolTip("Stop preview")

    # ------------------------------------------------------------------
    # Close / reject — stop any active preview
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._previewing_row >= 0:
            self._player.stop()
            self._previewing_row = -1
        super().closeEvent(event)

    def reject(self) -> None:
        if self._previewing_row >= 0:
            self._player.stop()
            self._previewing_row = -1
        super().reject()
