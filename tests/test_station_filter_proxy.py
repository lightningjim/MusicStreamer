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


# === Phase 68: Live Stream Detection (DI.fm) ===


def _di_station(id_: int, name: str, channel_key: str, tags: str = "") -> Station:
    """Phase 68 helper: build DI.fm Station with a stream URL for channel_key."""
    from musicstreamer.models import StationStream
    return Station(
        id=id_,
        name=name,
        provider_id=2,
        provider_name="DI.fm",
        tags=tags,
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=id_ * 10,
                station_id=id_,
                url=f"http://prem1.di.fm:80/di_{channel_key}?listen_key=k",
                position=1,
            )
        ],
    )


_DI_STATIONS = [
    _di_station(101, "House", "house", tags="dance"),
    _di_station(102, "Trance", "trance", tags="dance"),
    _di_station(103, "Lounge", "lounge", tags="chill"),
]


def test_set_live_only_with_live_map_filters_stations(qtbot):
    """Phase 68 / F-02: set_live_only(True) shows only stations in live_map."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({"house": "Show A", "trance": "Show B"})
    proxy.set_live_only(True)
    visible = _visible_station_names(proxy)
    assert "Lounge" not in visible
    assert "House" in visible and "Trance" in visible


def test_set_live_only_false_shows_all(qtbot):
    """Phase 68 / F-02 toggle off: set_live_only(False) restores all stations."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({"house": "Show A", "trance": "Show B"})
    proxy.set_live_only(True)
    proxy.set_live_only(False)
    visible = _visible_station_names(proxy)
    assert len(visible) == 3


def test_live_only_and_provider_chip_compose(qtbot):
    """Phase 68 / F-03: live_only AND provider filter compose with AND semantics."""
    mixed = [
        _di_station(101, "House", "house", tags="dance"),
        _di_station(102, "Trance", "trance", tags="dance"),
        make_station(201, "Groove Salad", "SomaFM", "chill,ambient"),
    ]
    _, proxy = _make_proxy(mixed)
    proxy.set_live_map({"house": "Show A"})
    proxy.set_live_only(True)
    proxy.set_providers({"DI.fm"})
    visible = _visible_station_names(proxy)
    assert visible == ["House"]


def test_live_only_empty_when_no_live(qtbot):
    """Phase 68 / F-04: live_only chip ON with empty live_map → empty tree."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({})
    proxy.set_live_only(True)
    assert _visible_station_names(proxy) == []


def test_set_live_map_no_invalidate_when_chip_off(qtbot):
    """Phase 68 / Pitfall 7: set_live_map must NOT call invalidate when live_only=False."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_only(False)
    calls = []
    original = proxy.invalidate
    proxy.invalidate = lambda: calls.append(1) or original()  # type: ignore[method-assign]
    proxy.set_live_map({"house": "Test"})
    assert calls == []
    proxy.set_live_only(True)
    invalidate_count_after_set_only = len(calls)
    proxy.set_live_map({"trance": "Test2"})
    assert len(calls) > invalidate_count_after_set_only


def test_has_active_filter_includes_live_only(qtbot):
    """Phase 68 / F-03: has_active_filter() returns True when live_only is active."""
    _, proxy = _make_proxy(_DI_STATIONS)
    assert proxy.has_active_filter() is False
    proxy.set_live_only(True)
    assert proxy.has_active_filter() is True
    proxy.set_live_only(False)
    assert proxy.has_active_filter() is False


def test_clear_all_resets_live_only(qtbot):
    """Phase 68 / F-03 clear_all extension: clear_all() also resets live_only."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({"house": "Show A"})
    proxy.set_live_only(True)
    proxy.clear_all()
    assert proxy.has_active_filter() is False
    visible = _visible_station_names(proxy)
    assert len(visible) == 3


# --- Phase 70 / HRES-01 ---


def test_set_hi_res_only_with_quality_map_filters_stations(qtbot):
    """HRES-01 / F-01: set_quality_map + set_hi_res_only(True) shows only hi-res stations.

    RED until Plan 70-09 ships set_quality_map / set_hi_res_only on StationFilterProxyModel.
    """
    stations = [
        make_station(1, "HiRes Station", "SomaFM"),
        make_station(2, "Lossless Station", "SomaFM"),
        make_station(3, "Lossy Station", "DI.fm"),
    ]
    _, proxy = _make_proxy(stations)
    proxy.set_quality_map({1: "hires", 2: "lossless", 3: ""})  # RED: AttributeError
    proxy.set_hi_res_only(True)  # RED: AttributeError
    visible = _visible_station_names(proxy)
    assert "HiRes Station" in visible
    assert "Lossless Station" not in visible
    assert "Lossy Station" not in visible


def test_set_quality_map_no_invalidate_when_chip_off(qtbot):
    """HRES-01 / Pitfall 7: set_quality_map must NOT call invalidate when hi_res_only=False.

    Mirrors Phase 68's Pitfall 7 guard — no spurious re-filter on every live-map push.

    RED until Plan 70-09 ships the invalidate-guard pattern.
    """
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_hi_res_only(False)  # RED: AttributeError
    calls = []
    original = proxy.invalidate
    proxy.invalidate = lambda: calls.append(1) or original()  # type: ignore[method-assign]
    proxy.set_quality_map({101: "hires", 102: "lossless"})  # RED: AttributeError
    assert calls == [], (
        "set_quality_map must NOT invalidate when hi_res_only=False (Pitfall 7 mirror)"
    )
    proxy.set_hi_res_only(True)  # RED: AttributeError
    invalidate_count_after_set_only = len(calls)
    proxy.set_quality_map({101: "hires"})  # RED: AttributeError
    assert len(calls) > invalidate_count_after_set_only, (
        "set_quality_map MUST invalidate when hi_res_only=True"
    )


def test_clear_all_clears_hi_res_only(qtbot):
    """HRES-01: clear_all() must reset hi_res_only to False.

    RED until Plan 70-09 ships set_hi_res_only + clear_all extension.
    """
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_quality_map({101: "hires"})  # RED: AttributeError
    proxy.set_hi_res_only(True)  # RED: AttributeError
    proxy.clear_all()
    assert proxy.has_active_filter() is False
    visible = _visible_station_names(proxy)
    assert len(visible) == len(_DI_STATIONS)
