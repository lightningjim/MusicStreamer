# Phase 75: Extend theme coloring to include toast colors — Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 9 (5 code + 1 doc + 4 tests, including 1 implicit `_theme_editor_dialog.py` only-labels)
**Analogs found:** 9 / 9 (every modified file has an in-tree analog — Phase 75 is a pure extension of Phase 66 patterns)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/theme.py` | palette source (preset dicts + EDITABLE_ROLES tuple + `apply_theme_palette`) | config → palette → QApplication | self (extend in place — Phase 66 baseline) | exact (extend) |
| `musicstreamer/ui_qt/toast.py` | widget consumer (palette-driven QSS rebuild + changeEvent) | palette → QSS string → setStyleSheet | `musicstreamer/ui_qt/now_playing_panel.py:194-197` `_MutedLabel.changeEvent` + `musicstreamer/ui_qt/eq_response_curve.py:121-124` | role-match (changeEvent template); pattern-NEW (setStyleSheet inside changeEvent — first site) |
| `musicstreamer/ui_qt/theme_picker_dialog.py` | live-preview palette mutator (mirror `setProperty("theme_name", ...)`) | tile click → `app.setPalette` + `app.setProperty` | self (Phase 66 `_on_tile_clicked` lines 260-285) | exact (extend) |
| `musicstreamer/ui_qt/theme_editor_dialog.py` | UI labels dict (additive `ROLE_LABELS` entries — rows auto-grow via `EDITABLE_ROLES` iteration) | EDITABLE_ROLES tuple → 11 `_ColorRow` instances | self (Phase 66 `ROLE_LABELS` dict at lines 37-47, iteration loop at lines 161-167) | exact (extend) |
| `.planning/REQUIREMENTS.md` | requirement doc (add THEME-02 + traceability row) | docs-only | self (THEME-01 entry at line 44 + status table at line 154) | exact (extend) |
| `tests/test_toast_overlay.py` | test harness (line 143 retrofit + new palette/changeEvent/geometry/typography assertions) | mutate `qapp.setProperty` + `qapp.setPalette` → assert toast.styleSheet() | self (existing 14-test file with `parent_widget` fixture lines 19-26) | exact (extend) |
| `tests/test_theme.py` | test harness (per-preset hex pins + EDITABLE_ROLES length + setProperty assertion) | `apply_theme_palette(qapp, repo)` → assert `qapp.palette().color(...)` + `qapp.property("theme_name")` | self (`test_all_presets_cover_9_roles` lines 202-209 + `test_apply_theme_palette_uses_repo_setting` lines 222-226) | exact (extend — change "9_roles" → "11_roles") |
| `tests/test_theme_editor_dialog.py` | test harness (11-row coverage; Save/Reset/Cancel for new keys) | swatch click → `_on_role_color_changed` → assert `_role_hex_dict` / `qapp.palette()` | self (lines 86-90 + 174-184 + 142-166 + 214-229; `stub_color_dialog` fixture lines 70-79) | exact (extend) |
| `tests/test_theme_picker_dialog.py` | test harness (tile-click sets `theme_name` property + retints toast) | tile click → `qapp.property("theme_name")` + `qapp.palette().color(ToolTipBase)` | self (`test_tile_click_applies_palette` lines 75-80) | exact (extend) |

---

## Pattern Assignments

### `musicstreamer/theme.py` (palette source, config→palette)

**Analog:** `musicstreamer/theme.py` (self — Phase 66 baseline, extended in place)

**THEME_PRESETS extension pattern** (lines 42-53 — vaporwave entry shape; planner appends 2 keys to each of 6 dicts):
```python
"vaporwave": {
    "Window": "#efe5ff",
    "WindowText": "#4a3a5a",
    "Base": "#fff5fb",
    "AlternateBase": "#f5e8ff",
    "Text": "#4a3a5a",
    "Button": "#d8c5f5",
    "ButtonText": "#4a3a5a",
    "Highlight": "#ff77ff",
    "HighlightedText": "#ffffff",
    "Link": "#7b5fef",
    # NEW Phase 75 — UI-SPEC §Color LOCKED hex pair:
    "ToolTipBase": "#f9d6f0",
    "ToolTipText": "#3a2845",
},
```
Locked pairs per UI-SPEC §Color (75-UI-SPEC.md:81-89):

| Preset | ToolTipBase | ToolTipText |
|--------|-------------|-------------|
| vaporwave | `#f9d6f0` | `#3a2845` |
| overrun | `#1a0a18` | `#ffe8f4` |
| gbs | `#2d5a2a` | `#f0f5e8` |
| gbs_after_dark | `#d5e8d3` | `#0a1a0d` |
| dark | `#181820` | `#f0f0f0` |
| light | `#2a2a32` | `#f5f5f5` |

