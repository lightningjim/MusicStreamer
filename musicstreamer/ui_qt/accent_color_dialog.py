"""Phase 59: AccentColorDialog — wrapper around QColorDialog (HSV wheel + eyedropper).

Replaces the Phase 19/40 swatch-grid + hex-edit dialog with a wrapper QDialog
hosting an embedded QColorDialog (NoButtons | DontUseNativeDialog). The 8 preset
hex values from ACCENT_PRESETS are seeded into QColorDialog's Custom Colors row
(slots 0..7) on every dialog open.

Public surface preserved (D-08):
    AccentColorDialog(repo, parent=None).exec()

Security: hex input validated by _is_valid_hex before QSS injection (T-40-02).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
)

from musicstreamer import paths
from musicstreamer.accent_utils import (
    _is_valid_hex,
    apply_accent_palette,
    build_accent_qss,
    reset_accent_palette,
)
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS


class AccentColorDialog(QDialog):
    """Modal dialog wrapping QColorDialog for accent color selection.

    Embeds a QColorDialog (NoButtons | DontUseNativeDialog) inside a wrapper
    QDialog with an Apply | Reset | Cancel button row. ACCENT_PRESETS are
    seeded into Custom Colors slots 0..7 on every open (D-03 idempotent reseed).
    Public API preserved from Phase 19/40 (D-08): AccentColorDialog(repo, parent=None).
    """

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        # Phase 19/40 snapshot invariant — preserve verbatim.
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._current_hex: str = ""

        self.setWindowTitle("Accent Color")
        self.setModal(True)
        # NOTE: do NOT set a minimum width — Pitfall 7. Inner QColorDialog's
        # sizeHint() == QSize(522, 387) dominates; the legacy 360px hint is dead.

        # D-03 + Pitfall 1: seed ACCENT_PRESETS into Custom Colors slots
        # BEFORE inner dialog construction. setCustomColor is a STATIC method;
        # idempotent reseed each __init__.
        for idx, hex_val in enumerate(ACCENT_PRESETS):
            QColorDialog.setCustomColor(idx, QColor(hex_val))

        # Build the inner QColorDialog as an embedded widget.
        self._inner = QColorDialog(self)
        self._inner.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        # QColorDialog is itself a QDialog. When added to a layout as a child
        # widget, the default Qt.Dialog window flag causes Qt to suppress its
        # content rendering on real X11 (offscreen Qt happens to work without
        # this). Strip the dialog flag so it renders as a plain child widget.
        self._inner.setWindowFlags(Qt.Widget)
        self._inner.setSizeGripEnabled(False)

        # D-17 + Pitfall 3 color-flash guard: validate saved hex before
        # setCurrentColor; QColor("invalid") silently becomes #000000 and
        # would flash the entire app accent black for one tick.
        saved = self._repo.get_setting("accent_color", "")
        initial = saved if _is_valid_hex(saved) else ACCENT_COLOR_DEFAULT
        # Pitfall 6: post-init invariant `_current_hex == initial` (T-59-H).
        # Set manually because setCurrentColor before connect means the
        # initial emission does not reach our slot.
        self._current_hex = initial
        self._inner.setCurrentColor(QColor(initial))

        # D-11: bound-method connect (QA-05 — no self-capturing lambdas).
        self._inner.currentColorChanged.connect(self._on_color_changed)

        # UI-SPEC: 8/8/8/8 contentsMargins + 8 spacing (sm token; Pitfall 7).
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._inner)

        # D-09: Apply | Reset | Cancel; Apply default (Enter → Apply).
        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_color_changed(self, color: QColor) -> None:
        """Live-preview on every currentColorChanged (D-11, D-12)."""
        self._current_hex = color.name()  # lowercase #rrggbb
        apply_accent_palette(QApplication.instance(), self._current_hex)

    def _on_apply(self) -> None:
        """Persist accent_color, write QSS file, accept (D-14)."""
        # D-14.1: defense-in-depth — _is_valid_hex guard even though
        # currentColorChanged always emits valid QColor values.
        if not self._current_hex or not _is_valid_hex(self._current_hex):
            return
        self._repo.set_setting("accent_color", self._current_hex)
        try:
            import os
            css_path = paths.accent_css_path()
            os.makedirs(os.path.dirname(css_path), exist_ok=True)
            with open(css_path, "w") as f:
                f.write(build_accent_qss(self._current_hex))
        except OSError:
            pass  # Non-fatal — palette already applied via QPalette.
        self.accept()

    def _on_reset(self) -> None:
        """Clear saved accent, restore snapshot, reset picker; dialog stays open (D-15)."""
        self._repo.set_setting("accent_color", "")
        reset_accent_palette(QApplication.instance(), self._original_palette)
        # D-15.3: visually return picker to default. blockSignals so the
        # currentColorChanged emission from setCurrentColor does not
        # clobber our `_current_hex = ""` guard below.
        self._inner.blockSignals(True)
        self._inner.setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))
        self._inner.blockSignals(False)
        self._current_hex = ""
        # D-15.6: neutralize on-disk QSS file (write empty) so a stale
        # accent QSS does not apply on next startup before the user re-Applies.
        try:
            import os
            css_path = paths.accent_css_path()
            os.makedirs(os.path.dirname(css_path), exist_ok=True)
            with open(css_path, "w") as f:
                f.write("")
        except OSError:
            pass  # Non-fatal — main_window only applies QSS when accent_color is non-empty.

    def reject(self) -> None:
        """Cancel — restore snapshot palette and QSS (D-13).

        Window-manager close (X) and Esc both route through reject().
        """
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
        super().reject()
