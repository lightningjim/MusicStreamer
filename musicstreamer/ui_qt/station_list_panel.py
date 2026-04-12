"""Phase 37-01: StationListPanel.

Left-panel widget containing:
  1. "Recently Played" label + QListView (top, max 160px tall)
  2. QFrame.HLine separator
  3. Provider-grouped QTreeView backed by StationTreeModel (stretch)

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
    QFrame,
    QLabel,
    QListView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.models import Station
from musicstreamer.ui_qt.station_tree_model import StationTreeModel


_FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"


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
    """Left-panel widget — Recently Played + provider-grouped station tree."""

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
        # Main provider-grouped station tree (D-01)
        # ------------------------------------------------------------------
        self.tree = QTreeView(self)
        self.model = StationTreeModel(self._repo.list_stations())
        self.tree.setModel(self.model)
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

    # ----------------------------------------------------------------------
    # Slots (bound methods — no self-capturing lambdas)
    # ----------------------------------------------------------------------

    def _on_tree_activated(self, index: QModelIndex) -> None:
        station = self.model.station_for_index(index)
        if station is not None:
            self.station_activated.emit(station)

    def _on_recent_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        station = index.data(Qt.UserRole)
        if isinstance(station, Station):
            self.station_activated.emit(station)
