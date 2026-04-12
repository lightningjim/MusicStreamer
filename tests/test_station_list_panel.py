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

    def list_stations(self) -> list[Station]:
        return list(self._stations)

    def list_recently_played(self, n: int = 3) -> list[Station]:
        return list(self._recent[:n])


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

    # At least the first provider group is expanded
    first_group = panel.model.index(0, 0)
    assert panel.tree.isExpanded(first_group) is True


def test_tree_click_on_station_emits_station_activated(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Pick any station row index.
    provider_idx = panel.model.index(0, 0)
    station_idx = panel.model.index(0, 0, provider_idx)
    expected = panel.model.station_for_index(station_idx)
    assert expected is not None

    with qtbot.waitSignal(panel.station_activated, timeout=500) as blocker:
        panel.tree.clicked.emit(station_idx)

    emitted = blocker.args[0]
    assert emitted is expected


def test_tree_click_on_provider_does_not_emit(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    provider_idx = panel.model.index(0, 0)
    received: list[Station] = []
    panel.station_activated.connect(received.append)
    panel.tree.clicked.emit(provider_idx)
    assert received == []


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
