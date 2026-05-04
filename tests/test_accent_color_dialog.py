"""Phase 59-01: AccentColorDialog tests for the QColorDialog-based rewrite.

TDD-RED state: these tests target self._inner / self._current_hex which Plan 02
will introduce. Wave 0 commits these tests with all FAILING — that is the point.

Uses pytest-qt qtbot fixture. FakeRepo is used instead of real SQLite for
hermetic, fast tests. The QSS-write test uses tmp_path via paths._root_override.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QColorDialog

from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog


# ---------------------------------------------------------------------------
# FakeRepo (preserved verbatim from the Phase 40 test file)
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


@pytest.fixture
def _accent_root(tmp_path, monkeypatch):
    """Redirect paths.accent_css_path() under tmp_path for write-side tests."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Tests — VALIDATION.md T-59-A..T-59-H + Pitfall 3 defensive + structural lock
# ---------------------------------------------------------------------------

# T-59-A
def test_dialog_seeds_custom_colors_from_presets(qtbot, repo):
    """Custom Colors slots 0..7 == ACCENT_PRESETS after dialog construction.

    Per D-03 + Pitfall 1: seeding happens in __init__ BEFORE inner construction.
    QColorDialog.setCustomColor is process-static — neutralize inter-test
    pollution by resetting slots 0..7 to a sentinel (#ffffff) BEFORE constructing
    the dialog so we are asserting that the dialog itself seeded the slots.
    """
    # Neutralize process-static state to make this test order-independent.
    for idx in range(8):
        QColorDialog.setCustomColor(idx, QColor("#ffffff"))

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    for idx in range(8):
        assert (
            QColorDialog.customColor(idx).name() == ACCENT_PRESETS[idx].lower()
        ), (
            f"Custom color slot {idx} should equal ACCENT_PRESETS[{idx}] "
            f"({ACCENT_PRESETS[idx].lower()}) after AccentColorDialog construction"
        )


# T-59-B (subsumes T-59-C — QColorDialog's hex field is exercised at the
# setCurrentColor API level, which is what the user-visible hex field calls).
def test_setting_color_emits_signal_and_applies_palette(qtbot, dialog, qapp):
    """setCurrentColor → currentColorChanged → live preview applies to palette.

    Pitfall 2: setCurrentColor to the SAME color is a no-op (no emission).
    Use ACCENT_PRESETS[2] (#3a944a, Green) which is DIFFERENT from the initial
    blue ACCENT_COLOR_DEFAULT so the signal definitely fires.
    """
    target = QColor(ACCENT_PRESETS[2])  # "#3a944a" (Green) — different from initial

    with qtbot.waitSignal(
        dialog._inner.currentColorChanged,
        timeout=1000,
        check_params_cb=lambda c: c.name() == ACCENT_PRESETS[2].lower(),
    ):
        dialog._inner.setCurrentColor(target)

    assert dialog._current_hex == ACCENT_PRESETS[2].lower()
    assert (
        qapp.palette().color(QPalette.ColorRole.Highlight).name()
        == ACCENT_PRESETS[2].lower()
    )


# T-59-D
def test_apply_persists_to_repo_and_writes_qss(qtbot, dialog, repo, _accent_root):
    """Apply: repo.set_setting('accent_color', hex) AND accent.css written."""
    from musicstreamer import paths

    dialog._inner.setCurrentColor(QColor("#9141ac"))  # Purple — preset 6
    dialog._on_apply()

    assert repo.get_setting("accent_color", "") == "#9141ac"
    assert os.path.isfile(paths.accent_css_path()), (
        f"accent.css should have been written to {paths.accent_css_path()}"
    )


