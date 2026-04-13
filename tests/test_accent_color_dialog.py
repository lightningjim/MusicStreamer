"""Tests for AccentColorDialog (Phase 40-01).

Uses pytest-qt qtbot fixture. FakeRepo is used instead of real SQLite to
keep tests fast and hermetic.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton

from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog
from musicstreamer.constants import ACCENT_PRESETS


# ---------------------------------------------------------------------------
# FakeRepo
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
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    return dlg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dialog_has_8_swatches(dialog):
    """Swatch list has exactly 8 QPushButton instances."""
    assert len(dialog._swatches) == 8
    for swatch in dialog._swatches:
        assert isinstance(swatch, QPushButton)


def test_swatch_populates_hex_entry(qtbot, dialog):
    """Clicking a swatch populates the hex entry with the matching preset."""
    for idx, preset_hex in enumerate(ACCENT_PRESETS):
        dialog._on_swatch_clicked(idx)
        assert dialog._hex_edit.text() == preset_hex


def test_apply_saves_setting(qtbot, dialog, repo):
    """Clicking Apply after selecting a swatch saves accent_color to repo."""
    dialog._on_swatch_clicked(0)  # select Blue preset
    dialog._on_apply()
    assert repo.get_setting("accent_color", "") == ACCENT_PRESETS[0]


def test_reset_clears_setting(qtbot, dialog, repo):
    """After Reset, accent_color setting is empty string."""
    repo.set_setting("accent_color", ACCENT_PRESETS[2])
    dialog._on_swatch_clicked(2)
    dialog._on_reset()
    assert repo.get_setting("accent_color", "UNSET") == ""


def test_hex_entry_validation_no_crash(qtbot, dialog):
    """Entering an invalid hex does not crash the dialog."""
    dialog._hex_edit.setText("zzz")  # invalid
    # No exception raised — red border styling applied
    assert "c0392b" in dialog._hex_edit.styleSheet()


def test_hex_entry_valid_clears_error_style(qtbot, dialog):
    """After entering an invalid hex, entering a valid one clears the error style."""
    dialog._hex_edit.setText("zzz")
    dialog._hex_edit.setText("#3584e4")
    assert "c0392b" not in dialog._hex_edit.styleSheet()


def test_cancel_does_not_save(qtbot, dialog, repo):
    """Cancel restores palette without saving to repo."""
    dialog._on_swatch_clicked(3)
    # Don't call _on_apply — call reject instead
    dialog.reject()
    assert repo.get_setting("accent_color", "UNSET") == "UNSET"


def test_load_saved_accent_selects_swatch(qtbot, repo):
    """Dialog pre-selects matching swatch when accent_color is saved."""
    repo.set_setting("accent_color", ACCENT_PRESETS[4])  # Orange
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._selected_idx == 4
    assert dlg._hex_edit.text() == ACCENT_PRESETS[4]
