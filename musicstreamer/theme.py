"""Phase 66 / THEME-01: programmatic theme palette construction + application.

Parallels musicstreamer/accent_utils.py — pure helpers + one apply function.
No QSS-string interpolation of hex values (RESEARCH Q4 + Pitfall 9 — no parallel
QSS-on-disk file analogous to paths.accent_css_path()). All theme application
goes through QApplication.setPalette().

Layering contract (Phase 59 D-02 + Phase 66 D-02):
- Theme owns 11 QPalette primary roles (Window, WindowText, Base, AlternateBase,
  Text, Button, ButtonText, HighlightedText, Link, ToolTipBase, ToolTipText)
  plus a Highlight baseline.
- accent_color (when non-empty) overrides Highlight on top via apply_accent_palette
  (called from main_window.py:241-245 after theme is in place at startup).
- Picking a theme NEVER mutates accent_color setting.

Defense-in-depth:
- _is_valid_hex from accent_utils guards every hex before reaching QColor()
- getattr(QPalette.ColorRole, role_name, None) rejects unknown role names
- json.loads + try/except JSONDecodeError + isinstance(dict) check on theme_custom
"""
from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from musicstreamer.accent_utils import _is_valid_hex
from musicstreamer.constants import ACCENT_COLOR_DEFAULT

if TYPE_CHECKING:
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication


THEME_PRESETS: dict[str, dict[str, str]] = {
    # System default — sentinel: empty dict means "do not construct a palette"
    # (Linux: leave Qt default; Windows: app.setStyle("Fusion") + _apply_windows_palette)
    "system": {},

    # Vaporwave — light pastel, lavender base + pink/cyan accents.
    # WCAG: all body-text pairs pass AA; cyan Link replaced with purple-blue (#7b5fef)
    # because cyan #5fefef on near-white base = 1.4:1 (RESEARCH Q7 / A2).
    "vaporwave": {
        "Window": "#efe5ff",
        "WindowText": "#4a3a5a",
        "Base": "#fff5fb",
        "AlternateBase": "#f5e8ff",
        "Text": "#4a3a5a",
        "Button": "#d8c5f5",
        "ButtonText": "#4a3a5a",
        "Highlight": "#ff77ff",
        "HighlightedText": "#ffffff",
        "Link": "#7b5fef",
        "ToolTipBase": "#f9d6f0",
        "ToolTipText": "#3a2845",
    },

    # Overrun — dark neon, hot magenta on near-black.
    "overrun": {
        "Window": "#0a0408",
        "WindowText": "#ffe8f4",
        "Base": "#110a10",
        "AlternateBase": "#1c1218",
        "Text": "#ffe8f4",
        "Button": "#2d1828",
        "ButtonText": "#ffe8f4",
        "Highlight": "#ff2dd1",
        "HighlightedText": "#ffffff",
        "Link": "#00f0ff",
        "ToolTipBase": "#1a0a18",
        "ToolTipText": "#ffe8f4",
    },

    # GBS.FM — light, sampled live from https://gbs.fm/images/style.css 2026-05-09.
    # CONTEXT.md D-05 LOCKED — uppercase hex preserved verbatim from brand site.
    "gbs": {
        "Window": "#A1D29D",
        "WindowText": "#000000",
        "Base": "#D8E9D6",
        "AlternateBase": "#E7F1E6",
        "Text": "#000000",
        "Button": "#B1D07C",
        "ButtonText": "#000000",
        "Highlight": "#5AB253",
        "HighlightedText": "#FFFFFF",
        "Link": "#448F3F",
        "ToolTipBase": "#2d5a2a",
        "ToolTipText": "#f0f5e8",
    },

    # GBS.FM After Dark — dark interpretation of brand greens (site has no dark mode).
    # All body-text pairs pass WCAG AA (RESEARCH Q6).
    "gbs_after_dark": {
        "Window": "#0a1a0d",
        "WindowText": "#D8E9D6",
        "Base": "#102014",
        "AlternateBase": "#1a2c1f",
        "Text": "#D8E9D6",
        "Button": "#1f4a2a",
        "ButtonText": "#D8E9D6",
        "Highlight": "#5AB253",
        "HighlightedText": "#FFFFFF",
        "Link": "#A1D29D",
        "ToolTipBase": "#d5e8d3",
        "ToolTipText": "#0a1a0d",
    },

    # Dark — neutral utility. Highlight = ACCENT_COLOR_DEFAULT per D-07
    # (so users without accent_color see neutral blue, with override see their accent).
    "dark": {
        "Window": "#202020",
        "WindowText": "#f0f0f0",
        "Base": "#181818",
        "AlternateBase": "#252525",
        "Text": "#f0f0f0",
        "Button": "#2d2d2d",
        "ButtonText": "#f0f0f0",
        "Highlight": ACCENT_COLOR_DEFAULT,
        "HighlightedText": "#ffffff",
        "Link": ACCENT_COLOR_DEFAULT,
        "ToolTipBase": "#181820",
        "ToolTipText": "#f0f0f0",
    },

    # Light — neutral utility. Highlight = ACCENT_COLOR_DEFAULT per D-07.
    "light": {
        "Window": "#f5f5f5",
        "WindowText": "#202020",
        "Base": "#ffffff",
        "AlternateBase": "#fafafa",
        "Text": "#202020",
        "Button": "#e8e8e8",
        "ButtonText": "#202020",
        "Highlight": ACCENT_COLOR_DEFAULT,
        "HighlightedText": "#ffffff",
        "Link": ACCENT_COLOR_DEFAULT,
        "ToolTipBase": "#2a2a32",
        "ToolTipText": "#f5f5f5",
    },
}


