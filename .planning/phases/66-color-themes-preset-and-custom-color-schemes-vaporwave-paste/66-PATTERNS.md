# Phase 66: Color Themes — Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 10 (6 NEW + 4 MODIFIED)
**Analogs found:** 9 / 10 (REQUIREMENTS.md row is a docs edit, no code analog needed)

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `musicstreamer/theme.py` | utility (palette helpers) | transform / settings-read | `musicstreamer/accent_utils.py` | **exact** (CONTEXT.md explicitly: "parallels accent_utils.py") |
| `musicstreamer/ui_qt/theme_picker_dialog.py` | component (modal QDialog) | event-driven (snapshot/restore + live preview) | `musicstreamer/ui_qt/accent_color_dialog.py` | **exact** (Phase 59 idiom inheritance per UI-SPEC) |
| `musicstreamer/ui_qt/theme_editor_dialog.py` | component (modal QDialog) | event-driven (per-row QColorDialog launcher + snapshot/restore) | `musicstreamer/ui_qt/accent_color_dialog.py` | **exact** (same dialog idiom; row launches modal QColorDialog instead of embedding it) |
| `tests/test_theme.py` | test (unit) | request-response (pure functions + repo round-trip) | `tests/test_accent_provider.py` | **exact** (same shape: hex validators + palette mutators + Repo round-trip) |
| `tests/test_theme_picker_dialog.py` | test (pytest-qt integration) | event-driven (qtbot signals + snapshot assertions) | `tests/test_accent_color_dialog.py` | **exact** (same FakeRepo + qtbot fixtures + snapshot/restore tests) |
| `tests/test_theme_editor_dialog.py` | test (pytest-qt integration) | event-driven (qtbot + parent-modal interaction) | `tests/test_accent_color_dialog.py` | **exact** (same idiom; adds parent-picker `_save_committed` flag wiring) |
| `musicstreamer/__main__.py` (modified) | config (startup/entry) | request-response (one-shot palette init at app boot) | `musicstreamer/__main__.py:69-99` (`_apply_windows_palette`) + `__main__.py:185-192` (existing palette block) | **exact** (insertion in same code region) |
| `musicstreamer/ui_qt/main_window.py` (modified) | component (menu wiring + slot) | event-driven (action triggered) | `main_window.py:188-189` (`act_accent`) + `main_window.py:776-779` (`_open_accent_dialog`) | **exact** (parallel sibling action + slot) |
| `.planning/REQUIREMENTS.md` (modified) | doc | additive table-row edit | `REQUIREMENTS.md:40` (ACCENT-02 entry) + `REQUIREMENTS.md:96` (traceability row) | **exact** (same line format) |
| `.planning/ROADMAP.md` (modified) | doc | placeholder-fill | `ROADMAP.md:509-528` (Phase 65 completed-phase block) | **exact** (same heading + Goal + Requirements + Plans format) |

---

## Pattern Assignments

### `musicstreamer/theme.py` (utility, transform/settings-read)

**Analog:** `musicstreamer/accent_utils.py` (entire file, 71 lines)

**Imports pattern** (`accent_utils.py:1-8`):
```python
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette

_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
```
Theme module follows the same TYPE_CHECKING block; imports `_is_valid_hex` from `accent_utils` (do **not** redefine the regex). Lazy-import `QPalette`, `QColor` inside helper functions (matches `accent_utils.py:60` pattern).

**Validator-first persistence guard pattern** (`accent_utils.py:11-13` + `:22` + `:44`):
```python
def _is_valid_hex(value: str) -> bool:
    """Return True if value is a valid 3- or 6-digit hex color string."""
    return bool(_HEX_RE.match(value))

# Re-used at every persistence boundary:
def build_accent_qss(hex_value: str) -> str:
    if not _is_valid_hex(hex_value):
        return ""
    return (...)
```
**Apply to `theme.py`:** every hex value pulled from `theme_custom` JSON (or `THEME_PRESETS` if planner ever loosens the static dict) MUST pass `_is_valid_hex` before reaching `QColor(...)`. `build_palette_from_dict` skips invalid entries silently (RESEARCH Pitfall 3 — no black flash).

**Apply-palette idiom** (`accent_utils.py:54-65`):
```python
def apply_accent_palette(app: "QApplication", hex_value: str) -> None:
    """Modify app QPalette Highlight role to hex_value and apply QSS for slider."""
    from PySide6.QtGui import QPalette, QColor
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(hex_value))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(palette)
    app.setStyleSheet(build_accent_qss(hex_value))
```
**Apply to `theme.apply_theme_palette(app, repo)`:** read setting, build palette via `build_palette_from_dict`, call `app.setPalette(palette)`. **Do NOT** call `app.setStyleSheet(...)` — RESEARCH Q4 + Pitfall 9 forbid a parallel `theme.css` file. `getattr(QPalette.ColorRole, role_name, None)` is the role lookup pattern (RESEARCH §`theme.py` public surface).

