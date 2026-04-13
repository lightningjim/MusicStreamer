"""Phase 37-01 / Phase 38-01 / Phase 38-02: StationListPanel.

Left-panel widget containing:
  1. Segmented control [Stations | Favorites] (always visible, top)
  2. QStackedWidget:
     - Page 0 (Stations): Recently Played + filter strip (search, chips, clear-all) + tree
     - Page 1 (Favorites): FavoritesView (starred stations + tracks)

Emits `station_activated(Station)` when user clicks a station in tree, recently
played, or the favorites view. Provider group rows in the tree are non-selectable.

Emits `station_favorited(Station, bool)` when a station star is toggled in the
tree (for MainWindow to show toast).

Signal connections use bound methods only (no self-capturing lambdas) per QA-05.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QSize, Qt, Signal
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
    QSizePolicy,
    QStackedWidget,
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
from musicstreamer.ui_qt.favorites_view import FavoritesView
from musicstreamer.ui_qt.station_star_delegate import StationStarDelegate, _star_rect


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


_SEG_QSS = """
QPushButton[segState="active"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border-radius: 4px;
}
QPushButton[segState="inactive"] {
    background-color: transparent;
    color: palette(button-text);
    border-radius: 4px;
}
"""


class StationListPanel(QWidget):
    """Left-panel widget — segmented control + QStackedWidget (Stations | Favorites)."""

    station_activated = Signal(Station)
    station_favorited = Signal(Station, bool)  # (station, is_now_favorite)

    def __init__(self, repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setMinimumWidth(280)  # UI-SPEC component inventory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        # ------------------------------------------------------------------
        # Segmented control [Stations | Favorites] (D-05, D-12) — always visible
        # ------------------------------------------------------------------
        seg_row = QWidget(self)
        seg_layout = QHBoxLayout(seg_row)
        seg_layout.setContentsMargins(16, 8, 16, 8)
        seg_layout.setSpacing(0)

        self._stations_btn = QPushButton("Stations", seg_row)
        self._favorites_btn = QPushButton("Favorites", seg_row)

        for btn in (self._stations_btn, self._favorites_btn):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(32)
            btn.setStyleSheet(_SEG_QSS)

        self._seg_group = QButtonGroup(self)
        self._seg_group.setExclusive(True)
        self._seg_group.addButton(self._stations_btn, 0)
        self._seg_group.addButton(self._favorites_btn, 1)

        seg_layout.addWidget(self._stations_btn)
        seg_layout.addWidget(self._favorites_btn)
        layout.addWidget(seg_row)

        # Set initial state
        self._set_seg_state(self._stations_btn, True)
        self._set_seg_state(self._favorites_btn, False)

        # ------------------------------------------------------------------
        # QStackedWidget (D-15)
        # ------------------------------------------------------------------
        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, stretch=1)

        # -- Page 0: Stations mode ----------------------------------------
        stations_page = QWidget()
        sp_layout = QVBoxLayout(stations_page)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        sp_layout.setSpacing(0)

        # Recently Played section (D-02)
        recent_label = QLabel("Recently Played")
        recent_label.setContentsMargins(16, 0, 16, 4)
        rlabel_font = QFont()
        rlabel_font.setPointSize(9)
        rlabel_font.setWeight(QFont.Normal)
        recent_label.setFont(rlabel_font)
        sp_layout.addWidget(recent_label)

        self.recent_view = QListView(stations_page)
        self._recent_model = QStandardItemModel(self.recent_view)
        self.recent_view.setModel(self._recent_model)
        self.recent_view.setIconSize(QSize(32, 32))
        self.recent_view.setMaximumHeight(160)
        self.recent_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recent_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recent_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent_view.clicked.connect(self._on_recent_clicked)
        sp_layout.addWidget(self.recent_view)

        self._populate_recent()

        # Separator
        sep = QFrame(stations_page)
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sp_layout.addWidget(sep)

        # Filter strip toggle button
        self._filter_toggle = QPushButton("\u25b6 Filters", stations_page)
        self._filter_toggle.setFlat(True)
        self._filter_toggle.setFixedHeight(24)
        self._filter_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding-left: 16px; color: palette(highlight); }"
        )
        self._filter_toggle.clicked.connect(self._toggle_filter_strip)
        sp_layout.addWidget(self._filter_toggle)

        # Collapsible filter strip container
        self._filter_strip = QWidget(stations_page)
        fs_layout = QVBoxLayout(self._filter_strip)
        fs_layout.setContentsMargins(0, 0, 0, 0)
        fs_layout.setSpacing(0)

        # Filter strip — Search box (D-12)
        self._search_box = QLineEdit(self._filter_strip)
        self._search_box.setPlaceholderText("Search stations\u2026")
        self._search_box.setClearButtonEnabled(True)
        search_wrapper = QWidget(self._filter_strip)
        sw_layout = QHBoxLayout(search_wrapper)
        sw_layout.setContentsMargins(16, 4, 16, 4)
        sw_layout.addWidget(self._search_box)
        fs_layout.addWidget(search_wrapper)
        self._search_box.textChanged.connect(self._on_search_changed)

        # Provider chip row (D-13)
        self._provider_chip_group = QButtonGroup(self)
        self._provider_chip_group.setExclusive(False)
        provider_chip_container = QWidget(self._filter_strip)
        provider_chip_layout = FlowLayout(provider_chip_container, h_spacing=4, v_spacing=8)
        provider_chip_wrapper = QWidget(self._filter_strip)
        pcw_layout = QHBoxLayout(provider_chip_wrapper)
        pcw_layout.setContentsMargins(16, 4, 16, 0)
        pcw_layout.addWidget(provider_chip_container)
        fs_layout.addWidget(provider_chip_wrapper)

        self._provider_chip_container = provider_chip_container
        self._provider_chip_layout = provider_chip_layout

        # Tag chip row (D-13)
        self._tag_chip_group = QButtonGroup(self)
        self._tag_chip_group.setExclusive(False)
        tag_chip_container = QWidget(self._filter_strip)
        tag_chip_layout = FlowLayout(tag_chip_container, h_spacing=4, v_spacing=8)
        tag_chip_wrapper = QWidget(self._filter_strip)
        tcw_layout = QHBoxLayout(tag_chip_wrapper)
        tcw_layout.setContentsMargins(16, 4, 16, 0)
        tcw_layout.addWidget(tag_chip_container)
        fs_layout.addWidget(tag_chip_wrapper)

        self._tag_chip_container = tag_chip_container
        self._tag_chip_layout = tag_chip_layout

        self._build_chip_rows()

        self._provider_chip_group.buttonClicked.connect(self._on_provider_chip_clicked)
        self._tag_chip_group.buttonClicked.connect(self._on_tag_chip_clicked)

        # "Clear all" button (D-14)
        clear_row = QWidget(self._filter_strip)
        clear_layout = QHBoxLayout(clear_row)
        clear_layout.setContentsMargins(16, 4, 16, 4)
        clear_layout.addStretch(1)
        self._clear_btn = QPushButton(self._filter_strip)
        self._clear_btn.setToolTip("Clear all filters")
        clear_icon = QIcon(":/icons/edit-clear-all-symbolic.svg")
        if not clear_icon.isNull():
            self._clear_btn.setIcon(clear_icon)
        else:
            self._clear_btn.setText("\u2715 Clear")
        clear_layout.addWidget(self._clear_btn)
        fs_layout.addWidget(clear_row)
        self._clear_btn.clicked.connect(self._clear_all_filters)

        # Start collapsed
        self._filter_strip.setVisible(False)
        sp_layout.addWidget(self._filter_strip)

        # Provider-grouped station tree (D-01) + proxy
        self.tree = QTreeView(stations_page)
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
        self.tree.clicked.connect(self._on_tree_activated)
        self.tree.doubleClicked.connect(self._on_tree_activated)
        sp_layout.addWidget(self.tree, stretch=1)

        # Station star delegate (D-09)
        self._star_delegate = StationStarDelegate(self._repo, parent=self.tree)
        self.tree.setItemDelegate(self._star_delegate)
        # editorEvent won't fire with NoEditTriggers, so use viewport event filter
        self.tree.viewport().installEventFilter(self)

        self._stack.addWidget(stations_page)  # index 0

        # -- Page 1: Favorites mode ----------------------------------------
        self._favorites_view = FavoritesView(self._repo, parent=self._stack)
        self._favorites_view.station_activated.connect(self.station_activated.emit)
        self._favorites_view.favorites_changed.connect(self._on_favorites_changed)
        self._stack.addWidget(self._favorites_view)  # index 1

        # Wire segmented control
        self._stations_btn.clicked.connect(self._on_stations_clicked)
        self._favorites_btn.clicked.connect(self._on_favorites_clicked)

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

    def _toggle_filter_strip(self) -> None:
        visible = not self._filter_strip.isVisible()
        self._filter_strip.setVisible(visible)
        self._filter_toggle.setText(("\u25bc Filters" if visible else "\u25b6 Filters"))

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
            # Skip if click was on the star area — eventFilter handles that
            vis_rect = self.tree.visualRect(index)
            cursor_pos = self.tree.viewport().mapFromGlobal(self.tree.cursor().pos())
            if _star_rect(vis_rect).contains(cursor_pos):
                return
            self.station_activated.emit(station)

    def _on_recent_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        station = index.data(Qt.UserRole)
        if isinstance(station, Station):
            self.station_activated.emit(station)

    # ------------------------------------------------------------------
    # Segmented control helpers (D-05, D-15)
    # ------------------------------------------------------------------

    def _set_seg_state(self, btn: QPushButton, active: bool) -> None:
        btn.setProperty("segState", "active" if active else "inactive")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()

    def _on_stations_clicked(self) -> None:
        self._stack.setCurrentIndex(0)
        self._set_seg_state(self._stations_btn, True)
        self._set_seg_state(self._favorites_btn, False)

    def _on_favorites_clicked(self) -> None:
        self._stack.setCurrentIndex(1)
        self._set_seg_state(self._favorites_btn, True)
        self._set_seg_state(self._stations_btn, False)
        self._favorites_view.refresh()

    def _on_favorites_changed(self) -> None:
        """Slot called when FavoritesView removes a favorite — no-op here, view handles itself."""
        pass

    # ------------------------------------------------------------------
    # Viewport event filter — star click detection (D-09)
    # editorEvent won't fire with NoEditTriggers, so intercept here.
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self.tree.viewport() and event.type() == QEvent.MouseButtonRelease:
            pos = event.position().toPoint()
            index = self.tree.indexAt(pos)
            if index.isValid():
                source_idx = self._proxy.mapToSource(index)
                station = self.model.station_for_index(source_idx)
                if station is not None:
                    vis_rect = self.tree.visualRect(index)
                    if _star_rect(vis_rect).contains(pos):
                        self._on_station_star_toggled(station)
                        return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Station star delegate slot (D-09)
    # ------------------------------------------------------------------

    def _on_station_star_toggled(self, station: Station) -> None:
        new_fav = not self._repo.is_favorite_station(station.id)
        self._repo.set_station_favorite(station.id, new_fav)
        self.tree.viewport().update()
        self.station_favorited.emit(station, new_fav)
        # Refresh favorites view if it's active
        if self._stack.currentIndex() == 1:
            self._favorites_view.refresh()
