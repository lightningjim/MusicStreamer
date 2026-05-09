"""Phase 66 / THEME-01: ThemeEditorDialog — 9-role Custom palette editor.

Modal QDialog reachable only from ThemePickerDialog.Customize…  button.
Mirrors musicstreamer/ui_qt/accent_color_dialog.py (Phase 59) snapshot/restore idiom
with key deviations:
- QColorDialog is launched via static getColor PER ROW (not embedded once)
- 9 rows for primary palette roles; Highlight excluded (D-08 — owned by accent path)
- On Save, parent ThemePickerDialog._save_committed/_active_tile_id/_selected_theme_id
  are mutated to coordinate with the picker's snapshot-restore semantics (Pitfall 1)

Security: every hex flows through _is_valid_hex (defense-in-depth);
QColor.name() is lowercase #rrggbb per Qt convention but check is still applied.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer.accent_utils import _is_valid_hex, apply_accent_palette
from musicstreamer.theme import EDITABLE_ROLES, THEME_PRESETS


# UI-SPEC §Copywriting Contract — locked verbatim. Do NOT renumber/rename.
ROLE_LABELS: dict[str, str] = {
    "Window": "Window background",
    "WindowText": "Window text",
    "Base": "Base",
    "AlternateBase": "Alternating row",
    "Text": "Body text",
    "Button": "Button background",
    "ButtonText": "Button text",
    "HighlightedText": "Selected text",
    "Link": "Hyperlink",
}


class _ColorRow(QWidget):
    """One row in the editor: role label + clickable color swatch + hex display.

    Click on swatch opens modal QColorDialog (DontUseNativeDialog).
    Emits color_changed(role_name, new_hex) when QColorDialog accepts.
    """

    color_changed = Signal(str, str)  # (role_name, new_hex)

    def __init__(self, role_name: str, role_label: str, initial_hex: str, parent=None):
        super().__init__(parent)
        self._role_name = role_name
        self._role_label = role_label
        self._current_hex = initial_hex if _is_valid_hex(initial_hex) else "#cccccc"

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)  # xs vertical padding inside row
        row.setSpacing(8)

        label = QLabel(role_label, self)
        label.setMinimumWidth(160)
        row.addWidget(label)

        self._swatch_btn = QPushButton(self)
        self._swatch_btn.setFixedSize(48, 24)
        self._swatch_btn.setToolTip(f"Edit {role_label}…")  # U+2026
        self._swatch_btn.clicked.connect(self._on_swatch_clicked)  # QA-05 bound
        row.addWidget(self._swatch_btn)

        row.addStretch(1)

        self._hex_label = QLabel(self._current_hex, self)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._hex_label.setFont(mono)
        self._hex_label.setMinimumWidth(80)
        row.addWidget(self._hex_label)

        self._refresh_visual()

    def _refresh_visual(self) -> None:
        """Update swatch QSS, hex label text, and accessible name."""
        # Swatch background = current hex (validated). NOT QSS-interpolating
        # foreign data — _current_hex was validated on every write site.
        self._swatch_btn.setStyleSheet(
            f"QPushButton {{ background-color: {self._current_hex}; "
            f"border: 1px solid palette(mid); border-radius: 2px; }}"
        )
        self._hex_label.setText(self._current_hex)
        self._swatch_btn.setAccessibleName(
            f"{self._role_label} color, currently {self._current_hex}"
        )

    def refresh(self, new_hex: str) -> None:
        """Public API — update row's visible state to new_hex (validated)."""
        if not _is_valid_hex(new_hex):
            return
        self._current_hex = new_hex
        self._refresh_visual()

    def _on_swatch_clicked(self) -> None:
        """Open modal QColorDialog (DontUseNativeDialog) and emit on accept."""
        chosen = QColorDialog.getColor(
            QColor(self._current_hex),
            self,
            f"Choose {self._role_label} color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,  # Wayland Q15
        )
        if not chosen.isValid():
            return  # user cancelled QColorDialog
        new_hex = chosen.name()  # lowercase #rrggbb
        if not _is_valid_hex(new_hex):
            return  # defense-in-depth (T-66-09)
        self._current_hex = new_hex
        self._refresh_visual()
        self.color_changed.emit(self._role_name, new_hex)


# Task 2b lands ThemeEditorDialog here.