**Reset / no-op idiom** (`accent_utils.py:68-71`):
```python
def reset_accent_palette(app: "QApplication", original_palette: "QPalette") -> None:
    """Restore app palette and clear QSS to remove accent customization."""
    app.setPalette(original_palette)
    app.setStyleSheet("")
```
**Apply to `theme.py`:** the `theme == 'system'` branch on Linux is a true no-op (return early). On Windows, it preserves `app.setStyle("Fusion") + _apply_windows_palette(app)` verbatim (CONTEXT.md D-23.1).

---

### `musicstreamer/ui_qt/theme_picker_dialog.py` (component, event-driven)

**Analog:** `musicstreamer/ui_qt/accent_color_dialog.py` (entire file, 163 lines)

**Module docstring + import block pattern** (`accent_color_dialog.py:1-32`):
```python
"""Phase 59: AccentColorDialog — wrapper around QColorDialog (HSV wheel + eyedropper).
...
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
```
**Apply to `theme_picker_dialog.py`:** copy the `from __future__ import annotations` + grouped Qt imports. Import `_is_valid_hex, apply_accent_palette` from `musicstreamer.accent_utils` (re-used to re-impose Highlight override after every theme mutation per UI-SPEC §"Live preview wiring"). Import `THEME_PRESETS, DISPLAY_NAMES, DISPLAY_ORDER, EDITABLE_ROLES, build_palette_from_dict, apply_theme_palette` from `musicstreamer.theme`.

**Snapshot-on-init pattern** (`accent_color_dialog.py:44-51`):
```python
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
```
**Apply to picker `__init__`:**
```python
def __init__(self, repo, parent=None):
    super().__init__(parent)
    self._repo = repo
    app = QApplication.instance()
    self._original_palette = app.palette()
    self._original_qss = app.styleSheet()
    self._save_committed: bool = False  # NEW — set True if editor saves while picker is open (UI-SPEC §"Modal stacking")
    saved = repo.get_setting("theme", "system")
    self._selected_theme_id: str = saved
    self._active_tile_id: str = saved

    self.setWindowTitle("Theme")
    self.setModal(True)
```

**Layout + spacing token pattern** (`accent_color_dialog.py:90-94`):
```python
# UI-SPEC: 8/8/8/8 contentsMargins + 8 spacing (sm token; Pitfall 7).
root = QVBoxLayout(self)
root.setContentsMargins(8, 8, 8, 8)
root.setSpacing(8)
root.addWidget(self._inner)
```
**Apply to picker:** same `8/8/8/8` margins + `8` spacing. Replace `addWidget(self._inner)` with `addLayout(self._tile_grid_layout)` (a `QGridLayout` of 4 columns × 2 rows of `_ThemeTile` widgets per UI-SPEC §"Spacing Scale" tile dimensions 120×100, gap 8, grid margins 8).

**Button-row idiom** (`accent_color_dialog.py:96-105`):
```python
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
```
**Apply to picker** (UI-SPEC §"Picker button row"): drop Reset; add Customize… as ActionRole (left-aligned, Qt-default placement on Linux):
```python
btn_box = QDialogButtonBox()
self._customize_btn = btn_box.addButton("Customize…", QDialogButtonBox.ActionRole)  # U+2026
self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
self._apply_btn.setDefault(True)
self._customize_btn.clicked.connect(self._on_customize)
self._apply_btn.clicked.connect(self._on_apply)
self._cancel_btn.clicked.connect(self.reject)
root.addWidget(btn_box)
```

**Apply-then-accept slot pattern** (`accent_color_dialog.py:116-131`):
```python
def _on_apply(self) -> None:
    """Persist accent_color, write QSS file, accept (D-14)."""
    if not self._current_hex or not _is_valid_hex(self._current_hex):
        return
    self._repo.set_setting("accent_color", self._current_hex)
    try:
        ...
    except OSError:
        pass  # Non-fatal — palette already applied via QPalette.
    self.accept()
```
**Apply to picker `_on_apply`:** persist `theme = self._selected_theme_id`, then `self.accept()`. **Drop** the QSS-file write (no `theme.css`).

**Reject-restores-snapshot pattern** (`accent_color_dialog.py:155-163`):
```python
def reject(self) -> None:
    """Cancel — restore snapshot palette and QSS (D-13).

    Window-manager close (X) and Esc both route through reject().
    """
    app = QApplication.instance()
    app.setPalette(self._original_palette)
    app.setStyleSheet(self._original_qss)
    super().reject()
```
**Apply to picker** with `_save_committed` short-circuit (UI-SPEC §"Modal stacking" Pitfall 1):
```python
def reject(self) -> None:
    if not self._save_committed:
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
    super().reject()
```

