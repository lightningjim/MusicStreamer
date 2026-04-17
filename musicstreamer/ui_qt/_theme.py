"""Shared UI design tokens for ui_qt widgets.

Centralizes color and sizing constants that were previously hardcoded at
call sites. The module is underscore-prefixed to mark it internal-to-ui_qt;
the constants are the public surface.

Tokens:
    ERROR_COLOR_HEX    — hex string "#c0392b" for QSS stylesheet strings
                         ("color: {ERROR_COLOR_HEX};"). A QColor cannot be
                         inlined into a QSS string, so the hex form is
                         required separately.
    ERROR_COLOR_QCOLOR — QColor("#c0392b") for QColor-consuming APIs such as
                         QTreeWidgetItem.setForeground(QColor). A raw hex
                         string cannot be passed to setForeground.
    STATION_ICON_SIZE  — station-row icon dimension in pixels (32). Consumed
                         by load_station_icon default and by every list/tree
                         that shows station rows (setIconSize(QSize(N, N))).

Phase 46 decisions:
    D-02 — two-constant form (_HEX and _QCOLOR) avoids callers constructing
           QColor repeatedly.
    D-06 — STATION_ICON_SIZE lives here (not in _art_paths.py) because it's
           a visual token, not a path-resolution concern.
"""
from __future__ import annotations

from PySide6.QtGui import QColor


# Destructive/error foreground color. Use _HEX in stylesheet strings and
# _QCOLOR for APIs that take a QColor (e.g. item.setForeground).
ERROR_COLOR_HEX: str = "#c0392b"
ERROR_COLOR_QCOLOR: QColor = QColor(ERROR_COLOR_HEX)

# Station-row icon dimension in pixels. Consumed by load_station_icon
# default and by every list/tree that shows station rows.
STATION_ICON_SIZE: int = 32