`system` preset entry stays `{}` (line 37 — Phase 66 D-23 invariant).

**EDITABLE_ROLES extension pattern** (lines 154-164 — append 2 entries):
```python
EDITABLE_ROLES: tuple[str, ...] = (
    "Window",
    "WindowText",
    "Base",
    "AlternateBase",
    "Text",
    "Button",
    "ButtonText",
    "HighlightedText",
    "Link",
    # NEW Phase 75 — appended last; editor auto-grows via iteration at theme_editor_dialog.py:161
    "ToolTipBase",
    "ToolTipText",
)
```

**apply_theme_palette setProperty pattern** (lines 205-208 — insert ONE line after `theme_name = repo.get_setting(...)`):
```python
def apply_theme_palette(app: "QApplication", repo) -> None:
    """..."""
    theme_name = repo.get_setting("theme", "system")
    app.setProperty("theme_name", theme_name)   # NEW Phase 75 (D-10 path b)

    if theme_name == "system":
        ...
```
Placement rationale: set BEFORE branch logic so even the Linux+system early-return at line 214 leaves the property in a sane state.

**Docstring update pattern** (line 9):
```python
# BEFORE:
# - Theme owns 9 QPalette primary roles (Window, WindowText, Base, AlternateBase,
#   Text, Button, ButtonText, HighlightedText, Link) plus a Highlight baseline.

# AFTER:
# - Theme owns 11 QPalette primary roles (Window, WindowText, Base, AlternateBase,
#   Text, Button, ButtonText, HighlightedText, Link, ToolTipBase, ToolTipText)
#   plus a Highlight baseline.
```

**Adaptation notes:** Pure additive change — no removal, no reordering of existing keys. New keys land at the END of each preset dict and at the END of `EDITABLE_ROLES` so the editor's tab/focus order in `theme_editor_dialog.py:170` (initial focus on `_rows["Window"]._swatch_btn`) is undisturbed.

---

### `musicstreamer/ui_qt/toast.py` (widget consumer, palette→QSS)

**Analog:** `musicstreamer/ui_qt/now_playing_panel.py:194-197` (changeEvent template); `musicstreamer/ui_qt/eq_response_curve.py:121-124` (multi-event variant — DO NOT use both event types per RESEARCH §Risk Surface §1)

**Imports addition pattern** (modify `toast.py:9-16` — `QEvent` already imported; add `QPalette`, `QApplication`):
```python
from PySide6.QtCore import (
    QAbstractAnimation,
    QEvent,        # already present
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QPalette                                        # NEW Phase 75
from PySide6.QtWidgets import (
    QApplication,                                                          # NEW Phase 75
    QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget,
)
```

**Replace hardcoded setStyleSheet block** (lines 44-52) — call helper instead:
```python
# REPLACE lines 44-52:
self.setStyleSheet(
    "QLabel#ToastLabel {"
    " background-color: rgba(40, 40, 40, 220);"
    " color: white;"
    " border-radius: 8px;"
    " padding: 8px 12px;"
    "}"
)
# WITH:
self._rebuild_stylesheet()   # NEW Phase 75
```

**New `_rebuild_stylesheet()` method** (analog: `theme_editor_dialog._ColorRow._refresh_visual` at lines 89-100 for QSS string interpolation idiom; new logic for branch):
```python
def _rebuild_stylesheet(self) -> None:
    """Build palette-driven QSS; falls back to legacy QSS on theme='system' (D-09)."""
    app = QApplication.instance()
    theme_name = app.property("theme_name") if app is not None else None
    if not theme_name or theme_name == "system":
        # UI-SPEC §Color §System-theme legacy fallback — IMMUTABLE QSS LOCK
        self.setStyleSheet(
            "QLabel#ToastLabel {"
            " background-color: rgba(40, 40, 40, 220);"
            " color: white;"
            " border-radius: 8px;"
            " padding: 8px 12px;"
            "}"
        )
        return
    # UI-SPEC §Color §Non-system QSS build template
    pal = self.palette()
    bg = pal.color(QPalette.ToolTipBase)
    fg = pal.color(QPalette.ToolTipText).name()  # lowercase #rrggbb
    self.setStyleSheet(
        "QLabel#ToastLabel {"
        f" background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 220);"
        f" color: {fg};"
        " border-radius: 8px;"
        " padding: 8px 12px;"
        "}"
    )
```