DISPLAY_NAMES: dict[str, str] = {
    "system": "System default",
    "vaporwave": "Vaporwave",
    "overrun": "Overrun",
    "gbs": "GBS.FM",
    "gbs_after_dark": "GBS.FM After Dark",
    "dark": "Dark",
    "light": "Light",
    "custom": "Custom",
}


DISPLAY_ORDER: tuple[str, ...] = (
    "system",
    "vaporwave",
    "overrun",
    "gbs",
    "gbs_after_dark",
    "dark",
    "light",
    "custom",
)


EDITABLE_ROLES: tuple[str, ...] = (
    "Window",
    "WindowText",
    "Base",
    "AlternateBase",
    "Text",
    "Button",
    "ButtonText",
    "HighlightedText",
    "Link",
    "ToolTipBase",
    "ToolTipText",
)


def build_palette_from_dict(role_hex: dict[str, str]) -> "QPalette":
    """Construct a fresh QPalette with the given {role_name: hex} mapping.

    Defense-in-depth (RESEARCH Pitfall 3):
    - _is_valid_hex guards every hex value before QColor()
    - Unknown role_name (typo, tampered JSON) silently skipped via getattr default

    Roles missing from the dict use Qt defaults for that role. No exceptions raised
    on malformed input — this is the consumption boundary for theme_custom JSON.
    """
    from PySide6.QtGui import QColor, QPalette
    palette = QPalette()
    for role_name, hex_value in role_hex.items():
        if not isinstance(hex_value, str) or not _is_valid_hex(hex_value):
            continue  # silently skip — falls back to Qt default for that role
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is None:
            continue  # silently skip unknown role names (RESEARCH Pitfall 4)
        palette.setColor(role, QColor(hex_value))
    return palette


def apply_theme_palette(app: "QApplication", repo) -> None:
    """Read theme setting and apply the corresponding palette to app.

    Called from __main__._run_gui after QApplication construction and BEFORE
    MainWindow construction. The existing accent_color restore in
    main_window.py:241-245 then layers on top of this baseline.

    Branches:
    - theme=='system' on Linux: no-op (preserve Qt default)
    - theme=='system' on Windows: app.setStyle("Fusion") + _apply_windows_palette
    - theme=='custom': load theme_custom JSON (defense-in-depth) → setPalette
    - other preset name: build_palette_from_dict(THEME_PRESETS[name]) → setPalette
    - unknown name: falls through to empty dict → default Qt palette (no exception)

    On Windows, non-system themes also call app.setStyle("Fusion") first so the
    custom palette renders consistently (RESEARCH Q2).
    """
    theme_name = repo.get_setting("theme", "system")
    app.setProperty("theme_name", theme_name)

    if theme_name == "system":
        if sys.platform == "win32":
            # Lazy-import to avoid circular __main__ → theme → __main__ chain
            from musicstreamer.__main__ import _apply_windows_palette
            app.setStyle("Fusion")
            _apply_windows_palette(app)
        return  # Linux/macOS: no-op, leave Qt default

    if theme_name == "custom":
        raw = repo.get_setting("theme_custom", "")
        try:
            role_hex = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            role_hex = {}  # Defense: corrupt JSON → empty dict → default palette
        if not isinstance(role_hex, dict):
            role_hex = {}  # Defense: non-dict JSON (list, scalar) → empty dict
    else:
        role_hex = THEME_PRESETS.get(theme_name, {})  # Unknown name → empty dict

    if sys.platform == "win32":
        app.setStyle("Fusion")  # Cross-platform palette consistency on Windows

    palette = build_palette_from_dict(role_hex)
    app.setPalette(palette)
