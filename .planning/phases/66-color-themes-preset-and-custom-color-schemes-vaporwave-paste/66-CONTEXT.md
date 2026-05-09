# Phase 66: Color Themes — preset and custom color schemes (Vaporwave pastel, Overrun neon+black) - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a base **theme** layer to MusicStreamer that owns the running app's full QPalette (9 primary roles), shipping with **6 hard-coded presets** + **1 user-editable Custom slot**, exposed via a new "Theme" entry in the hamburger menu. Theme is the *base* layer; the existing `accent_color` setting (from Phase 19/40 + Phase 59 visual picker) layers on top to override `Highlight` whenever non-empty. Picking a theme changes Window/WindowText/Base/AlternateBase/Text/Button/ButtonText/HighlightedText/Link palette roles app-wide; it does **not** change the user's accent.

**In scope:**
- New `musicstreamer/theme.py` (or equivalent module) with theme definitions, palette construction, and live-application helpers — paralleling `accent_utils.py` but at the full-palette level.
- New `musicstreamer/ui_qt/theme_picker_dialog.py` — modal dialog with a 6-tile (5 presets + Custom) swatch grid, "Customize…" button, Apply / Cancel buttons, snapshot-restore on cancel.
- New `musicstreamer/ui_qt/theme_editor_dialog.py` — modal editor for the Custom slot. 9 color rows (one QColorDialog launcher per role, NOT 9 inline pickers), live preview, snapshot-restore on Cancel, Save persists + applies + switches active theme to "Custom", Reset reverts to source preset.
- Six presets shipped: **System default**, **Vaporwave**, **Overrun**, **GBS.FM**, **GBS.FM After Dark**, **Dark**, **Light**. (Picker grid order: System default → Vaporwave → Overrun → GBS.FM → GBS.FM After Dark → Dark → Light → Custom.)
- New SQLite settings keys: `theme` (enum string) + `theme_custom` (JSON-encoded `{role: hex}` blob).
- Hamburger menu integration: new "Theme" action in main_window.py, immediately above existing "Accent Color".
- Startup wiring (in `__main__.py:_run_gui` + `main_window.py:189-192`): apply selected theme palette **before** the existing accent_color override branch. Windows: theme replaces `_apply_windows_palette` unless theme = `system`.
- Tests: theme palette construction (per-preset hex assertions), theme application order (theme then accent override), persistence round-trip (SQLite), picker dialog flow (snapshot-restore on Cancel), editor dialog flow (Reset to source preset, Save = persist + apply + switch).

**Out of scope:**
- Touching hardcoded QSS / `_theme.py` constants (`ERROR_COLOR_HEX` `#c0392b`, `WARNING_COLOR_HEX` `#d4a017`, station-row icon size). These survive unchanged across all themes.
- Touching toast background, splash, or other ad-hoc QSS strings. Theme = QPalette only.
- Per-widget theme variants (no "dark vaporwave"). Each preset is a single fixed palette.
- Theme import/export to file or via paste-as-JSON. Custom palette flows through the existing settings export/import ZIP via the new SQLite key — no new portability surface.
- Multiple named custom themes. Single "Custom" slot, overwrite-on-edit. Future phase if user wants more.
- Hover-preview on tiles (only click = apply). Live preview happens on commit-click, restored on Cancel.
- A separate "Customize Theme" hamburger entry. Editor is reached only from the picker's "Customize…" button.
- Editing Highlight in the Custom theme editor. Highlight is owned by the layered accent_color path and lives in the existing accent picker; the theme editor exposes only the other 9 roles.
- Renaming, retiring, or restructuring the existing "Accent Color" hamburger entry, the `accent_color` SQLite key, the `paths.accent_css_path()` write site, or anything in `accent_utils.py`. The accent layering contract from Phase 59 is preserved exactly.

</domain>

<decisions>
## Implementation Decisions

### Theme scope & palette roles

