"""Phase 66 / THEME-01: tests for ThemePickerDialog tile-grid picker.

Wave 0 RED stubs — fail with ImportError until Task 2 lands theme_picker_dialog.py.
Mirrors tests/test_accent_color_dialog.py shape (Phase 59 idiom).
"""
from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog

from musicstreamer.theme import THEME_PRESETS  # noqa: F401 — locks plan-01 contract
from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog


# ---------------------------------------------------------------------------
# FakeRepo (verbatim copy from tests/test_accent_color_dialog.py:25-33)
# ---------------------------------------------------------------------------

class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def dialog(qtbot, repo):
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    return dlg


# ---------------------------------------------------------------------------
# Tests — 13 covering tile-grid + click + accent + Apply + Cancel + Customize
# ---------------------------------------------------------------------------

def test_dialog_shows_8_tiles(qtbot, repo):
    """All 8 entries in DISPLAY_ORDER are rendered as tiles."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    expected = {"system", "vaporwave", "overrun", "gbs",
                "gbs_after_dark", "dark", "light", "custom"}
    assert set(dlg._tiles.keys()) == expected


def test_active_tile_has_active_state(qtbot, repo):
    """Saved theme is reflected by _active_tile_id and tile._is_active."""
    repo.set_setting("theme", "vaporwave")
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._active_tile_id == "vaporwave"
    assert dlg._tiles["vaporwave"]._is_active is True
    # Other tiles are NOT active.
    assert dlg._tiles["overrun"]._is_active is False
    assert dlg._tiles["system"]._is_active is False


def test_tile_click_applies_palette(qtbot, repo, qapp):
    """Click vaporwave tile → live preview applies #efe5ff Window."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#efe5ff"


def test_tile_click_preserves_accent_setting(qtbot, repo):
    """Picker NEVER mutates accent_color setting (T-66-07)."""
    repo.set_setting("accent_color", "#e62d42")
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["overrun"], Qt.LeftButton)
    assert repo.get_setting("accent_color", "UNSET") == "#e62d42"


def test_tile_click_reapplies_accent_override(qtbot, repo, qapp):
    """After tile click, accent_color overrides theme's Highlight baseline (D-02)."""
    repo.set_setting("accent_color", "#e62d42")
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    # vaporwave's Highlight baseline is #ff77ff but accent override beats it.
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name().lower() == "#e62d42"


def test_apply_persists_theme(qtbot, repo):
    """Apply persists `theme` setting and accepts the dialog."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    dlg._on_apply()
    assert repo.get_setting("theme", "") == "vaporwave"
    assert dlg.result() == QDialog.Accepted


def test_cancel_restores_snapshot_palette(qtbot, repo, qapp):
    """reject() restores snapshot palette AND repo is NOT mutated."""
    original_window = qapp.palette().color(QPalette.ColorRole.Window).name()
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["overrun"], Qt.LeftButton)
    # Live preview mutated the palette.
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#0a0408"
    dlg.reject()
    # Snapshot is restored.
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == original_window
    assert repo.get_setting("theme", "UNSET") == "UNSET"


def test_cancel_does_not_persist_theme(qtbot, repo):
    """Cancel without Apply leaves repo `theme` setting unset."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["overrun"], Qt.LeftButton)
    dlg.reject()
    assert repo.get_setting("theme", "UNSET") == "UNSET"


def test_wm_close_behaves_like_cancel(qtbot, repo, qapp):
    """close() (WM X) routes through reject() — palette restored, repo NOT mutated."""
    original_window = qapp.palette().color(QPalette.ColorRole.Window).name()
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["overrun"], Qt.LeftButton)
    dlg.close()
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == original_window
    assert repo.get_setting("theme", "UNSET") == "UNSET"


def test_empty_custom_tile_disabled(qtbot, repo):
    """Empty theme_custom → Custom tile is disabled."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._tiles["custom"].isEnabled() is False


def test_corrupt_theme_custom_disables_tile(qtbot, repo):
    """Corrupt JSON in theme_custom → Custom tile disabled (T-66-06)."""
    repo.set_setting("theme_custom", "{not-json")
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._tiles["custom"].isEnabled() is False


def test_populated_custom_tile_enabled(qtbot, repo):
    """Valid theme_custom JSON dict → Custom tile enabled."""
    repo.set_setting(
        "theme_custom",
        json.dumps({"Window": "#abcdef", "Base": "#fedcba"}),
    )
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._tiles["custom"].isEnabled() is True


def test_customize_button_opens_editor(qtbot, repo, monkeypatch):
    """Customize… opens ThemeEditorDialog with source_preset = current selection (D-18)."""
    captured = {}

    class RecorderEditor:
        def __init__(self, repo_arg, source_preset, parent=None):
            captured["repo"] = repo_arg
            captured["source_preset"] = source_preset
            captured["parent"] = parent

        def exec(self):
            return 0  # rejected

    # Patch the lazy-import target that _on_customize uses.
    monkeypatch.setattr(
        "musicstreamer.ui_qt.theme_editor_dialog.ThemeEditorDialog",
        RecorderEditor,
        raising=False,
    )
    # Also patch any direct reference in the picker module if implementation
    # ever inlines the import differently.
    import musicstreamer.ui_qt.theme_picker_dialog as picker_module
    if hasattr(picker_module, "ThemeEditorDialog"):
        monkeypatch.setattr(picker_module, "ThemeEditorDialog", RecorderEditor)

    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    dlg._on_customize()
    assert captured["source_preset"] == "vaporwave"
    assert captured["parent"] is dlg