**Bound-method connect pattern (QA-05)** (`accent_color_dialog.py:88` + `:102-104`):
```python
self._inner.currentColorChanged.connect(self._on_color_changed)
self._apply_btn.clicked.connect(self._on_apply)
self._reset_btn.clicked.connect(self._on_reset)
self._cancel_btn.clicked.connect(self.reject)
```
**Apply to picker:** every signal connection is a bound method. NO `connect(lambda ...)`. Tile clicks: `tile.clicked.connect(self._on_tile_clicked)` — slot reads `self.sender()._theme_id` to get the theme id (or planner uses `functools.partial(self._on_tile_clicked, theme_id)` and stores the partial as a tile-instance attribute to keep a strong reference).

**Live-preview slot pattern** (`accent_color_dialog.py:111-114`):
```python
def _on_color_changed(self, color: QColor) -> None:
    """Live-preview on every currentColorChanged (D-11, D-12)."""
    self._current_hex = color.name()  # lowercase #rrggbb
    apply_accent_palette(QApplication.instance(), self._current_hex)
```
**Apply to picker `_on_tile_clicked`** (UI-SPEC §"Live preview wiring"):
```python
def _on_tile_clicked(self, theme_id: str) -> None:
    self._selected_theme_id = theme_id
    app = QApplication.instance()
    if theme_id == "system":
        app.setPalette(QPalette())  # fresh Qt-default; Windows branch handled via apply_theme_palette
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
    # Re-impose accent override (RESEARCH Pitfall 2)
    accent = self._repo.get_setting("accent_color", "")
    if accent and _is_valid_hex(accent):
        apply_accent_palette(app, accent)
    self._refresh_active_tile()
```

**Customize → child editor pattern** (uses Phase 59 dialog `.exec()` precedent at `main_window.py:778-779`):
```python
def _on_customize(self) -> None:
    from musicstreamer.ui_qt.theme_editor_dialog import ThemeEditorDialog
    editor = ThemeEditorDialog(self._repo, source_preset=self._selected_theme_id, parent=self)
    editor.exec()
    # editor's _on_save sets self._save_committed = True if Saved
    self._refresh_active_tile()  # editor may have changed _active_tile_id → 'custom'
```

---

### `musicstreamer/ui_qt/theme_editor_dialog.py` (component, event-driven)

**Analog:** `musicstreamer/ui_qt/accent_color_dialog.py` (entire file)

Same imports + snapshot-on-init + reject-restores pattern as the picker. Editor-specific deviations:

**Constructor signature** (UI-SPEC §"Files Owned by This Contract"):
```python
def __init__(self, repo, source_preset: str, parent=None):
    super().__init__(parent)
    self._repo = repo
    app = QApplication.instance()
    self._original_palette = app.palette()
    self._original_qss = app.styleSheet()
    self.setWindowTitle("Customize Theme")
    self.setModal(True)
    # Stash source preset for Reset semantics (D-14):
    self._source_preset_palette: dict[str, str] = self._compute_source_palette(source_preset)
    # Working dict for live edits (D-13):
    self._role_hex_dict: dict[str, str] = dict(self._source_preset_palette)
```

**Per-row QColorDialog launcher pattern** — adapts `accent_color_dialog.py:65-74` (where QColorDialog is *embedded*) into a *static-call-modal* idiom (UI-SPEC §"Editor row interaction"):
```python
# Static-call modal idiom (NOT embedded — different from Phase 59):
def _on_swatch_clicked(self, role_name: str) -> None:
    label = ROLE_LABELS[role_name]
    initial = QColor(self._role_hex_dict[role_name])
    chosen = QColorDialog.getColor(
        initial,
        self,
        f"Choose {label} color",
        QColorDialog.ColorDialogOption.DontUseNativeDialog,  # MATCHES accent_color_dialog.py:67
    )
    if not chosen.isValid():
        return
    new_hex = chosen.name()  # lowercase #rrggbb
    if not _is_valid_hex(new_hex):
        return
    self._on_role_color_changed(role_name, new_hex)
```

**Live-preview-per-role slot** — adapts `accent_color_dialog.py:111-114` for 9 roles:
```python
def _on_role_color_changed(self, role_name: str, new_hex: str) -> None:
    app = QApplication.instance()
    palette = app.palette()
    role = getattr(QPalette.ColorRole, role_name, None)
    if role is None or not _is_valid_hex(new_hex):
        return  # defense-in-depth
    palette.setColor(role, QColor(new_hex))
    app.setPalette(palette)
    accent = self._repo.get_setting("accent_color", "")
    if accent and _is_valid_hex(accent):
        apply_accent_palette(app, accent)
    self._role_hex_dict[role_name] = new_hex
    self._rows[role_name].refresh(new_hex)  # update swatch bg + hex label + accessibleName
```