- **D-01:** Theme owns **9 QPalette primary roles**: `Window`, `WindowText`, `Base`, `AlternateBase`, `Text`, `Button`, `ButtonText`, `HighlightedText`, `Link`. **Highlight is NOT in the theme editor** — it is owned by the layered accent_color path.
- **D-02:** Each preset declares its own `Highlight` value as a *baseline* used only when `accent_color` is empty. When `accent_color` is non-empty, the existing `apply_accent_palette()` from `accent_utils.py:54` overrides Highlight on top of the theme's baseline (Phase 59 layering contract). Picking a theme does NOT mutate the user's `accent_color` setting.
- **D-03:** Hardcoded QSS constants in `musicstreamer/ui_qt/_theme.py` (`ERROR_COLOR_HEX = "#c0392b"`, `WARNING_COLOR_HEX = "#d4a017"`, `STATION_ICON_SIZE = 32`) are **NOT** touched. These survive across all themes.
- **D-04:** **Reset behavior in the existing AccentColorDialog stays exactly as Phase 59 D-15 specifies** — clears `accent_color` setting, restores snapshot palette, sets picker visual to `ACCENT_COLOR_DEFAULT`, neutralizes accent QSS file. After theme ships, the snapshot will already include the theme's Highlight baseline, so clearing accent leaves the theme Highlight in effect — no Phase 59 change required.

### Preset bundle

- **D-05:** Ship six hard-coded presets + one Custom slot:
  - **System default** — uses Qt's stock palette on Linux; on Windows preserves `__main__.py:_apply_windows_palette()` exact verbatim behavior (Fusion + dark-mode QPalette via `colorScheme() == Qt.ColorScheme.Dark` branch). When theme = `system`, no custom palette construction runs.
  - **Vaporwave** — light. Lavender base + pink/cyan accents.
    - Window/Base ~ `#efe5ff` / `#fff5fb`, Text ~ `#4a3a5a` (deep purple), Highlight baseline ~ `#ff77ff` (hot pink), Link ~ `#5fefef` (cyan). Exact hex per role: planner refines in PLAN.md.
  - **Overrun** — dark. Neon pink/magenta dominant on near-black.
    - Window/Base ~ `#0a0408` / `#110a10`, Text ~ `#ffe8f4`, Highlight baseline ~ `#ff2dd1` (hot magenta), Link ~ `#00f0ff` (electric cyan). Pairs visually with Vaporwave as a "sister" look. Exact hex per role: planner refines in PLAN.md.
  - **GBS.FM** — light. Sampled from live `https://gbs.fm/images/style.css` brand palette.
    - **LOCK these exact mappings:**
      - Window: `#A1D29D` (sage menu/bottom-bar)
      - WindowText: `#000000`
      - Base: `#D8E9D6` (mint body)
      - AlternateBase: `#E7F1E6` (lighter mint, even rows)
      - Text: `#000000`
      - Button: `#B1D07C` (lime)
      - ButtonText: `#000000`
      - Highlight (baseline): `#5AB253` (kelly green, "playing" state)
      - HighlightedText: `#FFFFFF`
      - Link: `#448F3F` (forest, column titles)
  - **GBS.FM After Dark** — dark. Brand-signature greens on near-black. Live site has no dark mode; this is our interpretation.
    - **Proposed (planner tunes in PLAN.md):**
      - Window: `#0a1a0d` · WindowText: `#D8E9D6` · Base: `#102014` · AlternateBase: `#1a2c1f` · Text: `#D8E9D6` · Button: `#1f4a2a` · ButtonText: `#D8E9D6` · Highlight (baseline): `#5AB253` · HighlightedText: `#FFFFFF` · Link: `#A1D29D`
  - **Dark** — neutral dark. Window/Base ~ `#202020` / `#181818`, Text white-ish, **Highlight baseline left empty** so accent_color (or the `ACCENT_COLOR_DEFAULT` neutral blue fallback) drives the Highlight role.
  - **Light** — neutral light. Window/Base ~ `#f5f5f5` / `#ffffff`, Text near-black, **Highlight baseline left empty** (same fallback policy as Dark).