# T-59-E
def test_cancel_restores_palette_and_does_not_save(qtbot, repo, qapp):
    """reject() restores snapshot palette AND repo is NOT mutated."""
    # Snapshot the highlight BEFORE constructing the dialog so we have a clean
    # baseline to assert restoration against.
    original_highlight = qapp.palette().color(QPalette.ColorRole.Highlight)

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    # Pick a color guaranteed different from any prior state — Red (#e62d42).
    dlg._inner.setCurrentColor(QColor("#e62d42"))
    # Sanity: the live preview should have changed the highlight away from
    # the original snapshot.
    assert (
        qapp.palette().color(QPalette.ColorRole.Highlight).name() == "#e62d42"
    )

    dlg.reject()

    # After reject, the highlight role must be restored to the pre-open snapshot.
    assert qapp.palette().color(QPalette.ColorRole.Highlight) == original_highlight
    # And repo must NOT have been mutated — sentinel survives.
    assert repo.get_setting("accent_color", "UNSET") == "UNSET"


# T-59-F
def test_reset_clears_setting_and_keeps_dialog_open(qtbot, dialog, repo):
    """Reset clears repo + zeroes _current_hex + dialog stays open."""
    repo.set_setting("accent_color", ACCENT_PRESETS[2])
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[2]))

    dialog._on_reset()

    assert repo.get_setting("accent_color", "UNSET") == ""
    assert dialog._current_hex == ""
    # Dialog stays open: neither accept() nor reject() has been called.
    # QDialog.result() == 0 means the dialog has not been finished yet.
    assert dialog.result() == 0


# T-59-G
def test_window_close_behaves_like_cancel(qtbot, dialog, repo):
    """close() (WM X button) routes through reject() — repo NOT mutated."""
    repo.set_setting("accent_color", "UNSET-MARKER")  # sentinel — Reset would zero it
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[5]))  # Red preset

    dialog.close()  # Qt routes this through reject() for modal dialogs

    # Cancel does NOT touch repo — sentinel survives.
    assert repo.get_setting("accent_color", "") == "UNSET-MARKER"


# T-59-H
def test_load_saved_accent_pre_selects_in_picker(qtbot, repo):
    """Saved accent_color hex pre-selects in the picker on dialog open."""
    repo.set_setting("accent_color", ACCENT_PRESETS[4])  # Orange (#ed5b00)

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    assert dlg._inner.currentColor().name() == ACCENT_PRESETS[4].lower()
    # Pitfall 6: _current_hex MUST be set in __init__ regardless of whether
    # the wiring is before or after setCurrentColor.
    assert dlg._current_hex == ACCENT_PRESETS[4]


# Defensive — Pitfall 3 / UI-SPEC color-flash guard (no T-59 number)
def test_corrupt_saved_hex_falls_back_to_default(qtbot, repo):
    """Corrupt saved hex MUST fall back to ACCENT_COLOR_DEFAULT.

    Pitfall 3: QColor('not-a-hex') is invalid and QColorDialog.setCurrentColor
    silently accepts it, mutating state to '#000000' AND emitting
    currentColorChanged. If the wrapper does not _is_valid_hex-guard the
    saved value before passing it to setCurrentColor, the live-preview wire
    paints the entire app accent black for one frame. The defensive fallback
    path is what prevents the black flash.
    """
    repo.set_setting("accent_color", "not-a-hex")

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    assert dlg._inner.currentColor().name() == ACCENT_COLOR_DEFAULT.lower()
    assert dlg._current_hex == ACCENT_COLOR_DEFAULT


# Structural lock — supplements T-59-B with a bound-method wiring assertion.
def test_currentColorChanged_drives_live_preview_via_bound_method(qtbot, dialog):
    """currentColorChanged → _on_color_changed → _current_hex update.

    Locks the bound-method wiring against a future refactor that drops the
    slot. Picks Purple (#9141ac) — different from initial blue so emission
    is guaranteed (Pitfall 2: setCurrentColor to the same color is a no-op).
    """
    target = QColor("#9141ac")  # Purple — different from initial blue

    with qtbot.waitSignal(dialog._inner.currentColorChanged, timeout=1000):
        dialog._inner.setCurrentColor(target)

    assert dialog._current_hex == "#9141ac"
