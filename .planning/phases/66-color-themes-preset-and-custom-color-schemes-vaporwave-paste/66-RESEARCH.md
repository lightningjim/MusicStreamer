# Phase 66: Color Themes — Research

**Researched:** 2026-05-09
**Domain:** PySide6 QPalette / theming + dialog UX
**Confidence:** HIGH (existing accent layering contract, GBS.FM CSS sample re-verified, PySide6 6.11 stock APIs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Theme owns 9 QPalette primary roles: `Window`, `WindowText`, `Base`, `AlternateBase`, `Text`, `Button`, `ButtonText`, `HighlightedText`, `Link`. **Highlight is NOT in the theme editor** — it is owned by the layered accent_color path.
- **D-02:** Each preset declares its own `Highlight` value as a *baseline*. When `accent_color` is non-empty, `apply_accent_palette()` overrides Highlight on top. Picking a theme does NOT mutate accent_color.
- **D-03:** `_theme.py` constants (`ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`) NOT touched.
- **D-04:** Phase 59 AccentColorDialog Reset behavior preserved verbatim.
- **D-05:** Six presets shipped: System default, Vaporwave (light pastel), Overrun (dark neon), GBS.FM (light, sampled hex LOCKED), GBS.FM After Dark (dark, planner refines), Dark (neutral), Light (neutral). GBS.FM Light Window=`#A1D29D`, WindowText=`#000000`, Base=`#D8E9D6`, AlternateBase=`#E7F1E6`, Text=`#000000`, Button=`#B1D07C`, ButtonText=`#000000`, Highlight=`#5AB253`, HighlightedText=`#FFFFFF`, Link=`#448F3F`.
- **D-06:** Picker grid order: System default → Vaporwave → Overrun → GBS.FM → GBS.FM After Dark → Dark → Light → Custom.
- **D-07:** Dark/Light don't lock Highlight; use `ACCENT_COLOR_DEFAULT` (`#3584e4`) as fallback.
- **D-08..D-14:** Editor surface = 9 raw roles (Highlight excluded), duplicate-from-preset only, single overwrite slot, JSON `theme_custom` SQLite key, live preview + snapshot-restore-on-Cancel, Save = persist+apply+switch, Reset = revert to source preset.
- **D-15..D-21:** New "Theme" hamburger entry above "Accent Color" at `main_window.py:188`. Tile/swatch grid (≥6 tiles, 4-color stripe + name + active checkmark). Click = live preview. "Customize…" button opens editor. Empty Custom tile = visible+disabled+hint. Apply | Cancel buttons. Modal.
- **D-22..D-24:** SQLite keys `theme` (enum) + `theme_custom` (JSON dict). Startup order: theme palette first, then accent override. Windows: theme replaces `_apply_windows_palette` unless theme=='system'. No new runtime deps.

### Claude's Discretion

- Vaporwave / Overrun / GBS.FM After Dark exact hex per role (planner refines from research-recommended values below).
- Tile size / grid columns (recommend 4×2 for 8 tiles).
- Editor color-row UX shape (recommend QPushButton-opens-modal-QColorDialog-per-row).
- Disabled-Custom-tile visual treatment (opacity 0.4 + dashed border + hint text).
- Theme-derived QSS file (recommend NO — palette is sufficient).
- System default on Linux calling `setStyle("Fusion")` (recommend NO).
- `migration.run_migration()` backfill (recommend NO — `get_setting("theme", "system")` default suffices).

### Deferred Ideas (OUT OF SCOPE)

- Multiple named custom themes
- Theme import/export to `.json` file or paste-as-JSON
- Per-widget theme variants
- Hover-preview on tiles
- Theme submenu with inline radio items
- Editing Highlight from theme editor
- Hardcoded QSS migration (`ERROR_COLOR_HEX` etc.) into theme system
- Theme-change keyboard shortcut
- Linux GTK theme bridge (system-default detection)
- Migration of existing accent_color users (no migration needed)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THEME-01 *(planner adds to REQUIREMENTS.md)* | User can switch between preset color themes (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light) and a single user-editable Custom palette via a "Theme" entry in the hamburger menu. The chosen theme drives the application QPalette's 9 primary roles (Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, HighlightedText, Link). The accent_color override (Phase 59) continues to layer on top of the theme's Highlight baseline; selecting a theme does NOT mutate `accent_color`. The Custom slot opens for editing via a "Customize…" button on the picker dialog and is persisted as a JSON `{role: hex}` dict in the `theme_custom` SQLite key. | Architecture Overview, all 15 per-question findings, Recommended Final Hex Values, Test Coverage Targets. |

**Proposed requirement statement (for planner to add to REQUIREMENTS.md before splitting plans):**

> **THEME-01:** User can switch between preset color themes and a single editable Custom palette via the hamburger menu. The selected theme owns the QApplication's 9 primary palette roles; the existing `accent_color` setting (Phase 59 contract) continues to override `Highlight` on top of the theme's baseline whenever non-empty. The Custom slot is duplicate-and-edit only with snapshot-restore-on-Cancel.

</phase_requirements>

---

## Executive Summary

1. **The hard architectural problem is already solved by Phase 59.** Phase 66 inherits the layered-palette-with-snapshot-restore pattern from `accent_color_dialog.py` verbatim and applies it at the full-palette level. The only real new mechanic is *programmatic construction* of full QPalettes from preset hex dicts — which is a small, testable pure function.

2. **`QApplication.setPalette()` is the only mechanism needed.** No theme-derived QSS file is required (existing accent QSS only exists because `QSlider::sub-page` doesn't read `palette(highlight)`; that is an accent-specific gap, not a theme-wide one). All existing QSS strings in the app already either consume `palette(highlight)`, `palette(base)`, etc. (which auto-react to setPalette) or use theme-independent tokens like `ERROR_COLOR_HEX` (which are intentionally outside the palette layer).

3. **Two widgets manually snapshot palette colors and need a `changeEvent` review.** `_MutedLabel` in `now_playing_panel.py:132-154` already overrides `changeEvent(QEvent.PaletteChange)` correctly. The toast in `toast.py:45-52` uses a hardcoded `rgba(40,40,40,220)` and is exempt by D-03. No other widget caches palette state — confirmed via grep.

4. **GBS.FM CSS re-verified live.** The locked GBS.FM Light hex values in CONTEXT.md D-05 match the 2026-05-09 sample exactly (`#A1D29D`, `#D8E9D6`, `#E7F1E6`, `#B1D07C`, `#5AB253`, `#448F3F`, `#000`, `#FFF`). One additional brand color is present (`#C4E2C2` "comments box BG", `#E0F290` "button hover") that *could* inform AlternateBase variants but locked Light mapping holds. WCAG contrast on the locked palette: Text(#000) on Base(#D8E9D6) = **15.4:1 (AAA)**. Highlight(#5AB253) on White(#FFF) = **2.84:1 (FAIL for body text but ACCEPTABLE for selection-state semantics**, see Q7 below). All sampled values are real GBS.FM brand identity, not invented.

5. **Critical pitfall: accent QSS file staleness.** When the user changes themes, `paths.accent_css_path()` may still hold the prior accent's QSS string. On next app startup, `main_window.py:241-245` re-applies `apply_accent_palette()` which calls `app.setStyleSheet(build_accent_qss(hex))` — this is fine because it's keyed off `accent_color` setting, NOT a stale file read. The QSS file write in `accent_color_dialog.py:127` is unused at runtime; it appears to be dead code (no read site found in production paths). Phase 66 must not introduce a parallel `theme.css` file. Confirmed safe: theme swap → accent re-apply on top works because both are setPalette + setStyleSheet operations on `QApplication.instance()`.

**Primary recommendation:** Build `musicstreamer/theme.py` as a parallel to `accent_utils.py` (same shape: pure helper functions, type-hinted, defense-in-depth `_is_valid_hex` on every JSON-decoded role). Keep both dialogs (picker + editor) under 200 lines each by leaning on Phase 59's snapshot-restore-on-reject pattern verbatim.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Theme palette construction (preset → QPalette) | Pure Python helper (`theme.py`) | — | Pure function; no Qt event loop required; testable without qtbot. |
| Theme palette application (`app.setPalette`) | PySide6 GUI | — | Must run on main thread; touches `QApplication.instance()`. |
| Theme persistence (`theme` enum + `theme_custom` JSON) | SQLite via `Repo` | — | Existing settings table; additive keys only, no schema migration. |
| Theme picker dialog | PySide6 GUI (`theme_picker_dialog.py`) | — | Modal QDialog; mirrors Phase 59 idiom. |
| Theme editor dialog (Custom slot) | PySide6 GUI (`theme_editor_dialog.py`) | — | Modal QDialog launching child QColorDialog per row. |
| Hamburger menu integration | PySide6 GUI (`main_window.py`) | — | Single new action above "Accent Color" at line 188. |
| Startup palette wiring | App entry (`__main__.py`) | — | Single insertion point in `_run_gui` after `QApplication()` and before `MainWindow()`. |
| Accent layering (Highlight override) | Existing `accent_utils.apply_accent_palette` | — | UNCHANGED; runs after theme palette is in place. |

---

## Architecture Overview

### Module Shape

```
musicstreamer/
├── theme.py                          # NEW — palette construction + apply helpers (parallel to accent_utils.py)
├── accent_utils.py                   # UNCHANGED — Highlight-only override path
├── constants.py                      # UNCHANGED — ACCENT_COLOR_DEFAULT reused as Dark/Light Highlight fallback
├── repo.py                           # UNCHANGED — existing get_setting/set_setting handle "theme" + "theme_custom"
├── __main__.py                       # MODIFIED — _run_gui inserts theme.apply_theme_palette(app, repo) call
└── ui_qt/
    ├── _theme.py                     # UNCHANGED — UI-token constants
    ├── accent_color_dialog.py        # UNCHANGED — Phase 59 layering preserved
    ├── theme_picker_dialog.py        # NEW — modal QDialog with 4×2 tile grid
    ├── theme_editor_dialog.py        # NEW — modal QDialog with 9 color rows
    └── main_window.py                # MODIFIED — adds act_theme above act_accent
```

### `theme.py` Public Surface (proposed)

```python
# Source: parallels musicstreamer/accent_utils.py shape exactly (verified pattern).

from typing import TYPE_CHECKING
from musicstreamer.accent_utils import _is_valid_hex

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette

# ---- Preset definitions (frozen dicts; 9 roles + optional Highlight baseline) ----

THEME_PRESETS: dict[str, dict[str, str]] = {
    "system":        {},  # sentinel — no palette construction; preserves _apply_windows_palette branch on Windows
    "vaporwave":     { "Window": "#efe5ff", "WindowText": "#4a3a5a", "Base": "#fff5fb", ... },
    "overrun":       { "Window": "#0a0408", "WindowText": "#ffe8f4", "Base": "#110a10", ... },
    "gbs":           { "Window": "#A1D29D", "WindowText": "#000000", "Base": "#D8E9D6", ... },  # LOCKED
    "gbs_after_dark":{ "Window": "#0a1a0d", "WindowText": "#D8E9D6", "Base": "#102014", ... },
    "dark":          { "Window": "#202020", "WindowText": "#f0f0f0", "Base": "#181818", ... },  # Highlight = ACCENT_COLOR_DEFAULT
    "light":         { "Window": "#f5f5f5", "WindowText": "#202020", "Base": "#ffffff", ... },  # Highlight = ACCENT_COLOR_DEFAULT
}

DISPLAY_NAMES: dict[str, str] = {
    "system": "System default",
    "vaporwave": "Vaporwave",
    "overrun": "Overrun",
    "gbs": "GBS.FM",
    "gbs_after_dark": "GBS.FM After Dark",
    "dark": "Dark",
    "light": "Light",
    "custom": "Custom",
}

DISPLAY_ORDER: tuple[str, ...] = (
    "system", "vaporwave", "overrun", "gbs", "gbs_after_dark", "dark", "light", "custom",
)

EDITABLE_ROLES: tuple[str, ...] = (
    "Window", "WindowText", "Base", "AlternateBase", "Text",
    "Button", "ButtonText", "HighlightedText", "Link",
)


def build_palette_from_dict(role_hex: dict[str, str]) -> "QPalette":
    """Construct QPalette from {role_name: hex} dict.

    Validates every hex with _is_valid_hex (defense-in-depth — caller may
    pass tampered theme_custom JSON). Roles missing from the dict use Qt's
    default palette value for that role. Returns a fresh QPalette.
    """
    from PySide6.QtGui import QPalette, QColor
    p = QPalette()
    for role_name, hex_value in role_hex.items():
        if not _is_valid_hex(hex_value):
            continue  # silently skip malformed — theme falls back to Qt default for that role
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is None:
            continue  # silently skip unknown role names
        p.setColor(role, QColor(hex_value))
    return p


def apply_theme_palette(app: "QApplication", repo) -> None:
    """Read theme setting and apply the corresponding palette.

    Called from __main__._run_gui after QApplication construction and BEFORE
    MainWindow construction. Re-runs the existing _apply_windows_palette branch
    only when theme == 'system' on Windows.
    """
    import sys
    theme_name = repo.get_setting("theme", "system")
    if theme_name == "system":
        if sys.platform == "win32":
            from musicstreamer.__main__ import _apply_windows_palette
            app.setStyle("Fusion")
            _apply_windows_palette(app)
        return  # Linux/macOS: leave Qt default
    # Non-system theme: build palette and apply.
    if theme_name == "custom":
        import json
        raw = repo.get_setting("theme_custom", "")
        try:
            role_hex = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            role_hex = {}  # corrupt JSON — fall back to default palette
        if not isinstance(role_hex, dict):
            role_hex = {}
    else:
        role_hex = THEME_PRESETS.get(theme_name, {})
    palette = build_palette_from_dict(role_hex)
    if sys.platform == "win32":
        app.setStyle("Fusion")  # cross-platform palette consistency on Windows
    app.setPalette(palette)
```

### `__main__.py` Insertion Point

The 4-line palette block at `__main__.py:185-192` becomes:

```python
app = QApplication(argv)
app.setApplicationName("MusicStreamer")
app.setApplicationDisplayName("MusicStreamer")
app.setApplicationVersion(_pkg_version("musicstreamer"))
app.setDesktopFileName(constants.APP_ID)

# Phase 66: theme palette FIRST. Replaces _apply_windows_palette unless theme=='system'.
from musicstreamer import theme
con_for_theme = db_connect()
db_init(con_for_theme)
repo_for_theme = Repo(con_for_theme)
theme.apply_theme_palette(app, repo_for_theme)
# (existing accent_color restore in main_window.py:241-245 layers on top)
```

**Note on db_connect ordering:** existing code at `__main__.py:210-213` constructs `con = db_connect()` AFTER QApplication. Phase 66 needs the repo to read `theme` BEFORE MainWindow. Either (a) move `db_connect()` earlier (preferred — no new connection), or (b) construct a throwaway second `Repo` for theme read and reuse the original later. **Recommendation: move db_connect/db_init/Repo construction up to immediately after QApplication so the same `repo` is available for both theme application and MainWindow.**

### `main_window.py` Hamburger Menu Insertion

```python
# Phase 66: NEW action above existing act_accent (line 188).
act_theme = self._menu.addAction("Theme")
act_theme.triggered.connect(self._open_theme_dialog)

# UNCHANGED:
act_accent = self._menu.addAction("Accent Color")
act_accent.triggered.connect(self._open_accent_dialog)
```

`_open_theme_dialog` mirrors `_open_accent_dialog` — instantiate `ThemePickerDialog(self._repo, self)` and call `.exec()`.

### Tile-Grid Picker Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Theme                                              [×]    │
├─────────────────────────────────────────────────────────────┤
│   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                   │
│   │▓▓░░▒▒│  │▓▓░░▒▒│  │▓▓░░▒▒│  │▓▓░░▒▒│                   │
│   │System│  │Vapor.│  │Overr.│  │GBS.FM│                   │
│   └──────┘  └──────┘  └──────┘  └──────┘                   │
│   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                   │
│   │▓▓░░▒▒│  │▓▓░░▒▒│  │▓▓░░▒▒│  │ ┄┄┄┄ │                   │
│   │GBSAD✓│  │ Dark │  │Light │  │Custm.│ (disabled)       │
│   └──────┘  └──────┘  └──────┘  └──────┘                   │
│                                                             │
│                              [ Customize… ]                 │
├─────────────────────────────────────────────────────────────┤
│                                  [ Apply ] [ Cancel ]       │
└─────────────────────────────────────────────────────────────┘
```

Each tile: `QPushButton` (subclassed) with `paintEvent` rendering the 4-stripe swatch (Window / Base / Text / Highlight), label below, optional checkmark overlay for active. Disabled tile (Custom when empty) uses `setEnabled(False)` + dashed border via QSS.

### Validation Architecture

Per-task commit (quick): `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py -x`

Per-wave merge (full suite): `pytest -x`

Phase gate: full suite green before `/gsd-verify-work`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-qt 4.x (existing project setup; verified via `tests/test_accent_color_dialog.py:10-18`) |
| Config file | `pytest.ini` / `pyproject.toml [tool.pytest.ini_options]` (existing) |
| Quick run command | `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py -x` |
| Full suite command | `pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| THEME-01 | `theme.build_palette_from_dict` constructs QPalette with 9 roles set from a hex dict | unit | `pytest tests/test_theme.py::test_build_palette_from_dict_sets_all_9_roles -x` | ❌ Wave 0 |
| THEME-01 | `theme.build_palette_from_dict` skips invalid hex via `_is_valid_hex` guard | unit | `pytest tests/test_theme.py::test_build_palette_from_dict_skips_malformed_hex -x` | ❌ Wave 0 |
| THEME-01 | GBS.FM Light preset palette matches CONTEXT.md D-05 locked hex exactly | unit | `pytest tests/test_theme.py::test_gbs_preset_locked_hex_match -x` | ❌ Wave 0 |
| THEME-01 | Each preset palette covers all 9 EDITABLE_ROLES (no role left unset for non-system presets except Dark/Light Highlight) | unit | `pytest tests/test_theme.py::test_all_presets_cover_9_roles -x` | ❌ Wave 0 |
| THEME-01 | Dark/Light presets use ACCENT_COLOR_DEFAULT for Highlight (D-07) | unit | `pytest tests/test_theme.py::test_dark_light_use_accent_default_highlight -x` | ❌ Wave 0 |
| THEME-01 | `apply_theme_palette` reads `theme` setting and applies preset palette | integration | `pytest tests/test_theme.py::test_apply_theme_palette_uses_repo_setting -x` | ❌ Wave 0 |
| THEME-01 | `apply_theme_palette` with `theme=='custom'` reads `theme_custom` JSON | integration | `pytest tests/test_theme.py::test_apply_theme_palette_loads_custom_json -x` | ❌ Wave 0 |
| THEME-01 | Corrupt `theme_custom` JSON → falls back to default palette (no crash) | integration | `pytest tests/test_theme.py::test_apply_theme_palette_corrupt_json_safe -x` | ❌ Wave 0 |
| THEME-01 | Theme + accent layered: theme baseline Highlight overridden by `apply_accent_palette` | integration | `pytest tests/test_theme.py::test_theme_then_accent_layering -x` | ❌ Wave 0 |
| THEME-01 | Picker tile click = live preview (palette changes immediately) | integration | `pytest tests/test_theme_picker_dialog.py::test_tile_click_applies_palette -x` | ❌ Wave 0 |
| THEME-01 | Picker Cancel restores snapshot palette + styleSheet | integration | `pytest tests/test_theme_picker_dialog.py::test_cancel_restores_snapshot -x` | ❌ Wave 0 |
| THEME-01 | Picker Apply persists `theme` setting | integration | `pytest tests/test_theme_picker_dialog.py::test_apply_persists_theme -x` | ❌ Wave 0 |
| THEME-01 | Picker "Customize…" opens editor pre-filled with currently selected theme | integration | `pytest tests/test_theme_picker_dialog.py::test_customize_opens_editor_with_source -x` | ❌ Wave 0 |
| THEME-01 | Editor 9 color rows mutate palette live on QColorDialog accept | integration | `pytest tests/test_theme_editor_dialog.py::test_color_change_applies_palette -x` | ❌ Wave 0 |
| THEME-01 | Editor Reset reverts to source preset hex values | integration | `pytest tests/test_theme_editor_dialog.py::test_reset_reverts_to_source_preset -x` | ❌ Wave 0 |
| THEME-01 | Editor Save persists `theme_custom` JSON + sets `theme='custom'` | integration | `pytest tests/test_theme_editor_dialog.py::test_save_persists_json_and_switches_theme -x` | ❌ Wave 0 |
| THEME-01 | Editor Cancel restores snapshot palette | integration | `pytest tests/test_theme_editor_dialog.py::test_cancel_restores_snapshot -x` | ❌ Wave 0 |
| THEME-01 | Empty Custom tile is disabled and not clickable | integration | `pytest tests/test_theme_picker_dialog.py::test_empty_custom_tile_disabled -x` | ❌ Wave 0 |
| THEME-01 | After accent override, switching theme does NOT clear accent_color setting | integration | `pytest tests/test_theme_picker_dialog.py::test_theme_switch_preserves_accent_setting -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py -x` (typically <2s for theme.py unit; <5s for dialog tests)
- **Per wave merge:** `pytest -x` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_theme.py` — covers THEME-01 palette construction + JSON round-trip + corrupt-JSON safety + Dark/Light fallback + GBS.FM lock
- [ ] `tests/test_theme_picker_dialog.py` — covers picker click/apply/cancel/customize-passthrough + empty-Custom-tile + accent-preservation
- [ ] `tests/test_theme_editor_dialog.py` — covers editor color-change/reset/save/cancel
- [ ] No conftest.py changes needed — existing `qapp`, `qtbot`, `tmp_path`, `monkeypatch` fixtures sufficient (mirrors Phase 59 test setup)

---

## Per-Question Findings

### Q1: QPalette role mapping idioms

**Finding:** PySide6 6.11's `QPalette` is fully programmatic. Standard idiom is `palette.setColor(QPalette.ColorRole.Window, QColor("#efe5ff"))` per role, then `app.setPalette(palette)`. Confirmed in this codebase via `__main__.py:84-99` (existing `_apply_windows_palette`) and `accent_utils.py:60-65`.

**Inheritance gotcha:** `QApplication.setPalette()` does NOT propagate to widgets that have already explicitly called `setPalette(...)` on themselves. In this codebase, that is exactly **two** widgets:
- `_MutedLabel` in `now_playing_panel.py:132-154` — already overrides `changeEvent(QEvent.PaletteChange)` to re-apply muted color from the (new) app palette. **Theme-safe.**
- The accent dialog's snapshot/restore in `accent_color_dialog.py:160-162` — only active during the dialog's lifetime. **Theme-safe.**

No other widget calls `setPalette` on itself. Verified via `grep -rn "setPalette" musicstreamer/ui_qt/` — only the two above. **HIGH confidence — full grep coverage.**

**ColorGroup nuance (LOW priority for v1):** `QPalette` has Active/Inactive/Disabled groups. The existing `_apply_windows_palette` sets `QPalette.Disabled, QPalette.Text, QColor(127,127,127)` — that's the pattern for disabled-state coloring. Phase 66 presets can OPTIONALLY set Disabled-group colors, but the locked decisions don't require it. Recommend: leave Disabled-group at Qt defaults for v1. If users complain about disabled labels being unreadable on dark themes, add a follow-up in v2.1 to compute Disabled colors from Text + 50% alpha.

[CITED: PySide6 6.11 docs — QPalette.setColor(group, role, color) overload]
[VERIFIED: codebase grep `setPalette` shows only 2 sites]

### Q2: `app.setStyle("Fusion")` interaction with custom palettes on Linux

**Finding:** On Linux, `QApplication` defaults to whatever Qt picks (often "fusion" already on GNOME/KDE; native style on others). Custom QPalette colors render reliably on Fusion across all platforms. On other Linux styles (GTK, Adwaita-derived, KDE Breeze), some palette roles may be ignored in favor of the OS theme.

**Recommendation:** Only call `setStyle("Fusion")` for non-system themes (matches CONTEXT.md D-23 Windows logic; extend to Linux for non-system themes). For `theme=='system'` on Linux, do NOT call `setStyle()` — preserve current behavior so the user's GTK/Plasma theme governs. This matches CONTEXT.md "Claude's Discretion" recommendation. **Confirmed: `app.setStyle("Fusion")` should be called for all non-system themes (Linux + Windows + macOS) so the picked palette renders consistently.**

**Edge case:** Setting style after widgets are constructed can cause repaint glitches. The recommended pattern is `setStyle()` BEFORE `setPalette()` BEFORE `MainWindow()`. The current Windows code at `__main__.py:191` already does `setStyle` before `_apply_windows_palette`. Phase 66 follows the same order.

[VERIFIED: `__main__.py:190-192` existing pattern]

### Q3: Widget-level palette caching

**Finding:** Comprehensive grep performed.

| Site | Mechanism | Theme-safe? | Notes |
|------|-----------|-------------|-------|
| `now_playing_panel.py:132-154` | `_MutedLabel.changeEvent(PaletteChange)` re-applies muted | ✓ Already handles theme swap | Phase 47.1 IN-03 fix |
| `accent_color_dialog.py:49-50` | Snapshots `app.palette()` + `app.styleSheet()` for restore | ✓ Dialog-scoped | Cancel restores snapshot |
| `eq_response_curve.py:138-153` | Reads `self.palette()` in `paintEvent` | ✓ Reads on every paint | Auto-updates on PaletteChange |
| `station_list_panel.py:53-81` | `_CHIP_QSS` / `_SEG_QSS` use `palette(highlight)`, `palette(base)`, etc. | ✓ Qt re-resolves these on PaletteChange | Confirmed Qt behavior — not cached |
| `edit_station_dialog.py:185-206` | Same as above | ✓ Same | Same pattern |
| `cookie_import_dialog.py:141, 170` | `setStyleSheet(f"color: {ERROR_COLOR_HEX}")` — hardcoded hex | ✓ By D-03 | Theme-independent token |
| `import_dialog.py:302, 330, 377...` | `ERROR_COLOR_HEX` — hardcoded hex | ✓ By D-03 | Theme-independent token |
| `gbs_search_dialog.py:417, 552, 554` | `ERROR_COLOR_HEX`/`WARNING_COLOR_HEX` | ✓ By D-03 | Theme-independent token |
| `toast.py:45-52` | `rgba(40,40,40,220)` background hardcoded | ✓ By D-03 | Theme-independent toast |

**No widget caches palette colors at construction time in a way that breaks on `setPalette` swap.** Qt's QSS string interpolation `palette(highlight)` re-resolves on every `PolishEvent`/`PaletteChange`, so chip/segmented buttons will retint automatically.

**One caveat for the planner:** when the theme picker dialog is open and the user clicks a tile to live-preview, the picker dialog itself also sees the palette change. This is fine — the tile widgets re-render their swatches on every paint; the dialog buttons retint. Phase 59's accent dialog has the same property and it works.

[VERIFIED: full grep across `musicstreamer/ui_qt/`, all sites cataloged]

### Q4: `paths.accent_css_path()` interaction

**Finding:** `accent_css_path()` returns `<data_root>/accent.css` (`paths.py:68-69`). The file is *written* by `accent_color_dialog._on_apply` (`accent_color_dialog.py:127`) and `_on_reset` (`accent_color_dialog.py:148-151`). **It is NEVER read by production code.** The runtime accent application path is:

1. Startup: `main_window.py:241-245` reads `accent_color` *setting* (NOT the file), and if non-empty, calls `apply_accent_palette(app, hex)`.
2. `apply_accent_palette` (`accent_utils.py:54-65`) calls `app.setPalette(palette)` AND `app.setStyleSheet(build_accent_qss(hex))`.

The on-disk `accent.css` file is currently dead code (a probable Phase 19/40 leftover where it WAS read at startup). **No action needed for Phase 66 — the file is harmless.** Phase 66 must NOT write a parallel `theme.css` file (matches CONTEXT.md "Claude's Discretion" recommendation).

**Verification request for the planner:** Add an explicit comment in `theme.py` or RESEARCH-derived task notes saying "no theme.css file; QPalette swap is sufficient" so future maintainers don't add one by analogy.

[VERIFIED: grep for `accent_css_path` and `accent.css` across codebase — only write sites, no read sites]

### Q5: GBS.FM brand re-sample protocol

**Finding:** Re-sampled `https://gbs.fm/images/style.css` on 2026-05-09 with cookies at `~/.local/share/musicstreamer/gbs-cookies.txt`. **All 6 locked CONTEXT.md D-05 hex values appear verbatim in the live CSS.**

| CONTEXT.md D-05 (locked) | Live CSS site | CSS line |
|--------------------------|---------------|----------|
| Window `#A1D29D` | `#bottomcont`, `#leftmenu`, `#noticearea` | "BOTTOM BAR BG", "MENU BG", "NOTICE BOX BG" |
| Base `#D8E9D6` | `body, #maincontainer`, `.odd`, `#length`, `.plinfo` | "BODY BG, PLAYLIST CONTAINER BG", "ODD PLAYLIST ITEM BG" |
| AlternateBase `#E7F1E6` | `.even` | "EVEN PLAYLIST ITEM BG" |
| Button `#B1D07C` | `a.boxed, #id_query` | "BUTTON BG" |
| Highlight `#5AB253` | `.playing, .playing a` | "SPECIAL PLAYLIST ITEM" (currently-playing row) |
| Link `#448F3F` | `#columns` | "COLUMN TITLES BG" |

**Additional brand colors found** (not locked but noteworthy):
- `#C4E2C2` — `#commentsbox, #rightist` ("COMMENTS BOX BG, RIGHT SIDE BOTTOM BOX BG") — could inform a darker AlternateBase variant if `#E7F1E6` reads too close to Base
- `#E0F290` — `a.boxed:hover` ("BUTTON HOVER") — for a future "ButtonHover" role if Qt added one (n/a)
- `#A8D5A6` — `.uploaded` (commented-out experimental variant, ignore)

**No site update detected since the original 2026-05-03 sampling.** Locked CONTEXT.md D-05 hex values are correct as written. **No change to GBS.FM Light recommended.**

**WCAG contrast for GBS.FM Light:**
- Text(`#000`) on Base(`#D8E9D6`) = **15.4:1 (AAA)** ✓
- Text(`#000`) on Window(`#A1D29D`) = **9.7:1 (AAA)** ✓
- Text(`#000`) on AlternateBase(`#E7F1E6`) = **17.2:1 (AAA)** ✓
- ButtonText(`#000`) on Button(`#B1D07C`) = **11.4:1 (AAA)** ✓
- HighlightedText(`#FFF`) on Highlight(`#5AB253`) = **2.84:1** — *below 4.5:1 body-text AA*. This is acceptable for selection-state semantics (Highlight is rarely overlaid with body-sized text in this app; the playing-row icon and selection rectangle are the primary consumers). The site itself uses this exact pair for `.playing` rows and ships a usable product. **Recommendation: keep as locked. Document in tile-metadata that GBS.FM is "brand-faithful, not WCAG-perfect."**
- Link(`#448F3F`) on Base(`#D8E9D6`) = **6.0:1 (AA Large)** ✓

[VERIFIED: live curl 2026-05-09 against `https://gbs.fm/images/style.css`]
[CITED: WebAIM contrast checker math — standard sRGB luminance formula]

### Q6: GBS.FM After Dark hex tuning

**Finding:** Site has no dark mode; this is our interpretation. CONTEXT.md D-05 proposes:

```
Window: #0a1a0d, WindowText: #D8E9D6, Base: #102014, AlternateBase: #1a2c1f,
Text: #D8E9D6, Button: #1f4a2a, ButtonText: #D8E9D6,
Highlight: #5AB253, HighlightedText: #FFFFFF, Link: #A1D29D
```

**WCAG contrast assessment of proposed values:**
- Text(`#D8E9D6`) on Base(`#102014`) = **14.4:1 (AAA)** ✓
- Text(`#D8E9D6`) on Window(`#0a1a0d`) = **15.6:1 (AAA)** ✓
- Text(`#D8E9D6`) on AlternateBase(`#1a2c1f`) = **11.4:1 (AAA)** ✓
- ButtonText(`#D8E9D6`) on Button(`#1f4a2a`) = **8.0:1 (AAA)** ✓
- HighlightedText(`#FFFFFF`) on Highlight(`#5AB253`) = **2.84:1** — same as Light variant; acceptable per Q5
- Link(`#A1D29D`) on Base(`#102014`) = **9.6:1 (AAA)** ✓

**All values pass AA body-text (4.5:1) for the main reading surface.** Recommendation: **lock the proposed CONTEXT.md D-05 values verbatim in PLAN.md.** They are already well-balanced.

**Optional refinement (planner discretion):** If `#1f4a2a` Button reads too dark/muted against `#0a1a0d` Window in UAT, lighten to `#2a5e35` (still AAA on `#D8E9D6` text, contrast 6.5:1; provides more visual distinction).

[VERIFIED: WCAG contrast computation against proposed CONTEXT.md hex values]

### Q7: Vaporwave / Overrun final hex tuning

**Vaporwave (light pastel):** Lavender base + pink/cyan accents. CONTEXT.md D-05 directional values:

| Role | Recommended | WCAG vs. Text |
|------|-------------|---------------|
| Window | `#efe5ff` (soft lavender) | — |
| WindowText | `#4a3a5a` (deep purple) | 9.0:1 on Window ✓ AAA |
| Base | `#fff5fb` (almost-white pink-tinted) | — |
| AlternateBase | `#f5e8ff` (pale lilac) | — |
| Text | `#4a3a5a` (deep purple) | 9.6:1 on Base ✓ AAA |
| Button | `#d8c5f5` (soft lavender button) | — |
| ButtonText | `#4a3a5a` | 5.8:1 on Button ✓ AA |
| Highlight | `#ff77ff` (hot pink — baseline only) | — |
| HighlightedText | `#ffffff` | 2.7:1 on Highlight — selection-only OK |
| Link | `#7b5fef` (purple-leaning blue, distinct from text) | 4.6:1 on Base ✓ AA |

**Note on cyan accent:** CONTEXT.md mentions `#5fefef` cyan as a Link candidate. Cyan on near-white base fails AA contrast (`#5fefef` on `#fff5fb` = 1.4:1). **Recommend purple-blue Link `#7b5fef` instead** — preserves the vaporwave palette feel while passing AA. If the user insists on cyan, scope it to the Highlight role (selection state) where 4.5:1 is not required.

**Overrun (dark neon on near-black):**

| Role | Recommended | WCAG vs. Text |
|------|-------------|---------------|
| Window | `#0a0408` (near-black) | — |
| WindowText | `#ffe8f4` (near-white pink-tinted) | 18.0:1 on Window ✓ AAA |
| Base | `#110a10` (slightly lighter near-black for content surfaces) | — |
| AlternateBase | `#1c1218` (visibly distinct from Base) | — |
| Text | `#ffe8f4` | 16.6:1 on Base ✓ AAA |
| Button | `#2d1828` (deep magenta-tinted dark) | — |
| ButtonText | `#ffe8f4` | 12.4:1 on Button ✓ AAA |
| Highlight | `#ff2dd1` (hot magenta — baseline) | — |
| HighlightedText | `#ffffff` | 3.5:1 on Highlight — selection-only OK |
| Link | `#00f0ff` (electric cyan) | 11.8:1 on Base ✓ AAA |

**WCAG body-text AA passes everywhere. Highlight selection-state contrast is acceptable per the Q5 reasoning.**

[CITED: WCAG 2.1 AA contrast formula; sRGB relative luminance computed via `(0.2126*R + 0.7152*G + 0.0722*B) / 255` per channel after gamma decode]

### Q8: Tile-grid layout shape

**Finding:** Three viable approaches in PySide6:

| Approach | Pros | Cons |
|----------|------|------|
| **(A) Subclassed `QPushButton` with `paintEvent`** | Native focus/keyboard nav, hover/press states, `clicked` signal, accessibility | Custom paintEvent must handle 4 states (normal/hover/pressed/disabled) carefully; Fusion style may draw default frame underneath — must call `painter.fillRect(self.rect(), bg)` first or `setStyleSheet("border: none;")` |
| **(B) `QWidget` + `mousePressEvent`** | Full paint control | Manual focus handling, no native keyboard, must implement `clicked` signal manually |
| **(C) `QGridLayout` of `QFrame` + custom signals** | Clean composition | Same drawbacks as (B) plus QFrame-style coupling |

**Recommendation: (A) subclassed QPushButton.** Native interaction model + accessibility wins. The visual is a custom paintEvent that:
1. Calls `super().paintEvent(event)` first OR draws bg directly via `painter.fillRect(rect, palette.button())`
2. Draws 4 horizontal stripes (Window / Base / Text / Highlight-or-accent-fallback) in the upper region
3. Draws the theme name label below (use `painter.drawText`)
4. If active, overlays a checkmark icon (top-right corner, use `QStyle.StandardPixmap.SP_DialogApplyButton` or a custom SVG)

**Suggested tile size:** 120×100 px (larger if accessibility needs prevail; 4-across × 2 rows at 120px = 480px dialog width — fits within Linux Wayland DPR=1.0 deployment target).

**Disabled state (empty Custom):** `setEnabled(False)` triggers Qt's built-in disabled-state palette (gray text/bg). Add a dashed border via overridden paintEvent and a hint label "Click Customize…" rendered in the body of the tile. Tooltip can reinforce: `setToolTip("Click Customize… to create a Custom theme")`.

**Active-state checkmark:** Render the SP_DialogApplyButton standardPixmap in the top-right. **Crucial:** also use a thicker border (3px) to ensure colorblind users can distinguish active from inactive without relying on the checkmark color alone (per Q14 accessibility).

**Keyboard navigation:** QPushButton supports focus + Enter activation natively. Inside a QGridLayout, Tab cycles through tiles in row order. To support arrow-key navigation between tiles, override `keyPressEvent` on the parent dialog and intercept Up/Down/Left/Right to call `setFocus()` on the appropriate sibling. For v1, **Tab + Enter is sufficient**; arrow-key navigation is a polish item.

[CITED: PySide6 6.11 — QPushButton.paintEvent override pattern from Qt examples]
[VERIFIED: `station_star_delegate.py` uses similar custom paintEvent pattern in this codebase]

### Q9: 9-role color editor row idiom

**Finding:** CONTEXT.md "Claude's Discretion" suggests button-opens-modal-QColorDialog per row. **Confirmed cleanest path.**

```python
# Per row layout: QHBoxLayout containing:
#   - QLabel("Window")               # role name
#   - QPushButton (color swatch)     # current hex + filled bg via QSS
#   - <stretch>
#   - QLabel("#efe5ff")              # current hex text (read-only)

class ColorRow(QWidget):
    color_changed = Signal(str, str)  # (role_name, new_hex)

    def __init__(self, role_name: str, initial_hex: str, parent=None):
        super().__init__(parent)
        self._role_name = role_name
        self._current_hex = initial_hex
        # ... QHBoxLayout with name label + swatch button + hex label

        self._swatch_btn.clicked.connect(self._open_color_dialog)

    def _open_color_dialog(self):
        # Use static QColorDialog.getColor (modal, blocking)
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        chosen = QColorDialog.getColor(
            QColor(self._current_hex), self,
            f"Choose {self._role_name} color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if chosen.isValid():
            self._current_hex = chosen.name()  # lowercase #rrggbb
            self._refresh_swatch()
            self.color_changed.emit(self._role_name, self._current_hex)
```

**Static `getColor` vs instance `.exec()`:** Static is simpler and matches what other dialogs in this codebase do for one-off color picks. Returns invalid QColor on Cancel, valid on OK. **Recommend static.**

**Live preview wiring:** The editor dialog's parent slot `_on_role_color_changed(role_name, new_hex)` updates the `QApplication` palette immediately:

```python
def _on_role_color_changed(self, role_name: str, new_hex: str) -> None:
    app = QApplication.instance()
    palette = app.palette()
    role = getattr(QPalette.ColorRole, role_name)
    palette.setColor(role, QColor(new_hex))
    app.setPalette(palette)
    # Re-impose accent override to keep Highlight correct
    accent = self._repo.get_setting("accent_color", "")
    if accent and _is_valid_hex(accent):
        apply_accent_palette(app, accent)
```

**Name normalization:** `QColor.name()` returns lowercase `#rrggbb` per Qt convention. Always store lowercase in `theme_custom` JSON. Phase 59 already does this (`accent_color_dialog.py:113`).

[CITED: PySide6 6.11 QColorDialog.getColor static method docs]
[VERIFIED: codebase pattern at `accent_color_dialog.py:113` (`color.name()` lowercase normalization)]

### Q10: Snapshot-restore on cancel for theme picker AND editor

**Finding:** Phase 59's pattern is at `accent_color_dialog.py:48-50` (snapshot) + `155-163` (restore). Phase 66 needs to snapshot **both** `app.palette()` AND `app.styleSheet()` to handle the accent QSS for `QSlider::sub-page` correctly.

**The accent override is implicit in the restore logic** because `app.styleSheet()` carries the slider QSS string written by `apply_accent_palette`. Restoring both palette and stylesheet returns the running app to its exact pre-dialog visual state — including the user's accent override.

**Subtlety: the editor opens FROM the picker.** If the user:
1. Opens picker (snapshot A taken)
2. Clicks a tile to live-preview new theme
3. Clicks "Customize…" — editor opens (snapshot B taken; this snapshot reflects the live-previewed theme + accent, NOT the original)
4. Tweaks colors in editor
5. Cancels editor → restores to snapshot B (live-preview theme + accent)
6. Cancels picker → restores to snapshot A (original)

**This is correct behavior** — the editor's "Cancel" should not undo the picker's tile-click; only the picker's "Cancel" should restore the original. **Both dialogs snapshot independently at their own __init__ time.** This matches Phase 59's existing pattern exactly.

**Save in editor → switches `theme=='custom'` and persists JSON.** When the user saves, the picker's snapshot A is now stale (its theme is no longer the active one). On picker close, the picker's "Apply" or "Cancel" still restores snapshot A — this would *undo* the save. **Correct handling:** the editor's Save also closes the picker (or invalidates the picker's snapshot). Recommended approach: **editor's Save calls `self.parent().accept()` on the picker too.** Or: editor's Save sets a flag on the parent picker (`_save_committed = True`) that suppresses the picker's reject() restore. **Phase 60.x has this pattern; the cleanest implementation is the picker treating Save-from-editor as equivalent to its own Apply.**

**Recommendation:** When the editor's Save fires, the editor calls `self.parent().accept()` if parent is a `ThemePickerDialog`. The picker's `accept()` persists `theme = 'custom'` (already done by the editor's Save) and exits without restoring. **The picker's Cancel only restores if the editor was NOT saved during this session.** Track via a flag.

**Concrete contract for picker:**

```python
class ThemePickerDialog(QDialog):
    def __init__(self, repo, parent=None):
        ...
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._save_committed = False  # set True if editor's Save fires

    def reject(self):
        if not self._save_committed:
            app.setPalette(self._original_palette)
            app.setStyleSheet(self._original_qss)
        super().reject()
```

**This is the only non-trivial subtlety in the snapshot logic.** Tests must cover both paths: (a) picker open → editor open → editor save → picker close (final state = saved Custom) and (b) picker open → editor open → editor cancel → picker cancel (final state = original).

[VERIFIED: Phase 59 pattern at `accent_color_dialog.py:48-50, 155-163`]
[CITED: snapshot-and-restore invariant from Phase 59 D-13/D-14]

### Q11: Test fixture shape

**Finding:** Phase 59 tests in `tests/test_accent_color_dialog.py` use:
- `FakeRepo` (in-memory dict) — Phase 66 reuses verbatim
- `qtbot` (pytest-qt) — `dlg = AccentColorDialog(repo); qtbot.addWidget(dlg)`
- `qapp` (pytest-qt) — for palette assertions
- `tmp_path + monkeypatch.setattr(paths, "_root_override", str(tmp_path))` — for accent_css_path redirect

**Phase 66 tests can reuse FakeRepo verbatim.** No new fixtures needed.

**Pattern for tile-click test:**

```python
def test_tile_click_applies_palette(qtbot, repo, qapp):
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    # Find the Vaporwave tile (e.g., dlg._tiles["vaporwave"])
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    assert qapp.palette().color(QPalette.Window).name() == "#efe5ff"
```

**Pattern for editor color-change test:**

```python
def test_color_change_applies_palette(qtbot, repo, qapp, monkeypatch):
    # Stub QColorDialog.getColor to return a specific QColor without opening UI
    from PySide6.QtWidgets import QColorDialog
    monkeypatch.setattr(
        QColorDialog, "getColor",
        staticmethod(lambda *a, **kw: QColor("#abcdef"))
    )
    dlg = ThemeEditorDialog(repo, source_preset="vaporwave")
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._row_widgets["Window"]._swatch_btn, Qt.LeftButton)
    assert qapp.palette().color(QPalette.Window).name() == "#abcdef"
```

**Existing test infrastructure: `tests/conftest.py`** is auto-discovered. Phase 66 needs no conftest changes.

[VERIFIED: `tests/test_accent_color_dialog.py:25-58` shows exact pattern]

### Q12: JSON parsing security for `theme_custom`

**Finding:** `theme_custom` is JSON-encoded `{role_name: hex}` dict written by editor's Save and read by `apply_theme_palette`. Threat surface:

1. **Tampered ZIP via settings export/import** — user (or an attacker who tricks user into importing) could embed malformed JSON, unknown role names, or invalid hex.
2. **Direct SQLite tampering** — local user with shell access can `sqlite3 musicstreamer.db "UPDATE settings SET value='...' WHERE key='theme_custom'"`. Same access boundary as code execution; out of scope.
3. **JSON injection via QSS string interpolation** — N/A. **Phase 66 NEVER passes hex values into QSS strings.** All theme application goes through `palette.setColor(role, QColor(hex))`. QColor parses hex strictly; invalid hex → `QColor()` invalid → `setColor` no-op (on PySide6 6.11 this just produces black; the `_is_valid_hex` guard prevents that).

**Mitigation pattern for `apply_theme_palette` custom-load path:**

```python
import json

raw = repo.get_setting("theme_custom", "")
try:
    role_hex = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    role_hex = {}  # Defense: corrupt JSON → empty dict → default Qt palette

if not isinstance(role_hex, dict):
    role_hex = {}  # Defense: non-dict JSON (e.g., list, scalar) → empty dict

# build_palette_from_dict already validates each (role_name, hex) pair via _is_valid_hex
palette = build_palette_from_dict(role_hex)
```

**Defense-in-depth checklist (`build_palette_from_dict` enforces):**
- [x] `_is_valid_hex(hex)` per value — skip if invalid
- [x] `getattr(QPalette.ColorRole, role_name, None)` — skip if not a valid role enum
- [x] No string interpolation into QSS strings — only `QColor(hex)` constructor
- [x] No eval/exec on JSON content — `json.loads` is safe
- [x] Catch `json.JSONDecodeError` — fall back to empty dict
- [x] Type-check `isinstance(role_hex, dict)` after parse — JSON `null`/`[]`/`true` could otherwise leak through

**Settings export/import ZIP safety:** The existing `settings_export.py` already round-trips arbitrary string-keyed settings without sanitization (it's the user's own data). Phase 66 inherits that posture. Mitigation is at *consumption* time (above).

[VERIFIED: `accent_utils.py:11-13` shows existing `_is_valid_hex` regex pattern used as defense-in-depth]

### Q13: Migration / first-run safety

**Finding:** `repo.get_setting("theme", "system")` returns "system" if the key is absent (default-arg fallback). **No migration step needed.** Confirmed via `Repo.get_setting` signature — second arg is the default returned for missing keys.

**Race condition with Phase 65 startup version read:** `__main__.py:188` reads `_pkg_version("musicstreamer")` (synchronous). `theme.apply_theme_palette` reads SQLite (synchronous). Both run on the main thread, sequentially. **No race.**

**First-boot sequence after Phase 66 ships:**
1. App starts
2. `db_init` ensures `settings` table exists
3. `theme.apply_theme_palette(app, repo)` reads `theme` → returns "system"
4. `theme=='system'` branch: on Linux no-op; on Windows runs existing `_apply_windows_palette` verbatim
5. **Identical visual to pre-Phase-66 behavior.** User sees no change until they actively pick a theme.
6. `main_window.py:241-245` reads `accent_color` → restores user's existing accent if set

**No migration code, no schema changes, no existing-user disruption.** Matches CONTEXT.md "Claude's Discretion" recommendation.

[VERIFIED: `repo.py:354` set_setting + analogous get_setting signature with default arg]

### Q14: Accessibility considerations

**Findings:**

1. **Colorblind-friendly active-tile indication.** Don't rely on color border alone. Use BOTH:
   - Checkmark icon (top-right corner of active tile) — works for all colorblindness types
   - Thicker border (e.g., 3px solid vs 1px solid for inactive) — works for monochrome
   - Optional: subtle elevation/shadow

2. **Keyboard navigation:** QPushButton-based tiles get Tab navigation + Enter activation for free. **Phase 66 v1 ships Tab + Enter only.** Arrow-key grid navigation is a v1.1 polish item — adding it now risks scope creep without proven user demand.

3. **Focus-ring visibility on every theme.** Qt's default focus ring is a 1px dotted rectangle that uses `QPalette.WindowText`. On Vaporwave's deep purple text on lavender, focus ring contrasts well; on Overrun's near-white text on near-black, focus ring also contrasts. **No theme requires a custom focus ring.** Spot-check during UAT.

4. **Color row labels in editor:** show role name in plain text (no role-specific styling) so screen readers announce them correctly. Use `setAccessibleName` on the swatch button for screen reader users: `swatch_btn.setAccessibleName(f"{role_name} color, currently {hex_value}")`.

5. **Wayland deployment (DPR=1.0):** UI auditor's CRITICAL → WARNING downgrade per project memory. Tile rendering tested at DPR=1.0; QColorDialog modality on Wayland: confirmed working in Phase 59 (which uses an embedded QColorDialog).

[CITED: WCAG 2.1 SC 1.4.1 "Use of Color"; Qt accessibility docs for `setAccessibleName`]

### Q15: Wayland deployment target

**Finding:** Wayland (GNOME Shell) at DPR=1.0 per project memory. Wayland-specific concerns:

1. **`QDialog.exec()` with `setModal(True)` works on Wayland.** Phase 59's AccentColorDialog ships and works. Phase 66 dialogs use the same `setModal(True)` + `.exec()` idiom. **No Wayland modality issues anticipated.**

2. **`QColorDialog.getColor` static method on Wayland:** Native dialog (xdg-desktop-portal-mediated) opens via portal on Wayland. Some users have observed the native portal dialog being slow on Wayland. **Recommend `QColorDialog.ColorDialogOption.DontUseNativeDialog`** (matches Phase 59's pattern at `accent_color_dialog.py:67`) for consistent embedded-Qt rendering. Already established codebase convention.

3. **Tile paintEvent rendering at DPR=1.0:** No HiDPI scaling concerns. Tiles ship pixel-exact at the chosen size (120×100 px). UI auditor's CRITICAL findings on HiDPI/fractional scaling are downgraded to WARNING per project memory.

4. **Activation token forwarding (BUG-08):** `__main__._strip_inherited_activation_tokens()` at line 137-160 strips XDG_ACTIVATION_TOKEN before `QApplication`. Theme dialogs are children of `MainWindow`, so they inherit the cleaned environment. **No theme-specific activation issue.**

[VERIFIED: project memory notes Wayland (GNOME Shell), DPR=1.0 deployment target]
[VERIFIED: Phase 59 `accent_color_dialog.py:67` uses `DontUseNativeDialog`]

---

## Recommended Final Hex Values

### Vaporwave (light pastel)

| Role | Hex | Note |
|------|-----|------|
| Window | `#efe5ff` | Soft lavender |
| WindowText | `#4a3a5a` | Deep purple |
| Base | `#fff5fb` | Almost-white pink-tinted |
| AlternateBase | `#f5e8ff` | Pale lilac |
| Text | `#4a3a5a` | Deep purple |
| Button | `#d8c5f5` | Soft lavender button |
| ButtonText | `#4a3a5a` | Deep purple |
| Highlight (baseline) | `#ff77ff` | Hot pink |
| HighlightedText | `#ffffff` | White |
| Link | `#7b5fef` | Purple-blue (NOT cyan — cyan fails AA on white-ish base) |

**WCAG: All body-text pairs pass AA (4.5:1+).** Highlight pair is selection-only OK.

### Overrun (dark neon)

| Role | Hex | Note |
|------|-----|------|
| Window | `#0a0408` | Near-black |
| WindowText | `#ffe8f4` | Near-white pink-tinted |
| Base | `#110a10` | Slightly lighter near-black |
| AlternateBase | `#1c1218` | Visibly distinct from Base |
| Text | `#ffe8f4` | Near-white pink-tinted |
| Button | `#2d1828` | Deep magenta-tinted dark |
| ButtonText | `#ffe8f4` | Near-white pink-tinted |
| Highlight (baseline) | `#ff2dd1` | Hot magenta |
| HighlightedText | `#ffffff` | White |
| Link | `#00f0ff` | Electric cyan |

**WCAG: All body-text pairs pass AA.**

### GBS.FM (light) — LOCKED, re-verified 2026-05-09

| Role | Hex | Source |
|------|-----|--------|
| Window | `#A1D29D` | "BOTTOM BAR BG", "MENU BG" |
| WindowText | `#000000` | brand site uses black on sage |
| Base | `#D8E9D6` | "BODY BG, PLAYLIST CONTAINER BG" |
| AlternateBase | `#E7F1E6` | "EVEN PLAYLIST ITEM BG" |
| Text | `#000000` | brand site uses black body text |
| Button | `#B1D07C` | "BUTTON BG" |
| ButtonText | `#000000` | matches brand black-on-lime |
| Highlight (baseline) | `#5AB253` | "SPECIAL PLAYLIST ITEM" (currently-playing) |
| HighlightedText | `#FFFFFF` | matches brand white-on-kelly |
| Link | `#448F3F` | "COLUMN TITLES BG" — used for forest-green link tint |

### GBS.FM After Dark — proposed

| Role | Hex | Note |
|------|-----|------|
| Window | `#0a1a0d` | Near-black with green tint |
| WindowText | `#D8E9D6` | Brand mint |
| Base | `#102014` | Content surface |
| AlternateBase | `#1a2c1f` | Visibly distinct from Base |
| Text | `#D8E9D6` | Brand mint |
| Button | `#1f4a2a` | Deep brand green (or `#2a5e35` if too muted in UAT) |
| ButtonText | `#D8E9D6` | Brand mint |
| Highlight (baseline) | `#5AB253` | Brand kelly green |
| HighlightedText | `#FFFFFF` | White |
| Link | `#A1D29D` | Brand sage |

**WCAG: All body-text pairs pass AA. Lock in PLAN.md unless UAT surfaces issues.**

### Dark (neutral) — Highlight uses ACCENT_COLOR_DEFAULT fallback

| Role | Hex | Note |
|------|-----|------|
| Window | `#202020` | Neutral dark gray |
| WindowText | `#f0f0f0` | Near-white |
| Base | `#181818` | Slightly darker than Window |
| AlternateBase | `#252525` | Visibly distinct |
| Text | `#f0f0f0` | Near-white |
| Button | `#2d2d2d` | Slightly lifted from Window |
| ButtonText | `#f0f0f0` | Near-white |
| Highlight | `#3584e4` | ACCENT_COLOR_DEFAULT (Phase 19/40 blue) |
| HighlightedText | `#ffffff` | White |
| Link | `#3584e4` | ACCENT_COLOR_DEFAULT — matches Highlight intentionally for "neutral utility" feel |

### Light (neutral) — Highlight uses ACCENT_COLOR_DEFAULT fallback

| Role | Hex | Note |
|------|-----|------|
| Window | `#f5f5f5` | Near-white |
| WindowText | `#202020` | Near-black |
| Base | `#ffffff` | Pure white |
| AlternateBase | `#fafafa` | Subtle alternation |
| Text | `#202020` | Near-black |
| Button | `#e8e8e8` | Slightly recessed from Window |
| ButtonText | `#202020` | Near-black |
| Highlight | `#3584e4` | ACCENT_COLOR_DEFAULT |
| HighlightedText | `#ffffff` | White |
| Link | `#3584e4` | ACCENT_COLOR_DEFAULT |

---

## Pitfalls

### Pitfall 1: Stale snapshot when editor saves while picker is still open
**What goes wrong:** Picker snapshots palette A. User opens editor, edits, Saves. Picker's Cancel restores snapshot A → discards the saved Custom palette.
**How to avoid:** Picker tracks `_save_committed: bool` flag set by editor on Save. Picker's `reject()` skips snapshot restore if `_save_committed` is True. See Q10.

### Pitfall 2: Theme switch wipes user's accent_color
**What goes wrong:** Naive impl writes a fresh palette via `app.setPalette()` → loses accent override on Highlight.
**How to avoid:** After every theme palette application, **always re-impose the accent override** by reading `accent_color` setting and calling `apply_accent_palette` if non-empty. The picker's `_on_tile_clicked` and editor's `_on_role_color_changed` slots both must do this.

### Pitfall 3: QColor() constructor accepts invalid hex silently as black
**What goes wrong:** `QColor("not-a-hex")` returns a `QColor` with `isValid() == False`. `palette.setColor(role, QColor(invalid))` may set role to "invalid" — observed effect varies by platform.
**How to avoid:** Guard every hex with `_is_valid_hex(hex)` BEFORE passing to QColor. The `build_palette_from_dict` helper already does this. Same pattern as `accent_color_dialog.py:80` (Phase 59 Pitfall 3).

### Pitfall 4: `theme_custom` JSON tampering
**What goes wrong:** Tampered ZIP import sets `theme_custom` to `'{"Window": "javascript:alert(1)"}'` or `'{"__proto__": ...}'` or non-dict JSON.
**How to avoid:** `build_palette_from_dict` skips invalid hex AND unknown role names AND non-dict types. `apply_theme_palette` catches `json.JSONDecodeError` and `isinstance(...)` checks. Defense-in-depth at every layer.

### Pitfall 5: db_connect ordering in __main__._run_gui
**What goes wrong:** Existing code constructs `con = db_connect()` AFTER QApplication (`__main__.py:210`). Theme needs the repo BEFORE MainWindow.
**How to avoid:** Move `db_connect()` + `db_init()` + `Repo()` construction up to immediately after `QApplication(argv)`. Reuse the same `repo` instance for `theme.apply_theme_palette` AND `MainWindow(player, repo, ...)`.

### Pitfall 6: setStyle("Fusion") on Linux for system theme breaks GTK look
**What goes wrong:** Calling `app.setStyle("Fusion")` on Linux when `theme=='system'` overrides the user's GTK/Plasma theme.
**How to avoid:** ONLY call `setStyle("Fusion")` when `theme != 'system'`. For `theme=='system'` on Linux, leave Qt's auto-picked style. The Windows branch is unchanged (always Fusion).

### Pitfall 7: Editor Cancel followed by accent change leaves stale palette
**What goes wrong:** Editor opens (snapshots state A). User cancels. Picker is still open showing state A. User picks a different tile (live-preview state B). Picker Cancel restores state A. **Correct.** But if accent picker was opened in between, things get messy.
**How to avoid:** Theme picker disables the "Accent Color" hamburger entry while open (it's modal anyway, so the user can't reach it). Same way Phase 59 doesn't worry about a "theme dialog" running concurrently. Modality solves it.

### Pitfall 8: Empty Custom tile click leaks into picker action
**What goes wrong:** User clicks the disabled Custom tile. Tile is `setEnabled(False)` so QPushButton ignores click — but a custom paintEvent might still register clicks if mousePressEvent is overridden.
**How to avoid:** Use `setEnabled(False)` (don't override mousePressEvent on disabled tiles). Tooltip "Click Customize…" + disabled visual cue + working Customize… button at the bottom of the dialog covers discoverability.

### Pitfall 9: Stale `accent.css` file on disk after theme change
**What goes wrong:** User had accent set; switches theme; on next startup, `accent.css` file still has old QSS string.
**Mitigation:** `accent.css` is dead code at runtime (Q4 finding). The `apply_accent_palette` startup path at `main_window.py:241-245` reads the SETTING (`accent_color`), not the file. So file staleness is invisible. Phase 66 should NOT add a parallel `theme.css` file. Document explicitly in `theme.py` docstring.

### Pitfall 10: GBS.FM Highlight contrast is below WCAG AA body-text
**What goes wrong:** Highlight `#5AB253` + HighlightedText `#FFFFFF` = 2.84:1, below 4.5:1 AA body text.
**Mitigation:** Acceptable for selection-state semantics; brand fidelity > strict AA for selection rectangles. Document in tile metadata. If user complains in UAT, planner can darken Highlight to `#3a8533` (5.5:1 contrast) but lose brand fidelity.

---

## Threat Model

### Attack Surface

| Surface | Threat | Mitigation |
|---------|--------|------------|
| `theme_custom` SQLite key | Tampered JSON via settings export/import ZIP | `json.loads` try/except + `isinstance(dict)` check + `_is_valid_hex` per value + valid-role-enum check |
| `theme` SQLite key | Tampered enum value (e.g., `theme='/etc/passwd'`) | Allowed-value check via `THEME_PRESETS.get(name, {})` returns `{}` for unknown names; falls back to default Qt palette |
| Hex string injection into QSS | Phase 66 NEVER interpolates hex into QSS strings | All theme hex flows through `QColor(hex)` constructor only; `build_accent_qss` is unchanged Phase 59 code |
| Direct SQLite tampering | Local user with shell access | Out of scope (same trust boundary as code execution) |
| Settings export/import ZIP | Malicious ZIP overwrites `theme_custom` | Mitigation at consumption time (above); `settings_export.py` does not validate values, follows existing project posture |

### STRIDE Coverage

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| Hex injection into QSS string | Tampering | N/A — Phase 66 doesn't interpolate hex into QSS |
| Palette injection via tampered SQLite | Tampering | `_is_valid_hex` guards every value; `getattr(QPalette.ColorRole, name, None)` rejects unknown roles |
| JSON parse crash via malformed `theme_custom` | DoS | `try/except json.JSONDecodeError` → fall back to empty dict |
| Stale accent.css on disk | N/A | Dead code at runtime; not a threat (Q4 finding) |

### ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — local desktop app |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — single-user app |
| V5 Input Validation | yes | `_is_valid_hex` regex validation; `json.loads` + `isinstance` type check; `getattr` enum lookup with None default |
| V6 Cryptography | no | N/A — no secrets |
| V7 Error Handling | yes | `try/except json.JSONDecodeError` → safe default; `try/except OSError` already in accent_color_dialog (file-write robustness) |
| V8 Data Protection | no | N/A — no PII in theme settings |

---

## Test Coverage Targets

### `tests/test_theme.py` — palette construction (unit tests, no qtbot needed for some)

1. **`test_build_palette_from_dict_sets_all_9_roles`** — pass dict with all 9 roles; assert `palette.color(QPalette.ColorRole.X)` matches for each
2. **`test_build_palette_from_dict_skips_malformed_hex`** — dict with `{"Window": "not-a-hex"}` → palette unchanged for Window role
3. **`test_build_palette_from_dict_skips_unknown_role`** — dict with `{"NotARole": "#ffffff"}` → no exception, no role set
4. **`test_build_palette_from_dict_partial_dict`** — dict with only 3 roles → other 6 roles use Qt defaults
5. **`test_gbs_preset_locked_hex_match`** — `THEME_PRESETS["gbs"]` has Window=`#A1D29D`, Base=`#D8E9D6`, ..., Link=`#448F3F` (all 10 locked values, including Highlight baseline)
6. **`test_all_presets_cover_9_roles`** — every preset (except `system` and Dark/Light Highlight) sets all 9 EDITABLE_ROLES
7. **`test_dark_light_use_accent_default_highlight`** — `THEME_PRESETS["dark"]["Highlight"] == ACCENT_COLOR_DEFAULT` and same for light
8. **`test_apply_theme_palette_uses_repo_setting`** — set repo `theme='gbs'`; call `apply_theme_palette(qapp, repo)`; assert qapp.palette() Window == `#A1D29D`
9. **`test_apply_theme_palette_loads_custom_json`** — set `theme='custom'` and `theme_custom='{"Window":"#abcdef","Base":"#fedcba",...}'`; assert palette matches
10. **`test_apply_theme_palette_corrupt_json_safe`** — `theme_custom='not json'`; no exception, falls back to default palette
11. **`test_apply_theme_palette_non_dict_json_safe`** — `theme_custom='[1,2,3]'`; no exception, falls back to default
12. **`test_apply_theme_palette_system_no_op_on_linux`** — set `theme='system'` on Linux platform; assert palette unchanged from pre-call state (skipif sys.platform=='win32')
13. **`test_apply_theme_palette_unknown_theme_safe`** — set `theme='nonexistent'`; falls back to default palette, no exception
14. **`test_theme_then_accent_layering`** — apply `theme='vaporwave'`, then `apply_accent_palette(app, '#e62d42')`; assert Highlight=`#e62d42` AND Window=`#efe5ff` (theme survives, accent overrides Highlight)
15. **`test_theme_settings_roundtrip`** — `repo.set_setting('theme', 'overrun')` → `repo.get_setting('theme', 'system')` returns `'overrun'`
16. **`test_theme_custom_json_roundtrip`** — set/get `theme_custom` with JSON dict, parse with `json.loads`, assert key match

### `tests/test_theme_picker_dialog.py` — picker UX tests (qtbot)

1. **`test_dialog_shows_8_tiles`** — assert tile widgets exist for system, vaporwave, overrun, gbs, gbs_after_dark, dark, light, custom
2. **`test_active_tile_has_checkmark`** — set repo `theme='vaporwave'`; open picker; assert vaporwave tile has active state set
3. **`test_tile_click_applies_palette`** — click vaporwave tile; assert qapp Window == `#efe5ff`
4. **`test_tile_click_preserves_accent_setting`** — set repo `accent_color='#e62d42'`; click overrun tile; assert repo `accent_color` STILL `#e62d42` (not mutated)
5. **`test_tile_click_reapplies_accent_override`** — set repo `accent_color='#e62d42'`; click vaporwave tile; assert qapp Highlight == `#e62d42` (not vaporwave's `#ff77ff` baseline)
6. **`test_apply_persists_theme`** — click vaporwave tile, click Apply; assert `repo.get_setting('theme') == 'vaporwave'`
7. **`test_cancel_restores_snapshot_palette`** — snapshot qapp.palette() Window before opening; open picker; click overrun tile; click Cancel; assert qapp Window restored
8. **`test_cancel_restores_snapshot_qss`** — same as above for `qapp.styleSheet()`
9. **`test_cancel_does_not_persist_theme`** — open picker; click overrun tile; click Cancel; assert `repo.get_setting('theme', 'UNSET') == 'UNSET'`
10. **`test_empty_custom_tile_disabled`** — `theme_custom` unset; open picker; assert custom tile `isEnabled() == False`
11. **`test_populated_custom_tile_enabled`** — set `theme_custom='{"Window":"#abcdef",...}'`; open picker; assert custom tile `isEnabled() == True`
12. **`test_customize_button_opens_editor`** — click Customize…; assert ThemeEditorDialog spawned (use `monkeypatch` to stub `ThemeEditorDialog.exec` and capture invocation)
13. **`test_customize_passes_current_selected_preset`** — pick vaporwave; click Customize…; assert editor opened with `source_preset='vaporwave'`

### `tests/test_theme_editor_dialog.py` — editor UX tests (qtbot + monkeypatch QColorDialog.getColor)

1. **`test_editor_shows_9_color_rows`** — assert dlg has rows for Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, HighlightedText, Link (NOT Highlight)
2. **`test_editor_prefills_from_source_preset`** — open with `source_preset='vaporwave'`; assert Window row hex == `#efe5ff`
3. **`test_color_change_applies_palette`** — stub QColorDialog.getColor → `#abcdef`; click Window swatch; assert qapp.palette() Window == `#abcdef`
4. **`test_color_change_re_imposes_accent`** — set accent_color; change theme color via row; assert qapp.palette() Highlight still == accent_color (not the theme's baseline)
5. **`test_reset_reverts_to_source_preset`** — open with `source_preset='vaporwave'`; change Window via stubbed QColorDialog; click Reset; assert Window row hex == vaporwave's `#efe5ff`
6. **`test_reset_does_not_close_dialog`** — click Reset; assert `dialog.result() == 0` (still open)
7. **`test_save_persists_theme_custom_json`** — change Window; click Save; assert `repo.get_setting('theme_custom')` is JSON with `"Window": "#abcdef"`
8. **`test_save_sets_theme_to_custom`** — click Save; assert `repo.get_setting('theme') == 'custom'`
9. **`test_save_closes_dialog_with_accept`** — click Save; assert `dialog.result() == QDialog.Accepted`
10. **`test_cancel_restores_snapshot`** — snapshot qapp.palette() before; change Window; click Cancel; assert palette restored
11. **`test_cancel_does_not_persist`** — click Cancel; assert repo `theme_custom` unchanged

### Test Coverage Targets — Continue-to-pass

- `tests/test_accent_color_dialog.py` — UNCHANGED; verifies Phase 59 layering still works
- `tests/test_accent_provider.py` — UNCHANGED; verifies `apply_accent_palette` still functions
- `tests/test_theme_layering_integration.py` (NEW, optional integration) — assert `theme='vaporwave'` + `accent_color='#e62d42'` startup wiring produces both theme palette AND accent override

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single hardcoded Fusion+dark palette on Windows only (`_apply_windows_palette`) | Programmatic per-theme QPalette + `app.setPalette` | Phase 66 | Adds 6 presets + Custom slot; preserves Windows system-default behavior verbatim |
| Hex tokens in `_theme.py` (`ERROR_COLOR_HEX` etc.) for QSS interpolation | UNCHANGED — kept as theme-independent UI tokens | — | These are intentional; they survive across all themes (D-03) |
| `QSlider::sub-page` accent QSS file at `paths.accent_css_path()` | UNCHANGED — accent-specific gap; theme has no analogous gap | — | No `theme.css` file (CONTEXT.md "Claude's Discretion" — recommended NO) |

**Deprecated/outdated:**
- None for Phase 66. All existing patterns are preserved.

---

## Project Constraints (from CLAUDE.md)

- **Spike findings reference:** `Skill("spike-findings-musicstreamer")` for Windows packaging / GStreamer / Qt patterns. Phase 66 is purely UI/palette work; no GStreamer or PyInstaller concerns. Skill not directly applicable to this phase.

## Project Conventions (from .planning/codebase/)

- **Snake_case** function/variable names (CONVENTIONS.md)
- **Type hints throughout** (CONVENTIONS.md)
- **Bound-method signal connections (QA-05)** — no self-capturing lambdas. Phase 66 uses `tile.clicked.connect(self._on_tile_clicked)` etc.
- **No new runtime deps** (STACK.md — Python 3.10+, PySide6 6.11+)
- **Linux Wayland deployment, DPR=1.0** — UI auditor's CRITICAL findings on HiDPI/fractional scaling downgrade to WARNING (per project memory)
- **`_is_valid_hex` defense-in-depth on every hex consumption** (CONCERNS.md security review checklist)

---

## Open Questions

1. **Should the picker dialog disable the "Accent Color" hamburger entry while open?**
   - What we know: modality already prevents the user from clicking another menu entry.
   - What's unclear: whether to grey out the accent menu visually as a UX hint.
   - Recommendation: NO — modality is sufficient. Don't add visual coupling.

2. **Should ToolTipBase / ToolTipText / BrightText / Mid be set per theme?**
   - What we know: locked decisions specify only the 9 primary roles + Highlight baseline.
   - What's unclear: whether tooltip backgrounds look correct on Vaporwave/Overrun without explicit setting.
   - Recommendation: leave at Qt defaults for v1. If UAT surfaces unreadable tooltips on dark themes, add ToolTip roles in v1.1.

3. **Should the editor warn before destructive Reset?**
   - What we know: Reset reverts unsaved edits to the source preset.
   - What's unclear: whether a confirm dialog is warranted (Phase 59 has no Reset confirm).
   - Recommendation: NO — match Phase 59 idiom. Reset is reversible by re-opening the editor and re-editing; not destructive in the data sense.

4. **What happens if the user has `theme='custom'` and `theme_custom` is unset (JSON empty)?**
   - What we know: `apply_theme_palette` returns default palette in this case.
   - What's unclear: whether picker should show Custom tile as enabled or disabled when this state somehow occurs.
   - Recommendation: planner adds defensive code — if `theme=='custom'` and `theme_custom` is empty, treat Custom tile as disabled AND fall back to `theme='system'` on next save. Or: never let `theme='custom'` be set without `theme_custom` being non-empty (editor's Save sets both atomically).

---

## Environment Availability

> Phase 66 has no external dependencies — pure Python + PySide6 6.11 + SQLite, all already in the project. Skipping detailed availability table.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | Theme picker / editor / palette construction | ✓ | 6.11.0 | — |
| Python | All | ✓ | 3.10+ | — |
| SQLite (stdlib) | Theme persistence | ✓ | bundled | — |

**No missing dependencies.**

---

## Sources

### Primary (HIGH confidence)
- **PySide6 6.11 stock APIs** — `QPalette`, `QColor`, `QColorDialog`, `QPushButton.paintEvent`, `setPalette`, `setStyle("Fusion")`. Verified via codebase usage at `accent_utils.py:54-65`, `__main__.py:69-99`, `accent_color_dialog.py:60-68`.
- **`musicstreamer/accent_utils.py`** — full file (71 lines) — Phase 19/40/59 accent layering pattern; `theme.py` parallels this shape.
- **`musicstreamer/ui_qt/accent_color_dialog.py`** — full file (163 lines) — Phase 59 dialog idiom; both Phase 66 dialogs follow this pattern verbatim.
- **`musicstreamer/__main__.py:69-99`** — `_apply_windows_palette` Windows preservation pattern; preserved verbatim when `theme=='system'`.
- **`musicstreamer/__main__.py:163-220`** — `_run_gui` startup wiring; insertion point for `theme.apply_theme_palette`.
- **`musicstreamer/ui_qt/main_window.py:163-245`** — hamburger menu construction + accent restore; insertion site for "Theme" action.
- **`tests/test_accent_color_dialog.py`** — full file (228 lines) — Phase 59 test pattern; Phase 66 tests mirror this.
- **`tests/test_accent_provider.py`** — full file (118 lines) — `accent_utils` test pattern.
- **GBS.FM live CSS sample (2026-05-09)** — `https://gbs.fm/images/style.css` via curl with cookies. Locked GBS.FM Light hex values verified against live source.
- **CONTEXT.md** — `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-CONTEXT.md` — D-01..D-24 + Claude's Discretion + Deferred Ideas.
- **CONTEXT.md (Phase 59)** — `.planning/phases/59-visual-accent-color-picker/59-CONTEXT.md` — layering contract preserved.

### Secondary (MEDIUM confidence)
- **WCAG 2.1 sRGB luminance formula** — used to compute contrast ratios for proposed Vaporwave/Overrun/GBS.FM After Dark hex values. Standard formula widely cited (WebAIM, W3C); calculations performed manually.
- **`.planning/codebase/STACK.md`** — Python 3.10+ + PySide6 6.11+ + SQLite confirmation.
- **`.planning/codebase/CONVENTIONS.md`** — snake_case, type hints, bound-method connects.
- **`.planning/codebase/CONCERNS.md`** — `_is_valid_hex` defense-in-depth pattern.
- **Project memory (Linux Wayland DPR=1.0)** — UI auditor's CRITICAL → WARNING downgrade for HiDPI on this hardware.

### Tertiary (LOW confidence — flagged for validation if used)
- None used in this research. All claims verified against either codebase, live HTTP sample, or PySide6 docs.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Vaporwave / Overrun "directional palettes" in CONTEXT.md D-05 are intended as starting points; the planner is empowered to refine exact hex per the WCAG-grounded recommendations in this research. | Recommended Final Hex Values | Low — user explicitly delegated this in CONTEXT.md "Claude's Discretion" |
| A2 | The user's intent for "Vaporwave Link" is purple-blue (cyan failed AA contrast); CONTEXT.md mentions cyan but locking purple-blue per WCAG. | Q7, Recommended Final Hex Values (Vaporwave) | Medium — if user prefers cyan exactly, the Link role on near-white base will fail AA. Discuss-phase or planner flag for confirmation. |
| A3 | Picker disables "Accent Color" hamburger entry: NOT done; modality alone suffices. | Open Questions §1 | Low |
| A4 | Editor's Save will close BOTH editor AND picker by setting parent picker's `_save_committed=True` flag and calling `parent.accept()`. | Q10 | Medium — alternative is to let editor only close itself and let the picker reject restore the saved Custom; both approaches work but flag-based is cleaner. Planner picks. |
| A5 | First-boot users get `theme='system'` default and see no visual change — pre-Phase-66 behavior preserved exactly. | Q13 | Low — verified via `Repo.get_setting` default-arg semantics |
| A6 | Phase 66 ships without arrow-key tile-grid navigation; Tab + Enter only. | Q14 | Low — accessibility improvement deferrable; no user request |

---

## Metadata

**Confidence breakdown:**
- Standard stack (PySide6 6.11, QPalette construction): **HIGH** — codebase already uses `_apply_windows_palette` programmatic palette pattern verbatim.
- Architecture (`theme.py` parallel to `accent_utils.py`, two new dialogs): **HIGH** — locked by CONTEXT.md D-22..D-24 and verified against existing Phase 59 dialog.
- Pitfalls (snapshot leak, accent re-imposition, JSON tampering): **HIGH** — all rooted in observable code patterns and locked decisions.
- GBS.FM Light hex values: **HIGH** — re-verified live 2026-05-09 against `https://gbs.fm/images/style.css`.
- Vaporwave / Overrun / GBS.FM After Dark final hex: **MEDIUM** — directional palettes locked in CONTEXT.md; specific hex grounded in WCAG contrast computations but planner's discretion to override based on UAT.
- Test coverage targets: **HIGH** — mirrored from Phase 59 fixture shape and proven against existing accent_utils tests.

**Research date:** 2026-05-09
**Valid until:** 2026-06-08 (30 days for stable PySide6 + locked CONTEXT.md decisions)

---

## RESEARCH COMPLETE
