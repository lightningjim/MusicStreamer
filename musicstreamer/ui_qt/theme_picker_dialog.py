"""Phase 66 / THEME-01: ThemePickerDialog — modal QDialog with 4x2 tile grid.

Mirrors musicstreamer/ui_qt/accent_color_dialog.py (Phase 59) idiom.

Public surface:
    ThemePickerDialog(repo, parent=None).exec()

Layering invariants (Phase 59 D-02 + Phase 66 D-02):
- Tile click = live preview (palette mutated; accent_color override re-imposed if non-empty)
- Apply persists `theme` setting; Cancel restores snapshot palette + styleSheet
- Modality: setModal(True); Esc/X routes through reject()
- _save_committed flag suppresses snapshot restore when editor saved during picker session (Pitfall 1)

Security: hex from theme_custom JSON validated by _is_valid_hex via build_palette_from_dict;
JSON parse wrapped in try/except + isinstance(dict) check (T-66-05).
"""
from __future__ import annotations

import functools
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from musicstreamer.accent_utils import _is_valid_hex, apply_accent_palette
from musicstreamer.constants import ACCENT_COLOR_DEFAULT
from musicstreamer.theme import (
    DISPLAY_NAMES,
    DISPLAY_ORDER,
    THEME_PRESETS,
    build_palette_from_dict,
)


class _ThemeTile(QPushButton):
    """120x100 tile rendering 4-color stripe + theme name + optional active state.

    UI-SPEC: tile dims 120x100; stripe 96x16 centered 8px from top;
    active = 3px border using palette().highlight() + SP_DialogApplyButton checkmark
    in top-right corner; disabled (empty Custom) = italic hint label, no stripe.
    """

    def __init__(self, theme_id: str, repo, parent=None):
        super().__init__(parent)
        self._theme_id = theme_id
        self._repo = repo
        self._is_active = False
        self.setFixedSize(120, 100)
        self.setText("")  # we render the name in paintEvent
        display_name = DISPLAY_NAMES[theme_id]
        self.setAccessibleName(display_name)
        self.setToolTip("")  # default; disabled-Custom override set externally

    def set_active(self, is_active: bool) -> None:
        if self._is_active == is_active:
            return
        self._is_active = is_active
        self.update()

    def _stripe_colors(self) -> list[str]:
        """Return 4 hex strings for Window / Base / Text / Highlight-or-fallback.

        - System default tile: read fresh QPalette() at paint time for slots 1-3,
          ACCENT_COLOR_DEFAULT for slot 4.
        - Custom tile: load theme_custom JSON (defense-in-depth) for slots 1-3,
          ACCENT_COLOR_DEFAULT for slot 4.
        - Preset tile: use preset dict directly; Highlight baseline (or fallback).
        """
        if self._theme_id == "system":
            p = QPalette()  # fresh Qt-default palette
            return [
                p.color(QPalette.ColorRole.Window).name(),
                p.color(QPalette.ColorRole.Base).name(),
                p.color(QPalette.ColorRole.Text).name(),
                ACCENT_COLOR_DEFAULT,
            ]
        if self._theme_id == "custom":
            raw = self._repo.get_setting("theme_custom", "")
            try:
                role_hex = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                role_hex = {}
            if not isinstance(role_hex, dict):
                role_hex = {}
            window = role_hex.get("Window", "#cccccc")
            base = role_hex.get("Base", "#ffffff")
            text = role_hex.get("Text", "#000000")
            if not _is_valid_hex(window):
                window = "#cccccc"
            if not _is_valid_hex(base):
                base = "#ffffff"
            if not _is_valid_hex(text):
                text = "#000000"
            return [window, base, text, ACCENT_COLOR_DEFAULT]
        preset = THEME_PRESETS.get(self._theme_id, {})
        highlight = preset.get("Highlight", ACCENT_COLOR_DEFAULT)
        if not _is_valid_hex(highlight):
            highlight = ACCENT_COLOR_DEFAULT
        return [
            preset.get("Window", "#cccccc"),
            preset.get("Base", "#ffffff"),
            preset.get("Text", "#000000"),
            highlight,
        ]

    def paintEvent(self, event):
        # Let QPushButton draw bg + focus ring first.
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        display_name = DISPLAY_NAMES[self._theme_id]
        is_empty_custom = (self._theme_id == "custom" and not self.isEnabled())

        # 1. Stripe (96x16 centered horizontally, 8px from top) — skip if empty Custom.
        if not is_empty_custom:
            stripe_x = (self.width() - 96) // 2
            stripe_y = 8
            stripe_w_per_swatch = 24  # 96 / 4
            colors = self._stripe_colors()
            for i, hex_str in enumerate(colors):
                if not _is_valid_hex(hex_str):
                    continue
                painter.fillRect(
                    stripe_x + i * stripe_w_per_swatch,
                    stripe_y,
                    stripe_w_per_swatch,
                    16,
                    QColor(hex_str),
                )

        # 2. Name label (centered horizontally, below stripe at y=32).
        painter.setPen(self.palette().windowText().color())
        label_rect = self.rect().adjusted(4, 32, -4, -4)
        if is_empty_custom:
            font = painter.font()
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(label_rect, Qt.AlignCenter | Qt.TextWordWrap, "Click Customize…")
        else:
            painter.drawText(label_rect, Qt.AlignCenter | Qt.TextWordWrap, display_name)

        # 3. Active state: 3px border + checkmark.
        if self._is_active:
            pen = QPen(self.palette().highlight().color())
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
            # Checkmark in top-right corner (16x16 with 4px padding).
            style = self.style()
            pixmap = style.standardPixmap(QStyle.SP_DialogApplyButton).scaled(16, 16)
            painter.drawPixmap(self.width() - 20, 4, pixmap)

        painter.end()


