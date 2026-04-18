"""Phase 46-01: unit + grep-regression tests for the UI theme token module.

Covers the three exported constants (type + value shape) and enforces that
migrated call sites do not regress to raw literals.

Scope of grep assertions: musicstreamer/ui_qt/ only. Test files are
deliberately NOT scanned — tests/test_station_list_panel.py legitimately
asserts `panel.tree.iconSize() == QSize(32, 32)` against the widget's
actual iconSize property (not against source text), which is semantically
correct and must not be touched.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QColor

from musicstreamer.ui_qt._theme import (
    ERROR_COLOR_HEX,
    ERROR_COLOR_QCOLOR,
    STATION_ICON_SIZE,
)


UI_QT = Path(__file__).parent.parent / "musicstreamer" / "ui_qt"


def test_error_color_hex_is_string():
    assert isinstance(ERROR_COLOR_HEX, str)
    assert ERROR_COLOR_HEX.startswith("#")
    assert len(ERROR_COLOR_HEX) == 7  # '#' + 6 hex digits


def test_error_color_qcolor_is_qcolor():
    assert isinstance(ERROR_COLOR_QCOLOR, QColor)
    assert ERROR_COLOR_QCOLOR.name().lower() == ERROR_COLOR_HEX.lower()


def test_station_icon_size_is_32():
    assert isinstance(STATION_ICON_SIZE, int)
    assert STATION_ICON_SIZE == 32


def test_no_raw_error_hex_outside_theme():
    """No file in musicstreamer/ui_qt/ (except _theme.py) may contain #c0392b."""
    offenders = []
    for py in UI_QT.glob("*.py"):
        if py.name == "_theme.py":
            continue
        text = py.read_text()
        if "#c0392b" in text:
            offenders.append(str(py))
    assert not offenders, f"Raw hex found in: {offenders}"


def test_no_raw_icon_size_in_migrated_sites():
    """Station-row icon-size sites must use STATION_ICON_SIZE, not a literal."""
    targets = ("station_list_panel.py", "favorites_view.py", "station_tree_model.py")
    offenders = []
    for name in targets:
        path = UI_QT / name
        if not path.exists():
            continue
        text = path.read_text()
        if re.search(r"QSize\(\s*32\s*,\s*32\s*\)", text):
            offenders.append(name)
    assert not offenders, f"Raw QSize(32, 32) found in: {offenders}"