**New `changeEvent` override** (analog: `now_playing_panel.py:194-197` — but narrowed event filter):
```python
# musicstreamer/ui_qt/now_playing_panel.py:194-197 (ANALOG — for reference):
def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
    if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
        self._apply_muted_palette()
    super().changeEvent(event)

# Phase 75 ToastOverlay — NARROWED FILTER (RESEARCH §Risk Surface §1):
def changeEvent(self, event) -> None:  # type: ignore[override]
    # NB: PaletteChange ONLY — NOT StyleChange. setStyleSheet() re-fires
    # StyleChange and would cause infinite recursion (RESEARCH §Risk 1).
    if event.type() == QEvent.PaletteChange:
        self._rebuild_stylesheet()
    super().changeEvent(event)
```

**Adaptation notes:**
- Mirror NowPlayingPanel `_MutedLabel.changeEvent` shape (handler logic first, `super()` last) but NARROW the filter to `PaletteChange` only. The two existing changeEvent analogs (`now_playing_panel.py:194`, `eq_response_curve.py:121`) get away with `(PaletteChange, StyleChange)` because they call `setPalette()`/`update()`, not `setStyleSheet()`. ToastOverlay is the FIRST `setStyleSheet`-inside-`changeEvent` site in the codebase and must NOT match the analog's both-event filter.
- Lazy palette read inside `_rebuild_stylesheet`, never cached at `__init__`.
- `__init__` call order: place `self._rebuild_stylesheet()` AFTER `self.label.setObjectName("ToastLabel")` at line 39 and AFTER `layout.addWidget(self.label)` at line 42 (replaces the lines 44-52 block).
- All other lifetime/animation/eventFilter code (lines 54-114) UNTOUCHED.

---

### `musicstreamer/ui_qt/theme_picker_dialog.py` (live-preview palette mutator)

**Analog:** `musicstreamer/ui_qt/theme_picker_dialog.py:260-285` (self — Phase 66 `_on_tile_clicked`)

**Mirror site pattern** (insert ONE line at line 264, after `app = QApplication.instance()`):
```python
def _on_tile_clicked(self, theme_id: str) -> None:
    """Tile click = live preview; no persistence (UI-SPEC §State Machine P-Previewing)."""
    self._selected_theme_id = theme_id
    self._active_tile_id = theme_id
    app = QApplication.instance()
    app.setProperty("theme_name", theme_id)   # NEW Phase 75 — mirror of apply_theme_palette

    if theme_id == "system":
        app.setPalette(QPalette())  # fresh Qt-default
    elif theme_id == "custom":
        raw = self._repo.get_setting("theme_custom", "")
        # ... existing JSON parse + setPalette unchanged ...
    else:
        app.setPalette(build_palette_from_dict(THEME_PRESETS[theme_id]))

    # Re-impose accent override (Phase 59 D-02 layering — Pitfall 2).
    accent = self._repo.get_setting("accent_color", "")
    if accent and _is_valid_hex(accent):
        apply_accent_palette(app, accent)

    self._refresh_active_tile()
```

**Adaptation notes:**
- `setProperty` set BEFORE the `setPalette` call so Qt's synchronous `PaletteChange` dispatch sees the new `theme_name` when ToastOverlay's `changeEvent` reads `app.property("theme_name")`.
- No change to JSON parse / accent re-impose / `_refresh_active_tile` — all preserved verbatim.
- All other methods (`_on_apply`, `_on_customize`, `reject`, `_on_tile_clicked` for system/custom branches) untouched.

---

### `musicstreamer/ui_qt/theme_editor_dialog.py` (UI labels only — rows auto-grow)

**Analog:** `musicstreamer/ui_qt/theme_editor_dialog.py:37-47` (self — `ROLE_LABELS` dict) + lines 161-167 (iteration loop)

**ROLE_LABELS extension pattern** (append 2 entries to dict at lines 37-47):
```python
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
    # NEW Phase 75 — UI-SPEC §Copywriting Contract LOCKED:
    "ToolTipBase": "Toast background",
    "ToolTipText": "Toast text",
}
```

**Iteration loop (UNCHANGED — auto-grows)** (lines 159-167):
```python
# 9 rows, single column, in EDITABLE_ROLES order (matches QPalette enum).
# After Phase 75: 11 rows — comment update only, no code change.
self._rows: dict[str, _ColorRow] = {}
for role_name in EDITABLE_ROLES:        # ← auto-grows once EDITABLE_ROLES gains keys
    label = ROLE_LABELS[role_name]      # ← KeyError if ROLE_LABELS missing entry — must add both
    initial_hex = self._role_hex_dict.get(role_name, "#cccccc")
    row = _ColorRow(role_name, label, initial_hex, self)
    row.color_changed.connect(self._on_role_color_changed)  # QA-05 bound
    root.addWidget(row)
    self._rows[role_name] = row
```

