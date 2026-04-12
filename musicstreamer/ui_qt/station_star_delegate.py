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
        super().paint(painter, option, index)
        station = index.data(Qt.UserRole)
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
        if isinstance(station, Station):
            return QSize(base.width() + _STAR_SIZE + _STAR_MARGIN, base.height())
        return base

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
