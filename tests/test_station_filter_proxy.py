"""Tests for StationFilterProxyModel (Phase 38-01 Task 1).

Covers:
  - Search text filtering
  - Provider set filtering (OR within, AND between)
  - Tag set filtering
  - Provider group row visibility (recurse into children)
  - clear_all resets all filters
"""
from __future__ import annotations

import pytest

from musicstreamer.models import Station
from musicstreamer.ui_qt.station_tree_model import StationTreeModel
from musicstreamer.ui_qt.station_filter_proxy import StationFilterProxyModel


def make_station(
    sid: int,
    name: str,
    provider: str | None,
    tags: str = "",
) -> Station:
    return Station(
        id=sid,
        name=name,
        provider_id=None,
        provider_name=provider,
        tags=tags,
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
        last_played_at=None,
    )


_STATIONS = [
    make_station(1, "Groove Salad", "SomaFM", "chill,ambient"),
    make_station(2, "Drone Zone", "SomaFM", "ambient,drone"),
    make_station(3, "Chillout", "DI.fm", "chill,electronic"),
    make_station(4, "Techno Beats", "DI.fm", "techno,electronic"),
    make_station(5, "Jazz Classics", "Radio.net", "jazz"),
]


def _make_proxy(stations=None) -> tuple[StationTreeModel, StationFilterProxyModel]:
    if stations is None:
        stations = _STATIONS
    model = StationTreeModel(stations)
    proxy = StationFilterProxyModel()
    proxy.setSourceModel(model)
    return model, proxy


def _visible_station_names(proxy: StationFilterProxyModel) -> list[str]:
    """Collect names of all visible station rows (depth 1 children)."""
    names = []
    # provider groups are at depth 0 of the proxy
    for p_row in range(proxy.rowCount()):
        p_idx = proxy.index(p_row, 0)
        for s_row in range(proxy.rowCount(p_idx)):
            s_idx = proxy.index(s_row, 0, p_idx)
            # map to source to get node label
            src_idx = proxy.mapToSource(s_idx)
            names.append(src_idx.data())
    return names


# ---------------------------------------------------------------------------
# Search text
# ---------------------------------------------------------------------------

def test_filter_by_search_text(qtbot):
    _, proxy = _make_proxy()
    proxy.set_search("drone")
    visible = _visible_station_names(proxy)
    assert "Drone Zone" in visible
    assert "Groove Salad" not in visible
    assert "Chillout" not in visible


def test_filter_by_search_text_case_insensitive(qtbot):
    _, proxy = _make_proxy()
    proxy.set_search("GROOVE")
    visible = _visible_station_names(proxy)
    assert "Groove Salad" in visible
    assert "Drone Zone" not in visible


# ---------------------------------------------------------------------------
# Provider set
# ---------------------------------------------------------------------------

def test_filter_by_provider_set(qtbot):
    _, proxy = _make_proxy()
    proxy.set_providers({"SomaFM"})
    visible = _visible_station_names(proxy)
    assert "Groove Salad" in visible
    assert "Drone Zone" in visible
    assert "Chillout" not in visible
    assert "Jazz Classics" not in visible


# ---------------------------------------------------------------------------
# Tag set
# ---------------------------------------------------------------------------

def test_filter_by_tag_set(qtbot):
    _, proxy = _make_proxy()
    proxy.set_tags({"chill"})
    visible = _visible_station_names(proxy)
    assert "Groove Salad" in visible   # has chill
    assert "Chillout" in visible       # has chill
    assert "Drone Zone" not in visible  # no chill
    assert "Techno Beats" not in visible


# ---------------------------------------------------------------------------
# AND between dimensions, OR within
# ---------------------------------------------------------------------------

def test_multi_select_and_between_or_within(qtbot):
    _, proxy = _make_proxy()
    proxy.set_providers({"SomaFM", "DI.fm"})
    proxy.set_tags({"chill"})
    visible = _visible_station_names(proxy)
    # Only chill stations from SomaFM or DI.fm
    assert "Groove Salad" in visible   # SomaFM + chill
    assert "Chillout" in visible       # DI.fm + chill
    assert "Drone Zone" not in visible  # SomaFM but no chill
    assert "Jazz Classics" not in visible  # not in provider set


# ---------------------------------------------------------------------------
# Provider group visibility
# ---------------------------------------------------------------------------

def test_provider_group_visible_when_child_matches(qtbot):
    _, proxy = _make_proxy()
    proxy.set_search("Groove")
    # SomaFM group should still be visible (Groove Salad matches)
    group_labels = []
    for p_row in range(proxy.rowCount()):
        p_idx = proxy.index(p_row, 0)
        src_idx = proxy.mapToSource(p_idx)
        group_labels.append(src_idx.internalPointer().label if src_idx.internalPointer() else None)
    # At least one group is visible (the one containing "Groove Salad")
    assert proxy.rowCount() >= 1


def test_provider_group_hidden_when_no_children_match(qtbot):
    _, proxy = _make_proxy()
    proxy.set_providers({"SomaFM"})
    # Radio.net group should be hidden entirely
    visible_group_names = []
    for p_row in range(proxy.rowCount()):
        p_idx = proxy.index(p_row, 0)
        src_idx = proxy.mapToSource(p_idx)
        node = src_idx.internalPointer()
        if node:
            visible_group_names.append(node.label)
    assert all("Radio.net" not in name for name in visible_group_names)


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------

def test_clear_resets_all(qtbot):
    _, proxy = _make_proxy()
    proxy.set_search("Groove")
    proxy.set_providers({"SomaFM"})
    proxy.set_tags({"chill"})
    proxy.clear_all()
    # All 5 stations should be visible again
    visible = _visible_station_names(proxy)
    assert len(visible) == len(_STATIONS)
