import re

_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _is_valid_hex(value: str) -> bool:
    """Return True if value is a valid 3- or 6-digit hex color string."""
    return bool(_HEX_RE.match(value))


def build_accent_css(hex_value: str) -> str:
    """Return the CSS string that sets the Libadwaita accent color."""
    return f"@define-color accent_bg_color {hex_value};"
