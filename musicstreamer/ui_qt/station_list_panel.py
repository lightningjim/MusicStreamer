"""Phase 37-01 / Phase 38-01: StationListPanel.

Left-panel widget containing:
  1. "Recently Played" label + QListView (top, max 160px tall)
  2. QFrame.HLine separator
  3. Filter strip — search box, provider chip row, tag chip row, clear-all button
  4. Provider-grouped QTreeView backed by StationTreeModel + StationFilterProxyModel (stretch)

Emits `station_activated(Station)` when the user clicks either a recent row
or a station row in the tree. Provider group rows are non-selectable and
click events on them are ignored (D-03).

Signal connections use bound methods only (no self-capturing lambdas) to
stay clear of the QA-05 widget-lifetime pitfall.
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap, QPixmapCache, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer import filter_utils
from musicstreamer.models import Station
from musicstreamer.ui_qt.station_tree_model import StationTreeModel
from musicstreamer.ui_qt.station_filter_proxy import StationFilterProxyModel
from musicstreamer.ui_qt.flow_layout import FlowLayout


_FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"

# UI-SPEC: chip QSS for selected/unselected states (D-13)
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


def _load_station_icon(station: Station) -> QIcon:
    """QPixmapCache-backed 32x32 station icon with fallback.

    Shared with StationTreeModel._icon_for_station semantics; kept as a
    module-level helper so RecentlyPlayedView can reuse it without coupling
    to the tree model internals.
    """
    path = station.station_art_path or _FALLBACK_ICON
    key = f"station-logo:{path}"
    pix = QPixmap()
    if not QPixmapCache.find(key, pix):
        pix = QPixmap(path)
        if pix.isNull():
            pix = QPixmap(_FALLBACK_ICON)
        pix = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        QPixmapCache.insert(key, pix)
    return QIcon(pix)


class StationListPanel(QWidget):
    """Left-panel widget — Recently Played + filter strip + provider-grouped station tree."""

    station_activated = Signal(Station)

    def __init__(self, repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setMinimumWidth(280)  # UI-SPEC component inventory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        # ------------------------------------------------------------------
        # Recently Played section (D-02)
        # ------------------------------------------------------------------
        recent_label = QLabel("Recently Played")
        recent_label.setContentsMargins(16, 0, 16, 4)
        # UI-SPEC Typography — Label role: 9pt Normal.
        rlabel_font = QFont()
        rlabel_font.setPointSize(9)
        rlabel_font.setWeight(QFont.Normal)
        recent_label.setFont(rlabel_font)
        layout.addWidget(recent_label)

        self.recent_view = QListView(self)
        self._recent_model = QStandardItemModel(self.recent_view)
        self.recent_view.setModel(self._recent_model)
        self.recent_view.setIconSize(QSize(32, 32))
        self.recent_view.setMaximumHeight(160)  # UI-SPEC
        self.recent_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recent_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recent_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent_view.clicked.connect(self._on_recent_clicked)
        layout.addWidget(self.recent_view)

        self._populate_recent()

        # ------------------------------------------------------------------
        # Separator
        # ------------------------------------------------------------------
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ------------------------------------------------------------------
        # Filter strip — Search box (D-12)
        # ------------------------------------------------------------------
        self._search_box = QLineEdit(self)
        self._search_box.setPlaceholderText("Search stations\u2026")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setContentsMargins(16, 4, 16, 4)
        # Apply L/R margins via wrapper widget with a layout
        search_wrapper = QWidget(self)
        sw_layout = QHBoxLayout(search_wrapper)
        sw_layout.setContentsMargins(16, 4, 16, 4)
        sw_layout.addWidget(self._search_box)
        layout.addWidget(search_wrapper)
        self._search_box.textChanged.connect(self._on_search_changed)

        # ------------------------------------------------------------------
        # Provider chip row (D-13, D-02)
        # ------------------------------------------------------------------
        self._provider_chip_group = QButtonGroup(self)
        self._provider_chip_group.setExclusive(False)
        provider_chip_container = QWidget(self)
        provider_chip_layout = FlowLayout(provider_chip_container, h_spacing=4, v_spacing=8)
        provider_chip_container.setContentsMargins(16, 0, 16, 0)
        provider_chip_wrapper = QWidget(self)
        pcw_layout = QHBoxLayout(provider_chip_wrapper)
        pcw_layout.setContentsMargins(16, 4, 16, 0)
        pcw_layout.addWidget(provider_chip_container)
        layout.addWidget(provider_chip_wrapper)

        self._provider_chip_container = provider_chip_container
        self._provider_chip_layout = provider_chip_layout

        # ------------------------------------------------------------------
        # Tag chip row (D-13, D-02)
        # ------------------------------------------------------------------
        self._tag_chip_group = QButtonGroup(self)
        self._tag_chip_group.setExclusive(False)
        tag_chip_container = QWidget(self)
        tag_chip_layout = FlowLayout(tag_chip_container, h_spacing=4, v_spacing=8)
        tag_chip_wrapper = QWidget(self)
        tcw_layout = QHBoxLayout(tag_chip_wrapper)
        tcw_layout.setContentsMargins(16, 4, 16, 0)
        tcw_layout.addWidget(tag_chip_container)
        layout.addWidget(tag_chip_wrapper)

        self._tag_chip_container = tag_chip_container
        self._tag_chip_layout = tag_chip_layout

        # Populate chips after layouts are set up
        self._build_chip_rows()

        # Connect chip group signals
        self._provider_chip_group.buttonClicked.connect(self._on_provider_chip_clicked)
        self._tag_chip_group.buttonClicked.connect(self._on_tag_chip_clicked)

        # ------------------------------------------------------------------
        # "Clear all" button (D-14) — right-aligned
        # ------------------------------------------------------------------
        clear_row = QWidget(self)
        clear_layout = QHBoxLayout(clear_row)
        clear_layout.setContentsMargins(16, 4, 16, 4)
        clear_layout.addStretch(1)
        self._clear_btn = QPushButton(self)
        self._clear_btn.setToolTip("Clear all filters")
        clear_icon = QIcon(":/icons/edit-clear-all-symbolic.svg")
        if not clear_icon.isNull():
            self._clear_btn.setIcon(clear_icon)
        else:
            self._clear_btn.setText("\u2715 Clear")
        clear_layout.addWidget(self._clear_btn)
        layout.addWidget(clear_row)
        self._clear_btn.clicked.connect(self._clear_all_filters)

        # ------------------------------------------------------------------
        # Main provider-grouped station tree (D-01) + proxy
        # ------------------------------------------------------------------
        self.tree = QTreeView(self)
        self.model = StationTreeModel(self._repo.list_stations())
        self._proxy = StationFilterProxyModel(parent=self)
        self._proxy.setSourceModel(self.model)
        self.tree.setModel(self._proxy)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(32, 32))
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.expandAll()
        # QA-05: bound methods only, never self-capturing lambdas.
        self.tree.clicked.connect(self._on_tree_activated)
        self.tree.doubleClicked.connect(self._on_tree_activated)
        layout.addWidget(self.tree, stretch=1)

    # ----------------------------------------------------------------------
    # Population
    # ----------------------------------------------------------------------

    def _populate_recent(self) -> None:
        self._recent_model.clear()
        stations = self._repo.list_recently_played(3)
        for station in stations:
            item = QStandardItem(station.name)
            item.setIcon(_load_station_icon(station))
            item.setEditable(False)
            item.setData(station, Qt.UserRole)
            self._recent_model.appendRow(item)

    def _build_chip_rows(self) -> None:
        """Populate provider and tag chip rows from repo data. Alphabetical order."""
        stations = self._repo.list_stations()

        # Provider chips
        providers = sorted({s.provider_name for s in stations if s.provider_name})
        for name in providers:
            btn = QPushButton(name, self._provider_chip_container)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(_CHIP_QSS)
            btn.setProperty("chipState", "unselected")
            self._provider_chip_layout.addWidget(btn)
            self._provider_chip_group.addButton(btn)

        # Tag chips
        all_tags = sorted({
            t
            for s in stations
            for t in filter_utils.normalize_tags(s.tags)
            if t
        })
        for tag in all_tags:
            btn = QPushButton(tag, self._tag_chip_container)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(_CHIP_QSS)
            btn.setProperty("chipState", "unselected")
            self._tag_chip_layout.addWidget(btn)
            self._tag_chip_group.addButton(btn)

    # ----------------------------------------------------------------------
    # Chip QSS helper (Pattern 4 from RESEARCH — unpolish/polish cycle)
    # ----------------------------------------------------------------------

    def _set_chip_state(self, btn: QPushButton, selected: bool) -> None:
        btn.setProperty("chipState", "selected" if selected else "unselected")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()

    # ----------------------------------------------------------------------
    # Slots (bound methods — no self-capturing lambdas)
    # ----------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._proxy.set_search(text)

    def _on_provider_chip_clicked(self, btn: QPushButton) -> None:
        self._set_chip_state(btn, btn.isChecked())
        provider_set = {
            b.text()
            for b in self._provider_chip_group.buttons()
            if b.isChecked()
        }
        self._proxy.set_providers(provider_set)

    def _on_tag_chip_clicked(self, btn: QPushButton) -> None:
        self._set_chip_state(btn, btn.isChecked())
        tag_set = {
            b.text()
            for b in self._tag_chip_group.buttons()
            if b.isChecked()
        }
        self._proxy.set_tags(tag_set)

    def _clear_all_filters(self) -> None:
        self._search_box.clear()
        for btn in self._provider_chip_group.buttons():
            btn.setChecked(False)
            self._set_chip_state(btn, False)
        for btn in self._tag_chip_group.buttons():
            btn.setChecked(False)
            self._set_chip_state(btn, False)
        self._proxy.clear_all()

    def _on_tree_activated(self, index: QModelIndex) -> None:
        # CRITICAL (Pitfall 1): map proxy index to source before station_for_index
        source_idx = self._proxy.mapToSource(index)
        station = self.model.station_for_index(source_idx)
        if station is not None:
            self.station_activated.emit(station)

    def _on_recent_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        station = index.data(Qt.UserRole)
        if isinstance(station, Station):
            self.station_activated.emit(station)
