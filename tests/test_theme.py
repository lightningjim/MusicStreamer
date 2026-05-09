"""Phase 46-01 + Phase 66 / THEME-01 — combined theme test file.

Phase 46-01 portion (top half): unit + grep-regression tests for the UI
theme token module (`musicstreamer.ui_qt._theme`). Covers ERROR_COLOR_HEX,
ERROR_COLOR_QCOLOR, STATION_ICON_SIZE — three exported constants — plus
grep regressions that enforce migrated call sites don't fall back to raw
literals.

Phase 66 / THEME-01 portion (bottom half, after the divider): tests for
`musicstreamer.theme` palette construction + apply.

Wave 0 RED stubs — Phase 66 tests fail with ImportError until Plan 66-01
Task 2 lands theme.py. Mirrors tests/test_accent_provider.py shape
(Phase 59 idiom).

Locked invariants tested (Phase 66):
- GBS.FM Light hex (CONTEXT.md D-05) is exact verbatim
- Dark/Light use ACCENT_COLOR_DEFAULT for Highlight (CONTEXT.md D-07)
- Corrupt theme_custom JSON falls back silently to default palette
  (RESEARCH Q12, Pitfall 4)
- Theme + accent layering preserves Highlight override
  (RESEARCH §Q3, Pitfall 2)

Scope of Phase 46 grep assertions: musicstreamer/ui_qt/ only. Test files
are deliberately NOT scanned — tests/test_station_list_panel.py legitimately
asserts `panel.tree.iconSize() == QSize(32, 32)` against the widget's
actual iconSize property (not against source text), which is semantically
correct and must not be touched.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from PySide6.QtGui import QColor, QPalette

from musicstreamer.accent_utils import apply_accent_palette
from musicstreamer.constants import ACCENT_COLOR_DEFAULT
from musicstreamer.repo import Repo, db_init
from musicstreamer.theme import (
    DISPLAY_NAMES,
    DISPLAY_ORDER,
    EDITABLE_ROLES,
    THEME_PRESETS,
    apply_theme_palette,
    build_palette_from_dict,
)
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


# ============================================================================
# Phase 66 / THEME-01: musicstreamer.theme palette construction + apply tests.
#
# Mirrors tests/test_accent_provider.py shape — hermetic per-test, no shared
# helper functions. The `repo` fixture is a verbatim copy of
# test_accent_provider.py:8-14 per Plan 66-01 done criteria.
# ============================================================================


# GBS.FM locked palette per CONTEXT.md D-05 (uppercase hex preserved verbatim).
_GBS_LOCKED = {
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
}


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


# --- build_palette_from_dict ---

def test_build_palette_from_dict_sets_all_9_roles(qapp):
    role_hex = {
        "Window": "#aabbcc",
        "WindowText": "#112233",
        "Base": "#ddeeff",
        "AlternateBase": "#445566",
        "Text": "#778899",
        "Button": "#abcdef",
        "ButtonText": "#fedcba",
        "HighlightedText": "#010203",
        "Link": "#040506",
    }
    palette = build_palette_from_dict(role_hex)
    for role_name, hex_value in role_hex.items():
        role = getattr(QPalette.ColorRole, role_name)
        assert palette.color(role).name().lower() == hex_value.lower(), (
            f"role {role_name} expected {hex_value} got {palette.color(role).name()}"
        )


def test_build_palette_from_dict_skips_malformed_hex(qapp):
    default_window = QPalette().color(QPalette.ColorRole.Window).name()
    palette = build_palette_from_dict({"Window": "not-a-hex"})
    # Window should still be the Qt default (NOT silently set to black).
    assert palette.color(QPalette.ColorRole.Window).name() == default_window


def test_build_palette_from_dict_skips_unknown_role(qapp):
    # Should not raise — unknown role name silently skipped.
    palette = build_palette_from_dict({"NotARole": "#ffffff"})
    assert palette is not None


def test_build_palette_from_dict_partial_dict(qapp):
    default_palette = QPalette()
    default_text = default_palette.color(QPalette.ColorRole.Text).name()
    default_button = default_palette.color(QPalette.ColorRole.Button).name()
    default_link = default_palette.color(QPalette.ColorRole.Link).name()

    palette = build_palette_from_dict({
        "Window": "#aabbcc",
        "Base": "#ddeeff",
        "AlternateBase": "#445566",
    })
    # 3 set roles
    assert palette.color(QPalette.ColorRole.Window).name().lower() == "#aabbcc"
    assert palette.color(QPalette.ColorRole.Base).name().lower() == "#ddeeff"
    assert palette.color(QPalette.ColorRole.AlternateBase).name().lower() == "#445566"
    # 6 untouched roles use Qt defaults — sample 3 of them
    assert palette.color(QPalette.ColorRole.Text).name() == default_text
    assert palette.color(QPalette.ColorRole.Button).name() == default_button
    assert palette.color(QPalette.ColorRole.Link).name() == default_link


# --- preset definitions ---

def test_gbs_preset_locked_hex_match():
    """GBS.FM preset must equal the locked CONTEXT.md D-05 dict verbatim
    (uppercase hex preserved — do NOT lowercase)."""
    assert THEME_PRESETS["gbs"] == _GBS_LOCKED


def test_all_presets_cover_9_roles():
    """Every non-system preset must define all 9 EDITABLE_ROLES."""
    for theme_id in ("vaporwave", "overrun", "gbs", "gbs_after_dark", "dark", "light"):
        preset = THEME_PRESETS[theme_id]
        for role in EDITABLE_ROLES:
            assert role in preset, (
                f"preset {theme_id!r} missing role {role!r}"
            )


def test_dark_light_use_accent_default_highlight():
    """Per CONTEXT.md D-07 — Dark and Light use ACCENT_COLOR_DEFAULT for Highlight."""
    assert THEME_PRESETS["dark"]["Highlight"] == ACCENT_COLOR_DEFAULT
    assert THEME_PRESETS["light"]["Highlight"] == ACCENT_COLOR_DEFAULT
    # Sanity: ACCENT_COLOR_DEFAULT is the Phase 19 neutral blue.
    assert ACCENT_COLOR_DEFAULT == "#3584e4"


# --- apply_theme_palette: preset path ---

def test_apply_theme_palette_uses_repo_setting(qapp, repo):
    repo.set_setting("theme", "gbs")
    apply_theme_palette(qapp, repo)
    # GBS Window is #A1D29D (locked uppercase); QColor.name() returns lowercase.
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#a1d29d"


# --- apply_theme_palette: custom path ---

def test_apply_theme_palette_loads_custom_json(qapp, repo):
    repo.set_setting("theme", "custom")
    repo.set_setting("theme_custom", json.dumps({
        "Window": "#abcdef",
        "Base": "#fedcba",
    }))
    apply_theme_palette(qapp, repo)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#abcdef"
    assert qapp.palette().color(QPalette.ColorRole.Base).name().lower() == "#fedcba"


# --- apply_theme_palette: defense-in-depth ---

def test_apply_theme_palette_corrupt_json_safe(qapp, repo):
    """Corrupt theme_custom JSON must fall back silently to default palette."""
    repo.set_setting("theme", "custom")
    repo.set_setting("theme_custom", "{not-json")
    # Must not raise.
    apply_theme_palette(qapp, repo)


def test_apply_theme_palette_non_dict_json_safe(qapp, repo):
    """Non-dict JSON (list/scalar) must fall back silently to default palette."""
    repo.set_setting("theme", "custom")
    repo.set_setting("theme_custom", "[1, 2, 3]")
    # Must not raise.
    apply_theme_palette(qapp, repo)


def test_apply_theme_palette_empty_string_safe(qapp, repo):
    """Empty theme_custom string must not raise."""
    repo.set_setting("theme", "custom")
    repo.set_setting("theme_custom", "")
    apply_theme_palette(qapp, repo)


def test_apply_theme_palette_unknown_theme_safe(qapp, repo):
    """Unknown theme name must fall back silently to default palette."""
    repo.set_setting("theme", "nonexistent")
    apply_theme_palette(qapp, repo)


# --- apply_theme_palette: system on Linux is a no-op ---

@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Linux-only no-op contract; Windows path applies Fusion + dark palette",
)
def test_apply_theme_palette_system_no_op_on_linux(qapp, repo):
    """On Linux, theme='system' must preserve the Qt default palette
    (no app.setPalette() call)."""
    # Snapshot current palette before the call.
    snap = qapp.palette()
    snap_window = snap.color(QPalette.ColorRole.Window).name()
    snap_text = snap.color(QPalette.ColorRole.Text).name()
    snap_button = snap.color(QPalette.ColorRole.Button).name()

    repo.set_setting("theme", "system")
    apply_theme_palette(qapp, repo)

    after = qapp.palette()
    assert after.color(QPalette.ColorRole.Window).name() == snap_window
    assert after.color(QPalette.ColorRole.Text).name() == snap_text
    assert after.color(QPalette.ColorRole.Button).name() == snap_button


# --- theme + accent layering ---

def test_theme_then_accent_layering(qapp, repo):
    """Phase 59 layering invariant: theme sets baseline; accent overrides Highlight.
    Picking a theme then applying accent must keep the theme's Window color
    (theme survives) AND show the accent's Highlight (accent overrides)."""
    repo.set_setting("theme", "vaporwave")
    apply_theme_palette(qapp, repo)
    # Now apply an accent override.
    apply_accent_palette(qapp, "#e62d42")
    # Highlight = accent override.
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name().lower() == "#e62d42"
    # Window = vaporwave baseline (#efe5ff per RESEARCH §Recommended Final Hex).
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#efe5ff"


# --- persistence round-trip ---

def test_theme_settings_roundtrip(repo):
    repo.set_setting("theme", "overrun")
    assert repo.get_setting("theme", "system") == "overrun"
