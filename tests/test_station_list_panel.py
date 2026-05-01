"""Tests for StationListPanel (Phase 37-01 T3).

Covers panel construction, tree configuration, signal emission on click
(tree and recently-played rows), and provider-row click suppression.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QTreeView

# Side-effect import: register :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.models import Station


def make_station(
    sid: int, name: str, provider: str | None, art: str | None = None
) -> Station:
    return Station(
        id=sid,
        name=name,
        provider_id=None,
        provider_name=provider,
        tags="",
        station_art_path=art,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
        last_played_at=None,
    )


class FakeRepo:
    def __init__(self, stations: list[Station], recent: list[Station]) -> None:
        self._stations = stations
        self._recent = recent
        self._station_favs: dict = {}

    def list_stations(self) -> list[Station]:
        return list(self._stations)

    def list_recently_played(self, n: int = 3) -> list[Station]:
        return list(self._recent[:n])

    def set_station_favorite(self, station_id: int, is_favorite: bool) -> None:
        self._station_favs[station_id] = is_favorite

    def is_favorite_station(self, station_id: int) -> bool:
        return self._station_favs.get(station_id, False)

    def list_favorite_stations(self) -> list[Station]:
        return [s for s in self._stations if self._station_favs.get(s.id, False)]

    def list_favorites(self) -> list:
        return []


def _sample_repo() -> FakeRepo:
    stations = [
        make_station(1, "Groove Salad", "SomaFM"),
        make_station(2, "Drone Zone", "SomaFM"),
        make_station(3, "Chillout", "DI.fm"),
    ]
    recent = [
        make_station(1, "Groove Salad", "SomaFM"),
        make_station(3, "Chillout", "DI.fm"),
        make_station(2, "Drone Zone", "SomaFM"),
    ]
    return FakeRepo(stations, recent)


def test_panel_min_width_and_structure(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    assert panel.minimumWidth() == 280
    assert isinstance(panel.tree, QTreeView)
    assert isinstance(panel.recent_view, QListView)

    # Separator frame between recent + tree
    hlines = [f for f in panel.findChildren(QFrame) if f.frameShape() == QFrame.HLine]
    assert len(hlines) >= 1


def test_panel_exposes_station_activated_signal(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    assert hasattr(panel, "station_activated")


def test_tree_configuration(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    assert panel.tree.isHeaderHidden() is True
    assert panel.tree.rootIsDecorated() is False
    assert panel.tree.iconSize() == QSize(32, 32)
    assert panel.tree.indentation() == 16
    assert panel.tree.selectionMode() == QAbstractItemView.SingleSelection


def test_provider_groups_collapsed_after_construction(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    # Groups start collapsed so the full list is scannable without scrolling
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        assert panel.tree.isExpanded(group_proxy) is False


def test_provider_groups_expand_when_search_active(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    panel._search_box.setText("a")

    # Any group that survives the filter should be expanded so matches are visible
    any_expanded = False
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        if panel.tree.isExpanded(group_proxy):
            any_expanded = True
            break
    assert any_expanded is True

    # Clearing the search collapses them again
    panel._search_box.clear()
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        assert panel.tree.isExpanded(group_proxy) is False


def test_tree_click_on_station_emits_station_activated(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Use proxy model indexes (what the view sees)
    provider_proxy_idx = panel._proxy.index(0, 0)
    station_proxy_idx = panel._proxy.index(0, 0, provider_proxy_idx)
    # Map to source to get expected station
    source_idx = panel._proxy.mapToSource(station_proxy_idx)
    expected = panel.model.station_for_index(source_idx)
    assert expected is not None

    with qtbot.waitSignal(panel.station_activated, timeout=500) as blocker:
        panel.tree.clicked.emit(station_proxy_idx)

    emitted = blocker.args[0]
    assert emitted is expected


def test_tree_click_on_provider_does_not_emit(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    provider_proxy_idx = panel._proxy.index(0, 0)
    received: list[Station] = []
    panel.station_activated.connect(received.append)
    panel.tree.clicked.emit(provider_proxy_idx)
    assert received == []


def test_tree_click_via_proxy_emits_station_activated(qtbot):
    """Proxy index mapping: click on proxy station index emits correct Station."""
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Get first station via proxy (what the tree actually uses)
    provider_proxy_idx = panel._proxy.index(0, 0)
    station_proxy_idx = panel._proxy.index(0, 0, provider_proxy_idx)
    source_idx = panel._proxy.mapToSource(station_proxy_idx)
    expected = panel.model.station_for_index(source_idx)
    assert expected is not None

    with qtbot.waitSignal(panel.station_activated, timeout=500) as blocker:
        panel.tree.clicked.emit(station_proxy_idx)

    assert blocker.args[0] is expected


def test_search_filters_tree(qtbot):
    """Setting search text reduces visible proxy row count."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    # Count visible station rows before search
    def _count_stations():
        total = 0
        for p_row in range(panel._proxy.rowCount()):
            p_idx = panel._proxy.index(p_row, 0)
            total += panel._proxy.rowCount(p_idx)
        return total

    before = _count_stations()
    panel._search_box.setText("Drone")
    after = _count_stations()
    assert after < before
    assert after >= 1  # "Drone Zone" still visible


