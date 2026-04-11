"""Phase 36 Qt MainWindow scaffold.

Per Phase 36 D-01/D-02/D-03/D-23/D-24, this is a bare-chrome QMainWindow:
structural containers (menubar, central widget, status bar) wired but empty.
All visible content (station list, now-playing, toasts, menu actions) lands
in Phase 37+.
"""
from __future__ import annotations

# Side-effect import: registers the :/icons/ resource prefix before any
# QIcon lookup. Must live at module top so tests that construct MainWindow
# (not just the GUI entry point) also get resources registered — per
# Phase 36 research Pitfall 2 and D-24.
from musicstreamer.ui_qt import icons_rc  # noqa: F401

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """Bare Qt main window — structural containers only (D-01)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # D-02: window title + default geometry. No QSettings persistence.
        self.setWindowTitle("MusicStreamer")
        self.setWindowIcon(
            QIcon.fromTheme(
                "application-x-executable",
                QIcon(":/icons/app-icon.svg"),
            )
        )
        self.resize(1200, 800)

        # D-03: menubar placeholder — one empty menu, zero QActions.
        # Phase 40 (UI-10) wires real menu actions.
        menubar: QMenuBar = self.menuBar()
        menubar.addMenu("\u2261")  # ≡ hamburger placeholder

        # D-01: central widget with empty layout — Phase 37 populates.
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(central)

        # D-01: status bar — Phase 37 adds the toast overlay (UI-12).
        self.setStatusBar(QStatusBar(self))