**Adaptation notes:**
- ONLY change is `ROLE_LABELS` dict — 2 string entries. NO change to iteration loop (auto-grows via `EDITABLE_ROLES` extension in PLAN-01).
- Optional (RESEARCH §Risk 8 mitigation): consider adding `app.setProperty("theme_name", "custom")` at the top of `_on_role_color_changed` (lines 253-268) to handle the system→edit→toast-stays-grey edge case. Recommend YES per RESEARCH §Risk 8.
- Snapshot-restore-on-Cancel via `reject()` (lines 309-314) automatically covers the new roles because it stashes the full `QApplication.palette()` at line 143.
- `_compute_source_palette` (lines 187-227) auto-handles new keys because it iterates `EDITABLE_ROLES` in cases A/C/D/E.

---

### `.planning/REQUIREMENTS.md` (requirement doc)

**Analog:** `.planning/REQUIREMENTS.md:44` (THEME-01 entry, Features section) + line 154 (traceability table row)

**THEME-02 addition pattern** (insert after THEME-01 at line 44):
```markdown
- [x] **THEME-01**: ... existing entry preserved verbatim ...
- [ ] **THEME-02**: Toast notifications track the active theme via `QPalette.ToolTipBase`/`ToolTipText`. When user picks a theme via the Picker (preset or Custom), the next-fired and currently-visible toasts retint to the theme's tooltip colors at alpha=220. `theme='system'` preserves the legacy `rgba(40, 40, 40, 220)` + white QSS byte-for-byte (no regression on day-one default). The Custom theme editor grows from 9 → 11 editable roles (appending `ToolTipBase` and `ToolTipText` after `Link`). Custom JSON additive — no SQLite schema change. *(Phase 75)*
```

**Traceability table row pattern** (insert at line 154 neighbourhood, after THEME-01 row):
```markdown
| THEME-01 | Phase 66 | Complete |
| THEME-02 | Phase 75 | Pending |
| WIN-05 | Phase 69 | Complete |
```

**Adaptation notes:** Pure doc edit. THEME-02 status starts as `[ ]` (Pending) — flips to `[x]` only at phase-completion time. Traceability table row sits between THEME-01 and the next phase's row in numerical order (Phase 75 lands AFTER Phase 69's WIN-05).

---

### `tests/test_toast_overlay.py` (test harness)

**Analog:** `tests/test_toast_overlay.py:140-145` (existing `test_14_stylesheet_color_contract`) + `tests/test_theme_editor_dialog.py:214-229` (snapshot-mutate-assert pattern for palette changes)

**Line 143 retrofit pattern** — gate existing assertion to system-theme-only:
```python
# BEFORE (lines 140-145):
def test_14_stylesheet_color_contract(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    assert "rgba(40, 40, 40, 220)" in qss
    assert "border-radius: 8px" in qss

# AFTER (rename to system-theme-only):
def test_14_stylesheet_system_theme_color_contract(qtbot, parent_widget, qapp):
    qapp.setProperty("theme_name", "system")   # explicit system branch
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    assert "rgba(40, 40, 40, 220)" in qss   # UI-SPEC §Color IMMUTABLE QSS LOCK
    assert "color: white" in qss
    assert "border-radius: 8px" in qss
    assert "padding: 8px 12px" in qss
```

**New test patterns** — derived from existing `parent_widget` fixture (lines 19-26) + palette-mutation idiom from `test_theme.py:222-226`:

```python
# Non-system QSS uses ToolTipBase/ToolTipText
def test_stylesheet_non_system_uses_tooltip_palette(qtbot, parent_widget, qapp):
    qapp.setProperty("theme_name", "vaporwave")
    from musicstreamer.theme import THEME_PRESETS, build_palette_from_dict
    qapp.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    # UI-SPEC LOCKED hex pair for vaporwave: ToolTipBase=#f9d6f0, ToolTipText=#3a2845
    # #f9d6f0 → rgb(249, 214, 240)
    assert "rgba(249, 214, 240, 220)" in qss
    assert "color: #3a2845" in qss
    assert "border-radius: 8px" in qss   # geometry invariant
    assert "padding: 8px 12px" in qss    # geometry invariant

# changeEvent retint — snapshot-mutate-assert pattern
def test_changeEvent_palette_change_rebuilds_qss(qtbot, parent_widget, qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtCore import QCoreApplication
    qapp.setProperty("theme_name", "system")
    toast = ToastOverlay(parent_widget)
    qss_before = toast.styleSheet()
    assert "rgba(40, 40, 40, 220)" in qss_before
    # Switch to non-system theme
    qapp.setProperty("theme_name", "vaporwave")
    from musicstreamer.theme import THEME_PRESETS, build_palette_from_dict
    qapp.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))
    # Qt dispatches PaletteChange synchronously to all widgets including toast
    qss_after = toast.styleSheet()
    assert qss_after != qss_before
    assert "rgba(249, 214, 240, 220)" in qss_after

# Typography invariance lock
def test_stylesheet_no_font_properties(qtbot, parent_widget, qapp):
    for theme in ("system", "vaporwave", "overrun", "dark"):
        qapp.setProperty("theme_name", theme)
        toast = ToastOverlay(parent_widget)
        qss = toast.styleSheet()
        assert "font-size:" not in qss
        assert "font-family:" not in qss
        assert "font-weight:" not in qss
```

**Adaptation notes:**
- Reuse the existing `parent_widget` fixture verbatim (lines 19-26). No new fixtures needed.
- `qapp` is a `pytest-qt` builtin — no import needed (matches `tests/test_theme.py:140` usage).
- All new tests are additive — no deletion of existing tests except renaming `test_14_stylesheet_color_contract` (the function name change is the only mutation).
- The `pytest-qt` `qapp` fixture survives across tests via session-scoped QApplication; ALWAYS call `qapp.setProperty("theme_name", ...)` at the start of each test to avoid cross-test pollution from a stray prior `setProperty` call (consider adding an autouse fixture if RED-cycle reveals flakiness).

---

### `tests/test_theme.py` (test harness)

**Analog:** `tests/test_theme.py:202-209` (`test_all_presets_cover_9_roles`) + lines 222-226 (`test_apply_theme_palette_uses_repo_setting` for `apply_theme_palette` + assert pattern)

**Update existing 9-roles test → 11-roles** (lines 202-209):
```python
# BEFORE:
def test_all_presets_cover_9_roles():
    """Every non-system preset must define all 9 EDITABLE_ROLES."""
    for theme_id in ("vaporwave", "overrun", "gbs", "gbs_after_dark", "dark", "light"):
        preset = THEME_PRESETS[theme_id]
        for role in EDITABLE_ROLES:
            assert role in preset, f"preset {theme_id!r} missing role {role!r}"

# AFTER (rename + retain assertion logic — EDITABLE_ROLES auto-grows):
def test_all_presets_cover_11_roles():
    """Every non-system preset must define all 11 EDITABLE_ROLES (Phase 75 D-08)."""
    assert len(EDITABLE_ROLES) == 11
    for theme_id in ("vaporwave", "overrun", "gbs", "gbs_after_dark", "dark", "light"):
        preset = THEME_PRESETS[theme_id]
        for role in EDITABLE_ROLES:
            assert role in preset, f"preset {theme_id!r} missing role {role!r}"
```

**New tests** — locked-hex pin pattern (analog: `_GBS_LOCKED` dict at lines 114-126 + `test_gbs_preset_locked_hex_match` at lines 196-199):
```python
# Per-preset hex pin — UI-SPEC §Color LOCKED pairs (12 assertions)
def test_tooltip_role_locked_hex_per_preset():
    """UI-SPEC §Color: ToolTipBase + ToolTipText hex pairs locked per preset."""
    expected = {
        "vaporwave":      ("#f9d6f0", "#3a2845"),
        "overrun":        ("#1a0a18", "#ffe8f4"),
        "gbs":            ("#2d5a2a", "#f0f5e8"),
        "gbs_after_dark": ("#d5e8d3", "#0a1a0d"),
        "dark":           ("#181820", "#f0f0f0"),
        "light":          ("#2a2a32", "#f5f5f5"),
    }
    for theme_id, (bg, fg) in expected.items():
        assert THEME_PRESETS[theme_id]["ToolTipBase"] == bg
        assert THEME_PRESETS[theme_id]["ToolTipText"] == fg

# system preset remains sentinel — Phase 66 D-23 invariant
def test_system_preset_stays_empty():
    """system entry is `{}` sentinel — no toast keys leak in."""
    assert THEME_PRESETS["system"] == {}

# EDITABLE_ROLES tail order
def test_editable_roles_appends_tooltip_pair_last():
    assert EDITABLE_ROLES[-2:] == ("ToolTipBase", "ToolTipText")
    assert len(EDITABLE_ROLES) == 11

# apply_theme_palette sets QApplication property — analog: lines 222-226
def test_apply_theme_palette_sets_theme_name_property(qapp, repo):
    repo.set_setting("theme", "gbs")
    apply_theme_palette(qapp, repo)
    assert qapp.property("theme_name") == "gbs"

def test_apply_theme_palette_sets_property_for_system(qapp, repo):
    repo.set_setting("theme", "system")
    apply_theme_palette(qapp, repo)
    assert qapp.property("theme_name") == "system"
```

