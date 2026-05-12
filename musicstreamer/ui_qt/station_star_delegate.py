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
from PySide6.QtGui import QFont, QIcon, QPainter, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.models import Station
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE
from musicstreamer.hi_res import best_tier_for_station, TIER_LABEL_BADGE

_STAR_SIZE = 20
_STAR_MARGIN = 4
# Phase 70 — quality pill geometry constants (UI-SPEC §Spacing Scale lock).
_PILL_PADDING_X = 6   # horizontal inner padding (matches Phase 68 LIVE QSS `padding: 2px 6px`)
_PILL_PADDING_Y = 4   # vertical inner padding
_PILL_TO_STAR_GAP = 8 # gap between pill right edge and star left edge (lg spacing token)
_PILL_RADIUS = 8      # corner radius (matches Phase 68 LIVE badge `border-radius: 8px`)
# Worst-case pill width for sizeHint reservation: "LOSSLESS" at 9pt bold ≈ 78 px.
# Using a constant (80 px) rather than QFontMetrics because option.font is not
# reliably available at sizeHint() time on every platform (mirrors _STAR_SIZE idiom).
_PILL_WIDTH_WORST_CASE = 80
# Floor for provider-row sizeHint height. Decoupled from STATION_ICON_SIZE on
# purpose: tree.setUniformRowHeights(True) probes the FIRST row (a provider)
# for the per-row height, so a station-only floor is silently bypassed and
# provider rows must report >= STATION_ICON_SIZE for stations to render
# square. Kept as a separate knob so a future increase to STATION_ICON_SIZE
# (e.g. for HiDPI) does not silently inflate provider-tree row height.
# WR-02 / Phase 54 review.
_PROVIDER_TREE_MIN_ROW_HEIGHT = 32


def _star_rect(row_rect: QRect) -> QRect:
    """Compute the 20x20 star icon rect, right-aligned with STAR_MARGIN from edge."""
    x = row_rect.right() - _STAR_SIZE - _STAR_MARGIN
    y = row_rect.top() + (row_rect.height() - _STAR_SIZE) // 2
    return QRect(x, y, _STAR_SIZE, _STAR_SIZE)


def _pill_rect(row_rect: QRect, pill_width: int, pill_height: int) -> QRect:
    """Compute the quality-pill rect: right-anchored, immediately LEFT of the star column.

    Pill right edge is _PILL_TO_STAR_GAP pixels left of the star left edge.
    Pill is vertically centered in the row. UI-SPEC OD-1 / §Component Inventory item 2.
    """
    star_left_x = row_rect.right() - _STAR_SIZE - _STAR_MARGIN
    pill_right_x = star_left_x - _PILL_TO_STAR_GAP
    pill_left_x = pill_right_x - pill_width
    pill_top_y = row_rect.top() + (row_rect.height() - pill_height) // 2
    return QRect(pill_left_x, pill_top_y, pill_width, pill_height)


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
        # shorter than 32px. Qt has already populated `option` (including
        # selected/hover/focus state) before paint() is invoked, so we mutate
        # `option` in place — calling self.initStyleOption() here would
        # overwrite that view-supplied state. The mutations MUST happen
        # before super().paint() so Qt's CE_ItemViewItem path reads them.
        # WR-01 / Phase 54 review.
        station = index.data(Qt.UserRole)
        if isinstance(station, Station):
            option.decorationSize = QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)
            option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft
        super().paint(painter, option, index)
        if not isinstance(station, Station):
            return  # provider row — no star, no pill

        # Phase 70 — paint quality pill BEFORE the star icon (UI-SPEC §Component Inventory item 2).
        # Uses QPainter primitives only (QSS does not flow into delegate paint — UI-SPEC §Color lock).
        tier = best_tier_for_station(station)
        if tier:
            label = TIER_LABEL_BADGE[tier]
            text_font = QFont(option.font)
            text_font.setBold(True)
            painter.save()
            painter.setFont(text_font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(label)
            pill_w = text_w + 2 * _PILL_PADDING_X
            pill_h = fm.height() + 2 * _PILL_PADDING_Y
            r = _pill_rect(option.rect, pill_w, pill_h)
            # UI-SPEC §Color OD-3: swap fill/text under State_Selected so the pill
            # stays visible against the selected-row palette(highlight) background.
            if option.state & QStyle.State_Selected:
                pill_fill = option.palette.color(QPalette.HighlightedText)
                pill_text = option.palette.color(QPalette.Highlight)
            else:
                pill_fill = option.palette.color(QPalette.Highlight)
                pill_text = option.palette.color(QPalette.HighlightedText)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(pill_fill)
            painter.drawRoundedRect(r, _PILL_RADIUS, _PILL_RADIUS)
            painter.setPen(pill_text)
            painter.drawText(r, Qt.AlignCenter, label)
            painter.restore()

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
        # Phase 54 Plan 04 (BLOCKER #1 fix): floor row height for ALL rows
        # because tree.setUniformRowHeights(True) computes the view's row
        # height from the FIRST row (a provider row in this tree), so a
        # station-only floor is silently bypassed. Station rows floor at
        # STATION_ICON_SIZE; provider rows floor at the decoupled
        # _PROVIDER_TREE_MIN_ROW_HEIGHT (see constant docstring above).
        # WR-02 / Phase 54 review.
        if isinstance(station, Station):
            h = max(base.height(), STATION_ICON_SIZE)
            # Phase 70: grow width by worst-case pill + gap for stations that may
            # have a quality tier. Using a constant (not QFontMetrics) so sizeHint
            # is deterministic across platforms — mirrors _STAR_SIZE + _STAR_MARGIN idiom.
            return QSize(
                base.width() + _STAR_SIZE + _STAR_MARGIN + _PILL_WIDTH_WORST_CASE + _PILL_TO_STAR_GAP,
                h,
            )
        h = max(base.height(), _PROVIDER_TREE_MIN_ROW_HEIGHT)
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
