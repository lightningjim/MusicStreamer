# Phase 59: Visual Accent Color Picker — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 2 (1 source rewrite + 1 test rewrite)
**Analogs found:** 2 / 2

---

## File Classification

| New / Modified File | Status | Role | Data Flow | Closest Analog | Match Quality |
|----|----|----|----|----|----|
| `musicstreamer/ui_qt/accent_color_dialog.py` | REWRITE (235 → ~80–130 LOC) | UI / modal dialog wrapper hosting a complex Qt widget + button row | request-response (modal `exec()` returns Accepted / Rejected), with side-effect persistence (SQLite `set_setting` + on-disk QSS write) and live-preview signal handling | `musicstreamer/ui_qt/accent_color_dialog.py` (current) — same role, identical public API, supplies the snapshot/restore pattern. **Plus** `musicstreamer/ui_qt/equalizer_dialog.py` for the QDialog + complex inner widget + QDialogButtonBox role-based button row + bound-method connect convention. | exact (self-analog) + role-match (Equalizer) |
| `tests/test_accent_color_dialog.py` | REWRITE (107 LOC) | Test / pytest-qt widget smoke tests | request-response (synchronous slot invocation), assertion of repo state + on-disk file state + emitted signal | `tests/test_accent_color_dialog.py` (current) — supplies the FakeRepo + qtbot fixture pattern. **Plus** `tests/test_equalizer_dialog.py` for monkeypatch-of-Qt-stdlib-dialogs + tmp_path-via-`paths._root_override` + `qtbot.waitSignal` wiring (used here for `currentColorChanged`). | exact (self-analog) + role-match (Equalizer) |

**Untouched files (no pattern needed — confirmed in CONTEXT.md):**
- `musicstreamer/accent_utils.py` — 4 helpers reused as-is.
- `musicstreamer/constants.py` — `ACCENT_PRESETS` (lines 74–83) + `ACCENT_COLOR_DEFAULT` (line 73) survive.
- `musicstreamer/ui_qt/main_window.py` — `from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog` at line 53; launcher at lines 680–683 (`dlg = AccentColorDialog(self._repo, parent=self); dlg.exec()`).
- `musicstreamer/paths.py` — `accent_css_path()` at lines 59–60 (write target on Apply).
- `tests/test_accent_provider.py` — exercises `accent_utils.py` only; verify in plan-checker that no test references the removed swatch grid.

---

## Pattern Assignments

### `musicstreamer/ui_qt/accent_color_dialog.py` (REWRITE)

**Primary analog (snapshot/restore + Apply path + reject pattern):** the file as it exists today. Even though we are rewriting it, the snapshot/restore plumbing, Apply persistence path, and `reject()` override are load-bearing patterns to preserve verbatim — they are the Phase 19/40 invariant.

**Secondary analog (QDialog wrapper + complex inner widget + QDialogButtonBox row):** `musicstreamer/ui_qt/equalizer_dialog.py`.

#### Imports pattern (preserve from `accent_color_dialog.py:9–35`)

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,        # NEW for Phase 59
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
)
from PySide6.QtGui import QColor

from musicstreamer.accent_utils import (
    _is_valid_hex,
    apply_accent_palette,
    build_accent_qss,
    reset_accent_palette,
)
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer import paths
```

**Removed imports** (Phase 59 drops these — only `QApplication`, `QDialog`, `QDialogButtonBox`, `QVBoxLayout`, `QColor` survive from the QtWidgets/QtGui set):
- `functools` (used only by `_on_swatch_clicked` partial — no longer needed)
- `Qt` from `QtCore` (used only by `Qt.PointingHandCursor` + `Qt.PlainText` for the swatch grid + section label — both removed)
- `QFont` (used only by the `setPointSize(10) + DemiBold` section label — removed per UI-SPEC)
- `QGridLayout`, `QHBoxLayout`, `QLabel`, `QLineEdit`, `QPushButton` (swatch grid + hex entry are removed)
- `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` (used only for the hex-entry red border — `QColorDialog` cannot produce invalid hex)

**Note:** `os` is imported INSIDE `_on_apply` (`accent_color_dialog.py:177`) — keep that pattern unless the planner decides to hoist it. Either is fine; today's file uses lazy import for `os`.

#### Class declaration + constructor signature (preserve verbatim from `accent_color_dialog.py:38–46`)

```python
class AccentColorDialog(QDialog):
    """Modal dialog for selecting an accent color via QColorDialog."""

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._current_hex: str = ""
```

**Why preserve:** D-08 locks the constructor signature `AccentColorDialog(repo, parent=None)` so `main_window.py:680–683` continues to work. The snapshot lines (49–51 in current file) ARE the Phase 19/40 invariant — copy verbatim. Drop `self._selected_idx` (used only by the removed swatch grid).

#### Window setup pattern (adapt from `accent_color_dialog.py:55–57`)

```python
        self.setWindowTitle("Accent Color")
        self.setModal(True)
        # DROP: self.setMinimumWidth(360) — UI-SPEC RESEARCH Pitfall 7 says
        # the inner QColorDialog reports sizeHint() == QSize(522, 387) and
        # dominates the wrapper minimum; the 360px hint is dead.
