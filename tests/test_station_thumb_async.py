"""Phase 94 Wave-0: integration tests for async thumb generation and StationTreeModel wiring.

Tests in this file encode decisions D-01 and D-03:
  - D-01: now_playing_panel._load_scaled_pixmap must NOT reference station_art.thumb
           (drift-guard; passes GREEN immediately)
  - D-03: StationTreeModel._request_thumb/_on_thumb_landing/_in_flight_thumbs/
           index_for_station_id exist and deliver dataChanged after async write.
           These 3 tests are RED until Plan 03 adds the symbols.

Analog: tests/test_gbs_marquee.py lines 229-350 — QTest.qWait + daemon-thread
Signal delivery pattern.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtTest import QTest

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt import icons_rc  # noqa: F401 — register :/icons/ prefix
from musicstreamer.ui_qt.station_tree_model import StationTreeModel


# ----------------------------------------------------------------------
# QApplication singleton — required for QAbstractItemModel + Signal delivery
# ----------------------------------------------------------------------

def _get_qapp():
    """Return the running QApplication or create one (module-scoped singleton)."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

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
# Helpers
# ----------------------------------------------------------------------

def _make_station(sid: int, name: str, provider: str, art: str | None) -> Station:
    """Build a Station object with all required fields (matches test_station_icon_integration.py)."""
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