**Reset = revert-and-stay-open pattern** (`accent_color_dialog.py:133-153`):
```python
def _on_reset(self) -> None:
    """Clear saved accent, restore snapshot, reset picker; dialog stays open (D-15)."""
    self._repo.set_setting("accent_color", "")
    reset_accent_palette(QApplication.instance(), self._original_palette)
    self._inner.blockSignals(True)
    self._inner.setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))
    self._inner.blockSignals(False)
    self._current_hex = ""
    ...
```
**Apply to editor `_on_reset`** (UI-SPEC §"Editor button row"; D-14): does NOT touch repo (theme_custom is only persisted on Save). Reverts each of the 9 rows to `self._source_preset_palette[role_name]`, applies all 9 roles to the running palette in a single setPalette pass, re-imposes accent override; **dialog stays open** (no `accept()` / no `reject()`):
```python
def _on_reset(self) -> None:
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
        self._rows[role_name].refresh(hex_value)
    app.setPalette(palette)
    accent = self._repo.get_setting("accent_color", "")
    if accent and _is_valid_hex(accent):
        apply_accent_palette(app, accent)
```

**Save = persist-and-accept pattern** — composite of `accent_color_dialog.py:116-131` (persist + accept) plus parent-flag-set (UI-SPEC §"Modal stacking" Pitfall 1):
```python
def _on_save(self) -> None:
    import json
    self._repo.set_setting("theme_custom", json.dumps(self._role_hex_dict))
    self._repo.set_setting("theme", "custom")
    parent = self.parent()
    if parent is not None and hasattr(parent, "_save_committed"):
        parent._save_committed = True
        parent._active_tile_id = "custom"
        parent._selected_theme_id = "custom"
    self.accept()
```

---

### `tests/test_theme.py` (test, unit + integration)

**Analog:** `tests/test_accent_provider.py` (118 lines)

**Imports + fixture pattern** (`test_accent_provider.py:1-14`):
```python
import sqlite3
import pytest
from musicstreamer.accent_utils import _is_valid_hex, build_accent_css
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer.repo import Repo, db_init


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```
**Apply to `test_theme.py`:** copy the same `repo` fixture verbatim. Import `THEME_PRESETS, EDITABLE_ROLES, build_palette_from_dict, apply_theme_palette` from `musicstreamer.theme`.

**Validator-table pattern** (`test_accent_provider.py:78-84`):
```python
def test_presets_all_valid():
    for hex_val in ACCENT_PRESETS:
        assert _is_valid_hex(hex_val), f"Invalid hex in ACCENT_PRESETS: {hex_val!r}"
```
**Apply to `test_theme.py`:** `test_all_presets_cover_9_roles` iterates `THEME_PRESETS.values()` (skip `system`) and asserts each non-system preset has every key in `EDITABLE_ROLES` (or none for Highlight in Dark/Light per D-07).

**GBS.FM lock test** (RESEARCH §"Phase Requirements → Test Map"): assert `THEME_PRESETS["gbs"] == {"Window": "#A1D29D", "WindowText": "#000000", "Base": "#D8E9D6", "AlternateBase": "#E7F1E6", "Text": "#000000", "Button": "#B1D07C", "ButtonText": "#000000", "Highlight": "#5AB253", "HighlightedText": "#FFFFFF", "Link": "#448F3F"}`. Pattern: use `==` on dicts; do not lower-case the locked uppercase hex.

**Settings round-trip pattern** (`test_accent_provider.py:67-73`):
```python
def test_settings_roundtrip(repo):
    repo.set_setting("accent_color", "#e62d42")
    assert repo.get_setting("accent_color", "#3584e4") == "#e62d42"


def test_settings_default(repo):
    assert repo.get_setting("accent_color", "#3584e4") == "#3584e4"
```
**Apply to `test_theme.py`:** mirror with `theme` and `theme_custom` keys. Add a corrupt-JSON test that calls `apply_theme_palette(qapp, repo)` after `repo.set_setting("theme", "custom"); repo.set_setting("theme_custom", "{not-json")` and asserts no exception is raised.

**qapp-fixture palette-mutator pattern** (`test_accent_provider.py:105-118`):
```python
def test_apply_accent_palette_changes_highlight(qapp):
    from musicstreamer.accent_utils import apply_accent_palette
    from PySide6.QtGui import QPalette, QColor
    apply_accent_palette(qapp, "#e62d42")
    assert qapp.palette().color(QPalette.ColorRole.Highlight) == QColor("#e62d42")


def test_reset_accent_palette_restores(qapp):
    from musicstreamer.accent_utils import apply_accent_palette, reset_accent_palette
    from PySide6.QtGui import QPalette
    original = qapp.palette()
    apply_accent_palette(qapp, "#e62d42")
    reset_accent_palette(qapp, original)
    assert qapp.palette().color(QPalette.ColorRole.Highlight) == original.color(QPalette.ColorRole.Highlight)
```
**Apply to `test_theme.py`:** layered-palette test calls `apply_theme_palette` then `apply_accent_palette`, asserts `Highlight` is the accent (proves theme then accent override semantics — RESEARCH Q3).

---

### `tests/test_theme_picker_dialog.py` (test, pytest-qt integration)

**Analog:** `tests/test_accent_color_dialog.py` (228 lines)

**FakeRepo pattern** (`test_accent_color_dialog.py:25-33`):
```python
class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
```
**Apply to `test_theme_picker_dialog.py`:** copy verbatim (or import via shared conftest if planner prefers — but Phase 59 inlines per-test-file, so do the same to keep tests hermetic and grep-reviewable).