class ThemePickerDialog(QDialog):
    """Phase 66 D-15..D-21 — modal theme picker with 4x2 tile grid.

    Mirrors AccentColorDialog (Phase 59) shape: snapshot palette + styleSheet
    on init; reject restores; accept persists `theme` setting.
    """

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        # Phase 19/40/59 snapshot invariant — preserve verbatim.
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._save_committed: bool = False  # Phase 66 Pitfall 1

        saved = repo.get_setting("theme", "system")
        self._selected_theme_id: str = saved if saved in DISPLAY_NAMES else "system"
        self._active_tile_id: str = self._selected_theme_id

        self.setWindowTitle("Theme")
        self.setModal(True)

        # Wrapper layout (Phase 59 8/8/8/8 + 8 spacing token).
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Tile grid (4 cols x 2 rows; 8px gaps).
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._tiles: dict[str, _ThemeTile] = {}
        for idx, theme_id in enumerate(DISPLAY_ORDER):
            tile = _ThemeTile(theme_id, self._repo, self)
            row, col = divmod(idx, 4)
            grid.addWidget(tile, row, col)
            self._tiles[theme_id] = tile
            # QA-05: bound method via partial; partial is held as a tile attr
            # to keep a strong reference (no self-capturing lambdas).
            tile._click_handler = functools.partial(self._on_tile_clicked, theme_id)
            tile.clicked.connect(tile._click_handler)
        root.addLayout(grid)

        # Disable Custom tile if theme_custom is missing/empty/corrupt (T-66-06).
        self._refresh_custom_tile_enabled()

        # Initial active-state render (must run after Custom-enabled refresh
        # so disabled tiles render their hint label correctly).
        self._refresh_active_tile()

        # Set initial focus to the active tile (UI-SPEC §A11y).
        self._tiles[self._active_tile_id].setFocus()

        # Button row: Customize... (ActionRole, left) | Apply (Accept, default) | Cancel (Reject)
        btn_box = QDialogButtonBox()
        self._customize_btn = btn_box.addButton("Customize…", QDialogButtonBox.ActionRole)
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.setDefault(True)
        self._customize_btn.clicked.connect(self._on_customize)
        self._apply_btn.clicked.connect(self._on_apply)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_custom_tile_enabled(self) -> None:
        """Set Custom tile enabled iff theme_custom is a non-empty JSON dict."""
        raw = self._repo.get_setting("theme_custom", "")
        valid = False
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed:
                    valid = True
            except json.JSONDecodeError:
                valid = False
        self._tiles["custom"].setEnabled(valid)
        if not valid:
            self._tiles["custom"].setToolTip("Click Customize… to create a Custom theme")
        else:
            self._tiles["custom"].setToolTip("")

    def _refresh_active_tile(self) -> None:
        for theme_id, tile in self._tiles.items():
            tile.set_active(theme_id == self._active_tile_id)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_tile_clicked(self, theme_id: str) -> None:
        """Tile click = live preview; no persistence (UI-SPEC §State Machine P-Previewing)."""
        self._selected_theme_id = theme_id
        self._active_tile_id = theme_id
        app = QApplication.instance()
        app.setProperty("theme_name", theme_id)

        if theme_id == "system":
            app.setPalette(QPalette())  # fresh Qt-default
        elif theme_id == "custom":
            raw = self._repo.get_setting("theme_custom", "")
            try:
                role_hex = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                role_hex = {}
            if not isinstance(role_hex, dict):
                role_hex = {}
            app.setPalette(build_palette_from_dict(role_hex))
        else:
            app.setPalette(build_palette_from_dict(THEME_PRESETS[theme_id]))

        # Re-impose accent override (Phase 59 D-02 layering — Pitfall 2).
        accent = self._repo.get_setting("accent_color", "")
        if accent and _is_valid_hex(accent):
            apply_accent_palette(app, accent)

        self._refresh_active_tile()

    def _on_apply(self) -> None:
        """Persist theme setting and accept (UI-SPEC §State Machine P-Applied)."""
        self._repo.set_setting("theme", self._selected_theme_id)
        self.accept()

    def _on_customize(self) -> None:
        """Open the editor with currently-selected preset as source (D-18)."""
        # Lazy import — Plan 03 owns the real implementation.
        from musicstreamer.ui_qt.theme_editor_dialog import ThemeEditorDialog
        editor = ThemeEditorDialog(self._repo, source_preset=self._selected_theme_id, parent=self)
        editor.exec()
        # Editor's _on_save (Plan 03) mutates self._save_committed + _active_tile_id directly.
        # Always refresh visuals after editor closes (covers both saved + cancelled paths).
        self._refresh_custom_tile_enabled()
        self._refresh_active_tile()

    def reject(self) -> None:
        """Cancel — restore snapshot UNLESS editor saved during this session (Pitfall 1)."""
        if not self._save_committed:
            app = QApplication.instance()
            app.setPalette(self._original_palette)
            app.setStyleSheet(self._original_qss)
        super().reject()

    def closeEvent(self, event) -> None:
        """Window-manager close (X / Esc / Alt+F4) routes through reject().

        Qt's QDialog.closeEvent only calls reject() when the dialog is currently
        visible; this override makes the WM-close contract robust for the
        not-yet-shown case as well (Phase 59 invariant — UI-SPEC §A11y).
        """
        self.reject()
        event.accept()