def test_recently_played_populated(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    assert panel.recent_view.model().rowCount() == 3


def test_recently_played_click_emits_station_activated(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    recent_model = panel.recent_view.model()
    idx = recent_model.index(0, 0)
    expected = idx.data(Qt.UserRole)
    assert isinstance(expected, Station)

    with qtbot.waitSignal(panel.station_activated, timeout=500) as blocker:
        panel.recent_view.clicked.emit(idx)

    assert blocker.args[0] is expected


def test_recent_view_max_height_and_icon_size(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    assert panel.recent_view.maximumHeight() == 160
    assert panel.recent_view.iconSize() == QSize(32, 32)


# ---------------------------------------------------------------------------
# Phase 38-02: Segmented control + QStackedWidget tests
# ---------------------------------------------------------------------------


class FakeRepoWithFavorites(FakeRepo):
    """Extended fake repo with favorites support for 38-02 tests."""

    def __init__(self, stations, recent, favorites=None, fav_stations=None):
        super().__init__(stations, recent)
        self._favorites = list(favorites or [])
        self._fav_stations = list(fav_stations or [])
        self._station_favs: dict = {}

    def add_favorite(self, station_name, provider_name, track_title, genre):
        from musicstreamer.models import Favorite
        self._favorites.append(
            Favorite(id=len(self._favorites) + 1, station_name=station_name,
                     provider_name=provider_name, track_title=track_title, genre=genre)
        )

    def remove_favorite(self, station_name, track_title):
        self._favorites = [
            f for f in self._favorites
            if not (f.station_name == station_name and f.track_title == track_title)
        ]

    def list_favorites(self):
        return list(reversed(self._favorites))

    def is_favorited(self, station_name, track_title):
        return any(
            f.station_name == station_name and f.track_title == track_title
            for f in self._favorites
        )

    def set_station_favorite(self, station_id, is_favorite):
        self._station_favs[station_id] = is_favorite

    def is_favorite_station(self, station_id):
        return self._station_favs.get(station_id, False)

    def list_favorite_stations(self):
        return [s for s in self._stations if self._station_favs.get(s.id, False)]


def _make_station_with_is_fav(sid, name, provider, is_fav=False):
    return Station(
        id=sid, name=name, provider_id=None, provider_name=provider,
        tags="", station_art_path=None, album_fallback_path=None,
        icy_disabled=False, streams=[], last_played_at=None, is_favorite=is_fav,
    )


def _sample_repo_with_favorites():
    stations = [
        _make_station_with_is_fav(1, "Groove Salad", "SomaFM"),
        _make_station_with_is_fav(2, "Drone Zone", "SomaFM"),
        _make_station_with_is_fav(3, "Chillout", "DI.fm"),
    ]
    recent = [stations[0]]
    return FakeRepoWithFavorites(stations, recent)


def test_segmented_control_switches_stack(qtbot):
    """Clicking 'Favorites' switches QStackedWidget to page 1; 'Stations' back to page 0."""
    from PySide6.QtWidgets import QStackedWidget
    panel = StationListPanel(_sample_repo_with_favorites())
    qtbot.addWidget(panel)

    assert hasattr(panel, "_stack"), "StationListPanel must have _stack QStackedWidget"
    assert isinstance(panel._stack, QStackedWidget)
    # Initially on Stations page (0)
    assert panel._stack.currentIndex() == 0

    # Click "Favorites" button
    panel._favorites_btn.click()
    assert panel._stack.currentIndex() == 1

    # Click "Stations" button
    panel._stations_btn.click()
    assert panel._stack.currentIndex() == 0


def test_filter_strip_hidden_in_favorites_mode(qtbot):
    """Search box and chip rows are on page 0; not visible when page 1 is active."""
    from PySide6.QtWidgets import QStackedWidget
    panel = StationListPanel(_sample_repo_with_favorites())
    qtbot.addWidget(panel)

    # In Stations mode, search box is on page 0
    assert panel._stack.currentIndex() == 0
    assert panel._search_box.isVisibleTo(panel), "search box should be visible in Stations mode"

    # Switch to Favorites
    panel._favorites_btn.click()
    assert panel._stack.currentIndex() == 1
    # Search box is on page 0 of the stack, so it's not visible
    assert not panel._search_box.isVisibleTo(panel), "search box should not be visible in Favorites mode"


def test_station_panel_has_station_favorited_signal(qtbot):
    """StationListPanel must expose station_favorited = Signal(Station, bool)."""
    panel = StationListPanel(_sample_repo_with_favorites())
    qtbot.addWidget(panel)
    assert hasattr(panel, "station_favorited")


# ---------------------------------------------------------------------------
# Phase 40.1-04: Per-row logo rendering (D-11)
# ---------------------------------------------------------------------------


def test_station_row_logo_loads_via_abs_path(qtbot, tmp_path, monkeypatch):
    """_load_station_icon resolves relative station_art_path against paths.data_dir()."""
    import os
    from PySide6.QtGui import QPixmap, QPixmapCache
    from musicstreamer import paths as _paths
    from musicstreamer.ui_qt._art_paths import load_station_icon as _load_station_icon

    monkeypatch.setattr(_paths, "_root_override", str(tmp_path))
    QPixmapCache.clear()

    asset_dir = os.path.join(str(tmp_path), "assets", "7")
    os.makedirs(asset_dir, exist_ok=True)
    pix = QPixmap(16, 16)
    pix.fill(0xFF00FF00)
    asset_path = os.path.join(asset_dir, "station_art.png")
    assert pix.save(asset_path, "PNG")

    station = make_station(7, "Row Station", "Prov", art="assets/7/station_art.png")
    icon = _load_station_icon(station)
    loaded = icon.pixmap(32, 32)
    # Non-null pixmap from our real PNG (not fallback). Assert the source
    # green reaches the scaled output — fallback SVG will not be green.
    assert not loaded.isNull()
    img = loaded.toImage()
    center = img.pixelColor(img.width() // 2, img.height() // 2)
    assert (center.red(), center.green(), center.blue()) == (0, 255, 0), \
        f"expected green from resolved abs path, got {center.getRgb()} (likely fallback)"


def test_cache_invalidation_on_logo_change(qtbot, tmp_path, monkeypatch):
    """After logo path changes, panel refresh picks up new pixmap (cache keyed on abs)."""
    import os
    from PySide6.QtGui import QPixmap, QPixmapCache
    from musicstreamer import paths as _paths
    from musicstreamer.ui_qt._art_paths import load_station_icon as _load_station_icon

    monkeypatch.setattr(_paths, "_root_override", str(tmp_path))
    QPixmapCache.clear()

    # Two distinct logos on disk.
    for sub, color in (("a", 0xFFFF0000), ("b", 0xFF0000FF)):
        d = os.path.join(str(tmp_path), "assets", sub)
        os.makedirs(d, exist_ok=True)
        p = QPixmap(16, 16)
        p.fill(color)
        assert p.save(os.path.join(d, "station_art.png"), "PNG")

    station = make_station(9, "S", "P", art="assets/a/station_art.png")
    icon_a = _load_station_icon(station)
    pix_a = icon_a.pixmap(32, 32)
    assert not pix_a.isNull()

    # Change path -> reload -> expect different (non-null) pixmap.
    station.station_art_path = "assets/b/station_art.png"
    icon_b = _load_station_icon(station)
    pix_b = icon_b.pixmap(32, 32)
    assert not pix_b.isNull()
    # Cache should not return the stale a-path pixmap bytes:
    assert pix_a.toImage() != pix_b.toImage()


# ---------------------------------------------------------------------------
# Phase 999.1 Wave 0 — "+" New Station button + select_station API (RED).
# These tests exercise additions introduced by Plan 02. Expected to FAIL
# until Plan 02 lands (new_station_requested signal + select_station method
# + _new_station_btn on the panel header row).
# ---------------------------------------------------------------------------


def test_new_station_button_exists_and_right_aligned(qtbot):
    """D-02a: panel exposes a QToolButton _new_station_btn, right-aligned
    (i.e. preceded by a stretch) in its host layout, with tooltip "New Station"."""
    from PySide6.QtWidgets import QToolButton

    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    assert hasattr(panel, "_new_station_btn"), \
        "StationListPanel must expose a _new_station_btn attribute"
    btn = panel._new_station_btn
    assert isinstance(btn, QToolButton), "_new_station_btn must be a QToolButton"
    assert btn.toolTip() == "New Station"

    # Walk up to find the parent layout containing the button and verify an
    # addStretch (QSpacerItem with expanding horizontal policy) precedes it.
    from PySide6.QtWidgets import QLayout, QSpacerItem
    from PySide6.QtWidgets import QSizePolicy as _SP

    def _layout_has_stretch_before(btn_widget) -> bool:
        # Find the layout that owns this widget.
        for lay in panel.findChildren(QLayout):
            btn_index = -1
            for i in range(lay.count()):
                item = lay.itemAt(i)
                if item is not None and item.widget() is btn_widget:
                    btn_index = i
                    break
            if btn_index <= 0:
                continue
            # Scan items before btn_index for a spacer with horizontal Expanding.
            for j in range(btn_index):
                item = lay.itemAt(j)
                if item is None:
                    continue
                spacer = item.spacerItem()
                if spacer is None:
                    continue
                sp = spacer.sizePolicy()
                if sp.horizontalPolicy() == _SP.Expanding:
                    return True
            # Also accept the "any stretch factor > 0 on a prior item" heuristic
            # in case the button is on a BoxLayout row with addStretch().
            # (QSpacerItem from addStretch has Expanding horizontal policy by
            # default, so the branch above should catch it; this is a fallback.)
        return False

    assert _layout_has_stretch_before(btn), \
        "_new_station_btn must be right-aligned via addStretch() in its row layout"


def test_new_station_button_emits_signal(qtbot):
    """D-02b: clicking _new_station_btn emits the new_station_requested signal."""
    from PySide6.QtCore import Qt as _Qt

    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    assert hasattr(panel, "new_station_requested"), \
        "StationListPanel must expose new_station_requested = Signal()"

    with qtbot.waitSignal(panel.new_station_requested, timeout=500):
        qtbot.mouseClick(panel._new_station_btn, _Qt.LeftButton)


def test_select_station_by_id_sets_current_index(qtbot):
    """D-07b: panel.select_station(station_id) sets a valid current index on
    the tree whose underlying Station has the requested id."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    assert hasattr(panel, "select_station"), \
        "StationListPanel must expose a select_station(station_id) method"
    panel.select_station(2)

    idx = panel.tree.currentIndex()
    assert idx.isValid(), "select_station must produce a valid current index"

    source_idx = panel._proxy.mapToSource(idx)
    st = panel.model.station_for_index(source_idx)
    assert st is not None, "current index must map to a Station (not a provider row)"
    assert st.id == 2


# ----------------------------------------------------------------------
# Phase 50 / BUG-01: refresh_recent() public API
# ----------------------------------------------------------------------

def test_refresh_recent_updates_list(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Simulate a different station becoming the most recently played.
    # Pitfall #3: mutate repo._recent BEFORE calling refresh_recent —
    # list_recently_played returns a snapshot of _recent at call time.
    new_top = make_station(99, "New Top Station", "TestFM")
    repo._recent = [new_top] + repo._recent

    panel.refresh_recent()

    assert panel.recent_view.model().rowCount() == 3
    top_station = panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert isinstance(top_station, Station)
    assert top_station.id == 99


def test_refresh_recent_does_not_touch_tree(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # SC #3: refresh_recent must not rebuild the provider tree.
    # If model.refresh() were called, rowCount would be re-derived from repo.list_stations().
    row_count_before = panel.tree.model().rowCount()

    panel.refresh_recent()

    assert panel.tree.model().rowCount() == row_count_before


# ----------------------------------------------------------------------
# Phase 55 / BUG-06: refresh_model preserves per-provider expansion state
# (capture/restore around model.refresh; _sync_tree_expansion no longer
# called from refresh_model body)
# ----------------------------------------------------------------------


def test_capture_and_restore_helpers_exist(qtbot):
    """Both private helpers must be present on StationListPanel (Plan 55-01)."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    assert hasattr(panel, "_capture_expanded_provider_names")
    assert hasattr(panel, "_restore_expanded_provider_names")


def test_refresh_model_preserves_user_expanded_provider(qtbot):
    """SC #1 — a group the user expanded before save stays expanded after refresh_model."""
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Locate the SomaFM provider via the source model (raw name, no " (N)" suffix).
    somafm_row = None
    for row in range(panel.model.rowCount()):
        if panel.model.provider_name_at(row) == "SomaFM":
            somafm_row = row
            break
    assert somafm_row is not None, "SomaFM should exist in the sample repo"

    source_idx = panel.model.index(somafm_row, 0)
    proxy_idx = panel._proxy.mapFromSource(source_idx)
    assert proxy_idx.isValid()

    # User expands the SomaFM group.
    panel.tree.expand(proxy_idx)
    assert panel.tree.isExpanded(proxy_idx) is True

    # Simulate the edit-save round-trip: refresh_model() reloads from the repo.
    panel.refresh_model()

    # Re-locate SomaFM after refresh and confirm it is STILL expanded.
    somafm_row_post = None
    for row in range(panel.model.rowCount()):
        if panel.model.provider_name_at(row) == "SomaFM":
            somafm_row_post = row
            break
    assert somafm_row_post is not None
    proxy_idx_post = panel._proxy.mapFromSource(panel.model.index(somafm_row_post, 0))
    assert proxy_idx_post.isValid()
    assert panel.tree.isExpanded(proxy_idx_post) is True


def test_refresh_model_preserves_user_collapsed_provider(qtbot):
    """SC #2 — groups the user has collapsed stay collapsed after refresh_model.

    Today (pre-fix) refresh_model calls _sync_tree_expansion which calls
    collapseAll when no filter is active — that's accidentally compatible with
    'collapsed stays collapsed'. The real proof is that the post-fix path no
    longer relies on _sync_tree_expansion, but the user-visible behavior is
    identical for this case. Asserted to lock the contract.
    """
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # All groups start collapsed. Refresh; all stay collapsed.
    panel.refresh_model()

    for row in range(panel.model.rowCount()):
        proxy_idx = panel._proxy.mapFromSource(panel.model.index(row, 0))
        if proxy_idx.isValid():
            assert panel.tree.isExpanded(proxy_idx) is False


def test_refresh_model_expands_brand_new_provider_group(qtbot):
    """D-06 — a provider group not present pre-refresh defaults to expanded."""
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Pre-state: groups exist for SomaFM and DI.fm; nothing is expanded.
    pre_provider_names = {
        panel.model.provider_name_at(row)
        for row in range(panel.model.rowCount())
    }
    assert "JazzFM" not in pre_provider_names

    # Simulate edit-save introducing a brand-new provider.
    repo._stations.append(make_station(42, "Smooth Operator", "JazzFM"))
    panel.refresh_model()

    # Find JazzFM in the post-refresh model and verify it is expanded.
    jazz_row = None
    for row in range(panel.model.rowCount()):
        if panel.model.provider_name_at(row) == "JazzFM":
            jazz_row = row
            break
    assert jazz_row is not None, "JazzFM should now appear in the model"
    proxy_idx = panel._proxy.mapFromSource(panel.model.index(jazz_row, 0))
    assert proxy_idx.isValid()
    assert panel.tree.isExpanded(proxy_idx) is True


def test_refresh_model_body_does_not_call_sync_tree_expansion(qtbot):
    """D-03 — refresh_model body must not invoke _sync_tree_expansion.

    Strategy: refresh_model() with no active filter MUST NOT collapse a
    group the user expanded. Pre-fix _sync_tree_expansion would call
    collapseAll() under that condition, causing the SomaFM group to
    collapse. This test fails on the pre-fix code path and passes on the
    capture/restore path.
    """
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # No active filter (default). Expand SomaFM.
    assert panel._proxy.has_active_filter() is False
    somafm_row = next(
        row for row in range(panel.model.rowCount())
        if panel.model.provider_name_at(row) == "SomaFM"
    )
    proxy_idx = panel._proxy.mapFromSource(panel.model.index(somafm_row, 0))
    panel.tree.expand(proxy_idx)
    assert panel.tree.isExpanded(proxy_idx) is True

    # Refresh; state must survive.
    panel.refresh_model()

    somafm_row_post = next(
        row for row in range(panel.model.rowCount())
        if panel.model.provider_name_at(row) == "SomaFM"
    )
    proxy_idx_post = panel._proxy.mapFromSource(panel.model.index(somafm_row_post, 0))
    assert panel.tree.isExpanded(proxy_idx_post) is True, (
        "refresh_model must preserve expanded SomaFM; was _sync_tree_expansion "
        "still called from refresh_model body?"
    )