```

#### Idempotent custom-color seed (NEW — D-03; from RESEARCH.md Pattern 1, lines 233–236)

```python
        # D-03: Seed ACCENT_PRESETS into Custom Colors slots BEFORE inner dialog
        # construction. setCustomColor is a STATIC method; persists for process
        # lifetime. Idempotent — slots 0..7 are reset to curated presets every
        # __init__ even if the user edited them via the inner dialog's
        # "Add to Custom Colors" button in a previous instance this session.
        for idx, hex_val in enumerate(ACCENT_PRESETS):  # 0..7
            QColorDialog.setCustomColor(idx, QColor(hex_val))
```

**Verifier predicate (UI-SPEC line 303):** `setCustomColor` line numbers MUST be < `QColorDialog(self)` line number.

#### Inner QColorDialog construction (NEW — D-04, D-05; from RESEARCH.md Pattern 1, lines 239–243)

```python
        self._inner = QColorDialog(self)
        self._inner.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
```

#### Pre-populate on open (D-17; from `accent_color_dialog.py:124–137` adapted)

```python
        # D-17 + UI-SPEC color-flash guard: validate before setCurrentColor or
        # the picker would briefly mutate to QColor("invalid") == #000000.
        saved = self._repo.get_setting("accent_color", "")
        initial = saved if _is_valid_hex(saved) else ACCENT_COLOR_DEFAULT
        self._inner.setCurrentColor(QColor(initial))
        self._current_hex = initial   # set BEFORE wiring the slot below
                                      # (currentColorChanged emits during
                                      # setCurrentColor; if we wire first we
                                      # double-apply, if we wire after we
                                      # need this manual seed — RESEARCH
                                      # Pitfall 6).
```

**Pattern source:** the `_load_saved_accent` method at `accent_color_dialog.py:124–137` already does the `_is_valid_hex` defensive check before mutating UI state — preserve the same guard, just route through `setCurrentColor` instead of `_hex_edit.setText` + `_select_swatch`.

#### Live-preview wiring (D-11, D-12; bound method per QA-05; from RESEARCH.md Pattern 2)

```python
        # QA-05: bound method, NOT lambda. UI-SPEC verifier predicate:
        #   grep -E 'currentColorChanged\.connect\(self\._' MUST match
        #   grep -E 'connect\(lambda' MUST NOT match
        self._inner.currentColorChanged.connect(self._on_color_changed)
```

```python
    def _on_color_changed(self, color: QColor) -> None:
        """Live-preview the selected color."""
        self._current_hex = color.name()  # lowercase #rrggbb
        apply_accent_palette(QApplication.instance(), self._current_hex)
