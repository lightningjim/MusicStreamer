import re

_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _is_valid_hex(value: str) -> bool:
    """Return True if value is a valid 3- or 6-digit hex color string."""
    return bool(_HEX_RE.match(value))


def build_accent_css(hex_value: str) -> str:
    """Return CSS that overrides accent-colored widgets with the given hex color."""
    return (
        f"button.suggested-action {{\n"
        f"    background-color: {hex_value};\n"
        f"    color: white;\n"
        f"}}\n"
        f"scale trough highlight {{\n"
        f"    background-color: {hex_value};\n"
        f"}}\n"
    )
