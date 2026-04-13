import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette

_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _is_valid_hex(value: str) -> bool:
    """Return True if value is a valid 3- or 6-digit hex color string."""
    return bool(_HEX_RE.match(value))


def build_accent_css(hex_value: str) -> str:
    """Return CSS that overrides accent-colored widgets with the given hex color.

    Validates hex_value with _is_valid_hex before interpolating (T-40-01).
    Returns empty string for invalid input.
    """
    if not _is_valid_hex(hex_value):
        return ""
    return (
        f"button.suggested-action {{\n"
        f"    background-color: {hex_value};\n"
        f"    color: white;\n"
        f"}}\n"
        f"scale trough highlight {{\n"
        f"    background-color: {hex_value};\n"
        f"}}\n"
    )


def build_accent_qss(hex_value: str) -> str:
    """Return a Qt QSS string targeting QSlider sub-page for the given hex color.

    Per D-11: only the slider sub-page needs global QSS because chip/segment/
    filter-toggle widgets use palette(highlight) in their per-widget stylesheets.
    The palette Highlight role change (see apply_accent_palette) handles those.
    Validates hex_value with _is_valid_hex before interpolating (T-40-01).
    Returns empty string for invalid input.
    """
    if not _is_valid_hex(hex_value):
        return ""
    return (
        f"QSlider::sub-page:horizontal {{\n"
        f"    background-color: {hex_value};\n"
        f"    border-radius: 2px;\n"
        f"}}\n"
    )


def apply_accent_palette(app: "QApplication", hex_value: str) -> None:
    """Modify app QPalette Highlight role to hex_value and apply QSS for slider.

    This causes all widgets using palette(highlight) in their per-widget QSS
    to pick up the new color on next polish.
    """
    from PySide6.QtGui import QPalette, QColor
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(hex_value))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(palette)
    app.setStyleSheet(build_accent_qss(hex_value))


def reset_accent_palette(app: "QApplication", original_palette: "QPalette") -> None:
    """Restore app palette and clear QSS to remove accent customization."""
    app.setPalette(original_palette)
    app.setStyleSheet("")
