"""Phase 38-01: StationFilterProxyModel.

QSortFilterProxyModel subclass that filters the provider-grouped
StationTreeModel by search text, provider set, and tag set.

Filter logic:
  - Search text: case-insensitive substring on station name (inactive when "")
  - Provider set: OR within — station matches if provider_name in set (inactive when empty)
  - Tag set: OR within — station matches if any tag in set (inactive when empty)
  - Live-only: stations whose AA channel key (derived from first stream URL via
    url_helpers._aa_channel_key_from_url) is in the live_map updated by the
    Phase 68 background poll. Inactive when False (default).
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
        # Phase 68 / F-02 / F-04 / Pitfall 7: live-only predicate state.
        #   _live_only: True when the "Live now" chip is engaged.
        #   _live_channel_keys: set of AA channel keys currently broadcasting
        #     a live show; updated by set_live_map from MainWindow when a
        #     poll cycle completes.
        self._live_only: bool = False
        self._live_channel_keys: set[str] = set()
        # Phase 70 / HRES-01 / F-01 / Pitfall 7: hi-res-only predicate state.
        #   _hi_res_only: True when the "Hi-Res only" chip is engaged.
        #   _hi_res_station_ids: set of station IDs that have at least one
        #     "hires" tier stream; updated by set_quality_map from MainWindow
        #     when the quality map is refreshed.
        self._hi_res_only: bool = False
        self._hi_res_station_ids: set[int] = set()

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

    def set_live_map(self, live_map: dict[str, str]) -> None:
        """Phase 68 / B-02: update the set of currently-live AA channel keys.

        Called from MainWindow whenever NowPlayingPanel's poll cycle completes.
        The live_map dict is from aa_live._parse_live_map (channel_key -> show_name);
        this proxy only needs the keys.

        Pitfall 7: invalidate ONLY when _live_only is active. Otherwise the
        proxy would re-run filterAcceptsRow for every row every 60 s even when
        the chip is off, causing visible tree-flicker.
        """
        self._live_channel_keys = set(live_map.keys()) if live_map else set()
        if self._live_only:
            self.invalidate()

    def set_live_only(self, enabled: bool) -> None:
        """Phase 68 / F-02: toggle the live-only predicate.

        Always invalidates because the predicate state itself changed —
        unlike set_live_map, the user-visible result MUST update.
        """
        self._live_only = bool(enabled)
        self.invalidate()

    def set_quality_map(self, quality_map: dict[int, str]) -> None:
        """Phase 70 / HRES-01 / F-01: update the set of hi-res station IDs.

        Called from StationListPanel.update_quality_map whenever MainWindow
        emits quality_map_changed. Only stations with tier == "hires" are
        enrolled; "lossless" and "" are excluded.

        Pitfall 7 invalidate-guard (mirrors Phase 68 set_live_map): invalidate
        ONLY when _hi_res_only is active to avoid spurious re-filter passes
        on every quality-map push when the chip is off.
        """
        self._hi_res_station_ids = {
            sid for sid, tier in (quality_map or {}).items() if tier == "hires"
        }
        if self._hi_res_only:
            self.invalidate()

    def set_hi_res_only(self, enabled: bool) -> None:
        """Phase 70 / HRES-01 / F-01: toggle the hi-res-only predicate.

        Always invalidates because the predicate state itself changed —
        unlike set_quality_map, the user-visible result MUST update.
        """
        self._hi_res_only = bool(enabled)
        self.invalidate()

    def clear_all(self) -> None:
        self._search_text = ""
        self._provider_set = set()
        self._tag_set = set()
        # Phase 68 / F-03 (clear_all extension): the "Live now" chip is one
        # of the predicate dimensions; clear_all wipes it too. Note: the
        # _live_channel_keys cache is NOT cleared — that data comes from
        # the background poll and stays valid.
        self._live_only = False
        # Phase 70 / HRES-01: hi_res_only is also a predicate dimension.
        # _hi_res_station_ids cache is NOT cleared — it comes from the
        # background quality map and stays valid.
        self._hi_res_only = False
        self.invalidate()

    def has_active_filter(self) -> bool:
        # Phase 68 / F-03: live_only is one more predicate dimension —
        # tree expansion (sync_tree_expansion) treats it as an active filter.
        # Phase 70 / HRES-01: hi_res_only is also a predicate dimension.
        return bool(
            self._search_text
            or self._provider_set
            or self._tag_set
            or self._live_only
            or self._hi_res_only
        )

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
            # Phase 70 / HRES-01 / F-01: hi-res-only short-circuit AND-composed
            # with other chip filters. Station must be in the hi-res station set.
            if self._hi_res_only and int(node.station.id) not in self._hi_res_station_ids:
                return False
            # Phase 68 / F-02 / F-03: live-only short-circuit AND-composed with
            # other chip filters. Lazy import of url_helpers matches the
            # existing in-method import idiom used elsewhere in the
            # codebase to keep proxy module imports minimal and avoid any
            # potential circular-import risk via the panels.
            if self._live_only:
                from musicstreamer.url_helpers import (
                    _aa_channel_key_from_url,
                    _aa_slug_from_url,
                    _is_aa_url,
                )
                station = node.station
                ch_key: str | None = None
                streams = getattr(station, "streams", None) or []
                if streams:
                    url = streams[0].url
                    if _is_aa_url(url):
                        slug = _aa_slug_from_url(url)
                        ch_key = _aa_channel_key_from_url(url, slug=slug)
                if ch_key is None or ch_key not in self._live_channel_keys:
                    return False
            return matches_filter_multi(
                node.station,
                self._search_text,
                self._provider_set,
                self._tag_set,
            )
        return True
