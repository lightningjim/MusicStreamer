"""Phase 45-01: regression tests for the unified station-icon loader.

Covers the bug where StationTreeModel and FavoritesView passed raw relative
station_art_path strings directly to QPixmap, producing null pixmaps and
triggering the fallback icon even when a valid logo file existed.

The shared helper lives in musicstreamer.ui_qt._art_paths and is consumed
by station_tree_model, favorites_view, and station_list_panel.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import FALLBACK_ICON, load_station_icon
# Side-effect import: registers the :/icons/ resource prefix so QPixmap can
# resolve FALLBACK_ICON in tests.
from musicstreamer.ui_qt import icons_rc  # noqa: F401


def _make_station(art_path):
    return Station(
        id=1,
        name="Test Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=art_path,
        album_fallback_path=None,
    )


def _write_logo(
    path: str,
    size: int = 64,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Write a real PNG file to ``path`` so QPixmap(path) returns a non-null pixmap.

    When ``width``/``height`` are provided, they override ``size`` and produce
    a non-square fixture (e.g. width=50, height=100 for a 1:2 portrait).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = width if width is not None else size
    h = height if height is not None else size
    pix = QPixmap(w, h)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"


@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    """Each test starts with a fresh QPixmapCache so cache-hit tests are deterministic."""
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Point paths.data_dir() at a temporary directory for the test."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)


def _non_transparent_bbox(pix: QPixmap) -> tuple[int, int, int, int]:
    """Return (min_x, min_y, max_x, max_y) of the non-transparent region.

    Cost: O(width * height) Python-to-C++ pixelColor() roundtrips. WR-05 /
    Phase 54 review: guard against null pixmaps (which would silently return
    bogus sentinels) and against accidentally being called on large pixmaps
    where this scan becomes prohibitively expensive.
    """
    assert not pix.isNull(), "_non_transparent_bbox requires a non-null pixmap"
    assert pix.width() <= 64 and pix.height() <= 64, (
        "_non_transparent_bbox is O(n^2); not for large pixmaps"
    )
    img = pix.toImage()
    min_x, min_y, max_x, max_y = img.width(), img.height(), -1, -1
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 0:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    return min_x, min_y, max_x, max_y


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_relative_station_art_path_resolves_via_abs_art_path(tmp_data_dir, qtbot):
    """Relative station_art_path must be joined with paths.data_dir() before QPixmap loads it.

    Regression: StationTreeModel._icon_for_station and FavoritesView._load_station_icon
    passed the raw relative string to QPixmap, which loads null → fallback always shown.
    """
    rel = "assets/1/station_art.png"
    abs_path = os.path.join(tmp_data_dir, rel)
    _write_logo(abs_path)

    station = _make_station(rel)
    icon = load_station_icon(station)

    assert isinstance(icon, QIcon)
    assert not icon.isNull(), "Icon must be non-null when a valid logo file exists"
    # WR-04 / Phase 54 review: assert the fixture's red pixel is present at
    # the canvas center rather than comparing full-image equality against the
    # fallback. The Plan-04 transparent-canvas patch makes the previous
    # equality check tautological (loaded canvas has transparent margins;
    # fallback.scaled does not), so it would always inequal regardless of
    # whether the real logo loaded.
    loaded_pix = icon.pixmap(32, 32)
    img = loaded_pix.toImage()
    center = img.pixelColor(img.width() // 2, img.height() // 2)
    assert center.red() > 200 and center.green() < 50 and center.blue() < 50, (
        f"expected red fixture logo at center, got "
        f"rgb=({center.red()},{center.green()},{center.blue()}) "
        f"alpha={center.alpha()} — likely the fallback or wrong pixel"
    )


def test_missing_file_falls_back_without_raising(tmp_data_dir, qtbot):
    """A station_art_path that does not exist on disk falls back to FALLBACK_ICON."""
    station = _make_station("assets/999/does_not_exist.png")
    icon = load_station_icon(station)  # must not raise
    assert isinstance(icon, QIcon)
    assert not icon.isNull(), "Fallback icon must render"


def test_none_station_art_path_uses_fallback(tmp_data_dir, qtbot):
    """station_art_path=None falls back cleanly."""
    station = _make_station(None)
    icon = load_station_icon(station)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_absolute_path_passes_through_unchanged(tmp_path, qtbot):
    """Absolute station_art_path is loaded directly (not re-rooted under data_dir)."""
    abs_path = str(tmp_path / "absolute_logo.png")
    _write_logo(abs_path)

    station = _make_station(abs_path)
    icon = load_station_icon(station)

    assert not icon.isNull()
    # WR-04 / Phase 54 review: see relative-path test above for rationale.
    loaded_pix = icon.pixmap(32, 32)
    img = loaded_pix.toImage()
    center = img.pixelColor(img.width() // 2, img.height() // 2)
    assert center.red() > 200 and center.green() < 50 and center.blue() < 50, (
        f"expected red fixture logo at center, got "
        f"rgb=({center.red()},{center.green()},{center.blue()}) "
        f"alpha={center.alpha()} — likely the fallback or wrong pixel"
    )


def test_default_size_is_32px(tmp_data_dir, qtbot):
    """Default size parameter produces a 32px-bounded pixmap."""
    rel = "assets/2/station_art.png"
    _write_logo(os.path.join(tmp_data_dir, rel), size=128)

    station = _make_station(rel)
    icon = load_station_icon(station)  # default size
    pix = icon.pixmap(64, 64)  # request larger than cached — Qt returns cached size
    # Cached pixmap is scaled to 32x32 bounds; width or height must be <= 32.
    assert max(pix.width(), pix.height()) <= 32


def test_explicit_size_honored(tmp_data_dir, qtbot):
    """Passing size=64 produces a 64px-bounded pixmap."""
    rel = "assets/3/station_art.png"
    _write_logo(os.path.join(tmp_data_dir, rel), size=128)

    station = _make_station(rel)
    icon = load_station_icon(station, size=64)
    pix = icon.pixmap(128, 128)
    assert max(pix.width(), pix.height()) <= 64
    assert max(pix.width(), pix.height()) > 32, "Expected larger-than-default size"


def test_cache_hit_on_second_call(tmp_data_dir, qtbot):
    """Second call for the same station returns a cached pixmap (QPixmapCache hit)."""
    rel = "assets/4/station_art.png"
    abs_path = os.path.join(tmp_data_dir, rel)
    _write_logo(abs_path)

    station = _make_station(rel)

    # First call: populates cache.
    load_station_icon(station)

    # Verify cache entry exists under the resolved-absolute-path key (D-03).
    expected_key = f"station-logo:{abs_path}"
    probe = QPixmap()
    assert QPixmapCache.find(expected_key, probe), (
        f"Expected cache entry at key {expected_key!r} after first load"
    )

    # Second call should hit the cache — load without reading from disk.
    # We assert by deleting the on-disk file: if the cache is hit, icon is still non-null.
    os.remove(abs_path)
    icon2 = load_station_icon(station)
    assert not icon2.isNull(), "Second call must hit QPixmapCache (file was deleted)"


def test_load_station_icon_preserves_portrait_aspect(tmp_data_dir, qtbot):
    """A 50w x 100h portrait source pixmap loads as 16w x 32h inside the QIcon
    (aspect ratio preserved, no center crop). Regression lock for BUG-05 / SC #3.

    Phase 54 (D-10): synthetic-pixmap unit test on load_station_icon. Locks
    the existing pillarbox-correct behavior — would fail under a hypothetical
    future change that reintroduced crop-to-square scaling.
    """
    rel = "assets/5/portrait.png"
    _write_logo(os.path.join(tmp_data_dir, rel), width=50, height=100)

    station = _make_station(rel)
    icon = load_station_icon(station)

    pix = icon.pixmap(QSize(32, 32))
    min_x, min_y, max_x, max_y = _non_transparent_bbox(pix)
    region_w = max_x - min_x + 1
    region_h = max_y - min_y + 1
    assert region_w == 16, f"expected painted region 16w, got {region_w}w"
    assert region_h == 32, f"expected painted region 32h, got {region_h}h"
    # Pillarbox bars are transparent on left + right.
    assert min_x == 8 and max_x == 23, f"expected centered x=8..23, got x={min_x}..{max_x}"
    assert min_y == 0 and max_y == 31, f"expected full-height y=0..31, got y={min_y}..{max_y}"


def test_load_station_icon_preserves_landscape_aspect(tmp_data_dir, qtbot):
    """A 100w x 50h landscape source pixmap loads as 32w x 16h inside the QIcon
    (aspect ratio preserved, no center crop). Covers BUG-05 / SC #2.

    Phase 54: parallel coverage to the portrait test — confirms the same
    Qt.KeepAspectRatio code path works symmetrically on the landscape axis.
    """
    rel = "assets/6/landscape.png"
    _write_logo(os.path.join(tmp_data_dir, rel), width=100, height=50)

    station = _make_station(rel)
    icon = load_station_icon(station)

    pix = icon.pixmap(QSize(32, 32))
    min_x, min_y, max_x, max_y = _non_transparent_bbox(pix)
    region_w = max_x - min_x + 1
    region_h = max_y - min_y + 1
    assert region_w == 32, f"expected painted region 32w, got {region_w}w"
    assert region_h == 16, f"expected painted region 16h, got {region_h}h"
    # Letterbox bars are transparent above + below.
    assert min_x == 0 and max_x == 31, f"expected full-width x=0..31, got x={min_x}..{max_x}"
    assert min_y == 8 and max_y == 23, f"expected centered y=8..23, got y={min_y}..{max_y}"
