"""Phase 38-01: StationFilterProxyModel.

QSortFilterProxyModel subclass that filters the provider-grouped
StationTreeModel by search text, provider set, and tag set.

Filter logic:
  - Search text: case-insensitive substring on station name (inactive when "")
  - Provider set: OR within — station matches if provider_name in set (inactive when empty)
  - Tag set: OR within — station matches if any tag in set (inactive when empty)
  - Between dimensions: AND logic (all active dimensions must match)

Provider group rows are shown when at least one child station passes all
filters (recursive child check — Pattern 1 from RESEARCH).
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel

from musicstreamer.filter_utils import matches_filter_multi


class StationFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy over StationTreeModel for search + multi-select chip filtering."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._provider_set: set[str] = set()
        self._tag_set: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_search(self, text: str) -> None:
        self._search_text = text
        self.invalidate()

    def set_providers(self, providers: set[str]) -> None:
        self._provider_set = providers
        self.invalidate()

    def set_tags(self, tags: set[str]) -> None:
        self._tag_set = tags
        self.invalidate()

    def clear_all(self) -> None:
        self._search_text = ""
        self._provider_set = set()
        self._tag_set = set()
        self.invalidate()

    def has_active_filter(self) -> bool:
        return bool(self._search_text or self._provider_set or self._tag_set)

    # ------------------------------------------------------------------
    # QSortFilterProxyModel override
    # ------------------------------------------------------------------

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source = self.sourceModel()
        if source is None:
            return True
        idx = source.index(source_row, 0, source_parent)
        node = idx.internalPointer()
        if node is None:
            return True
        if node.kind == "provider":
            # Show provider group if any child station passes filter (Pitfall 2 fix)
            for i in range(source.rowCount(idx)):
                if self.filterAcceptsRow(i, idx):
                    return True
            return False
        if node.kind == "station":
            return matches_filter_multi(
                node.station,
                self._search_text,
                self._provider_set,
                self._tag_set,
            )
        return True
