"""Phase 36 plan 04 — PORT-07 Windows Fusion palette code-path test.

The ``_apply_windows_palette`` helper is exercised directly under offscreen Qt.
We mock ``QGuiApplication.styleHints().colorScheme()`` to drive the Dark vs Light
branches without needing a real Windows VM. ``_apply_windows_palette`` imports
``QGuiApplication`` at function scope (see ``musicstreamer/__main__.py``), so we
patch ``PySide6.QtGui.QGuiApplication.styleHints`` directly rather than a name
on ``musicstreamer.__main__``.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from musicstreamer.__main__ import _apply_windows_palette


def _mock_style_hints(scheme):
    hints = MagicMock()
    hints.colorScheme.return_value = scheme
    return hints


@pytest.fixture
def restore_palette(qapp):
    """Snapshot and restore the QApplication palette around the test so the
    dark-palette mutation doesn't bleed into sibling tests."""
    original = QPalette(qapp.palette())
    yield qapp
    qapp.setPalette(original)


def test_apply_windows_palette_dark(restore_palette):
    qapp = restore_palette
    with patch(
        "PySide6.QtGui.QGuiApplication.styleHints",
        return_value=_mock_style_hints(Qt.ColorScheme.Dark),
    ):
        _apply_windows_palette(qapp)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert window_color == QColor(53, 53, 53)


def test_apply_windows_palette_light_noop(restore_palette):
    qapp = restore_palette
    pre = qapp.palette().color(QPalette.ColorRole.Window)
    with patch(
        "PySide6.QtGui.QGuiApplication.styleHints",
        return_value=_mock_style_hints(Qt.ColorScheme.Light),
    ):
        _apply_windows_palette(qapp)
    post = qapp.palette().color(QPalette.ColorRole.Window)
    # Early return on Light — unchanged
    assert post == pre


def test_apply_windows_palette_unknown_scheme_noop(restore_palette):
    qapp = restore_palette
    pre = qapp.palette().color(QPalette.ColorRole.Window)
    with patch(
        "PySide6.QtGui.QGuiApplication.styleHints",
        return_value=_mock_style_hints(Qt.ColorScheme.Unknown),
    ):
        _apply_windows_palette(qapp)
    post = qapp.palette().color(QPalette.ColorRole.Window)
    assert post == pre