```

**Anti-pattern reference:** today's file uses `functools.partial(self._on_swatch_clicked, idx)` at line 92 — that is acceptable per QA-05 (partial captures `self` via the bound method, not a closure), but the new file should not need any partial / lambda at all. Every `connect()` call routes to a parameterless or signal-typed bound method.

#### Layout pattern (adapt from `accent_color_dialog.py:67–69` + UI-SPEC §Spacing Scale)

```python
        # UI-SPEC: 8/8/8/8 contentsMargins + 8 spacing (sm token).
        # Old file used 16/16/16/16 + 16 spacing (md) — reduced per Pitfall 7
        # so the wrapper does not visually inflate beyond the inner
        # QColorDialog's intrinsic 522x387 footprint.
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._inner)
```

#### Button row (preserve verbatim from `accent_color_dialog.py:111–118`)

```python
        # D-09: Apply | Reset | Cancel ordering preserved from current file.
        # UI-SPEC: Apply is the AcceptRole DEFAULT button (Enter triggers it).
        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.setDefault(True)   # NEW for Phase 59 — Enter→Apply
        self._apply_btn.clicked.connect(self._on_apply)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)
```

**Pattern source:** identical to `equalizer_dialog.py:176–179` (which uses just a Close button at RejectRole) and `accent_color_dialog.py:111–118` (which uses all three roles in this exact order). The Phase 59 file copies the 3-button shape verbatim and adds `setDefault(True)` on Apply.

#### Apply handler (preserve verbatim from `accent_color_dialog.py:171–184`)

```python
    def _on_apply(self) -> None:
        """Save accent_color to repo, write QSS file, accept dialog."""
        # D-14.1: defense-in-depth via _is_valid_hex even though
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
            pass  # Non-fatal — palette is already applied via QPalette
        self.accept()
```

**Why preserve:** every line of this method is reused verbatim. The `try/except OSError: pass` wrapping is the established pattern for QSS-file writes (`accent_color_dialog.py:176–183`).

#### Reset handler (adapt from `accent_color_dialog.py:186–196`)

```python
    def _on_reset(self) -> None:
        """Clear saved accent setting, restore snapshot palette, reset picker.

        Per D-15: dialog STAYS OPEN after Reset.
        """
        self._repo.set_setting("accent_color", "")
        reset_accent_palette(QApplication.instance(), self._original_palette)
        # D-15.3: visually return picker to default blue.
        self._inner.blockSignals(True)
        self._inner.setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))
        self._inner.blockSignals(False)
        self._current_hex = ""
        # D-15.6 (Claude's Discretion — planner picks one):
        # (a) leave paths.accent_css_path() alone
        # (b) write empty string to it
        # (c) os.remove(...) wrapped in try/except OSError: pass
        # Recommended: (c) for clean on-disk state.
```

**`blockSignals` rationale:** `setCurrentColor(QColor(DEFAULT))` would otherwise emit `currentColorChanged`, which calls `_on_color_changed`, which would re-set `self._current_hex = "#3584e4"` — defeating the `_current_hex = ""` guard on the next Apply. Block during the visual reset, set `_current_hex = ""` afterward. (Pattern source: `accent_color_dialog.py:128–130` and `accent_color_dialog.py:147–149` already use `blockSignals` on the hex edit for exactly this reason.)

#### Reject handler (preserve verbatim from `accent_color_dialog.py:198–203`)

```python
    def reject(self) -> None:
        """Cancel — restore snapshot palette and QSS without saving."""
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
        super().reject()
```

**Why preserve:** identical Phase 19/40 invariant. Window-manager close (X) routes through `reject()` automatically (Qt convention) — no `closeEvent` override needed.

---

### `tests/test_accent_color_dialog.py` (REWRITE)

**Primary analog (FakeRepo + qtbot fixture):** the file as it exists today, lines 19–43.
**Secondary analog (monkeypatch-of-Qt-stdlib + tmp_path-via-`paths._root_override` + `qtbot.waitSignal`):** `tests/test_equalizer_dialog.py`.

#### FakeRepo class (preserve verbatim from `tests/test_accent_color_dialog.py:19–27`)

```python
class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
```

**Why preserve:** identical FakeRepo lives in `tests/test_equalizer_dialog.py:29–37` and is the canonical project pattern. No change needed.

#### Imports pattern (adapt from `tests/test_accent_color_dialog.py:1–12`)

```python
from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog

from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog
```

**Removed:** `from PySide6.QtWidgets import QPushButton` (the `_swatches` list is gone).

#### Fixtures (preserve verbatim from `tests/test_accent_color_dialog.py:34–43`)

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

**Why preserve:** identical pattern to `tests/test_equalizer_dialog.py:59–95` (which adds `player`, `toast_sink`, `_eq_root` to the dialog fixture — Phase 59 only needs `repo`).

#### Optional `_root_override` fixture for the QSS-write test (NEW — adapt from `tests/test_equalizer_dialog.py:81–88`)

```python
@pytest.fixture
def _accent_root(tmp_path, monkeypatch):
    """Redirect paths.accent_css_path() under tmp_path for write-side tests."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return tmp_path
```

**Why:** the Apply path calls `os.makedirs(os.path.dirname(paths.accent_css_path()), exist_ok=True)` and writes `paths.accent_css_path()`. The `_eq_root` fixture in `tests/test_equalizer_dialog.py:81–88` is the project-canonical way to redirect that under `tmp_path`. Without it, the test pollutes the user's actual config directory.

#### Test patterns (per D-18 — replaces every test in the current file)

**Pattern: assert idempotent custom-color seed (NEW — D-03)**

Source pattern: combine the assertion pattern from `tests/test_accent_color_dialog.py:50–55` (assert dialog state after construction) with the empirical verification noted in RESEARCH.md line 167 (`QColor.name()` returns lowercase `#rrggbb`).

```python
def test_custom_colors_seeded_with_presets(dialog):
    """Custom Colors slots 0..7 == ACCENT_PRESETS after dialog construction."""
    for idx, expected_hex in enumerate(ACCENT_PRESETS):
        assert QColorDialog.customColor(idx).name() == expected_hex.lower()
```

**Pattern: pre-populate from saved hex (NEW — D-17, replaces `test_load_saved_accent_selects_swatch`)**

Source pattern: `tests/test_accent_color_dialog.py:101–107` already constructs a fresh dialog with a pre-seeded repo. Replace `_selected_idx` / `_hex_edit.text()` assertions with `_inner.currentColor().name()`.

```python
def test_load_saved_accent_pre_selects_color(qtbot, repo):
    """Dialog opens with currentColor == saved accent_color."""
    repo.set_setting("accent_color", ACCENT_PRESETS[4])  # Orange
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._inner.currentColor().name() == ACCENT_PRESETS[4].lower()
    assert dlg._current_hex == ACCENT_PRESETS[4]
```

**Pattern: invalid saved hex falls back to DEFAULT (NEW — UI-SPEC color-flash guard)**

```python
def test_corrupt_saved_hex_falls_back_to_default(qtbot, repo):
    """An invalid saved hex must NOT propagate to setCurrentColor (no black flash)."""
    repo.set_setting("accent_color", "not-a-hex")
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    assert dlg._inner.currentColor().name() == ACCENT_COLOR_DEFAULT.lower()
```

**Pattern: live preview emits + applies (NEW — D-11, replaces `test_swatch_populates_hex_entry`)**

Source pattern: `qtbot.waitSignal` from `tests/test_edit_station_dialog.py:971` (`with qtbot.waitSignal(d.navigate_to_sibling, timeout=1000) as blocker`). Same shape, different signal.

```python
def test_currentColorChanged_drives_live_preview(qtbot, dialog):
    """Setting a new color emits currentColorChanged and updates _current_hex."""
    target = QColor("#9141ac")  # Purple
    with qtbot.waitSignal(dialog._inner.currentColorChanged, timeout=1000):
        dialog._inner.setCurrentColor(target)
    assert dialog._current_hex == "#9141ac"
```

**Note (RESEARCH.md line 14):** `setCurrentColor` to the SAME color is a no-op (no signal emission). If this test is flaky because the dialog was constructed with `ACCENT_COLOR_DEFAULT` and the test then sets `ACCENT_COLOR_DEFAULT` again, the signal won't fire — pick a color different from the initial.

**Pattern: Apply persists hex + writes QSS file (preserve from `tests/test_accent_color_dialog.py:64–68`, extend with file-system assertion)**

```python
def test_apply_saves_setting_and_writes_qss_file(qtbot, dialog, repo, _accent_root):
    """Apply persists hex to repo and writes accent.css."""
    import os
    from musicstreamer import paths
    dialog._inner.setCurrentColor(QColor("#9141ac"))
    dialog._on_apply()
    assert repo.get_setting("accent_color", "") == "#9141ac"
    assert os.path.isfile(paths.accent_css_path())
```

**Pattern: Reset clears repo + restores snapshot + keeps dialog open (extend from `tests/test_accent_color_dialog.py:71–76`)**

```python
def test_reset_clears_setting_and_keeps_dialog_open(qtbot, dialog, repo):
    """Reset writes empty string + dialog is still open afterward."""
    repo.set_setting("accent_color", ACCENT_PRESETS[2])
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[2]))
    dialog._on_reset()
    assert repo.get_setting("accent_color", "UNSET") == ""
    assert dialog._current_hex == ""
    assert dialog.isVisible() is False  # never shown — still "open" in the sense
                                        # that accept()/reject() were not called
```

**Pattern: Cancel does not write repo (preserve verbatim from `tests/test_accent_color_dialog.py:93–98`)**

```python
def test_cancel_does_not_save(qtbot, dialog, repo):
    """Cancel restores palette without saving to repo."""
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[3]))
    dialog.reject()
    assert repo.get_setting("accent_color", "UNSET") == "UNSET"
```

**Pattern: window-manager close (X) routes through reject (NEW — UI-SPEC line 141)**

```python
def test_close_event_routes_through_reject(qtbot, dialog, repo):
    """Calling close() (simulating WM X button) triggers reject()."""
    repo.set_setting("accent_color", "UNSET-MARKER")  # don't actually save
    dialog._inner.setCurrentColor(QColor(ACCENT_PRESETS[5]))
    dialog.close()  # Qt routes this through reject() for modal dialogs
    assert repo.get_setting("accent_color", "") == "UNSET-MARKER"
```

---

## Shared Patterns

### Snapshot-and-restore for live-preview cancel

**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:49–51, 198–203` (Phase 19/40 invariant)
**Apply to:** `accent_color_dialog.py` rewrite (this is the load-bearing cancel-safety pattern)

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

### Bound-method signal connections (QA-05)

**Source:** `musicstreamer/ui_qt/equalizer_dialog.py:112, 148, 166, 171` and `musicstreamer/ui_qt/accounts_dialog.py:101, 114`
**Apply to:** every `connect()` call in `accent_color_dialog.py`

```python
# CORRECT — bound method:
self._inner.currentColorChanged.connect(self._on_color_changed)
self._apply_btn.clicked.connect(self._on_apply)
self._reset_btn.clicked.connect(self._on_reset)
self._cancel_btn.clicked.connect(self.reject)

# FORBIDDEN — self-capturing lambda:
# self._inner.currentColorChanged.connect(lambda c: self._on_color_changed(c))
```

**UI-SPEC verifier predicate (line 301):** `grep -E 'connect\(lambda' accent_color_dialog.py` MUST return nothing.

### `_is_valid_hex` defense-in-depth on every UI→repo boundary

**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:127, 155, 173`
**Apply to:** `accent_color_dialog.py` rewrite — both the Apply path AND the pre-populate path

```python
# Pre-populate (D-17 + UI-SPEC color-flash guard):
saved = self._repo.get_setting("accent_color", "")
initial = saved if _is_valid_hex(saved) else ACCENT_COLOR_DEFAULT

# Apply (D-14.1):
if not self._current_hex or not _is_valid_hex(self._current_hex):
    return
```

### QSS-file write wrapped in try/except OSError

**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:176–183`
**Apply to:** `_on_apply` in the rewrite (verbatim copy)

```python
try:
    import os
    css_path = paths.accent_css_path()
    os.makedirs(os.path.dirname(css_path), exist_ok=True)
    with open(css_path, "w") as f:
        f.write(build_accent_qss(self._current_hex))
except OSError:
    pass  # Non-fatal — palette is already applied via QPalette
```

### Modal QDialog with `setModal(True)` + `setWindowTitle(...)`

**Source:** `musicstreamer/ui_qt/equalizer_dialog.py:91–94`, `musicstreamer/ui_qt/accent_color_dialog.py:55–57`, `musicstreamer/ui_qt/accounts_dialog.py:81–82`, `musicstreamer/ui_qt/edit_station_dialog.py` (every dialog in the project)
**Apply to:** `accent_color_dialog.py` rewrite

```python
self.setWindowTitle("Accent Color")
self.setModal(True)
# DROP setMinimumWidth(360) — UI-SPEC Pitfall 7
```

### `QDialogButtonBox` with role-based `addButton`

**Source:** `musicstreamer/ui_qt/accent_color_dialog.py:111–118` (3-role) and `musicstreamer/ui_qt/equalizer_dialog.py:176–179` (1-role)
**Apply to:** `accent_color_dialog.py` rewrite

```python
btn_box = QDialogButtonBox()
self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
self._apply_btn.setDefault(True)   # Enter→Apply
```

### FakeRepo + qtbot fixture pattern for dialog tests

**Source:** `tests/test_accent_color_dialog.py:19–43` and `tests/test_equalizer_dialog.py:29–95`
**Apply to:** `tests/test_accent_color_dialog.py` rewrite

```python
class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}
    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)
    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def dialog(qtbot, repo):
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)
    return dlg
```

### `paths._root_override` monkeypatch for filesystem-touching tests

**Source:** `tests/test_equalizer_dialog.py:81–88`
**Apply to:** the QSS-file-write test in `tests/test_accent_color_dialog.py` rewrite

```python
@pytest.fixture
def _accent_root(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return tmp_path
```

### `qtbot.waitSignal` for Qt signal assertions

**Source:** `tests/test_edit_station_dialog.py:971, 998, 1062`
**Apply to:** the live-preview test in `tests/test_accent_color_dialog.py` rewrite

```python
with qtbot.waitSignal(dialog._inner.currentColorChanged, timeout=1000):
    dialog._inner.setCurrentColor(target)
```

**Caveat (RESEARCH.md line 14):** `setCurrentColor` to the same already-set color is a no-op (no signal emission). Pick a target color different from the dialog's initial color — or use `timeout=0` and poll `currentColor()` directly.

---

## No Analog Found

None. Every concern in Phase 59 has a concrete project-internal analog:
- Wrapper-around-complex-Qt-widget shape: `EqualizerDialog` (response curve + sliders) + the existing `AccentColorDialog` (swatch grid + hex edit).
- Live-preview-with-snapshot-cancel: the existing `AccentColorDialog` (Phase 19/40 invariant).
- Modal QDialog + `QDialogButtonBox` + role-based buttons: every dialog in `musicstreamer/ui_qt/`.
- pytest-qt FakeRepo + qtbot fixture: `tests/test_accent_color_dialog.py` (current) + `tests/test_equalizer_dialog.py`.
- `qtbot.waitSignal`: `tests/test_edit_station_dialog.py`.
- `paths._root_override` for hermetic file-system tests: `tests/test_equalizer_dialog.py`.

**Genuinely new (no codebase analog — must follow RESEARCH.md):**
- `QColorDialog` itself (no prior usage anywhere in `musicstreamer/`). Pattern source is RESEARCH.md "Pattern 1: Embed `QColorDialog` as a child widget" (lines 207–270) which is empirically verified against PySide6 6.11.0.
- `setCustomColor` static-method seeding. Pattern source is RESEARCH.md D-03 commentary + Pattern 1 lines 233–236.

---

## Metadata

**Analog search scope:**
- `musicstreamer/ui_qt/*.py` — all 17 UI modules (focus on dialogs: `accent_color_dialog.py`, `accounts_dialog.py`, `cookie_import_dialog.py`, `discovery_dialog.py`, `edit_station_dialog.py`, `equalizer_dialog.py`, `import_dialog.py`, `settings_import_dialog.py`)
- `tests/test_*dialog*.py` — 8 dialog test files
- `musicstreamer/accent_utils.py`, `musicstreamer/constants.py`, `musicstreamer/paths.py` — direct callees of the rewritten dialog
- `tests/test_accent_provider.py` — to confirm no removed-swatch references (UI-SPEC verifier sign-off)

**Files scanned:** ~25 files read or grep'd
**`QColorDialog` prior usage check:** zero hits in `musicstreamer/**/*.py` — Phase 59 introduces the first usage in the codebase

**Pattern extraction date:** 2026-05-03