**Adaptation notes:**
- Reuse `repo` fixture verbatim (lines 129-135 — real `Repo` over temp SQLite).
- `qapp` is `pytest-qt` builtin.
- All new tests follow the existing `def test_*(qapp[, repo]):` shape.
- Lines 162-191 partial-dict tests for `build_palette_from_dict` already exercise the "missing role falls back to Qt default" path — auto-covers the new keys when absent.

---

### `tests/test_theme_editor_dialog.py` (test harness)

**Analog:** `tests/test_theme_editor_dialog.py:86-90` (`test_editor_shows_9_color_rows`) + lines 174-184 (`test_save_persists_theme_custom_json`) + lines 142-166 (`test_reset_reverts_to_source_preset`) + lines 214-229 (`test_cancel_restores_snapshot`) + lines 70-79 (`stub_color_dialog` fixture)

**Update 9-rows test → 11-rows** (lines 86-90):
```python
# BEFORE:
def test_editor_shows_9_color_rows(dialog):
    """dlg._rows has exactly 9 keys matching EDITABLE_ROLES; Highlight NOT a key (D-08)."""
    assert set(dialog._rows.keys()) == set(EDITABLE_ROLES)
    assert len(dialog._rows) == 9
    assert "Highlight" not in dialog._rows

# AFTER:
def test_editor_shows_11_color_rows(dialog):
    """dlg._rows has exactly 11 keys matching EDITABLE_ROLES (Phase 75 D-05)."""
    assert set(dialog._rows.keys()) == set(EDITABLE_ROLES)
    assert len(dialog._rows) == 11
    assert "Highlight" not in dialog._rows
    assert "ToolTipBase" in dialog._rows
    assert "ToolTipText" in dialog._rows
```

**Save round-trip extension** (lines 174-184 — extend to assert new keys; analog `for role in EDITABLE_ROLES` loop auto-covers):
```python
def test_save_persists_theme_custom_json(qtbot, repo, qapp, stub_color_dialog):
    """Save persists theme_custom JSON with all 11 EDITABLE_ROLES."""
    stub_color_dialog["color"] = QColor("#abcdef")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)
    dlg._on_save()
    saved = json.loads(repo.get_setting("theme_custom", ""))
    assert saved["Window"] == "#abcdef"
    for role in EDITABLE_ROLES:   # ← auto-grows to 11
        assert role in saved
    # Explicit new-key assertions (defense-in-depth):
    assert "ToolTipBase" in saved
    assert "ToolTipText" in saved
```

**New tests for ROLE_LABELS + new-row Save/Reset/Cancel coverage** (analog: existing row interactions):
```python
def test_role_labels_include_toast_pair():
    """UI-SPEC §Copywriting Contract — locked labels for toast rows."""
    from musicstreamer.ui_qt.theme_editor_dialog import ROLE_LABELS
    assert ROLE_LABELS["ToolTipBase"] == "Toast background"
    assert ROLE_LABELS["ToolTipText"] == "Toast text"

def test_save_persists_toast_keys_when_user_edits_them(qtbot, repo, qapp, stub_color_dialog):
    """Editing ToolTipBase row → Save → JSON contains the new hex."""
    stub_color_dialog["color"] = QColor("#abc123")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["ToolTipBase"]._swatch_btn, Qt.LeftButton)
    dlg._on_save()
    saved = json.loads(repo.get_setting("theme_custom", ""))
    assert saved["ToolTipBase"] == "#abc123"

def test_reset_restores_toast_rows_to_source_preset(qtbot, repo, qapp, stub_color_dialog):
    """Reset reverts ToolTipBase + ToolTipText to source-preset values."""
    stub_color_dialog["color"] = QColor("#000000")
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._rows["ToolTipBase"]._swatch_btn, Qt.LeftButton)
    qtbot.mouseClick(dlg._rows["ToolTipText"]._swatch_btn, Qt.LeftButton)
    dlg._on_reset()
    # UI-SPEC LOCKED vaporwave pair
    assert dlg._role_hex_dict["ToolTipBase"] == "#f9d6f0"
    assert dlg._role_hex_dict["ToolTipText"] == "#3a2845"

def test_cancel_restores_toast_roles_in_palette(qtbot, repo, qapp):
    """reject() snapshot covers new ToolTipBase/ToolTipText roles."""
    original_bg = qapp.palette().color(QPalette.ColorRole.ToolTipBase)
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    dlg._on_role_color_changed("ToolTipBase", "#000000")
    assert qapp.palette().color(QPalette.ColorRole.ToolTipBase).name().lower() == "#000000"
    dlg.reject()
    assert qapp.palette().color(QPalette.ColorRole.ToolTipBase) == original_bg
```