**Fixture pattern** (`test_accent_color_dialog.py:40-49`):
```python
@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def dialog(qtbot, repo):
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    return dlg
```
**Apply to `test_theme_picker_dialog.py`:** same shape, return `ThemePickerDialog(repo)`.

**Cancel-restores-snapshot test pattern** (`test_accent_color_dialog.py:128-151`):
```python
def test_cancel_restores_palette_and_does_not_save(qtbot, repo, qapp):
    """reject() restores snapshot palette AND repo is NOT mutated."""
    original_highlight = qapp.palette().color(QPalette.ColorRole.Highlight)

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    dlg._inner.setCurrentColor(QColor("#e62d42"))
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name() == "#e62d42"

    dlg.reject()

    assert qapp.palette().color(QPalette.ColorRole.Highlight) == original_highlight
    assert repo.get_setting("accent_color", "UNSET") == "UNSET"
```
**Apply to picker test `test_cancel_restores_snapshot`:** snapshot `qapp.palette().color(QPalette.ColorRole.Window)` before dialog construction; click a tile via `qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)`; assert Window changed; call `dlg.reject()`; assert Window is restored AND `repo.get_setting("theme", "UNSET") == "UNSET"`.

**Apply-persists test pattern** (`test_accent_color_dialog.py:114-125`):
```python
def test_apply_persists_to_repo_and_writes_qss(qtbot, dialog, repo, _accent_root):
    """Apply: repo.set_setting('accent_color', hex) AND accent.css written."""
    dialog._inner.setCurrentColor(QColor("#9141ac"))
    dialog._on_apply()
    assert repo.get_setting("accent_color", "") == "#9141ac"
    assert os.path.isfile(paths.accent_css_path()), ...
```
**Apply to picker `test_apply_persists_theme`:** click `dlg._tiles["overrun"]`, call `dlg._on_apply()`, assert `repo.get_setting("theme", "") == "overrun"`. **Drop** the file-write assertion (no `theme.css`).

**WM-close-routes-through-reject pattern** (`test_accent_color_dialog.py:170-178`):
```python
def test_window_close_behaves_like_cancel(qtbot, dialog, repo):
    """close() (WM X button) routes through reject() — repo NOT mutated."""
    repo.set_setting("accent_color", "UNSET-MARKER")
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[5]))
    dialog.close()
    assert repo.get_setting("accent_color", "") == "UNSET-MARKER"
```
**Apply to picker:** `test_wm_close_behaves_like_cancel` — preserves Phase 59 invariant.

**Pre-selection-on-open pattern** (`test_accent_color_dialog.py:182-192`):
```python
def test_load_saved_accent_pre_selects_in_picker(qtbot, repo):
    repo.set_setting("accent_color", ACCENT_PRESETS[4])
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._inner.currentColor().name() == ACCENT_PRESETS[4].lower()
```
**Apply to picker:** `repo.set_setting("theme", "gbs"); dlg = ThemePickerDialog(repo)`; assert `dlg._active_tile_id == "gbs"`.

**Defensive corrupt-input test pattern** (`test_accent_color_dialog.py:196-212`):
```python
def test_corrupt_saved_hex_falls_back_to_default(qtbot, repo):
    repo.set_setting("accent_color", "not-a-hex")
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._inner.currentColor().name() == ACCENT_COLOR_DEFAULT.lower()
```
**Apply to picker:** `test_empty_custom_tile_disabled` — `repo.set_setting("theme_custom", "")`, construct dialog, assert `dlg._tiles["custom"].isEnabled() is False`. Add `test_corrupt_theme_custom_disables_tile` mirroring this for `"{not-json"`.

**Accent-preservation test (NEW for Phase 66):** assert that after `dlg._on_tile_clicked("vaporwave")` runs, `repo.get_setting("accent_color", "UNSET")` is still UNSET (theme switch must not mutate accent setting per CONTEXT.md D-02).

---

### `tests/test_theme_editor_dialog.py` (test, pytest-qt integration)

**Analog:** `tests/test_accent_color_dialog.py` (228 lines)

Same FakeRepo + qtbot fixture pattern. Editor-specific tests:

**Reset-stays-open test pattern** (`test_accent_color_dialog.py:155-166`):
```python
def test_reset_clears_setting_and_keeps_dialog_open(qtbot, dialog, repo):
    repo.set_setting("accent_color", ACCENT_PRESETS[2])
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[2]))
    dialog._on_reset()
    assert repo.get_setting("accent_color", "UNSET") == ""
    assert dialog._current_hex == ""
    assert dialog.result() == 0  # dialog not finished
```
**Apply to editor `test_reset_reverts_to_source_preset`:** construct dialog with `source_preset="vaporwave"`, mutate one row to `#000000`, call `dlg._on_reset()`, assert all 9 `dlg._role_hex_dict` values match `THEME_PRESETS["vaporwave"]` minus the Highlight key, AND `dlg.result() == 0` (still open).

