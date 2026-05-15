"""Phase 66 / THEME-01: tests for ThemeEditorDialog 9-role custom palette editor.

Wave 0 RED stubs — fail with ImportError until Task 2 lands theme_editor_dialog.py.
Mirrors tests/test_accent_color_dialog.py shape (Phase 59 idiom).

QColorDialog.getColor is monkeypatched per test so the modal never actually opens.
"""
from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QColorDialog, QDialog

from musicstreamer.theme import EDITABLE_ROLES, THEME_PRESETS
from musicstreamer.ui_qt.theme_editor_dialog import ROLE_LABELS, ThemeEditorDialog


# ---------------------------------------------------------------------------
# FakeRepo (verbatim from tests/test_accent_color_dialog.py)
# ---------------------------------------------------------------------------

class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


# ---------------------------------------------------------------------------
# _FakePicker — stub mimicking ThemePickerDialog's three flag attributes (Plan 02)
# ---------------------------------------------------------------------------

class _FakePicker:
    """Stub mimicking ThemePickerDialog's three flag attributes (Plan 02).

    Used by test_save_sets_parent_flag to verify the cross-dialog mutation
    contract WITHOUT importing the real ThemePickerDialog (keeps this test file
    independent of Plan 02 — UI-SPEC §Modal stacking Pitfall 1).
    """

    def __init__(self):
        self._save_committed = False
        self._active_tile_id = "vaporwave"
        self._selected_theme_id = "vaporwave"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def dialog(qtbot, repo):
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def stub_color_dialog(monkeypatch):
    """Returns a setter so tests can choose what QColorDialog.getColor returns."""
    chosen_holder = {"color": QColor("#abcdef")}

    def _stub(*args, **kwargs):
        return chosen_holder["color"]

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(_stub))
    return chosen_holder


# ---------------------------------------------------------------------------
# Tests — UI-SPEC §State Machine + §Pre-population on open + D-08..D-14
# ---------------------------------------------------------------------------

def test_editor_shows_11_color_rows(dialog):
    """dlg._rows has exactly 11 keys matching EDITABLE_ROLES (Phase 75 D-05)."""
    assert set(dialog._rows.keys()) == set(EDITABLE_ROLES)
    assert len(dialog._rows) == 11
    assert "Highlight" not in dialog._rows
    assert "ToolTipBase" in dialog._rows
    assert "ToolTipText" in dialog._rows


def test_role_labels_include_toast_pair():
    """UI-SPEC §Copywriting Contract — locked Toast labels for new rows."""
    assert ROLE_LABELS["ToolTipBase"] == "Toast background"
    assert ROLE_LABELS["ToolTipText"] == "Toast text"


def test_editor_prefills_from_source_preset(dialog):
    """Open with source_preset='vaporwave'; Window prefilled to #efe5ff (Plan 01)."""
    assert dialog._role_hex_dict["Window"] == THEME_PRESETS["vaporwave"]["Window"]
    assert dialog._role_hex_dict["Window"] == "#efe5ff"


def test_editor_prefills_from_system_uses_qt_default(qtbot, repo):
    """Open with source_preset='system'; every editable role has a valid hex."""
    from musicstreamer.accent_utils import _is_valid_hex
    dlg = ThemeEditorDialog(repo, source_preset="system")
    qtbot.addWidget(dlg)
    for role in EDITABLE_ROLES:
        assert role in dlg._role_hex_dict
        assert _is_valid_hex(dlg._role_hex_dict[role]), (
            f"system source_preset must produce valid hex per role; "
            f"got {role}={dlg._role_hex_dict[role]!r}"
        )


def test_editor_prefills_from_custom_uses_saved_json(qtbot, repo):
    """Open with source_preset='custom'; reads theme_custom JSON from repo."""
    repo.set_setting(
        "theme_custom",
        json.dumps({"Window": "#abcdef", "Base": "#fedcba"}),
    )
    dlg = ThemeEditorDialog(repo, source_preset="custom")
    qtbot.addWidget(dlg)
    assert dlg._role_hex_dict["Window"] == "#abcdef"


def test_color_change_applies_palette(qtbot, repo, qapp, stub_color_dialog):
    """Click swatch → live preview applies palette role to QApplication."""
    stub_color_dialog["color"] = QColor("#abcdef")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#abcdef"


def test_color_change_re_imposes_accent(qtbot, repo, qapp, stub_color_dialog):
    """After per-row color change, accent_color override is re-imposed (Pitfall 2)."""
    repo.set_setting("accent_color", "#e62d42")
    stub_color_dialog["color"] = QColor("#abcdef")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name().lower() == "#e62d42"


def test_reset_reverts_to_source_preset(qtbot, repo, qapp, stub_color_dialog):
    """Reset reverts all 9 rows to source preset; Highlight is NOT mutated (D-08 invariant)."""
    # Set an accent so Highlight has a non-default value to preserve.
    repo.set_setting("accent_color", "#e62d42")
    stub_color_dialog["color"] = QColor("#000000")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    # Mutate Window to black via stubbed QColorDialog.
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#000000"

    # D-08 invariant: Highlight is owned by accent layering path, NOT theme editor.
    # Reset must not mutate Highlight even though all 9 editable roles revert.
    highlight_before_reset = qapp.palette().color(QPalette.ColorRole.Highlight)
    dlg._on_reset()
    highlight_after_reset = qapp.palette().color(QPalette.ColorRole.Highlight)
    assert highlight_after_reset == highlight_before_reset, (
        f"Reset must not mutate Highlight (D-08): "
        f"{highlight_before_reset.name()} → {highlight_after_reset.name()}"
    )

    # Roles 1-9 reverted to vaporwave preset.
    assert dlg._role_hex_dict["Window"] == "#efe5ff"
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#efe5ff"