- **D-06:** **Picker grid display order:** System default → Vaporwave → Overrun → GBS.FM → GBS.FM After Dark → Dark → Light → Custom. Mood themes grouped first; neutrals next; Custom last.
- **D-07:** **Dark/Light Highlight policy:** these two presets do NOT lock a Highlight value. Their `Highlight` palette role is set to `ACCENT_COLOR_DEFAULT` (#3584e4 neutral blue) at theme construction time, so users without an `accent_color` override see a neutral selection color; users with an override see their override. Picking Dark or Light does not mutate `accent_color`.

### Custom theme authoring UX

- **D-08:** **Editor surface = all 9 raw QPalette roles** (Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, HighlightedText, Link). Highlight is intentionally absent — owned by the layered accent_color path.
- **D-09:** **Authoring flow = duplicate-and-edit only.** No blank-slate option. To create or edit a Custom theme, user opens the picker, clicks "Customize…", and the editor opens pre-filled with the **currently selected preset** (or with the existing Custom palette if Custom is the active theme). The pre-fill is captured as the `_source_preset_palette` for Reset semantics (D-13).
- **D-10:** **Storage = single overwrite slot.** SQLite key `theme_custom` holds a JSON-encoded `{role_name: hex}` dict for the 9 editable roles. No named multi-theme list. Saving the editor overwrites this key.
- **D-11:** **No name field.** The Custom slot is always labeled `"Custom"` in the picker; no user-editable rename.
- **D-12:** **Live preview during edit, snapshot-restore on Cancel.** Editor opens snapshots `QApplication.palette()` and `QApplication.styleSheet()`. Each color picker's `currentColorChanged` updates the corresponding palette role on `QApplication` immediately and re-applies the accent_color override on top so Highlight stays correct. Cancel restores both snapshots. Mirrors Phase 59 `AccentColorDialog` pattern.
- **D-13:** **Save semantics:** persist palette to `theme_custom` JSON, write `theme = 'custom'` to settings, close the editor, and leave the active palette as-is (already showing the saved colors via live preview).
- **D-14:** **Reset button reverts to source preset.** Reset reads the `_source_preset_palette` captured at editor open (D-09) and pushes those 9 hex values back into the 9 color slots + the running palette. Does NOT close the editor; user can re-edit or Cancel.

### Picker location & dialog shape

- **D-15:** **Hamburger menu home:** new `"Theme"` action in the Settings group of the menu, **immediately above** the existing `"Accent Color"` action (`main_window.py:188`). Two peer entries — theme = base palette, accent = override.
- **D-16:** **Picker = dedicated modal dialog** (not a submenu). Tile/swatch grid layout: ≥ 6 tiles (5 presets + Custom; +1 if both GBS variants ship as separate tiles → 7). Each tile shows:
  - A small horizontal stripe of 4 swatches (Window / Base / Text / Highlight-baseline-or-accent-fallback).
  - The theme name below the stripe.
  - A checkmark or border highlight on the **currently active theme**.
- **D-17:** **Click = live preview.** Clicking a tile applies that theme's palette to `QApplication` immediately (then re-applies accent_color override on top). Apply persists; Cancel restores the snapshot taken at picker-open. Mirrors Phase 59 pattern.
- **D-18:** **Editor access = "Customize…" button on the picker dialog.** Single button covers both create-Custom and edit-Custom. Click opens the editor pre-filled with whichever theme is currently selected (the source preset, or current Custom).
- **D-19:** **Empty Custom tile = visible, disabled, hint label.** When `theme_custom` key is unset/empty, the Custom tile renders grayed out with a small hint reading `"Click Customize…"` (or similar). Tile is not clickable until a Custom palette has been saved. Discoverability stays high without hidden affordances.
- **D-20:** **Modality:** picker and editor both use `setModal(True)` — same as every other dialog.
- **D-21:** **Picker buttons:** `Apply | Cancel` (no Reset on the picker — Cancel restores snapshot). Apply persists `theme` setting; Cancel restores snapshot palette + styleSheet.

### Persistence & startup

- **D-22:** **Two SQLite settings keys** (extending the existing `settings` table; no schema migration — additive keys only):
  - `theme` — enum string. Allowed values: `system`, `vaporwave`, `overrun`, `gbs`, `gbs_after_dark`, `dark`, `light`, `custom`. Default `system` if unset.
  - `theme_custom` — JSON-encoded `{role_name: hex}` dict for the 9 editable roles. Empty/unset until first Save in the editor.
- **D-23:** **Startup application order (theme first, then accent override):**
  1. In `__main__.py:_run_gui` (after `QApplication` construction but BEFORE `MainWindow`), call new `theme.apply_theme_palette(app, repo)`:
     - Reads `theme` setting.
     - If `theme == 'system'`: no-op on Linux; on Windows, preserves the existing `app.setStyle("Fusion")` + `_apply_windows_palette(app)` branch verbatim.
     - Otherwise: builds the preset palette (or reads `theme_custom` JSON for `custom`), calls `app.setPalette(palette)`. On Windows for non-system themes, also calls `app.setStyle("Fusion")` first so the theme palette renders consistently across platforms.
  2. The existing `main_window.py:189-192` accent restore runs unchanged — reads `accent_color` and calls `apply_accent_palette(app, hex)` if non-empty. This overrides Highlight on top of the theme's baseline.
- **D-24:** **No new dependencies.** All theme work uses PySide6 stock APIs (`QPalette`, `QColor`, `QColorDialog` for the editor's color rows).

### Claude's Discretion

- **Vaporwave / Overrun exact hex per role** — directional palettes are locked (D-05); planner samples reference imagery in research and writes final hex per role in PLAN.md before execution.
- **GBS.FM After Dark exact hex per role** — proposed mapping is captured in D-05; planner refines in PLAN.md after sampling more of the brand site (e.g., border colors, hover states) for grounding.
- **Tile size / grid columns** — UI auditor's call. 4-across × 2 rows likely fits 7-8 tiles best; planner picks based on dialog sizeHint.
- **Editor color-row UX shape** — D-08 is "9 raw roles", but how each row is rendered is the planner's call: a `QPushButton` showing current color that opens `QColorDialog` on click, vs an inline `QColorDialog` widget per row, vs a `QToolButton` with a popup. Recommended path: button-opens-modal-QColorDialog-per-row (matches Phase 59's dialog-launcher idiom). Each row labeled with the role name.
- **Disabled-Custom-tile visual treatment** — D-19 says "grayed out with hint"; specific styling (opacity, border-dash, label text) is the UI auditor's call.
- **Whether to also write a theme-derived QSS file analogous to `paths.accent_css_path()`** — recommended NO. QPalette swap is sufficient for the 9 roles; the accent QSS file exists only because `QSlider::sub-page` doesn't read `palette(highlight)`, which is an accent-specific concern. Theme work should not introduce a parallel QSS file unless a similar slider-style gap surfaces during research.
- **Whether System default theme on Linux should call `app.setStyle("Fusion")`** — recommended NO. On Linux, leave whatever Qt picked (current behavior). Only Windows gets `setStyle("Fusion")` because the native style there has known palette issues (the reason `_apply_windows_palette` exists today).
- **Whether to add a `migration.run_migration()` step that backfills `theme = 'system'`** — recommended NO. `repo.get_setting("theme", "system")` is the read site; missing key returns the default. No migration needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 66: Color Themes — preset and custom color schemes (Vaporwave pastel, Overrun neon+black)" (lines 529-537) — phase goal stub. Goal text in this CONTEXT.md supersedes the placeholder.
- `.planning/REQUIREMENTS.md` — no existing requirement maps to "theme" yet. Planner's first move: add a new requirement (e.g., `THEME-01: User can switch between preset color themes and a single custom palette`) before splitting into plans. Reference `.planning/REQUIREMENTS.md` §ACCENT-02 for the existing accent invariant that must be preserved.
- `.planning/PROJECT.md` §Current Milestone: v2.1 Fixes and Tweaks — "open-ended scope" milestone; theme work is in scope.

### Phase 59 layering contract — DO NOT REGRESS

- `.planning/phases/59-visual-accent-color-picker/59-CONTEXT.md` — entire file. Specifically:
  - Phase 59 D-15 (accent dialog Reset semantics): clears `accent_color`, restores snapshot, neutralizes QSS file. Phase 66 must preserve this verbatim — clearing accent must leave the theme Highlight baseline in effect, NOT push a neutral default into accent.
  - Phase 59 D-13 / D-14 (snapshot-restore on Cancel + Apply persist): theme picker and editor must follow the same snapshot pattern.
- `musicstreamer/ui_qt/accent_color_dialog.py` (entire file, 163 lines) — Phase 59 implementation. Phase 66 follows the same dialog idiom (modal QDialog wrapping QColorDialog, snapshot-restore-on-cancel, bound-method connects per QA-05).
- `musicstreamer/accent_utils.py` (entire file, 71 lines) — `_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette`. Theme code MUST call `apply_accent_palette(app, accent_hex)` after applying the theme palette to re-impose the Highlight override (D-23.2). Do NOT modify this file.

### Existing palette / startup wiring (must integrate cleanly)

- `musicstreamer/__main__.py:69-99` — `_apply_windows_palette()` Fusion + dark-mode QPalette. Phase 66 wraps this: invoked only when `theme == 'system'` on Windows. Otherwise theme palette replaces it.
- `musicstreamer/__main__.py:185-192` — `_run_gui` palette-init block. Phase 66 inserts a new `theme.apply_theme_palette(app, repo)` call here, ordered such that the existing Windows branch is preserved when `theme == 'system'`.
- `musicstreamer/ui_qt/main_window.py:53` — `from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog`. Phase 66 adds parallel imports for the new theme picker + editor dialogs.
- `musicstreamer/ui_qt/main_window.py:163-198` — hamburger menu construction. Phase 66 adds a new `act_theme = self._menu.addAction("Theme")` action immediately above `act_accent = self._menu.addAction("Accent Color")` at line 188. Same group, same idiom.
- `musicstreamer/ui_qt/main_window.py:189-192` — startup-time accent restore (`accent_color` read + `apply_accent_palette` if `_is_valid_hex`). Phase 66 keeps this BUT it now runs after the theme palette is in place, so it overrides Highlight on top of the theme baseline.
- `musicstreamer/ui_qt/_theme.py` (entire file, 53 lines) — `ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`. Phase 66 does NOT modify this file. These QSS-string tokens are theme-independent.
- `musicstreamer/constants.py:72-83` — `ACCENT_COLOR_DEFAULT = "#3584e4"` and `ACCENT_PRESETS`. Phase 66 reuses `ACCENT_COLOR_DEFAULT` as the Highlight fallback for Dark and Light presets (D-07).
- `musicstreamer/repo.py` — `Repo.get_setting`/`Repo.set_setting`. Phase 66 adds two reads (`theme`, `theme_custom`) and two writes — no schema change.
- `musicstreamer/paths.py` — settings storage path. Phase 66 does NOT add a new on-disk file path. The Custom palette lives in SQLite via `theme_custom`.

### GBS.FM brand palette source (sampled)

- `https://gbs.fm/images/style.css` — live stylesheet sampled 2026-05-09 with cookies at `~/.local/share/musicstreamer/gbs-cookies.txt`. Brand color extraction is in D-05's GBS.FM block. Researcher should re-fetch and verify before locking final hex.

### Phase 60.4 reference (existing color-token pattern)

- `musicstreamer/ui_qt/gbs_search_dialog.py` — `_token_label` consumes `WARNING_COLOR_HEX` from `_theme.py:48` via QSS string. Confirms that `_theme.py` constants are theme-independent UI tokens, NOT palette tokens. Phase 66 leaves them untouched.

### Project conventions

- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints throughout, no formatter, no linter on save. Bound-method signal connections (QA-05) — applies to `currentColorChanged.connect(self._on_color_changed)`, `tile.clicked.connect(self._on_tile_clicked)`, etc.
- `.planning/codebase/STACK.md` — Python 3.10+, PySide6 6.11+. No new runtime deps for Phase 66.
- `.planning/codebase/CONCERNS.md` — security review checklist; `_is_valid_hex` validator is reused for `theme_custom` JSON parsing (defense-in-depth — JSON might be tampered with via export/import ZIP round-trip).
- `.planning/codebase/ARCHITECTURE.md` — module boundaries; theme code goes in `musicstreamer/theme.py` (top level, parallel to `accent_utils.py`) for the palette logic, plus `musicstreamer/ui_qt/theme_picker_dialog.py` and `musicstreamer/ui_qt/theme_editor_dialog.py` for UI surfaces.
- Linux Wayland deployment target, DPR=1.0 (per project memory) — UI auditor's CRITICAL findings on HiDPI/fractional scaling downgrade to WARNING. Tile-grid rendering and color-row alignment must be tested on Wayland with DPR=1.0.

### No external specs

No ADRs apply. The phase is captured by ROADMAP §Phase 66 (placeholder), Phase 59's CONTEXT.md (layering contract), the existing accent + Windows-palette code, this CONTEXT.md, and PySide6's QPalette + QColorDialog documentation (stdlib — no external doc to vendor in).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`musicstreamer/accent_utils.py:apply_accent_palette`** — called to layer accent on top of theme. Reused unchanged.
- **`musicstreamer/accent_utils.py:_is_valid_hex`** — defense-in-depth hex validator for `theme_custom` JSON parsing.
- **`musicstreamer/constants.py:ACCENT_COLOR_DEFAULT`** — `#3584e4`. Reused as Highlight fallback for Dark + Light presets (D-07).
- **`musicstreamer/__main__.py:_apply_windows_palette`** — preserved as the System-default-on-Windows branch (D-23). Not deleted, not refactored.
- **Phase 59 snapshot-and-restore pattern** (`accent_color_dialog.py:48-50` + `reject` at `155-163`) — copy verbatim into `theme_picker_dialog.py` and `theme_editor_dialog.py`.
- **`musicstreamer/repo.py:Repo.get_setting` / `Repo.set_setting`** — same SQLite settings table, no schema change.

### Established Patterns

- **Modal QDialog with `setModal(True)`** — every dialog in the app uses this; theme picker and editor follow.
- **Bound-method signal connections (QA-05)** — `tile.clicked.connect(self._on_tile_clicked)`, `currentColorChanged.connect(self._on_color_changed)`, etc. No self-capturing lambdas.
- **`_is_valid_hex` defense-in-depth on persistence boundaries** — applied to every hex read from `theme_custom` JSON before pushing into `QPalette.setColor(QColor(...))`.
- **Hamburger-menu Settings group** (`main_window.py:188-196`) — Theme action joins this group above Accent Color.
- **Snapshot-and-restore for live-preview cancel** — Phase 19 / Phase 40 / Phase 59 invariant. Theme picker + editor preserve it.

### Integration Points

- **New files (3):** `musicstreamer/theme.py` (palette construction + apply helpers), `musicstreamer/ui_qt/theme_picker_dialog.py` (tile-grid picker), `musicstreamer/ui_qt/theme_editor_dialog.py` (9-role editor for Custom slot).
- **Modified files (2):** `musicstreamer/__main__.py` (insert `theme.apply_theme_palette` call into `_run_gui`'s palette-init block), `musicstreamer/ui_qt/main_window.py` (add `"Theme"` menu action + `_open_theme_dialog` slot).
- **Untouched files (must not regress):** `musicstreamer/accent_utils.py`, `musicstreamer/ui_qt/accent_color_dialog.py`, `musicstreamer/ui_qt/_theme.py`, `musicstreamer/constants.py` (ACCENT_PRESETS, ACCENT_COLOR_DEFAULT survive).
- **Test files (new):** `tests/test_theme.py` (palette construction per preset, JSON round-trip for Custom), `tests/test_theme_picker_dialog.py` (snapshot-restore on Cancel, click = live preview, Customize button opens editor), `tests/test_theme_editor_dialog.py` (9 roles edit, Reset to source preset, Save = persist + apply + switch).
- **Test files (must continue to pass):** `tests/test_accent_color_dialog.py`, `tests/test_accent_provider.py` — no Phase 66 changes; verify integration tests still cover the layered Highlight contract.

</code_context>

<specifics>
## Specific Ideas

- **The user-visible promise:** "I open Theme from the hamburger menu, see a grid of mood tiles (Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light) plus a Custom tile, click one and the whole app instantly retints — Window backgrounds, button colors, text, link blues. My pink accent (or whatever I picked in Accent Color) stays in place over the top. If I want to make my own, I click Customize…, tweak any of the 9 palette roles via standard color pickers, save, and it lives forever as 'Custom' alongside the presets."
- **Phase 59 explicitly anticipated Phase 66.** Phase 59's `59-CONTEXT.md` contains the exact layering language used here (theme owns Highlight by default; accent_color overrides). Phase 66 does not invent the contract; it implements the theme half of it.
- **GBS.FM brand grounding is real.** The exact palette in D-05's GBS.FM block was sampled live from `https://gbs.fm/images/style.css` during this discussion. Researcher should re-fetch in case the site updated and pin the canonical hex in PLAN.md.
- **Vaporwave + Overrun are "sister" themes.** Light pastel + dark neon counterparts using a similar pink-cyan accent vocabulary. GBS.FM + GBS.FM After Dark form a parallel sister pair around the brand greens.
- **Dark and Light are the "neutral utility" presets.** Anyone who wants the OS-aware feel without System default's Linux/Windows split picks Dark or Light. Their Highlight is left empty so accent_color drives selection color.
- **Custom slot is bounded by design.** One slot, no name. Future user demand (from daily use in v2.1) can promote this to a multi-slot named-themes feature in a later phase. The schema (`theme = 'custom'` enum + `theme_custom` JSON dict) is forward-compatible — a future `theme_custom_named` JSON list of dicts is additive.

</specifics>

<deferred>
## Deferred Ideas

- **Multiple named custom themes** — a future phase if the user wants to keep both "kitchen pastel" and "late night" without re-editing. Schema upgrade is small (`theme_custom_named` JSON list); UI lift is bigger (rename / delete / reorder). Not needed for v1.
- **Theme import/export to `.json` file or paste-as-JSON in the editor** — explicit reject for Phase 66. The existing settings export/import ZIP round-trip already carries `theme` + `theme_custom` keys, which covers the personal-backup case. Sharing themes with friends becomes a feature only if the user community materializes.
- **Per-widget theme variants** (e.g., a "compact" Vaporwave with smaller swatches) — out of scope. Theme = palette only, not layout/density.
- **Hover-preview on tiles** — rejected. Click = live preview is the same idiom as Phase 59. Adding hover preview risks accidental palette swaps when the user mouses across tiles.
- **A "Theme" submenu in the hamburger menu with inline radio items** — considered, rejected (D-15 picks dialog over submenu). Submenu offers one-click theme change but loses the visual mood comparison that tiles provide.
- **Editing Highlight from the theme editor** — rejected. Highlight stays owned by the layered accent_color path. If a future phase wants to let users set "theme-default Highlight separate from accent override", the schema can grow `theme_custom.highlight` and the editor adds a 10th row.
- **Hardcoded QSS migration into the theme system** (toast bg, ERROR_COLOR_HEX, station-row icon size) — deferred to a future "Theme tokens v2" phase. Worth doing only if the hardcoded colors visibly clash with one of the dark presets — surfaces from daily use.
- **Theme-change keyboard shortcut** — not requested; hamburger menu access is fine for personal-app frequency. Add a shortcut later if theme-cycling becomes a frequent activity.
- **System-default-theme detection on Linux** (i.e., picking up the GTK theme's color scheme dynamically when theme = 'system') — rejected for v1. Linux 'system' = leave whatever Qt picked. If a future phase wants to bridge GNOME/KDE color-scheme changes into the running app, that's a separate effort.
- **Migration of existing accent_color users** — no migration needed. `theme = 'system'` default + existing accent_color override = identical behavior to today, day one. Users opt in by picking a non-default theme.

</deferred>

---

*Phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste*
*Context gathered: 2026-05-09*
