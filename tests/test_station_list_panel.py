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


def test_all_provider_groups_expanded_after_construction(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    # At least the first provider group is expanded (proxy index)
    first_group_proxy = panel._proxy.index(0, 0)
    assert panel.tree.isExpanded(first_group_proxy) is True


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
    from musicstreamer.ui_qt.station_list_panel import _load_station_icon

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
    from musicstreamer.ui_qt.station_list_panel import _load_station_icon

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
