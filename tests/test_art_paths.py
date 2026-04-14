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
from PySide6.QtCore import Qt
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


def _write_logo(path: str, size: int = 64) -> None:
    """Write a real PNG file to ``path`` so QPixmap(path) returns a non-null pixmap."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pix = QPixmap(size, size)
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
    # If the real logo loaded, the pixmap must NOT be the fallback.
    fallback_pix = QPixmap(FALLBACK_ICON)
    loaded_pix = icon.pixmap(32, 32)
    assert loaded_pix.toImage() != fallback_pix.scaled(
        32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
    ).toImage(), "Expected real logo, got fallback"


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
    fallback_pix = QPixmap(FALLBACK_ICON).scaled(
        32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    loaded_pix = icon.pixmap(32, 32)
    assert loaded_pix.toImage() != fallback_pix.toImage(), "Expected absolute-path logo, got fallback"


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
