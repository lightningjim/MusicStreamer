"""Phase 38-02: StationStarDelegate.

QStyledItemDelegate that paints a 20x20 star icon right-aligned in station
tree rows and handles click toggle via editorEvent.

Signals:
  star_toggled(Station) — emitted when the star area is clicked on a station row

Provider rows (where index.data(Qt.UserRole) is None) are untouched — super()
handles them normally.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.models import Station
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE

_STAR_SIZE = 20
_STAR_MARGIN = 4


def _star_rect(row_rect: QRect) -> QRect:
    """Compute the 20x20 star icon rect, right-aligned with STAR_MARGIN from edge."""
    x = row_rect.right() - _STAR_SIZE - _STAR_MARGIN
    y = row_rect.top() + (row_rect.height() - _STAR_SIZE) // 2
    return QRect(x, y, _STAR_SIZE, _STAR_SIZE)


class StationStarDelegate(QStyledItemDelegate):
    """Paints star icon on station rows and toggles is_favorite on click."""

    star_toggled = Signal(object)  # emits Station

    def __init__(self, repo, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo

    # ----------------------------------------------------------------------
    # Paint
    # ----------------------------------------------------------------------

    def paint(self, painter, option, index) -> None:
        # Phase 54-04 (Path B-2 / D-09 escalation): force a square 32x32
        # decoration rect for station rows so non-square pixmaps (portrait
        # 16x32, landscape 32x16) are not vertically squeezed when the
        # platform-default row geometry on Linux X11/Wayland gives Qt a row
        # shorter than 32px. The mutation MUST happen BEFORE super().paint()
        # so Qt's CE_ItemViewItem path reads the overridden values.
        station = index.data(Qt.UserRole)
        if isinstance(station, Station):
            self.initStyleOption(option, index)
            option.decorationSize = QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)
            option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft
        super().paint(painter, option, index)
        if not isinstance(station, Station):
            return  # provider row — no star

        is_fav = self._repo.is_favorite_station(station.id)
        icon_name = "starred-symbolic" if is_fav else "non-starred-symbolic"
        icon = QIcon.fromTheme(icon_name, QIcon(f":/icons/{icon_name}.svg"))

        rect = _star_rect(option.rect)
        icon.paint(painter, rect, Qt.AlignCenter, QIcon.Normal, QIcon.On)

    # ----------------------------------------------------------------------
    # sizeHint — add star width + margin to station rows
    # ----------------------------------------------------------------------

    def sizeHint(self, option, index) -> QSize:
        base = super().sizeHint(option, index)
        station = index.data(Qt.UserRole)
        # Phase 54 Plan 04 (BLOCKER #1 fix): floor row height at
        # STATION_ICON_SIZE for ALL rows (not just station rows) because
        # tree.setUniformRowHeights(True) computes the view's row height from
        # the FIRST row (a provider row in this tree), so a station-only floor
        # is silently bypassed. Flooring providers too keeps station names
        # vertically aligned and gives Qt's super().paint a square 32x32
        # decoration rect on Linux X11/Wayland (closes VERIFICATION.md Gap 1).
        h = max(base.height(), STATION_ICON_SIZE)
        if isinstance(station, Station):
            return QSize(base.width() + _STAR_SIZE + _STAR_MARGIN, h)
        return QSize(base.width(), h)

    # ----------------------------------------------------------------------
    # editorEvent — handle star click
    # ----------------------------------------------------------------------

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.MouseButtonRelease:
            station = index.data(Qt.UserRole)
            if isinstance(station, Station):
                if _star_rect(option.rect).contains(event.pos()):
                    self.star_toggled.emit(station)
                    return True
        return super().editorEvent(event, model, option, index)