**Adaptation notes:**
- All fixtures (`repo`, `dialog`, `stub_color_dialog`) reused verbatim from lines 58-79.
- Reuse `FakeRepo` (lines 25-33), `_FakePicker` (lines 40-51) — no new test scaffolding.
- The `for role in EDITABLE_ROLES` loop in the existing Save test auto-covers the new keys; explicit asserts are defense-in-depth.
- `_compute_source_palette` already handles `source_preset='vaporwave'` case D (line 218-225) — picks up the new keys from `THEME_PRESETS["vaporwave"]` once PLAN-01 adds them.

---

### `tests/test_theme_picker_dialog.py` (test harness)

**Analog:** `tests/test_theme_picker_dialog.py:75-80` (`test_tile_click_applies_palette`)

**New tests** — same shape as analog with two new assertions:
```python
def test_tile_click_sets_theme_name_property(qtbot, repo, qapp):
    """Tile click mirrors apply_theme_palette by setting QApplication property."""
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    assert qapp.property("theme_name") == "vaporwave"

def test_tile_click_retints_toast_overlay(qtbot, repo, qapp):
    """Live preview: vaporwave tile click → ToastOverlay rebuilds QSS with #f9d6f0."""
    from musicstreamer.ui_qt.toast import ToastOverlay
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    toast = ToastOverlay(parent)
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    # ToastOverlay.changeEvent(PaletteChange) → _rebuild_stylesheet — picks #f9d6f0 → rgb(249,214,240)
    qss = toast.styleSheet()
    assert "rgba(249, 214, 240, 220)" in qss

def test_tile_click_system_sets_theme_name_property(qtbot, repo, qapp):
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["system"], Qt.LeftButton)
    assert qapp.property("theme_name") == "system"
```

**Adaptation notes:**
- Reuse `FakeRepo` + `dialog` + `repo` fixtures verbatim (lines 23-47).
- `test_tile_click_retints_toast_overlay` is a light integration test; toast construction mirrors `tests/test_toast_overlay.py:19-26` shape (parent QWidget + qtbot.addWidget + waitExposed).
- Tests assert ON `qapp.property("theme_name")` directly — no mock needed because `setProperty` is the actual Qt API call.

---

## Shared Patterns

### Lazy palette + property read (no caching)

**Source:** new — see `_rebuild_stylesheet` in toast.py (RESEARCH §4)
**Apply to:** `musicstreamer/ui_qt/toast.py` only — Phase 75's single consumer

```python
app = QApplication.instance()
theme_name = app.property("theme_name") if app is not None else None
if not theme_name or theme_name == "system":
    # legacy QSS
else:
    pal = self.palette()
    bg = pal.color(QPalette.ToolTipBase)
    fg = pal.color(QPalette.ToolTipText).name()
```

**Why lazy:** picker live-preview flow mutates `theme_name` mid-session; caching at `__init__` would freeze the toast on whatever startup theme was active.

---

### `setProperty("theme_name", ...)` mirror at every palette-mutation site

**Source:** RESEARCH §1, §3
**Apply to:** `musicstreamer/theme.py:apply_theme_palette` (after `repo.get_setting`); `musicstreamer/ui_qt/theme_picker_dialog.py:_on_tile_clicked` (after `QApplication.instance()`); OPTIONALLY `musicstreamer/ui_qt/theme_editor_dialog.py:_on_role_color_changed` (RESEARCH §Risk 8 mitigation)

```python
app.setProperty("theme_name", theme_name)   # set BEFORE setPalette()
```

**Why:** `QApplication.setPalette()` dispatches `PaletteChange` synchronously; toast reads `app.property("theme_name")` inside its `changeEvent` handler. Property MUST be set before the palette mutation so the dispatch sees the new theme name.

