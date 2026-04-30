"""Phase 54-04: StationStarDelegate paint+sizeHint geometry tests.

Gap closure for Phase 54 Gap 1: portrait sources still cropped on Linux
X11/Wayland because the row's decoration rect was wider than tall. Plan 04
overrides StationStarDelegate.paint to force option.decorationSize = (32, 32)
and option.decorationAlignment = AlignVCenter | AlignLeft, and overrides
sizeHint to floor station-row height at STATION_ICON_SIZE (32).

These tests exercise the delegate paint+sizeHint contract directly. They do
NOT pixel-scan rendered output — that approach is too brittle across Qt
styles. Instead, they assert the option-state mutations and the sizeHint
return value.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPixmap, QPixmapCache
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE
from musicstreamer.ui_qt.station_star_delegate import (
    StationStarDelegate,
    _PROVIDER_TREE_MIN_ROW_HEIGHT,
)
from musicstreamer.ui_qt.station_tree_model import StationTreeModel
# Side-effect import: registers :/icons/ resource prefix so QPixmap can
# resolve FALLBACK_ICON in tests.
from musicstreamer.ui_qt import icons_rc  # noqa: F401


@pytest.fixture(autouse=True)
def _isolate_pixmap_cache():
    QPixmapCache.clear()
    yield
    QPixmapCache.clear()


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return str(tmp_path)


def _write_portrait_logo(abs_path: str, width: int = 50, height: int = 100) -> None:
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    pix = QPixmap(width, height)
    pix.fill(Qt.red)
    assert pix.save(abs_path, "PNG")


class _StubRepo:
    """Minimal repo stub that satisfies StationStarDelegate.__init__ + paint."""

    def is_favorite_station(self, station_id) -> bool:
        return False


def _make_station(art_rel_path: str, station_id: int = 1) -> Station:
    return Station(
        id=station_id,
        name="Test Station",
        provider_id=None,
        provider_name="TestProvider",
        tags="",
        station_art_path=art_rel_path,
        album_fallback_path=None,
    )


def _station_index(model: StationTreeModel):
    """Return the QModelIndex of the first station row in the model."""
    # Provider group is at row 0 of the root.
    provider_idx = model.index(0, 0)
    assert provider_idx.isValid(), "provider index must exist"
    # Station is at row 0 of the provider.
    station_idx = model.index(0, 0, provider_idx)
    assert station_idx.isValid(), "station index must exist"
    assert isinstance(station_idx.data(Qt.UserRole), Station), (
        "station_idx must yield a Station via UserRole"
    )
    return station_idx


def _provider_index(model: StationTreeModel):
    provider_idx = model.index(0, 0)
    assert provider_idx.isValid()
    assert model.station_for_index(provider_idx) is None
    return provider_idx


def _build_model_and_delegate(tmp_data_dir, qtbot):
    rel = "assets/1/portrait.png"
    _write_portrait_logo(os.path.join(tmp_data_dir, rel))
    station = _make_station(rel)
    model = StationTreeModel([station])
    delegate = StationStarDelegate(_StubRepo())
    return model, delegate


def _build_option_for_index(delegate, index) -> QStyleOptionViewItem:
    """Construct a QStyleOptionViewItem and let initStyleOption populate it.

    The delegate's paint() override is expected to call initStyleOption itself
    and then mutate option.decorationSize / option.decorationAlignment, but for
    the tests we want a baseline option to compare against — so we let
    initStyleOption populate it here and then pass it through to paint().
    """
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, index)
    return option


# ----------------------------------------------------------------------
# Tests — paint() decoration-geometry overrides
# ----------------------------------------------------------------------

def test_paint_forces_square_decoration_rect(tmp_data_dir, qtbot):
    """delegate.paint must set option.decorationSize to (32, 32) for station rows.

    This is the core Path B-2 fix — guarantees Qt's super().paint() draws the
    icon into a square 32x32 slot regardless of platform-default row geometry.
    """
    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    station_idx = _station_index(model)
    option = _build_option_for_index(delegate, station_idx)

    # Render to an off-screen pixmap so paint() runs through Qt's full pipeline.
    canvas = QPixmap(200, 64)
    canvas.fill(Qt.white)
    painter = QPainter(canvas)
    try:
        delegate.paint(painter, option, station_idx)
    finally:
        painter.end()

    assert option.decorationSize == QSize(STATION_ICON_SIZE, STATION_ICON_SIZE), (
        f"expected option.decorationSize == QSize(32, 32) after paint, got "
        f"{option.decorationSize}"
    )


def test_paint_forces_left_aligned_decoration(tmp_data_dir, qtbot):
    """delegate.paint must set option.decorationAlignment to AlignVCenter | AlignLeft."""
    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    station_idx = _station_index(model)
    option = _build_option_for_index(delegate, station_idx)

    canvas = QPixmap(200, 64)
    canvas.fill(Qt.white)
    painter = QPainter(canvas)
    try:
        delegate.paint(painter, option, station_idx)
    finally:
        painter.end()

    # PySide6 6.11 flag-safe: bitwise tests instead of strict equality, because
    # Qt.Alignment composites can carry style-derived bits that strict-equality
    # would reject. We only require AlignLeft and AlignVCenter to be SET.
    assert bool(option.decorationAlignment & Qt.AlignLeft), (
        f"expected AlignLeft bit set in option.decorationAlignment, "
        f"got {int(option.decorationAlignment)}"
    )
    assert bool(option.decorationAlignment & Qt.AlignVCenter), (
        f"expected AlignVCenter bit set in option.decorationAlignment, "
        f"got {int(option.decorationAlignment)}"
    )


# ----------------------------------------------------------------------
# Tests — sizeHint() row-height floor
# ----------------------------------------------------------------------

def test_sizehint_enforces_min_row_height_32_for_station_rows(tmp_data_dir, qtbot):
    """sizeHint() for a station row must return height >= STATION_ICON_SIZE (32).

    On Linux X11/Wayland the default super().sizeHint() height was apparently
    < 32 in setUniformRowHeights(True) mode, leading to a landscape-shaped
    decoration rect. Floor at 32.
    """
    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    station_idx = _station_index(model)
    option = _build_option_for_index(delegate, station_idx)

    hint = delegate.sizeHint(option, station_idx)
    assert hint.height() >= STATION_ICON_SIZE, (
        f"expected sizeHint height >= {STATION_ICON_SIZE}, got {hint.height()}"
    )


def test_sizehint_floors_height_at_32_for_provider_rows(tmp_data_dir, qtbot):
    """Provider rows must also report height >= STATION_ICON_SIZE because
    tree.setUniformRowHeights(True) uses the first row's sizeHint for ALL rows.
    Without this floor, the station-row floor is silently bypassed (regression
    of Phase 54 Gap 1 — BLOCKER #1).

    Also asserts that provider rows do NOT include the star-width reservation
    (D-01 invariant: provider rows untouched at the star-logic level).
    """
    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    provider_idx = _provider_index(model)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, provider_idx)

    hint = delegate.sizeHint(option, provider_idx)

    # Assertion 1 — height floored at the provider-tree row-height knob
    # (decoupled from STATION_ICON_SIZE; see WR-02 / Phase 54 review).
    assert hint.height() >= _PROVIDER_TREE_MIN_ROW_HEIGHT, (
        f"provider row sizeHint must floor at {_PROVIDER_TREE_MIN_ROW_HEIGHT}, "
        f"got {hint.height()}"
    )

    # Assertion 2 — width does NOT include star reservation (D-01 invariant).
    # WR-06 / Phase 54 review: call QStyledItemDelegate.sizeHint as an
    # unbound method on `delegate` rather than instantiating a fresh
    # __bases__[0]() — which both leaks an unparented QObject and couples
    # this test to the inheritance order of StationStarDelegate.
    super_hint = QStyledItemDelegate.sizeHint(delegate, option, provider_idx)
    assert hint.width() == super_hint.width(), (
        f"provider row width must NOT include star reservation, got "
        f"{hint.width()} vs base {super_hint.width()}"
    )


def test_uniform_row_height_applies_floor_with_provider_first_row(tmp_data_dir, qtbot):
    """Integration test: with setUniformRowHeights(True), tree.visualRect for a
    station row must be >= 32 px tall. Catches the Plan 04 BLOCKER #1 regression
    where a station-only sizeHint floor is bypassed by Qt using the first-row
    (provider) sizeHint for all rows.
    """
    from PySide6.QtCore import QSize as _QSize
    from PySide6.QtWidgets import QTreeView

    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    tree = QTreeView()
    qtbot.addWidget(tree)
    tree.setModel(model)
    tree.setItemDelegate(delegate)
    tree.setHeaderHidden(True)
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setIconSize(_QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))
    tree.expandAll()
    tree.show()
    # The first model row is a provider — that is the row Qt's
    # uniformRowHeights probe inspects to compute the per-row height.
    station_idx = _station_index(model)
    rect = tree.visualRect(station_idx)
    assert rect.height() >= STATION_ICON_SIZE, (
        f"station-row visualRect.height() must be >= {STATION_ICON_SIZE} when "
        f"tree.setUniformRowHeights(True) probes the first (provider) row; got "
        f"{rect.height()}. This is the BLOCKER #1 regression — provider-row "
        f"sizeHint is not flooring at 32."
    )


def test_paint_provider_row_does_not_force_decoration_size(tmp_data_dir, qtbot):
    """delegate.paint on a provider row must NOT mutate option.decorationSize.

    Provider rows have no station icon — forcing a 32x32 decoration rect on
    them would cause Qt to ask for a non-existent decoration. Provider rows
    must take the super-class default decoration path.
    """
    model, delegate = _build_model_and_delegate(tmp_data_dir, qtbot)
    provider_idx = _provider_index(model)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, provider_idx)
    # Capture decorationSize as initStyleOption set it (likely default, e.g. 0x0
    # since provider rows have no DecorationRole data).
    pre_paint_dec_size = QSize(option.decorationSize)

    canvas = QPixmap(200, 64)
    canvas.fill(Qt.white)
    painter = QPainter(canvas)
    try:
        delegate.paint(painter, option, provider_idx)
    finally:
        painter.end()

    # Provider-row paint must not have force-set decorationSize to 32x32.
    # If pre_paint_dec_size was already 32x32 by some accident, accept that.
    # Otherwise the post-paint value must equal the pre-paint value.
    assert option.decorationSize == pre_paint_dec_size, (
        f"provider-row paint must not mutate decorationSize; expected "
        f"{pre_paint_dec_size}, got {option.decorationSize}"
    )