def test_reset_restores_toast_rows_to_source_preset(qtbot, repo, qapp, stub_color_dialog):
    """Phase 75 D-14: Reset reverts ToolTipBase + ToolTipText to source-preset hex (vaporwave UI-SPEC LOCKED)."""
    stub_color_dialog["color"] = QColor("#000000")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    # Mutate both new rows to black via stubbed QColorDialog.
    qtbot.mouseClick(dlg._rows["ToolTipBase"]._swatch_btn, Qt.LeftButton)
    qtbot.mouseClick(dlg._rows["ToolTipText"]._swatch_btn, Qt.LeftButton)
    assert dlg._role_hex_dict["ToolTipBase"] == "#000000"
    assert dlg._role_hex_dict["ToolTipText"] == "#000000"

    dlg._on_reset()

    # UI-SPEC vaporwave LOCKED pair restored.
    assert dlg._role_hex_dict["ToolTipBase"] == "#f9d6f0"
    assert dlg._role_hex_dict["ToolTipText"] == "#3a2845"


def test_reset_does_not_close_dialog(dialog):
    """Reset does NOT call accept() / reject(); dialog stays open (D-14 / Phase 59 idiom)."""
    dialog._on_reset()
    assert dialog.result() == 0  # 0 = not finished


def test_save_persists_theme_custom_json(qtbot, repo, qapp, stub_color_dialog):
    """Save persists theme_custom JSON with all 9 EDITABLE_ROLES; Window contains user edit."""
    stub_color_dialog["color"] = QColor("#abcdef")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    dlg._on_save()
    saved = json.loads(repo.get_setting("theme_custom", ""))
    assert saved["Window"] == "#abcdef"
    for role in EDITABLE_ROLES:
        assert role in saved


def test_save_persists_toast_keys_when_user_edits_them(qtbot, repo, qapp, stub_color_dialog):
    """Phase 75 D-14: editing the ToolTipBase row → Save → JSON contains the new hex."""
    stub_color_dialog["color"] = QColor("#abc123")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["ToolTipBase"]._swatch_btn, Qt.LeftButton)
    dlg._on_save()
    saved = json.loads(repo.get_setting("theme_custom", ""))
    assert saved["ToolTipBase"] == "#abc123"


def test_save_sets_theme_to_custom(dialog, repo):
    """Save sets repo theme='custom' (D-13)."""
    dialog._on_save()
    assert repo.get_setting("theme", "") == "custom"


def test_save_closes_dialog_with_accept(dialog):
    """Save closes dialog with QDialog.Accepted result code."""
    dialog._on_save()
    assert dialog.result() == QDialog.Accepted


def test_save_sets_parent_flag(qtbot, repo):
    """Editor's _on_save mutates parent picker's three flags (Pitfall 1).

    Uses _FakePicker stub (NOT real ThemePickerDialog) to keep this test
    independent of Plan 02's full implementation.
    """
    parent = _FakePicker()
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave", parent=parent)
    qtbot.addWidget(dlg)
    dlg._on_save()
    assert parent._save_committed is True
    assert parent._active_tile_id == "custom"
    assert parent._selected_theme_id == "custom"


def test_cancel_restores_snapshot(qtbot, repo, qapp):
    """reject() restores the snapshot palette captured at editor open (RESEARCH Q10)."""
    # Snapshot Window BEFORE constructing the editor.
    original_window = qapp.palette().color(QPalette.ColorRole.Window)
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    # Editor opening with source_preset='vaporwave' immediately previews vaporwave?
    # Actually D-12 says editor snapshots on open; per UI-SPEC the preview happens
    # only after a row edit. The snapshot is what's restored — test that.
    # Mutate Window to black via _on_role_color_changed (no need for QColorDialog stub).
    dlg._on_role_color_changed("Window", "#000000")
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#000000"

    dlg.reject()

    assert qapp.palette().color(QPalette.ColorRole.Window) == original_window


def test_cancel_restores_toast_roles_in_palette(qtbot, repo, qapp):
    """Phase 75 D-14 + Phase 66 D-12: reject() snapshot-restore covers new ToolTipBase role in QApplication.palette()."""
    # Snapshot ToolTipBase BEFORE constructing the editor.
    original_bg = qapp.palette().color(QPalette.ColorRole.ToolTipBase)
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    # Mutate ToolTipBase to black via the slot directly (bypass stubbed dialog).
    dlg._on_role_color_changed("ToolTipBase", "#000000")
    assert qapp.palette().color(QPalette.ColorRole.ToolTipBase).name().lower() == "#000000"

    dlg.reject()

    assert qapp.palette().color(QPalette.ColorRole.ToolTipBase) == original_bg


def test_cancel_does_not_persist_theme_custom(qtbot, repo, qapp, stub_color_dialog):
    """Cancel does NOT persist theme_custom (theme_custom remains UNSET-MARKER)."""
    stub_color_dialog["color"] = QColor("#abcdef")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    dlg.reject()
    assert repo.get_setting("theme_custom", "UNSET") == "UNSET"
