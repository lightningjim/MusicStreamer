"""Phase 45 Nyquist validation: end-to-end integration tests for station-icon rendering.

Closes behavioral gaps left by tests/test_art_paths.py (helper-only) and the panel
test (only asserts the panel's helper import). These tests exercise the full
consumer path on the two previously-broken call sites:

  - PHASE-45-FIX-LIST-LOGO:  StationTreeModel.data(index, DecorationRole) must
    return a non-fallback QIcon when station_art_path resolves to a real file.

  - PHASE-45-FIX-FAVES-LOGO: FavoritesView._populate_stations must set a
    non-fallback icon on the list item for favorited stations with a real logo.

  - PHASE-45-UNIFY-LOADER:   Regression guard — any call site that re-introduces
    raw QPixmap(rel_path) would render the fallback icon and fail these tests.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt import icons_rc  # noqa: F401 — register :/icons/ prefix
from musicstreamer.ui_qt._art_paths import FALLBACK_ICON
from musicstreamer.ui_qt.favorites_view import FavoritesView
from musicstreamer.ui_qt.station_tree_model import StationTreeModel


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------

GREEN_RGB = (0, 255, 0)


def _make_station(sid: int, name: str, provider: str, art: str | None) -> Station:
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


def _write_green_logo(abs_path: str) -> None:
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    pix = QPixmap(32, 32)
    pix.fill(Qt.green)
    assert pix.save(abs_path, "PNG"), f"failed to write fixture logo at {abs_path}"


def _icon_center_rgb(icon: QIcon, size: int = 32) -> tuple[int, int, int]:
    pix = icon.pixmap(size, size)
    img = pix.toImage()
    c = img.pixelColor(img.width() // 2, img.height() // 2)
    return (c.red(), c.green(), c.blue())


def _fallback_center_rgb(size: int = 32) -> tuple[int, int, int]:
    pix = QPixmap(FALLBACK_ICON).scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    img = pix.toImage()
    c = img.pixelColor(img.width() // 2, img.height() // 2)
    return (c.red(), c.green(), c.blue())


@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)


class _FakeRepo:
    def __init__(self, stations: list[Station], fav_ids: set[int] | None = None):
        self._stations = stations
        self._fav_ids = set(fav_ids or set())

    def list_stations(self):
        return list(self._stations)

    def list_favorite_stations(self):
        return [s for s in self._stations if s.id in self._fav_ids]

    def list_favorites(self):
        return []

    def set_station_favorite(self, sid, val):
        if val:
            self._fav_ids.add(sid)
        else:
            self._fav_ids.discard(sid)

    def is_favorite_station(self, sid):
        return sid in self._fav_ids

    def remove_favorite(self, *args, **kwargs):
        return None


# ----------------------------------------------------------------------
# PHASE-45-FIX-LIST-LOGO — StationTreeModel renders real logo
# ----------------------------------------------------------------------


def test_station_tree_model_decoration_role_returns_real_logo(tmp_data_dir, qtbot):
    """DecorationRole on a station row must return the real logo (not fallback).

    Regression guard for the original bug: StationTreeModel._icon_for_station
    passed the raw relative path to QPixmap, which silently returned null, so
    the generic audio-x-symbolic fallback rendered in its place.
    """
    rel = "assets/100/station_art.png"
    _write_green_logo(os.path.join(tmp_data_dir, rel))

    station = _make_station(100, "Green Station", "TestProv", rel)
    model = StationTreeModel([station])

    # Navigate: root -> provider (row 0) -> station (row 0)
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)
    assert station_idx.isValid(), "expected a station row under the provider"

    icon = model.data(station_idx, Qt.DecorationRole)
    assert isinstance(icon, QIcon), f"DecorationRole must return QIcon, got {type(icon)}"
    assert not icon.isNull()

    center = _icon_center_rgb(icon)
    fallback_center = _fallback_center_rgb()
    assert center == GREEN_RGB, (
        f"Tree model returned fallback icon (center {center}) instead of the real "
        f"green logo. Fallback center: {fallback_center}. "
        "Likely regression: rel path passed directly to QPixmap without abs_art_path."
    )


def test_station_tree_model_decoration_role_falls_back_when_missing(tmp_data_dir, qtbot):
    """Stations with no art still render a valid (fallback) icon — no crash, no null."""
    station = _make_station(101, "No Art", "TestProv", None)
    model = StationTreeModel([station])

    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)
    icon = model.data(station_idx, Qt.DecorationRole)

    assert isinstance(icon, QIcon)
    assert not icon.isNull()


# ----------------------------------------------------------------------
# PHASE-45-FIX-FAVES-LOGO — FavoritesView renders real logo
# ----------------------------------------------------------------------


def test_favorites_view_station_item_icon_is_real_logo(tmp_data_dir, qtbot):
    """A favorited station with a valid logo renders its real icon in the favorites list."""
    rel = "assets/200/station_art.png"
    _write_green_logo(os.path.join(tmp_data_dir, rel))

    station = _make_station(200, "Fav Green", "TestProv", rel)
    repo = _FakeRepo([station], fav_ids={200})

    view = FavoritesView(repo)
    qtbot.addWidget(view)

    assert view._stations_list.count() == 1, "expected the favorited station in the list"
    item = view._stations_list.item(0)
    icon = item.icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()

    center = _icon_center_rgb(icon)
    fallback_center = _fallback_center_rgb()
    assert center == GREEN_RGB, (
        f"FavoritesView rendered fallback (center {center}) instead of the real "
        f"green logo. Fallback center: {fallback_center}. "
        "Likely regression: FavoritesView bypassed abs_art_path resolution."
    )


def test_favorites_view_missing_art_falls_back_cleanly(tmp_data_dir, qtbot):
    """Favorited station with no station_art_path renders the fallback — no crash."""
    station = _make_station(201, "Fav NoArt", "TestProv", None)
    repo = _FakeRepo([station], fav_ids={201})

    view = FavoritesView(repo)
    qtbot.addWidget(view)

    assert view._stations_list.count() == 1
    icon = view._stations_list.item(0).icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
