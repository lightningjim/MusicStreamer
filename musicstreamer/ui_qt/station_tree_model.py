"""Phase 37-01: StationTreeModel — provider-grouped station list model.

Two-level hierarchy:
  root (invisible) -> provider groups -> station rows

Provider rows are non-selectable (D-03). Station rows emit the clicked
signal via QTreeView; StationListPanel resolves them to Station via
`station_for_index`.

Icons are cached via QPixmapCache keyed on station art path; the bundled
`audio-x-generic-symbolic.svg` fallback is used when the station has no art
or the art file is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont

from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import load_station_icon


@dataclass
class _TreeNode:
    kind: str  # "root" | "provider" | "station"
    label: str
    parent: Optional["_TreeNode"] = None
    children: list["_TreeNode"] = field(default_factory=list)
    station: Optional[Station] = None


class StationTreeModel(QAbstractItemModel):
    """Provider-grouped station tree backing QTreeView (D-01)."""

    def __init__(self, stations: list[Station], parent=None) -> None:
        super().__init__(parent)
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, stations: list[Station]) -> None:
        self.beginResetModel()
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)
        self.endResetModel()

    def station_for_index(self, index: QModelIndex) -> Optional[Station]:
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()
        if node is None:
            return None
        return node.station if node.kind == "station" else None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _populate(self, stations: list[Station]) -> None:
        groups: dict[str, _TreeNode] = {}
        for st in stations:
            pname = st.provider_name or "Ungrouped"
            grp = groups.get(pname)
            if grp is None:
                grp = _TreeNode(kind="provider", label=pname, parent=self._root)
                self._root.children.append(grp)
                groups[pname] = grp
            grp.children.append(
                _TreeNode(
                    kind="station",
                    label=st.name,
                    parent=grp,
                    station=st,
                )
            )
        # D-04: append (N) count suffix to each provider label
        for grp in self._root.children:
            grp.label = f"{grp.label} ({len(grp.children)})"

    # ------------------------------------------------------------------
    # QAbstractItemModel overrides
    # ------------------------------------------------------------------

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt override)
        return 1

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if not parent.isValid():
            return len(self._root.children)
        node: _TreeNode = parent.internalPointer()
        if node is None:
            return 0
        return len(node.children)

    def index(self, row, column, parent=QModelIndex()) -> QModelIndex:
        if column != 0:
            return QModelIndex()
        parent_node = (
            parent.internalPointer() if parent.isValid() else self._root
        )
        if parent_node is None:
            return QModelIndex()
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, 0, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: A003
        if not index.isValid():
            return QModelIndex()
        node: _TreeNode = index.internalPointer()
        if node is None:
            return QModelIndex()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        grandparent = parent_node.parent or self._root
        row = grandparent.children.index(parent_node)
        return self.createIndex(row, 0, parent_node)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        node: _TreeNode = index.internalPointer()
        if node is None:
            return Qt.NoItemFlags
        if node.kind == "station":
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        # Provider groups: enabled (so they expand/collapse) but NOT selectable.
        return Qt.ItemIsEnabled

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()
        if node is None:
            return None
        if role == Qt.DisplayRole:
            return node.label
        if role == Qt.DecorationRole and node.kind == "station":
            return load_station_icon(node.station)
        if role == Qt.FontRole and node.kind == "provider":
            # UI-SPEC: 13pt DemiBold for provider group headers.
            f = QFont()
            f.setBold(True)
            f.setPointSize(13)
            return f
        if role == Qt.UserRole and node.kind == "station":
            return node.station
        return None
