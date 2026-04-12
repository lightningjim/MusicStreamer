"""Phase 36 plan 04 — QA-01 scaffold smoke test.

Proves the Qt harness actually renders MainWindow under QT_QPA_PLATFORM=offscreen
and that the bundled .qrc icon resource loads (PORT-08 fallback verification).
"""
from unittest.mock import MagicMock

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QMenuBar, QStatusBar, QWidget

from musicstreamer.ui_qt import icons_rc  # noqa: F401  — ensure resources registered
from musicstreamer.ui_qt.main_window import MainWindow


class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    elapsed_updated = Signal(int)

    def set_volume(self, v): pass
    def play(self, station): pass
    def pause(self): pass
    def stop(self): pass


class _FakeRepo:
    def list_stations(self): return []
    def list_recently_played(self, n=3): return []
    def get_setting(self, key, default=None): return default
    def set_setting(self, key, value): pass


def _make_window():
    return MainWindow(_FakePlayer(), _FakeRepo())


def test_main_window_constructs_and_renders(qtbot):
    window = _make_window()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.windowTitle() == "MusicStreamer"
    assert isinstance(window, QMainWindow)
    assert isinstance(window.menuBar(), QMenuBar)
    assert isinstance(window.centralWidget(), QWidget)
    assert isinstance(window.statusBar(), QStatusBar)


def test_bundled_app_icon_loads(qtbot):
    icon = QIcon(":/icons/app-icon.svg")
    assert icon.isNull() is False


def test_bundled_open_menu_icon_loads(qtbot):
    icon = QIcon(":/icons/open-menu-symbolic.svg")
    assert icon.isNull() is False


def test_fromtheme_fallback_uses_bundled_svg(qtbot):
    # PORT-08: On a Linux CI without the synthetic theme name, fromTheme
    # should return the bundled fallback SVG (non-null).
    icon = QIcon.fromTheme(
        "musicstreamer-nonexistent-theme-name-xyz",
        QIcon(":/icons/app-icon.svg"),
    )
    assert icon.isNull() is False


def test_main_window_default_geometry(qtbot):
    window = _make_window()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    # Loose bounds — offscreen platform may clamp; exact 1200x800 is aspirational
    assert window.width() >= 800
    assert window.height() >= 600
