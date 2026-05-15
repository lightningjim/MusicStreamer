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
    "ToolTipBase": "Toast background",
    "ToolTipText": "Toast text",
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


class ThemeEditorDialog(QDialog):
    """Phase 66 D-08..D-14 — modal Custom palette editor (9 roles, Highlight excluded)."""

    def __init__(self, repo, source_preset: str, parent=None):
        # Qt requires QWidget|None as the super().__init__() parent. We also
        # accept non-QWidget parents (e.g. _FakePicker test stub mimicking
        # ThemePickerDialog's flag attributes; T-66-11 mitigation contract).
        # Stash the caller's parent for the save-flag mutation regardless of
        # type, and only forward to super() if it is a real QWidget.
        self._save_target_parent = parent
        qt_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(qt_parent)
        self._repo = repo
        app = QApplication.instance()
        # Independent snapshot at editor open — captures whatever picker
        # has live-previewed, NOT picker's pre-Customize state (RESEARCH Q10).
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()

        self.setWindowTitle("Customize Theme")
        self.setModal(True)

        # Compute starting palette per source_preset (UI-SPEC §Pre-population).
        self._source_preset_palette: dict[str, str] = self._compute_source_palette(source_preset)
        # Working dict for live edits.
        self._role_hex_dict: dict[str, str] = dict(self._source_preset_palette)

        # Wrapper layout (Phase 59 8/8/8/8 + 8 spacing token).
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # 9 rows, single column, in EDITABLE_ROLES order (matches QPalette enum).
        self._rows: dict[str, _ColorRow] = {}
        for role_name in EDITABLE_ROLES:
            label = ROLE_LABELS[role_name]
            initial_hex = self._role_hex_dict.get(role_name, "#cccccc")
            row = _ColorRow(role_name, label, initial_hex, self)
            row.color_changed.connect(self._on_role_color_changed)  # QA-05 bound
            root.addWidget(row)
            self._rows[role_name] = row

        # Set initial focus to first row's swatch (UI-SPEC §A11y).
        self._rows["Window"]._swatch_btn.setFocus()

        # Button row: Save (Accept, default) | Reset (ResetRole) | Cancel (RejectRole)
        btn_box = QDialogButtonBox()
        self._save_btn = btn_box.addButton("Save", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Source-palette resolution (UI-SPEC §Pre-population on open — 5 cases)
    # ------------------------------------------------------------------

    def _compute_source_palette(self, source_preset: str) -> dict[str, str]:
        """Compute prefill dict per UI-SPEC §Pre-population (5 cases)."""
        # Case A: source_preset == 'custom' AND theme_custom JSON valid
        # Case B: source_preset == 'custom' AND JSON invalid/empty → fall back to active app palette
        # Case C: source_preset == 'system' → fresh QPalette() Qt-default values per role
        # Case D: source_preset is one of the 6 preset keys → THEME_PRESETS lookup
        # Case E: unknown source_preset → fall back to active app palette
        if source_preset == "custom":
            raw = self._repo.get_setting("theme_custom", "")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict) and parsed:
                result = {}
                for role_name in EDITABLE_ROLES:
                    hex_val = parsed.get(role_name, "")
                    if isinstance(hex_val, str) and _is_valid_hex(hex_val):
                        result[role_name] = hex_val
                    else:
                        # Defense (T-66-10): fall back to active app palette role
                        result[role_name] = self._read_app_palette_role(role_name)
                return result
            # Fall through to active app palette for case B
            return self._read_app_palette_role_dict()
        if source_preset == "system":
            p = QPalette()  # fresh Qt-default
            return {
                role_name: self._role_hex_from_palette(p, role_name)
                for role_name in EDITABLE_ROLES
            }
        preset = THEME_PRESETS.get(source_preset)
        if preset:
            # Skip Highlight key (not editable here — D-08); copy 9 EDITABLE_ROLES only.
            return {
                role_name: preset[role_name]
                for role_name in EDITABLE_ROLES
                if role_name in preset
            }
        # Unknown source_preset — case E fallback.
        return self._read_app_palette_role_dict()

    def _read_app_palette_role_dict(self) -> dict[str, str]:
        app = QApplication.instance()
        p = app.palette()
        return {
            role_name: self._role_hex_from_palette(p, role_name)
            for role_name in EDITABLE_ROLES
        }

    def _read_app_palette_role(self, role_name: str) -> str:
        app = QApplication.instance()
        return self._role_hex_from_palette(app.palette(), role_name)

    @staticmethod
    def _role_hex_from_palette(palette, role_name: str) -> str:
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is None:
            return "#cccccc"
        color = palette.color(role)
        return color.name()  # lowercase #rrggbb

    # ------------------------------------------------------------------
    # Slots — UI-SPEC §State Machine
    # ------------------------------------------------------------------

    def _on_role_color_changed(self, role_name: str, new_hex: str) -> None:
        """Live preview a role change + re-impose accent override (UI-SPEC §Live preview wiring)."""
        if not _is_valid_hex(new_hex):
            return  # defense-in-depth (T-66-09)
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is None:
            return  # defense — should never trigger because EDITABLE_ROLES is locked
        app = QApplication.instance()
        palette = app.palette()
        palette.setColor(role, QColor(new_hex))
        app.setPalette(palette)
        # Re-impose accent override (Phase 59 D-02 layering — Pitfall 2).
        accent = self._repo.get_setting("accent_color", "")
        if accent and _is_valid_hex(accent):
            apply_accent_palette(app, accent)
        self._role_hex_dict[role_name] = new_hex

    def _on_save(self) -> None:
        """Persist theme_custom JSON + theme='custom' + flip parent flags (UI-SPEC §State Machine E-Saved)."""
        self._repo.set_setting("theme_custom", json.dumps(self._role_hex_dict))
        self._repo.set_setting("theme", "custom")
        # Use the stashed save-target (caller's original parent arg), NOT
        # self.parent() — Qt's parent() returns the QWidget parent, which may
        # be None for non-QWidget callers (e.g. _FakePicker test stub).
        parent = self._save_target_parent
        if parent is not None and hasattr(parent, "_save_committed"):
            parent._save_committed = True
            parent._active_tile_id = "custom"
            parent._selected_theme_id = "custom"
        self.accept()

    def _on_reset(self) -> None:
        """Revert all 9 rows to source preset; dialog stays open (UI-SPEC §State Machine E-Reset).

        D-08 invariant: only the 9 EDITABLE_ROLES are mutated. Highlight is owned
        by the accent layering path and is NOT touched by Reset.
        """
        app = QApplication.instance()
        palette = app.palette()
        for role_name, hex_value in self._source_preset_palette.items():
            if not _is_valid_hex(hex_value):
                continue
            role = getattr(QPalette.ColorRole, role_name, None)
            if role is None:
                continue
            palette.setColor(role, QColor(hex_value))
            self._role_hex_dict[role_name] = hex_value
            if role_name in self._rows:
                self._rows[role_name].refresh(hex_value)
        app.setPalette(palette)
        # Re-impose accent override.
        accent = self._repo.get_setting("accent_color", "")
        if accent and _is_valid_hex(accent):
            apply_accent_palette(app, accent)
        # NO accept() / NO reject() — dialog stays open (D-14 / Phase 59 idiom)

    def reject(self) -> None:
        """Cancel — restore independent snapshot (RESEARCH Q10)."""
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
        super().reject()
