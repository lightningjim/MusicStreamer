"""Phase 40-01: AccentColorDialog — accent color picker with 8 presets + hex entry.

UI-11 feature: live preview via QPalette modification, SQLite persistence.

Constructor: AccentColorDialog(repo, parent=None)

Security: hex input validated by _is_valid_hex before QSS injection (T-40-02).
"""
from __future__ import annotations

import functools

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from musicstreamer.accent_utils import (
    _is_valid_hex,
    apply_accent_palette,
    build_accent_qss,
    reset_accent_palette,
)
from musicstreamer.constants import ACCENT_PRESETS
from musicstreamer import paths


class AccentColorDialog(QDialog):
    """Modal dialog for selecting an accent color.

    Shows 8 preset swatches in a 4x2 grid plus a hex entry for custom colors.
    Live preview is applied immediately; Apply saves to repo, Reset clears,
    Cancel restores the original palette.
    """

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._selected_idx: int | None = None
        self._current_hex: str = ""

        self.setWindowTitle("Accent Color")
        self.setMinimumWidth(360)
        self.setModal(True)

        self._build_ui()
        self._load_saved_accent()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Section label
        section_label = QLabel("Accent Color")
        section_label.setTextFormat(Qt.PlainText)
        font = QFont()
        font.setPointSize(10)
        font.setWeight(QFont.DemiBold)
        section_label.setFont(font)
        root.addWidget(section_label)

        # Swatch grid
        grid_widget_layout = QGridLayout()
        grid_widget_layout.setSpacing(8)
        self._swatches: list[QPushButton] = []
        for idx, hex_val in enumerate(ACCENT_PRESETS):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(
                f"background-color: {hex_val}; border-radius: 4px;"
                f" border: 2px solid transparent;"
            )
            btn.clicked.connect(functools.partial(self._on_swatch_clicked, idx))
            self._swatches.append(btn)
            row, col = divmod(idx, 4)
            grid_widget_layout.addWidget(btn, row, col)
        root.addLayout(grid_widget_layout)

        # Hex entry row
        hex_row = QHBoxLayout()
        hex_label = QLabel("Hex:")
        hex_label.setTextFormat(Qt.PlainText)
        self._hex_edit = QLineEdit()
        self._hex_edit.setMaxLength(7)
        self._hex_edit.setPlaceholderText("#rrggbb")
        self._hex_edit.textChanged.connect(self._on_hex_changed)
        hex_row.addWidget(hex_label)
        hex_row.addWidget(self._hex_edit)
        root.addLayout(hex_row)

        # Button box: Apply, Reset, Cancel
        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.clicked.connect(self._on_apply)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load_saved_accent(self) -> None:
        """Pre-select swatch and populate hex entry from saved setting."""
        saved = self._repo.get_setting("accent_color", "")
        if saved and _is_valid_hex(saved):
            self._hex_edit.blockSignals(True)
            self._hex_edit.setText(saved)
            self._hex_edit.blockSignals(False)
            self._current_hex = saved
            # Select matching swatch if it matches a preset
            try:
                idx = ACCENT_PRESETS.index(saved)
                self._select_swatch(idx)
            except ValueError:
                pass  # Custom hex not in presets — no swatch highlighted

    # ------------------------------------------------------------------
    # Interaction handlers
    # ------------------------------------------------------------------

    def _on_swatch_clicked(self, idx: int) -> None:
        """Select swatch, populate hex entry, and preview."""
        self._select_swatch(idx)
        hex_val = ACCENT_PRESETS[idx]
        self._hex_edit.blockSignals(True)
        self._hex_edit.setText(hex_val)
        self._hex_edit.blockSignals(False)
        self._current_hex = hex_val
        self._preview(hex_val)

    def _on_hex_changed(self, text: str) -> None:
        """Validate hex entry; preview live on valid input, show error on invalid."""
        if _is_valid_hex(text):
            self._hex_edit.setStyleSheet("")
            self._current_hex = text
            self._preview(text)
            # Update swatch selection if matches a preset
            try:
                idx = ACCENT_PRESETS.index(text)
                self._select_swatch(idx)
            except ValueError:
                self._deselect_all_swatches()
        else:
            if text:  # Only show error styling when there's actual invalid input
                self._hex_edit.setStyleSheet("border: 1px solid #c0392b;")

    def _on_apply(self) -> None:
        """Save accent_color to repo, write QSS file, accept dialog."""
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
            pass  # Non-fatal — palette is already applied via QPalette
        self.accept()

    def _on_reset(self) -> None:
        """Clear saved accent setting and restore original palette."""
        self._repo.set_setting("accent_color", "")
        reset_accent_palette(QApplication.instance(), self._original_palette)
        self._deselect_all_swatches()
        self._hex_edit.blockSignals(True)
        self._hex_edit.setText("")
        self._hex_edit.blockSignals(False)
        self._hex_edit.setStyleSheet("")
        self._current_hex = ""
        self._selected_idx = None

    def reject(self) -> None:
        """Cancel — restore original palette and QSS without saving."""
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
        super().reject()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _preview(self, hex_value: str) -> None:
        """Apply accent color live as preview (does not persist)."""
        apply_accent_palette(QApplication.instance(), hex_value)

    # ------------------------------------------------------------------
    # Swatch selection helpers
    # ------------------------------------------------------------------

    def _select_swatch(self, idx: int) -> None:
        self._deselect_all_swatches()
        self._selected_idx = idx
        hex_val = ACCENT_PRESETS[idx]
        btn = self._swatches[idx]
        btn.setStyleSheet(
            f"background-color: {hex_val}; border-radius: 4px;"
            f" border: 2px solid white;"
            f" outline: 2px solid {hex_val};"
        )

    def _deselect_all_swatches(self) -> None:
        for i, btn in enumerate(self._swatches):
            hex_val = ACCENT_PRESETS[i]
            btn.setStyleSheet(
                f"background-color: {hex_val}; border-radius: 4px;"
                f" border: 2px solid transparent;"
            )
        self._selected_idx = None