**Save-persist test:** call `dlg._on_save()`; assert `json.loads(repo.get_setting("theme_custom", ""))` matches `dlg._role_hex_dict`; assert `repo.get_setting("theme", "") == "custom"`; assert `dlg.result() != 0` (accepted).

**Parent-flag-set test (NEW for Phase 66):** construct picker as parent, then editor as child, call editor `_on_save`, assert `picker._save_committed is True` and `picker._active_tile_id == "custom"` (UI-SPEC §"Modal stacking" Pitfall 1).

---

### `musicstreamer/__main__.py` (modified, config/startup)

**Analog:** existing `__main__.py:163-220` (`_run_gui`) and `__main__.py:69-99` (`_apply_windows_palette`)

**Existing palette-init block to extend** (`__main__.py:185-192`):
```python
app = QApplication(argv)
app.setApplicationName("MusicStreamer")              # D-07: keep
app.setApplicationDisplayName("MusicStreamer")       # D-06: NEW (Phase 61)
app.setApplicationVersion(_pkg_version("musicstreamer"))  # Phase 65 D-07
app.setDesktopFileName(constants.APP_ID)             # D-02
if sys.platform == "win32":
    app.setStyle("Fusion")          # D-14: BEFORE widget construction
    _apply_windows_palette(app)     # D-15: dark-mode palette if applicable
```
**Apply for Phase 66:** the `sys.platform == "win32"` block is **moved into** `theme.apply_theme_palette` (the `theme == 'system'` Windows branch — CONTEXT.md D-23.1). The new insertion replaces lines 190-192 with:
```python
# Phase 66: theme palette FIRST. Replaces _apply_windows_palette unless theme=='system'.
con = db_connect()
db_init(con)
repo = Repo(con)
from musicstreamer import theme
theme.apply_theme_palette(app, repo)
```
And deletes the prior `con = db_connect(); db_init(con); ...; repo = Repo(con)` block at lines 210-213 (so the same `repo` is reused for `MainWindow(player, repo, node_runtime=...)` at line 215). RESEARCH Pitfall 5 documents this reorder.

**Existing `_apply_windows_palette` is UNCHANGED** (`__main__.py:69-99`). It is now called only from inside `theme.apply_theme_palette` when `theme == 'system'` on Windows.

---

### `musicstreamer/ui_qt/main_window.py` (modified, component)

**Analog:** `main_window.py:188-189` (`act_accent` action) + `main_window.py:776-779` (`_open_accent_dialog` slot)

**Existing accent-action pattern** (`main_window.py:185-189`):
```python
self._menu.addSeparator()

# Group 2: Settings dialogs (D-16, D-17, D-18)
act_accent = self._menu.addAction("Accent Color")
act_accent.triggered.connect(self._open_accent_dialog)
```
**Apply for Phase 66:** insert immediately ABOVE `act_accent` at line 188 (CONTEXT.md D-15):
```python
self._menu.addSeparator()

# Group 2: Settings dialogs (D-16, D-17, D-18)
act_theme = self._menu.addAction("Theme")  # Phase 66 / THEME-01
act_theme.triggered.connect(self._open_theme_dialog)  # QA-05 bound method

act_accent = self._menu.addAction("Accent Color")
act_accent.triggered.connect(self._open_accent_dialog)
```

**Existing dialog-opener slot pattern** (`main_window.py:776-779`):
```python
def _open_accent_dialog(self) -> None:
    """D-16: Open AccentColorDialog from hamburger menu."""
    dlg = AccentColorDialog(self._repo, parent=self)
    dlg.exec()
```
**Apply for Phase 66:** add lazy-import slot above `_open_accent_dialog`:
```python
def _open_theme_dialog(self) -> None:
    """Phase 66 D-15: Open ThemePickerDialog from hamburger menu."""
    from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog  # lazy import
    dlg = ThemePickerDialog(self._repo, parent=self)
    dlg.exec()
```
Lazy import matches `_open_equalizer_dialog` precedent (`main_window.py:792-796`).

**Existing accent restore at startup** (`main_window.py:241-245`) is **UNCHANGED**:
```python
# D-12: apply saved accent color on startup (UI-11)
_saved_accent = self._repo.get_setting("accent_color", "")
if _saved_accent and _is_valid_hex(_saved_accent):
    from PySide6.QtWidgets import QApplication
    apply_accent_palette(QApplication.instance(), _saved_accent)
```
This now runs AFTER `theme.apply_theme_palette` (which fires from `__main__._run_gui` before `MainWindow` is constructed), so accent layers on top of theme baseline (CONTEXT.md D-23.2).

---

### `.planning/REQUIREMENTS.md` (modified, doc)

**Analog:** `REQUIREMENTS.md:40` (FEAT entry) + `REQUIREMENTS.md:96` (traceability row)