---

### `changeEvent(QEvent.PaletteChange)` for palette-derived state

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:194-197`
**Apply to:** `musicstreamer/ui_qt/toast.py` (Phase 75 ADDS, NARROWED filter — PaletteChange only)

```python
# Existing pattern (now_playing_panel.py):
def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
    if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
        self._apply_muted_palette()
    super().changeEvent(event)

# Phase 75 NARROWED variant (toast.py) — PaletteChange ONLY to avoid setStyleSheet recursion:
def changeEvent(self, event) -> None:  # type: ignore[override]
    if event.type() == QEvent.PaletteChange:
        self._rebuild_stylesheet()
    super().changeEvent(event)
```

**Critical divergence:** The two existing in-tree analogs (`now_playing_panel.py:195`, `eq_response_curve.py:122`) match on `(PaletteChange, StyleChange)`. Phase 75 must NARROW to `PaletteChange` only because `setStyleSheet()` re-fires `StyleChange` and would cause infinite recursion (RESEARCH §Risk 1; verified against Qt 6.11 docs).

---

### Defense-in-depth hex validation (already established — no new code needed)

**Source:** `musicstreamer/accent_utils._is_valid_hex` imported into `theme.py:26` and used at `theme.py:180`
**Apply to:** the two new `ToolTipBase`/`ToolTipText` keys flow through the EXISTING validator at `build_palette_from_dict` line 180 — zero new code.

```python
# musicstreamer/theme.py:179-186 (UNCHANGED — auto-covers new keys):
for role_name, hex_value in role_hex.items():
    if not isinstance(hex_value, str) or not _is_valid_hex(hex_value):
        continue
    role = getattr(QPalette.ColorRole, role_name, None)
    if role is None:
        continue
    palette.setColor(role, QColor(hex_value))
```

---

### `pytest-qt` test harness: `qapp` + `parent_widget` + palette mutation

**Source:** `tests/test_toast_overlay.py:19-26` (parent_widget fixture); `tests/test_theme.py:222-226` (apply_theme_palette assert idiom); `tests/test_theme_editor_dialog.py:70-79` (stub_color_dialog fixture)
**Apply to:** all 4 test files

```python
# Standard parent fixture (test_toast_overlay.py:19-26 — reuse verbatim):
@pytest.fixture
def parent_widget(qtbot):
    parent = QWidget()
    parent.resize(1200, 800)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    return parent

# Standard palette-mutate-assert (test_theme.py:222-226):
def test_*(qapp, repo):
    repo.set_setting("theme", "gbs")
    apply_theme_palette(qapp, repo)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#a1d29d"

# QColorDialog stub (test_theme_editor_dialog.py:70-79 — reuse verbatim):
@pytest.fixture
def stub_color_dialog(monkeypatch):
    chosen_holder = {"color": QColor("#abcdef")}
    def _stub(*args, **kwargs):
        return chosen_holder["color"]
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(_stub))
    return chosen_holder
```

---

## No Analog Found

None — Phase 75 has an in-tree analog for every modification site. The only NEW pattern (palette-driven QSS interpolation with `setStyleSheet` inside `changeEvent`) builds on two close cousins (`_MutedLabel.changeEvent` which calls `setPalette`, and `_ColorRow._refresh_visual` which builds QSS strings from validated hex) — composing the two gives the Phase 75 toast pattern without inventing a new abstraction.

---

## Metadata

**Analog search scope:**
- `musicstreamer/theme.py` (entire file)
- `musicstreamer/ui_qt/toast.py` (entire file)
- `musicstreamer/ui_qt/theme_picker_dialog.py` (lines 1-40, 255-295)
- `musicstreamer/ui_qt/theme_editor_dialog.py` (entire file)
- `musicstreamer/ui_qt/now_playing_panel.py:180-200` (changeEvent template)
- `musicstreamer/ui_qt/eq_response_curve.py:115-130` (second changeEvent example)
- `tests/test_toast_overlay.py` (entire file)
- `tests/test_theme.py` (entire file)
- `tests/test_theme_editor_dialog.py:1-240` (fixtures + Save/Reset/Cancel patterns)
- `tests/test_theme_picker_dialog.py:1-120` (tile-click pattern)
- `.planning/REQUIREMENTS.md:35-160` (THEME-01 entry + traceability table)

**Files scanned:** 11
**Patterns extracted:** 14 (1 per modified-file + 5 shared)
**Pattern extraction date:** 2026-05-15
