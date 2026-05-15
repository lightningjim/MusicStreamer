"""ToastOverlay — frameless non-interactive notification widget for Phase 37.

UI-12: used for failover, connecting, and error messages on all play paths.
Lifetime: parent-owned (NO WA_DeleteOnClose) — same instance is reused for every
toast. See QA-05 (Pitfall §6) and RESEARCH.md Anti-Patterns.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ToastOverlay(QWidget):
    _MIN_WIDTH = 240
    _MAX_WIDTH = 480
    _SIDE_PADDING = 64        # subtracted from parent width to compute clamp
    _BOTTOM_OFFSET = 32       # px above parent bottom edge

    _FADE_IN_MS = 150
    _FADE_OUT_MS = 300

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # Lifetime + interaction attributes (D-09, D-10, Anti-Patterns)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Explicit: do NOT set WA_DeleteOnClose — parent ownership only.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(self)
        self.label.setObjectName("ToastLabel")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Palette-driven QSS — UI-SPEC §Color (Phase 75). System-theme branch
        # preserves the legacy hardcoded QSS verbatim per D-09 / UI-SPEC
        # IMMUTABLE QSS LOCK.
        self._rebuild_stylesheet()

        # Opacity effect — windowOpacity only works on top-level windows;
        # as a child widget we use QGraphicsOpacityEffect instead.
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        # Animations — pass `self` as third arg so Qt parent-owns them and they
        # are not GC'd mid-flight (Pitfall §6).
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_in.setDuration(self._FADE_IN_MS)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_out.setDuration(self._FADE_OUT_MS)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.hide)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._fade_out.start)

        self.hide()
        parent.installEventFilter(self)

    # --- Public API ---

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        # Re-show during fade-out: stop the fade-out cleanly so we don't flicker.
        if self._fade_out.state() == QAbstractAnimation.Running:
            self._fade_out.stop()
        self._hold_timer.stop()
        self.label.setText(text)
        self.adjustSize()
        self._reposition()
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()
        self._fade_in.start()
        self._hold_timer.start(duration_ms)

    # --- Internal ---

    def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
        # NB: PaletteChange ONLY — setStyleSheet() re-fires StyleChange (RESEARCH Risk 1).
        if event.type() == QEvent.PaletteChange:
            self._rebuild_stylesheet()
        super().changeEvent(event)

    def _rebuild_stylesheet(self) -> None:
        """Apply the toast QSS for the active theme.

        theme='system' (or property unset/None) → IMMUTABLE legacy QSS
        (rgba(40, 40, 40, 220) + white) per UI-SPEC §Color §System-theme legacy
        fallback / Phase 75 D-09.

        Non-system themes → palette-driven QSS interpolating ToolTipBase rgb
        (alpha 220 verbatim integer) and ToolTipText.name() (lowercase #rrggbb).

        Read lazily from QApplication.property("theme_name") at every call —
        the picker live-preview mutates the property mid-session, so caching
        would freeze the toast (RESEARCH §Pattern 2 / §4).
        """
        app = QApplication.instance()
        theme_name = app.property("theme_name") if app is not None else None
        if not theme_name or theme_name == "system":
            # IMMUTABLE QSS LOCK (D-09 / UI-SPEC §Color lines 96-103). Do not edit
            # the substring `rgba(40, 40, 40, 220)` or `color: white`.
            self.setStyleSheet(
                "QLabel#ToastLabel {"
                " background-color: rgba(40, 40, 40, 220);"
                " color: white;"
                " border-radius: 8px;"
                " padding: 8px 12px;"
                "}"
            )
            return
        pal = self.palette()
        bg = pal.color(QPalette.ToolTipBase)
        fg = pal.color(QPalette.ToolTipText).name()
        self.setStyleSheet(
            "QLabel#ToastLabel {"
            f" background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 220);"
            f" color: {fg};"
            " border-radius: 8px;"
            " padding: 8px 12px;"
            "}"
        )

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        hint = self.sizeHint().width()
        max_w = min(parent.width() - self._SIDE_PADDING, self._MAX_WIDTH)
        width = max(self._MIN_WIDTH, min(max_w, hint))
        self.setFixedWidth(width)
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - self._BOTTOM_OFFSET
        self.move(x, y)