**Existing FEAT entry pattern** (`REQUIREMENTS.md:40`):
```markdown
- [x] **ACCENT-02**: User can pick a custom accent color via a visual color picker (HSV/wheel surface), in addition to the existing 8 presets and hex entry *(harvest: SEED-006)*
```
**Apply:** add new entry under `### Features (FEAT)` (around line 41-42, after ACCENT-02):
```markdown
- [ ] **THEME-01**: User can switch between preset color themes (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light) and a single user-editable Custom palette via a "Theme" entry in the hamburger menu. The chosen theme drives the application QPalette's 9 primary roles (Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, HighlightedText, Link). The accent_color override (Phase 59 / ACCENT-02) continues to layer on top of the theme's Highlight baseline; selecting a theme does NOT mutate `accent_color`.
```

**Existing traceability row pattern** (`REQUIREMENTS.md:96`):
```markdown
| ACCENT-02 | Phase 59 | Complete |
```
**Apply:** insert new row in the table (`REQUIREMENTS.md:82-101`), keeping phase-numerical order:
```markdown
| THEME-01 | Phase 66 | Pending |
```

**Coverage counts at line 103-107** must increment: `v2.1 requirements: 19 total`, `Mapped to phases: 19`, `Pending: 17`.

---

### `.planning/ROADMAP.md` (modified, doc)

**Analog:** `ROADMAP.md:509-528` (Phase 65 completed-phase block — currently the closest fully-fleshed sibling)

**Existing completed-phase block pattern** (`ROADMAP.md:509-527`):
```markdown
### Phase 65: Show current version in app
**Goal:** The running app shows its current version (e.g. `v2.1.65`) as a disabled informational entry at the bottom of the hamburger menu, sourced at runtime from `pyproject.toml` via `importlib.metadata.version("musicstreamer")`. ...
**Depends on:** Phase 63 (auto-bump produces the version Phase 65 reads)

Plans:
- [x] 65-01-PLAN.md — ...
- [x] 65-02-PLAN.md — ...
```

**Existing placeholder block to replace** (`ROADMAP.md:529-537`):
```markdown
### Phase 66: Color Themes — preset and custom color schemes (Vaporwave pastel, Overrun neon+black)

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 65
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 66 to break down)
```

**Apply:** replace placeholder with concrete Goal + Requirements drawn from CONTEXT.md/RESEARCH.md, leave the `Plans:` checklist for the planner to fill from the plan files it generates. Match Phase 65's voice and field order verbatim.

---

## Shared Patterns

### Authentication / Authorization
**N/A.** Single-user desktop app; no auth boundary inside the app process. UI-SPEC §"Files Owned by This Contract" confirms no security perimeter is added by Phase 66.

### Defense-in-depth hex validation
**Source:** `musicstreamer/accent_utils.py:11-13` (`_is_valid_hex`)
**Apply to:** every hex value entering `theme.py`, `theme_picker_dialog.py`, and `theme_editor_dialog.py` — specifically before any `QColor(hex_value)` construction.
```python
def _is_valid_hex(value: str) -> bool:
    """Return True if value is a valid 3- or 6-digit hex color string."""
    return bool(_HEX_RE.match(value))
```
Call sites (per CONTEXT.md / RESEARCH Pitfall 3): `build_palette_from_dict` (skip invalid roles), `_on_role_color_changed` (return early if invalid), `apply_theme_palette` corrupt-JSON branch (skip non-dict / unknown roles silently), parent `accent_color` re-impose path (matches existing `main_window.py:243`).

### Snapshot-and-restore for live-preview cancel
**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:48-50` (snapshot) + `:155-163` (restore)
**Apply to:** both `theme_picker_dialog.py.__init__` and `theme_editor_dialog.py.__init__` (snapshot palette + styleSheet); both dialogs' `reject()` (restore). Picker adds `_save_committed` short-circuit per UI-SPEC §"Modal stacking".
```python
# In __init__:
app = QApplication.instance()
self._original_palette = app.palette()
self._original_qss = app.styleSheet()

# In reject():
def reject(self) -> None:
    app = QApplication.instance()
    app.setPalette(self._original_palette)
    app.setStyleSheet(self._original_qss)
    super().reject()
```

### Accent override re-imposition after every theme mutation
**Source:** `musicstreamer/accent_utils.py:54-65` (`apply_accent_palette`)
**Apply to:** `theme_picker_dialog._on_tile_clicked`, `theme_editor_dialog._on_role_color_changed`, `theme_editor_dialog._on_reset` — all three paths must call:
```python
accent = self._repo.get_setting("accent_color", "")
if accent and _is_valid_hex(accent):
    apply_accent_palette(app, accent)
