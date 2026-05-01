"""Tests for StationTreeModel (Phase 37-01 T2).

Covers provider grouping, row counts, parent()/flags() semantics (Pitfall §4),
DecorationRole fallback, and station_for_index lookup.
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QIcon

# Side-effect import: registers :/icons/ resource prefix before any QIcon lookup.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.station_tree_model import StationTreeModel
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


def test_empty_stations_zero_rowcount(qtbot):
    model = StationTreeModel([])
    assert model.rowCount(QModelIndex()) == 0


def test_provider_grouping_row_counts(qtbot):
    stations = [
        make_station(1, "Groove Salad", "SomaFM"),
        make_station(2, "Drone Zone", "SomaFM"),
        make_station(3, "Chillout", "DI.fm"),
    ]
    model = StationTreeModel(stations)

    # Top-level: 2 provider groups
    assert model.rowCount(QModelIndex()) == 2

    # Each provider group contains its stations
    child_counts = []
    for row in range(model.rowCount(QModelIndex())):
        parent_idx = model.index(row, 0)
        child_counts.append(model.rowCount(parent_idx))
    assert sorted(child_counts) == [1, 2]


def test_provider_label_includes_count_suffix(qtbot):
    stations = [
        make_station(1, "Groove Salad", "SomaFM"),
        make_station(2, "Drone Zone", "SomaFM"),
    ]
    model = StationTreeModel(stations)
    top = model.index(0, 0)
    label = model.data(top, Qt.DisplayRole)
    assert label == "SomaFM (2)"


def test_top_level_parent_is_invalid(qtbot):
    # Pitfall §4 — prevents infinite recursion on expandAll()
    stations = [make_station(1, "Groove Salad", "SomaFM")]
    model = StationTreeModel(stations)
    top = model.index(0, 0)
    assert top.isValid() is True
    assert model.parent(top).isValid() is False


def test_flags_provider_not_selectable_station_selectable(qtbot):
    stations = [make_station(1, "Groove Salad", "SomaFM")]
    model = StationTreeModel(stations)
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)

    p_flags = model.flags(provider_idx)
    s_flags = model.flags(station_idx)

    assert bool(p_flags & Qt.ItemIsSelectable) is False
    assert bool(p_flags & Qt.ItemIsEnabled) is True
    assert bool(s_flags & Qt.ItemIsSelectable) is True
    assert bool(s_flags & Qt.ItemIsEnabled) is True


def test_station_data_decoration_and_display(qtbot):
    stations = [make_station(1, "Groove Salad", "SomaFM")]
    model = StationTreeModel(stations)
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)

    display = model.data(station_idx, Qt.DisplayRole)
    assert display == "Groove Salad"

    icon = model.data(station_idx, Qt.DecorationRole)
    assert isinstance(icon, QIcon)
    assert icon.isNull() is False


def test_station_for_index_lookup(qtbot):
    st = make_station(1, "Groove Salad", "SomaFM")
    model = StationTreeModel([st])
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)

    assert model.station_for_index(station_idx) is st
    assert model.station_for_index(provider_idx) is None


def test_column_count_is_one(qtbot):
    model = StationTreeModel([])
    assert model.columnCount(QModelIndex()) == 1


def test_decoration_fallback_when_art_path_none(qtbot):
    st = make_station(1, "Groove Salad", "SomaFM", art=None)
    model = StationTreeModel([st])
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)

    icon = model.data(station_idx, Qt.DecorationRole)
    assert isinstance(icon, QIcon)
    assert icon.isNull() is False


# ----------------------------------------------------------------------
# Phase 55 / BUG-06: provider_name_at — raw provider name accessor
# (suffix-free; round-tripable key for capture/restore in StationListPanel)
# ----------------------------------------------------------------------


def test_provider_name_at_returns_raw_name_without_count_suffix(qtbot):
    # Display label is mutated to "SomaFM (2)" in _populate; provider_name_at
    # must return the raw "SomaFM" so capture/restore can match across refresh.
    stations = [
        make_station(1, "Groove Salad", "SomaFM"),
        make_station(2, "Drone Zone", "SomaFM"),
    ]
    model = StationTreeModel(stations)

    # Sanity-check: the DisplayRole still has the count suffix (untouched).
    top = model.index(0, 0)
    assert model.data(top, Qt.DisplayRole) == "SomaFM (2)"

    # And the raw provider name is "SomaFM" exactly — no whitespace, no parens.
    assert model.provider_name_at(0) == "SomaFM"


def test_provider_name_at_returns_none_for_out_of_range_row(qtbot):
    stations = [make_station(1, "Groove Salad", "SomaFM")]
    model = StationTreeModel(stations)
    assert model.provider_name_at(99) is None
    assert model.provider_name_at(-1) is None


def test_provider_name_at_preserves_parens_in_raw_provider_name(qtbot):
    # Regression case: a provider whose name itself contains " (Hi-Res)"
    # must round-trip unmodified through provider_name_at.
    stations = [make_station(1, "Foo", "SomeNet (Hi-Res)")]
    model = StationTreeModel(stations)
    # DisplayRole gets " (1)" appended on top of the existing parens — that's fine.
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "SomeNet (Hi-Res) (1)"
    # Raw name: no count suffix, parens-in-name preserved.
    assert model.provider_name_at(0) == "SomeNet (Hi-Res)"


def test_provider_name_at_after_refresh_reflects_new_data(qtbot):
    # provider_name_at must read from the post-refresh state (beginResetModel/
    # endResetModel rebuilt _root.children).
    model = StationTreeModel([make_station(1, "Groove Salad", "SomaFM")])
    assert model.provider_name_at(0) == "SomaFM"

    model.refresh([make_station(2, "Chillout", "DI.fm")])
    assert model.provider_name_at(0) == "DI.fm"