def _write_logo(path: str, size: int = 64, width: int | None = None, height: int | None = None) -> None:
    """Write a real PNG file so QPixmap(path) returns a non-null pixmap."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = width if width is not None else size
    h = height if height is not None else size
    pix = QPixmap(w, h)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_thumb_landing_emits_datachanged(tmp_data_dir, qtbot):
    """D-03 (async repaint): dataChanged is emitted after thumb generation completes.

    Build a model with one station whose source logo exists but no thumb is on
    disk. Trigger the DecorationRole path (which invokes on_thumb_needed ->
    _request_thumb -> daemon worker). After QTest.qWait(500), assert exactly
    one dataChanged emission covering a single row with Qt.DecorationRole.

    RED until Plan 03 adds _request_thumb/_on_thumb_landing/_thumb_landing/_in_flight_thumbs.
    """
    _get_qapp()

    rel = "assets/20/station_art.png"
    abs_source = os.path.join(tmp_data_dir, rel)
    _write_logo(abs_source)

    station = _make_station(20, "Async Station", "TestProv", rel)
    model = StationTreeModel([station])

    emissions = []
    model.dataChanged.connect(lambda tl, br, roles: emissions.append((tl, br, roles)))

    # Navigate to the station index: root -> provider (row 0) -> station (row 0)
    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)
    assert station_idx.isValid(), "expected a valid station index"

    # Trigger the DecorationRole path — this should call on_thumb_needed ->
    # _request_thumb -> daemon thread.  Symbols _request_thumb / _in_flight_thumbs /
    # _thumb_landing do NOT exist yet (Plan 03) — this line will AttributeError (RED).
    model.data(station_idx, Qt.DecorationRole)

    # Wait for the daemon thread to finish the PNG write and the QueuedConnection
    # to deliver _on_thumb_landing -> dataChanged on the main thread.
    QTest.qWait(500)

    assert len(emissions) == 1, (
        f"expected exactly 1 dataChanged emission, got {len(emissions)}"
    )
    top_left, bottom_right, roles = emissions[0]
    assert top_left == bottom_right, "dataChanged must cover a single row (top_left == bottom_right)"
    assert Qt.DecorationRole in roles, (
        f"Qt.DecorationRole must be in roles list, got {roles!r}"
    )


def test_in_flight_dedup(tmp_data_dir, qtbot, monkeypatch):
    """D-03 (dedup): rapid data() calls for the same station enqueue the worker only once.

    Simulate fast-scroll repaints by calling model.data(station_index, DecorationRole)
    multiple times before the worker finishes. Patch _generate_thumb with a spy
    that counts calls; assert call count == 1. After qWait, assert the station_id
    is no longer in model._in_flight_thumbs.

    RED until Plan 03 adds _request_thumb/_in_flight_thumbs/_thumb_landing.
    """
    _get_qapp()
    import musicstreamer.ui_qt._art_paths as _art_paths_mod

    rel = "assets/21/station_art.png"
    abs_source = os.path.join(tmp_data_dir, rel)
    _write_logo(abs_source)

    station = _make_station(21, "Dedup Station", "TestProv", rel)
    model = StationTreeModel([station])

    # Patch _generate_thumb with a spy that records calls but does not run the worker.
    generate_calls = []

    def _spy_generate_thumb(source_path, thumb_path, station_id, callback):
        generate_calls.append((station_id, source_path, thumb_path))
        # Call callback with None to simulate a miss (no actual file written),
        # so _on_thumb_landing discards the in-flight entry without touching disk.
        callback(station_id, source_path, None)

    monkeypatch.setattr(_art_paths_mod, "_generate_thumb", _spy_generate_thumb)

    provider_idx = model.index(0, 0)
    station_idx = model.index(0, 0, provider_idx)
    assert station_idx.isValid()

    # Rapid successive data() calls — should only enqueue once.
    # _request_thumb/_in_flight_thumbs do not exist yet (RED until Plan 03).
    N = 5
    for _ in range(N):
        model.data(station_idx, Qt.DecorationRole)

    # Allow QueuedConnection delivery.
    QTest.qWait(200)

    assert len(generate_calls) == 1, (
        f"_generate_thumb called {len(generate_calls)} times for {N} data() calls; "
        "expected exactly 1 (dedup guard must fire)"
    )
    assert generate_calls[0][0] == station.id

    # After landing, the station_id must be removed from _in_flight_thumbs.
    # This attribute does not exist yet (RED until Plan 03).
    assert station.id not in model._in_flight_thumbs, (
        f"station.id {station.id!r} should be removed from _in_flight_thumbs after landing"
    )


def test_now_playing_panel_does_not_use_thumb(tmp_data_dir):
    """D-01 (drift-guard): _load_scaled_pixmap in now_playing_panel must NOT reference station_art.thumb.

    This test reads the source file and asserts the substring 'station_art.thumb' is absent,
    and that _load_scaled_pixmap exists (proving the full-res Now Playing path is intact).

    This test passes GREEN immediately — it is a static source-text guard.
    """
    import inspect
    import musicstreamer.ui_qt.now_playing_panel as _npp_mod

    source = inspect.getsource(_npp_mod)

    assert "station_art.thumb" not in source, (
        "now_playing_panel.py must NOT reference 'station_art.thumb'; "
        "the full-res _load_scaled_pixmap path must never be rewired to the sidebar thumbnail"
    )
    assert "_load_scaled_pixmap" in source, (
        "_load_scaled_pixmap function must exist in now_playing_panel.py; "
        "if it was renamed or removed this drift-guard needs updating"
    )


def test_index_for_station_id_roundtrip(tmp_data_dir, qtbot):
    """D-03 (coordination): index_for_station_id returns a valid index for known IDs.

    Build a model with >=2 providers each with >=1 station. Assert:
    - model.index_for_station_id(known_id).isValid() is True
    - station_for_index(that index).id == known_id
    - model.index_for_station_id(unknown_id).isValid() is False

    RED until Plan 03 adds index_for_station_id to StationTreeModel.
    """
    _get_qapp()

    rel_a = "assets/30/station_art.png"
    rel_b = "assets/31/station_art.png"
    _write_logo(os.path.join(tmp_data_dir, rel_a))
    _write_logo(os.path.join(tmp_data_dir, rel_b))

    station_a = _make_station(30, "Station A", "ProviderAlpha", rel_a)
    station_b = _make_station(31, "Station B", "ProviderBeta", rel_b)
    model = StationTreeModel([station_a, station_b])

    # Two providers, one station each.
    assert model.rowCount() == 2, f"expected 2 provider rows, got {model.rowCount()}"

    # Round-trip for station_a.
    idx_a = model.index_for_station_id(30)  # AttributeError — RED until Plan 03
    assert idx_a.isValid(), "index_for_station_id(30) must return a valid index"
    assert model.station_for_index(idx_a).id == 30, (
        "station_for_index(index_for_station_id(30)).id must equal 30"
    )

    # Round-trip for station_b.
    idx_b = model.index_for_station_id(31)
    assert idx_b.isValid(), "index_for_station_id(31) must return a valid index"
    assert model.station_for_index(idx_b).id == 31

    # Unknown station_id -> invalid index.
    idx_unknown = model.index_for_station_id(99999)
    assert not idx_unknown.isValid(), (
        "index_for_station_id(99999) must return an invalid QModelIndex"
    )