```
This is the **load-bearing layering contract** from Phase 59 D-02 — preserves `accent_color` Highlight on top of any theme palette. RESEARCH Pitfall 2 calls this out explicitly.

### Bound-method signal connections (QA-05)
**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:88, 102-104` + project convention `.planning/codebase/CONVENTIONS.md`
**Apply to:** every `connect(...)` call in both new dialogs. **No** `connect(lambda ...)` (auditor predicate UI-SPEC §"Audit Hooks" `grep -E 'connect\(lambda' theme_picker_dialog.py theme_editor_dialog.py` must return nothing).
```python
self._apply_btn.clicked.connect(self._on_apply)        # bound method — OK
self._customize_btn.clicked.connect(self._on_customize) # bound method — OK
tile.clicked.connect(self._on_tile_clicked)            # OK; slot reads sender()._theme_id
# OR via partial held as instance attribute:
tile._click_handler = functools.partial(self._on_tile_clicked, theme_id)
tile.clicked.connect(tile._click_handler)
```

### Modal `setModal(True)` + Esc/X routing through `reject()`
**Source:** `accent_color_dialog.py:54` (`setModal(True)`) + `:155-163` (`reject` handles both Esc and WM-close)
**Apply to:** both new dialogs. Tested via `test_window_close_behaves_like_cancel` pattern (`test_accent_color_dialog.py:170-178`). Project convention: every dialog uses `setModal(True)` (CONTEXT.md "Established Patterns" + UI-SPEC §"Modality & lifecycle").

### `DontUseNativeDialog` for QColorDialog on Wayland
**Source:** `accent_color_dialog.py:67`
**Apply to:** `theme_editor_dialog.py._on_swatch_clicked` `QColorDialog.getColor(initial, parent, title, QColorDialog.ColorDialogOption.DontUseNativeDialog)`. Required for consistent Wayland rendering + avoids xdg-desktop-portal slowness (RESEARCH Q15 + UI-SPEC §"Wayland DPR=1.0 deployment target").

### 8/8/8/8 contentsMargins + spacing 8 (Phase 59 layout token)
**Source:** `accent_color_dialog.py:90-93`
**Apply to:** wrapper `QVBoxLayout` of both new dialogs. Auditor predicate: `grep -E 'setContentsMargins\(8, 8, 8, 8\)' theme_picker_dialog.py theme_editor_dialog.py`.

### Lazy import of dialog classes from MainWindow slots
**Source:** `main_window.py:792-796` (`_open_equalizer_dialog`)
```python
def _open_equalizer_dialog(self) -> None:
    """Phase 47.2 D-07: Open EqualizerDialog from hamburger menu."""
    from musicstreamer.ui_qt.equalizer_dialog import EqualizerDialog
    dlg = EqualizerDialog(self._player, self._repo, self.show_toast, parent=self)
    dlg.exec()
```
**Apply to:** `_open_theme_dialog` — lazy-imports `ThemePickerDialog` to keep `main_window.py` import graph small. (Note: existing `_open_accent_dialog` does **not** lazy-import; theme dialog is new so we follow the more recent convention from Phase 47.2.)

### Defense-in-depth `isinstance(dict)` for JSON-loaded settings
**Source (new for Phase 66):** RESEARCH §`apply_theme_palette` snippet — no exact existing analog (no other code path in the project loads JSON from `repo.get_setting`). Pattern is structurally analogous to `accent_utils._is_valid_hex` — verify shape before passing to consumer.
**Apply to:** `theme.apply_theme_palette` and `theme_picker_dialog._on_tile_clicked` (Custom branch):
```python
try:
    role_hex = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    role_hex = {}
if not isinstance(role_hex, dict):
    role_hex = {}
```

---

## No Analog Found

No new code path in Phase 66 lacks a close codebase analog. The only structural novelty is the `_ThemeTile` widget (a `QPushButton` subclass with custom `paintEvent` rendering a 4-color stripe + name label + active checkmark) — but its **interaction shape** (click → emit a discrete signal → live-preview wiring) is identical to the existing `accent_color_dialog._inner.currentColorChanged` flow, so the connection idiom transfers cleanly.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All 10 NEW/MODIFIED files have a strong analog. |

**`_ThemeTile` paintEvent reference (no in-codebase paintEvent analog for QPushButton subclasses):** the planner should reference PySide6 6.11 `QPushButton.paintEvent` docs and the in-codebase `eq_response_curve.py:138-153` paintEvent pattern (which reads `self.palette()` per paint — confirms Qt's PaletteChange auto-update). The 4-stripe rendering is a small `QPainter.fillRect` loop; no architectural risk.

---

## Metadata

**Analog search scope:**
- `musicstreamer/` (full tree)
- `musicstreamer/ui_qt/` (full tree)
- `tests/` (full tree)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`

**Files scanned:** 12 directly read + ~30 grep-matched (via Bash `grep`/`ls`)

**Pattern extraction date:** 2026-05-09

**Phase 59 idiom inheritance audit (per UI-SPEC §"Audit Hooks"):** every load-bearing pattern in this map traces back to `accent_color_dialog.py` or `accent_utils.py`. The new `_save_committed` flag (UI-SPEC §"Modal stacking" Pitfall 1) is the only Phase-66-original interaction primitive; it is documented in the picker's `reject()` deviation above and tested via the editor's `test_parent_save_flag_set` test.
