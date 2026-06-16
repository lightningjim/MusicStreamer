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

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont, QPixmapCache

from musicstreamer.models import Station
from musicstreamer.ui_qt import _art_paths as _art_paths_mod
from musicstreamer.ui_qt._art_paths import load_station_icon


@dataclass
class _TreeNode:
    kind: str  # "root" | "provider" | "station"
    label: str
    parent: Optional["_TreeNode"] = None
    children: list["_TreeNode"] = field(default_factory=list)
    station: Optional[Station] = None
    provider_name: Optional[str] = None  # raw, never gets the " (N)" label suffix (Phase 55 / BUG-06)


class StationTreeModel(QAbstractItemModel):
    """Provider-grouped station tree backing QTreeView (D-01)."""

    # Cross-thread channel: worker emits PNG path (station_id, source_abs_path, thumb_abs_path).
    # CR-01: NO QPixmap off the GUI thread; _on_thumb_landing (main-thread slot) decodes.
    _thumb_landing = Signal(int, str, str)  # (station_id, source_abs_path, thumb_abs_path or "")

    def __init__(self, stations: list[Station], parent=None) -> None:
        super().__init__(parent)
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)
        # Dedup guard: station ids currently being processed by a daemon worker.
        # Access is main-thread-only (called from data() and slot); no lock needed.
        self._in_flight_thumbs: set[int] = set()
        # Explicit QueuedConnection: guarantees _on_thumb_landing runs on the main
        # thread even when _thumb_landing is emitted from the daemon worker's callback
        # lambda. Matches gbs_marquee.py cadence_changed_internal precedent.
        self._thumb_landing.connect(self._on_thumb_landing, Qt.QueuedConnection)

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

    def provider_name_at(self, row: int) -> Optional[str]:
        """Return the raw provider name at the given top-level row, or None.

        Bypasses the " (N)" label suffix added in _populate; the raw name is
        the round-tripable key for capture/restore in StationListPanel
        (Phase 55 / BUG-06).
        """
        if row < 0 or row >= len(self._root.children):
            return None
        node = self._root.children[row]
        return node.provider_name if node.kind == "provider" else None

    def index_for_station_id(self, station_id: int) -> QModelIndex:
        """Return a QModelIndex for the given station id, or QModelIndex() if not found.

        O(N) two-level walk over providers -> stations. Mirrors the walk in
        station_list_panel.select_station (lines 476-486) but operates on the
        source model's internal node list (no proxy).

        Pitfall #3: this is always called inside _on_thumb_landing to re-derive
        a fresh QModelIndex rather than storing one across the async boundary
        (stored QModelIndex may be invalidated by refresh()).
        """
        for prov_node in self._root.children:
            for child_row, child_node in enumerate(prov_node.children):
                if child_node.station is not None and child_node.station.id == station_id:
                    return self.createIndex(child_row, 0, child_node)
        return QModelIndex()

    def _request_thumb(self, station_id: int, source_path: str, thumb_path: str) -> None:
        """Enqueue async thumbnail generation for station_id (main-thread only).

        Dedup guard: if station_id is already in-flight, returns immediately
        (Pitfall #2 — prevents duplicate daemon threads during fast scroll).
        On enqueue: adds station_id to _in_flight_thumbs, spawns _generate_thumb,
        and wires the callback to emit _thumb_landing so the QueuedConnection
        delivers the landing to the main-thread slot _on_thumb_landing.

        The lambda maps _generate_thumb's callback(sid, src, path|None) to
        Signal(int, str, str) by passing path or "" for the None case;
        _on_thumb_landing treats a falsy third arg as failure.
        """
        if station_id in self._in_flight_thumbs:
            return
        self._in_flight_thumbs.add(station_id)
        # Bind emit to a local name to avoid capturing self in the daemon closure.
        # Call via module reference (_art_paths_mod._generate_thumb) so that
        # test monkeypatching of the module attribute is effective.
        emit = self._thumb_landing.emit
        _art_paths_mod._generate_thumb(
            source_path,
            thumb_path,
            station_id,
            lambda sid, src, path: emit(sid, src, path or ""),
        )

    def _on_thumb_landing(self, station_id: int, source_path: str, thumb_path: str) -> None:
        """Main-thread slot: evict stale cache entry and trigger row repaint.

        Delivered via Qt.QueuedConnection so this always runs on the main thread
        regardless of which thread emitted _thumb_landing.

        Steps:
        1. Clear the in-flight guard for station_id.
        2. If thumb_path is falsy (generation failed), return — the fallback icon
           stays and no repaint is needed.
        3. Evict the stale QPixmapCache entry keyed on the source path (not the
           thumb path). This matches the key used by load_station_icon and
           edit_station_dialog._invalidate_cache_for (cache key scheme: T-94-06).
        4. Re-derive a fresh QModelIndex via index_for_station_id (Pitfall #3:
           never store a QModelIndex across async boundaries).
        5. If the index is still valid (station not removed by refresh()), emit
           dataChanged so Qt re-queries data(DecorationRole) for that row, which
           will now find the fresh thumb on disk (fast path in load_station_icon).
        """
        self._in_flight_thumbs.discard(station_id)
        if not thumb_path:
            # Generation failed; fallback icon stays, no repaint needed.
            return
        # Evict the stale fallback entry so the next data() call loads the real thumb.
        QPixmapCache.remove(f"station-logo:{source_path}")
        idx = self.index_for_station_id(station_id)
        if idx.isValid():
            self.dataChanged.emit(idx, idx, [Qt.DecorationRole])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _populate(self, stations: list[Station]) -> None:
        groups: dict[str, _TreeNode] = {}
        for st in stations:
            pname = st.provider_name or "Ungrouped"
            grp = groups.get(pname)
            if grp is None:
                grp = _TreeNode(
                    kind="provider",
                    label=pname,
                    parent=self._root,
                    provider_name=pname,  # Phase 55 / BUG-06: round-tripable key for capture/restore
                )
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
            return load_station_icon(node.station, on_thumb_needed=self._request_thumb)
        if role == Qt.FontRole and node.kind == "provider":
            # UI-SPEC: 13pt DemiBold for provider group headers.
            f = QFont()
            f.setBold(True)
            f.setPointSize(13)
            return f
        if role == Qt.UserRole and node.kind == "station":
            return node.station
        return None
