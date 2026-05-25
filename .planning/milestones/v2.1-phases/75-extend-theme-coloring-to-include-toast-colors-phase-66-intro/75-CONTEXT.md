# Phase 75: Extend theme coloring to include toast colors — Phase 66 introduced preset/custom color schemes; toast notifications still use hardcoded colors and don't track the active theme - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire `ToastOverlay` (currently hardcoded to `rgba(40, 40, 40, 220)` background + white text) into the Phase 66 theme system so toast notifications retint with the active theme and update live when the theme changes — without splitting toasts into severity tiers and without touching other deferred QSS-string tokens (`ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`).

Toast colors come from Qt's stock `QPalette.ToolTipBase` + `QPalette.ToolTipText` roles, set per-preset in `musicstreamer/theme.py:THEME_PRESETS` and per-user in `theme_custom` JSON. The Custom-theme editor grows from 9 → 11 rows. The widget installs a `changeEvent(QEvent.PaletteChange)` handler so visible/queued toasts retint instantly when the picker applies a new theme. The legacy `rgba(40, 40, 40, 220)` + white look is preserved when `theme = 'system'` so the default-theme experience does not regress.

**In scope:**
- Modify `musicstreamer/ui_qt/toast.py:ToastOverlay`:
  - Replace the hardcoded `setStyleSheet(...)` block with a palette-driven QSS builder that interpolates `palette().color(QPalette.ToolTipBase)` (with alpha `220` appended via `rgba(R, G, B, 220)`) into the background and `palette().color(QPalette.ToolTipText)` into the foreground.
  - Add `changeEvent(self, event)` override that calls the QSS rebuilder when `event.type() in (QEvent.PaletteChange, QEvent.StyleChange)` (mirrors `now_playing_panel.py:194-197`).
  - Add a system-theme branch: when `theme == 'system'` the widget falls back to the legacy hardcoded `background-color: rgba(40, 40, 40, 220); color: white;` QSS instead of the palette-driven path. Implementation knob (planner's discretion) for how the widget knows the active theme — see `<discretion>`.
- Modify `musicstreamer/theme.py:THEME_PRESETS` — add `ToolTipBase` and `ToolTipText` keys to all 6 non-system presets (`vaporwave`, `overrun`, `gbs`, `gbs_after_dark`, `dark`, `light`). Exact hex per preset is planner's discretion (must pass WCAG AA contrast for body text on the chosen background); `system` preset entry stays empty (`{}`) per Phase 66 D-23.
- Modify `musicstreamer/theme.py:EDITABLE_ROLES` — append `"ToolTipBase"` and `"ToolTipText"` to the tuple. Custom editor auto-grows to 11 rows because the dialog iterates `EDITABLE_ROLES`.
- Modify `musicstreamer/ui_qt/theme_editor_dialog.py` — accommodate the 2 new rows. Source-preset Reset (Phase 66 D-14) restores all 11 rows including the new toast pair. Save persists all 11 keys to `theme_custom` JSON. Snapshot-restore-on-Cancel (Phase 66 D-12) covers the toast roles automatically because it snapshots the full `QApplication.palette()`.
- Modify `musicstreamer/ui_qt/theme_picker_dialog.py` — palette-builder path that constructs preset palettes for the live-preview-on-tile-click action must include `ToolTipBase` + `ToolTipText` (it already iterates `THEME_PRESETS[theme_id]` so this is automatic once the dict gains the keys; verify no hardcoded role allow-list).
- Update `tests/test_toast_overlay.py:143` — the existing assertion `assert "rgba(40, 40, 40, 220)" in qss` becomes a system-theme-only assertion. Add new assertions for: palette-driven QSS uses `ToolTipBase`/`ToolTipText` for non-system themes; `changeEvent(QEvent.PaletteChange)` triggers a QSS rebuild; alpha `220` is preserved across both code paths.
- Add tests: per-preset toast hex assertions in `tests/test_theme.py` (the 6 non-system presets each declare `ToolTipBase` + `ToolTipText`); editor 11-row coverage in `tests/test_theme_editor_dialog.py` (Save round-trip includes both new keys; Reset to source preset restores them); picker live-preview retints toast (light integration test).

**Out of scope:**
- Splitting toast into severity tiers (info/success/error). All 28 `show_toast()` call sites in `main_window.py` and elsewhere stay untouched — single style, single signature `show_toast(text, duration_ms=3000)`.
- Touching `musicstreamer/ui_qt/_theme.py` constants (`ERROR_COLOR_HEX = "#c0392b"`, `WARNING_COLOR_HEX = "#d4a017"`, `STATION_ICON_SIZE = 32`). These QSS-string tokens stay theme-independent (Phase 66 D-03 invariant).
- Touching toast geometry/animation (fade-in/out duration, hold-timer, rounded-corner radius, padding, min/max width, side padding, bottom offset). Only the `background-color` + `color` QSS properties change; everything else in `ToastOverlay` is invariant.
- Touching the `accent_color` layering contract. Highlight-role override remains owned by `accent_utils.apply_accent_palette()` (Phase 59 D-02 / Phase 66 D-02). Toast colors are independent of accent — picking an accent color does NOT change toast appearance.
- New SQLite settings keys. Toast colors flow through the existing `theme` enum + `theme_custom` JSON dict — purely additive keys inside the existing JSON blob, no schema change.
- New on-disk QSS file analogous to `paths.accent_css_path()`. The `QSlider::sub-page` issue that justifies the accent QSS file does not apply here; QSS rebuilt at runtime + applied via `setStyleSheet()` is sufficient.
- Hover-preview / per-call-site toast tinting / animated color transitions on retint — out of scope, repaint-on-PaletteChange is sufficient.
- Editing toast colors from the picker dialog. Toast colors are only editable through the Customize… → editor flow, same idiom as the other 9 palette roles (Phase 66 D-08 / D-18).

</domain>

<decisions>
## Implementation Decisions

### Color derivation strategy

- **D-01:** **Toast colors come from `QPalette.ToolTipBase` + `QPalette.ToolTipText`** — Qt's stock palette roles intended for floaty notification widgets. `ToastOverlay` reads `palette().color(QPalette.ToolTipBase)` and `palette().color(QPalette.ToolTipText)` at QSS-rebuild time and interpolates the resulting hex into the background-color and color properties. No new `QPalette.ColorRole` enum members (the enum is closed); no synthetic role; no algorithmic derivation from `Window`/`WindowText`.
- **D-02:** **80% opacity preserved.** When interpolating `ToolTipBase` into the background-color QSS string, alpha=`220` (out of 255) is appended explicitly: `f"background-color: rgba({r}, {g}, {b}, 220);"`. Toast remains visually translucent — no regression vs current behavior. `ToolTipText` is fully opaque (no alpha) to keep text crisp.
- **D-03:** **Live retint via `changeEvent(QEvent.PaletteChange)`.** `ToastOverlay` overrides `changeEvent` and rebuilds its stylesheet whenever the parent palette changes. Mirrors the established pattern in `musicstreamer/ui_qt/now_playing_panel.py:194-197` and `musicstreamer/ui_qt/eq_response_curve.py:122`. Also responds to `QEvent.StyleChange` for symmetry. No restart required when picking a new theme — the next-fired (and currently-visible) toast immediately reflects the new palette.

### Severity tiers (deliberately rejected)

- **D-04:** **Single retinted style — no severity tiers.** The toast widget exposes one signature `show_toast(text, duration_ms=3000)` with one stylesheet path. The 28 existing call sites in `main_window.py` (and `now_playing_panel.py`, `discovery_dialog.py`, etc.) stay untouched. No `kind=` parameter, no info/success/error split, no per-tier color rows. Roadmap intent is "extend theme coloring to include toast colors" — adding tiers is its own future phase if daily use surfaces a need.

### Custom theme editor expansion

- **D-05:** **Editor grows from 9 → 11 rows.** `musicstreamer/theme.py:EDITABLE_ROLES` gains `"ToolTipBase"` and `"ToolTipText"` appended after the existing 9 entries. `theme_editor_dialog.py` iterates `EDITABLE_ROLES` to lay out color-picker rows, so the editor auto-grows. Each new row launches a modal `QColorDialog` per the Phase 66 button-opens-modal idiom (Phase 66 Discretion §"Editor color-row UX shape").
- **D-06:** **`theme_custom` JSON gains `ToolTipBase` + `ToolTipText` keys.** No schema change, no new SQLite key — the JSON dict already accepts arbitrary `{role_name: hex}` entries (filtered by `_is_valid_hex` + `getattr(QPalette.ColorRole, role_name, None)` in `theme.build_palette_from_dict()`). Existing Custom palettes saved before Phase 75 deploy will simply lack the two keys; on load they fall back to Qt defaults for those roles → toast renders in whatever ToolTipBase/ToolTipText Qt picks (typically the user's previous Custom Window/WindowText approximation). Minor visual drift on first launch after upgrade for existing Custom users — acceptable and self-healing once they re-open the editor and Save.
- **D-07:** **Reset to source preset (Phase 66 D-14) covers the new rows.** When the user clicks Reset in the editor, the captured `_source_preset_palette` from the source preset's `THEME_PRESETS` entry includes `ToolTipBase` + `ToolTipText` (because D-08 below adds them to all 6 non-system presets), so Reset pushes those values back into the 11 color slots and the running palette. Snapshot-restore on Cancel (Phase 66 D-12) is automatic because it snapshots the full `QApplication.palette()`.

### Per-preset coverage

- **D-08:** **All 6 non-system presets declare `ToolTipBase` + `ToolTipText` explicitly.** `musicstreamer/theme.py:THEME_PRESETS` entries for `vaporwave`, `overrun`, `gbs`, `gbs_after_dark`, `dark`, `light` each add the two keys. Exact hex per preset is **Claude's discretion** (planner's call) — see `<discretion>` for the contrast/aesthetic constraints. The `system` entry stays `{}` (sentinel, meaning "do not construct a palette" — Phase 66 D-23 invariant).

### System theme behavior (legacy preservation)

- **D-09:** **When `theme = 'system'`, `ToastOverlay` falls back to legacy hardcoded QSS** — `background-color: rgba(40, 40, 40, 220); color: white;`. Same string as today's `toast.py:45-52`. This preserves the dark-grey overlay aesthetic the user is accustomed to under the default-theme experience (theme='system' is the day-one default and likely the most common state on Linux GNOME/Wayland).
- **D-10:** **Branching mechanism is planner's discretion.** Two viable paths: (a) `ToastOverlay.__init__` takes a `repo` reference and reads `repo.get_setting("theme", "system")` inside the QSS-builder method (couples toast to repo, requires constructor-arg threading from `main_window.py:356`); (b) the active theme name is stored as a `QApplication.setProperty("theme_name", ...)` whenever `theme.apply_theme_palette()` runs, and `ToastOverlay` reads `QApplication.instance().property("theme_name")` (zero coupling, but requires writing to the property in two sites: `__main__._run_gui` after `apply_theme_palette` and inside `theme_picker_dialog._on_apply` / live-preview tile-click). Recommended path: (b) — keeps `ToastOverlay` decoupled from `Repo`, and the property already needs to exist for any future widget that branches on theme name.

### Persistence & startup

- **D-11:** **No SQLite schema change.** `theme` enum and `theme_custom` JSON dict from Phase 66 D-22 carry the new keys additively. No migration step needed (`theme_custom` is parsed defensively; missing keys silently fall back to Qt defaults via `theme.build_palette_from_dict()`).
- **D-12:** **Startup application order unchanged from Phase 66 D-23.** Theme palette → accent override → MainWindow construction → ToastOverlay construction. Toast reads palette() lazily at QSS-builder time (first `show_toast()` call), so it picks up whatever palette is in effect at that moment.

### Test surface

- **D-13:** **Existing assertion `tests/test_toast_overlay.py:143` (`assert "rgba(40, 40, 40, 220)" in qss`) updates to a system-theme-only assertion.** Test must construct the toast with `theme='system'` (set the `QApplication.property("theme_name")` or pass repo with `theme='system'`, depending on D-10 outcome) and assert the legacy QSS string. New assertions cover: (a) per-non-system-theme palette-driven QSS contains the preset's `ToolTipBase` rgb values + `, 220)` alpha suffix; (b) `changeEvent(QEvent.PaletteChange)` triggers a stylesheet rebuild (verifiable via mock or by snapshotting `widget.styleSheet()` before/after a `setPalette` call on the toast's parent); (c) `ToolTipText` hex appears in the foreground `color:` property for non-system themes.
- **D-14:** **Editor test (`tests/test_theme_editor_dialog.py`) gains 11-row coverage.** Save round-trip asserts both new keys land in the `theme_custom` JSON; Reset asserts both new rows revert to the source preset values; snapshot-restore-on-Cancel asserts both roles revert in the running `QApplication.palette()`.
- **D-15:** **Per-preset hex assertions in `tests/test_theme.py`.** Each of the 6 non-system presets must have `ToolTipBase` and `ToolTipText` keys present in `THEME_PRESETS`. Optional: assert specific hex values once planner locks them.

### Claude's Discretion

- **Per-preset toast hex values for the 6 non-system presets.** Constraints: (1) `ToolTipText` must pass WCAG AA contrast (≥ 4.5:1) against `ToolTipBase` for body text; (2) the hex should feel cohesive with the preset's aesthetic — e.g., Vaporwave gets a soft pink/lavender translucent overlay (lighter than `Window`), Overrun gets near-black-magenta (darker than the already-dark `Window`), GBS.FM gets a forest-green tinted overlay, GBS.FM After Dark inverts that, Dark/Light each get a darkened-vs-Window pair similar to today's grey but tinted by 1-2% toward the theme's accent family. Planner samples each preset and writes locked hex into PLAN.md before execution. Acceptable to derive from existing preset roles (e.g., `Window` darkened by ~60% for `ToolTipBase`, `WindowText` for `ToolTipText`) as a starting point, then hand-tune for contrast.
- **Branching mechanism for theme = 'system' (D-10 a vs b).** Recommended path: `QApplication.property("theme_name")` (option b) for decoupling. Planner picks based on whether any other widget will need to branch on theme name in the near term.
- **Whether `apply_theme_palette()` should `setProperty("theme_name", theme_name)` on `QApplication`.** Recommended YES (enables D-10 option b cleanly). The same property update needs to fire from `theme_picker_dialog._apply_theme_to_app` for live preview to keep the toast's branch in sync.
- **Whether the empty Custom slot (`theme_custom` unset) should pre-populate `ToolTipBase`/`ToolTipText` from the source preset on first editor-open**. Recommended YES — Phase 66 D-09 already specifies "duplicate-and-edit only" with source-preset pre-fill; the new rows naturally inherit from the source preset when the editor opens.
- **Whether to add a `QPalette.ColorRole.ToolTipBase` defense-in-depth allow-list to `build_palette_from_dict()`.** Not needed — `getattr(QPalette.ColorRole, role_name, None)` already silently skips unknown role names; `ToolTipBase` and `ToolTipText` are valid `QPalette.ColorRole` enum members so they pass through naturally.
- **Whether the `theme.py` docstring "Theme owns 9 QPalette primary roles" wording should update to "Theme owns 11 QPalette primary roles".** Yes — also update `EDITABLE_ROLES` count comment (if any) and the Phase 66 D-08 cross-reference. Documentation-only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & this phase

- `.planning/ROADMAP.md` §"Phase 75: Extend theme coloring to include toast colors — Phase 66 introduced preset/custom color schemes; toast notifications still use hardcoded colors and don't track the active theme" (lines 694-702) — phase goal stub. Goal text in this CONTEXT.md supersedes the placeholder.
- `.planning/REQUIREMENTS.md` — no existing requirement maps to "toast theming" yet. Planner's first move: add a new requirement under the THEME family from Phase 66 (e.g., `THEME-02: Toast notifications track the active theme via ToolTipBase/ToolTipText palette roles`) before splitting into plans.
- `.planning/PROJECT.md` §Current Milestone: v2.1 Fixes and Tweaks — open-ended polish milestone; toast theming is in scope.

### Phase 66 — DO NOT REGRESS

- `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-CONTEXT.md` — entire file. Specifically:
  - **D-01 / D-08** — 9 editable QPalette roles. Phase 75 D-05 extends this to 11 (adds `ToolTipBase` + `ToolTipText`). Update the wording carry-forward in any reference to "9 roles".
  - **D-03** — `_theme.py` constants (`ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`) NOT touched. Phase 75 preserves this.
  - **D-09 / D-10 / D-12 / D-13 / D-14** — duplicate-and-edit, single overwrite slot, live-preview-snapshot-restore, save semantics, Reset to source preset. Phase 75 inherits all of these for the toast roles.
  - **D-22** — `theme` enum + `theme_custom` JSON. Phase 75 reuses both unchanged.
  - **D-23** — startup application order (theme → accent override). Phase 75 leaves this exactly as-is; toast reads palette lazily at first `show_toast()` so it picks up post-startup palette.
- `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-RESEARCH.md` lines 1020-1023 — Phase 66 explicitly anticipated this work: "Should ToolTipBase / ToolTipText / BrightText / Mid be set per theme? RESOLVED: leave at Qt defaults for v1. If UAT surfaces unreadable tooltips on dark themes, add ToolTip roles in v1.1." Phase 75 IS that v1.1.
- `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-RESEARCH.md` line 372 — table entry: `toast.py:45-52 | rgba(40,40,40,220) background hardcoded | ✓ By D-03 | Theme-independent toast`. Phase 75 reverses this exemption.
- `musicstreamer/theme.py` (entire file, 232 lines) — `THEME_PRESETS`, `EDITABLE_ROLES`, `build_palette_from_dict`, `apply_theme_palette`. Phase 75 modifies `THEME_PRESETS` (per-preset additions), `EDITABLE_ROLES` (append two), and may add a `setProperty("theme_name", theme_name)` line in `apply_theme_palette` (D-10 path b).
- `musicstreamer/ui_qt/theme_editor_dialog.py` — Custom theme editor. Phase 75 grows row count from 9 → 11 by appending to `EDITABLE_ROLES`; no editor-specific code change beyond verifying the row layout still fits.
- `musicstreamer/ui_qt/theme_picker_dialog.py` — preset picker. Phase 75 verifies the live-preview tile-click path iterates `THEME_PRESETS[theme_id]` (no hardcoded role allow-list); also writes `QApplication.setProperty("theme_name", theme_id)` if D-10 path b is chosen.

### Toast widget — primary modification target

- `musicstreamer/ui_qt/toast.py` (entire file, 115 lines) — the modification target. Specifically:
  - Lines 44-52 — the hardcoded `setStyleSheet(...)` block replaced with palette-driven QSS rebuilder (per D-01 + D-09 system-theme branch).
  - Lines 28-79 — `__init__` shape unchanged except for: optional `repo` constructor arg if D-10 path a chosen; `changeEvent` override added at end of class.
  - Lines 82-94 — `show_toast()` unchanged. Toast reads palette lazily; QSS-rebuilder runs in `__init__` and on every `changeEvent(PaletteChange)`.
  - Lifetime contract preserved: `WA_TransparentForMouseEvents=True`, `WA_ShowWithoutActivating=True`, NO `WA_DeleteOnClose`, parent-owned animations (Pitfall §6) — none of these change.

### Established palette-tracking patterns to mirror

- `musicstreamer/ui_qt/now_playing_panel.py:194-197` — `_MutedLabel.changeEvent(QEvent.PaletteChange)` handler that re-runs `_apply_muted_palette()`. Direct template for ToastOverlay's `changeEvent` override.
- `musicstreamer/ui_qt/eq_response_curve.py:122` — second example of the same pattern (handles both `PaletteChange` and `StyleChange`). ToastOverlay's `changeEvent` should handle both event types for consistency.
- `musicstreamer/__main__.py:88-89` — `_apply_windows_palette` already sets `QPalette.ToolTipBase` + `QPalette.ToolTipText` to `Qt.white` on Windows for `theme = 'system'`. Phase 75 D-09 (system-theme legacy fallback in ToastOverlay) bypasses this on the toast widget specifically — the toast's own QSS branch overrides whatever Qt thinks ToolTipBase should be when `theme = 'system'`. Other tooltip-using widgets (which Qt creates internally for `setToolTip(...)` strings) continue to read the system palette unchanged.

### Phase 59 / accent layering — UNTOUCHED

- `.planning/phases/59-visual-accent-color-picker/59-CONTEXT.md` D-02 + D-15 — accent layering contract. Phase 75 does NOT touch this. Toast colors are independent of `accent_color`; picking a new accent color does NOT retint toasts.
- `musicstreamer/accent_utils.py` (entire file, 71 lines) — `_is_valid_hex`, `apply_accent_palette`. Phase 75 reuses `_is_valid_hex` for any new defensive validation in toast (e.g., guarding `palette().color().name()` output, though `QColor.name()` is always a valid hex).

### Existing toast call-site invariant — UNTOUCHED

- `musicstreamer/ui_qt/main_window.py:539-541` — `MainWindow.show_toast(text, duration_ms=3000)` proxy. Signature stays exactly as-is (D-04: no severity tiers).
- 28 call sites across `main_window.py` (e.g., lines 558, 748, 781, 786, 790, 814, 817, 872, 1173, 1356, 1360, 1395), `now_playing_panel.py` (via `live_status_toast` signal at `main_window.py:416`), `discovery_dialog.py:151`, `gbs_search_dialog.py`, etc. — every call site keeps its current signature. NO file-modification required to these.
- `musicstreamer/ui_qt/station_list_peek_overlay.py:5, 19, 23, 116, 117` — z-order coupling with ToastOverlay. Phase 75 does NOT change toast geometry, raise_/show order, or parenting — peek overlay's invariants are preserved.

### Project conventions

- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints throughout, no formatter, no linter on save. Bound-method signal connections (QA-05) — applies to any new signal hookups. `changeEvent` override follows established pattern.
- `.planning/codebase/STACK.md` — Python 3.10+, PySide6 6.11+. No new runtime deps for Phase 75 (`QPalette`, `QEvent.PaletteChange`, `QGraphicsOpacityEffect` are all stock).
- `.planning/codebase/CONCERNS.md` — `_is_valid_hex` validator stays the consumption-boundary guard for `theme_custom` JSON parsing (defense-in-depth — JSON might be tampered with via export/import ZIP round-trip). Phase 75 inherits this for the two new keys.
- `.planning/codebase/ARCHITECTURE.md` — module boundaries; toast widget stays in `musicstreamer/ui_qt/toast.py`. Theme code stays in `musicstreamer/theme.py`.
- Linux Wayland deployment target, DPR=1.0 (per project memory) — toast retint on PaletteChange must be tested on Wayland with DPR=1.0. UI auditor's CRITICAL findings on HiDPI/fractional scaling downgrade to WARNING.

### No external specs

No ADRs apply. The phase is captured by ROADMAP §Phase 75 (placeholder), Phase 66's CONTEXT.md/RESEARCH.md (theme system + foreshadowing), the existing toast widget + theme code, this CONTEXT.md, and PySide6's `QPalette` documentation (`ToolTipBase`/`ToolTipText` are stock palette roles documented in PySide6 6.11 — no external doc to vendor in).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`musicstreamer/theme.py:THEME_PRESETS`** — extend in place: add `ToolTipBase` + `ToolTipText` keys to all 6 non-system preset entries.
- **`musicstreamer/theme.py:EDITABLE_ROLES`** — append `"ToolTipBase"` and `"ToolTipText"` after `"Link"`. Editor row count auto-grows from 9 → 11.
- **`musicstreamer/theme.py:build_palette_from_dict`** — already handles arbitrary `{role_name: hex}` entries via `getattr(QPalette.ColorRole, role_name, None)`. No change required to accept the new keys.
- **`musicstreamer/theme.py:apply_theme_palette`** — read site for `theme` setting. Phase 75 may add `app.setProperty("theme_name", theme_name)` here (D-10 path b).
- **`musicstreamer/ui_qt/now_playing_panel.py:194-197`** — `changeEvent(QEvent.PaletteChange)` template. Copy verbatim into `ToastOverlay`.
- **`musicstreamer/ui_qt/eq_response_curve.py:122`** — second `changeEvent` example handling both `PaletteChange` and `StyleChange`. Confirms the multi-event-type approach.
- **`musicstreamer/__main__.py:88-89`** — confirms `ToolTipBase`/`ToolTipText` are valid `QPalette.ColorRole` members and already used elsewhere in the codebase. No new roles introduced.

### Established Patterns

- **`changeEvent(QEvent.PaletteChange | QEvent.StyleChange)` for live-retint widgets** (`now_playing_panel.py:194`, `eq_response_curve.py:122`) — Phase 75 ToastOverlay joins this pattern.
- **Palette-driven QSS interpolation** — when QSS needs hex values that should track the palette, build the stylesheet string at runtime from `palette().color(role).name()` (Qt returns `#rrggbb`) rather than hardcoded literals. Toast splits this into a `_rebuild_stylesheet()` helper called from `__init__` and `changeEvent`.
- **`alpha = 220` translucency convention** — preserved verbatim from current `toast.py:47`. Appended via `rgba(R, G, B, 220)` at QSS-build time.
- **Bound-method signal/event connections (QA-05)** — `changeEvent` is an override (no `.connect()`); no QA-05 concern here.
- **Single-instance ToastOverlay reuse** — `main_window.py:356` constructs once, `show_toast` is called repeatedly. Palette-driven QSS rebuild is cheap; safe to call in `changeEvent` even if no toast is currently visible.
- **System-theme legacy preservation** (Phase 66 D-23 verbatim-Windows-palette branch sets the precedent of "theme='system' is a special-cased branch with bespoke behavior"). Phase 75 D-09 follows the same idiom for the toast widget.

### Integration Points

- **Modified files (3):**
  - `musicstreamer/theme.py` — `THEME_PRESETS` per-preset additions; `EDITABLE_ROLES` append; optional `app.setProperty("theme_name", ...)` in `apply_theme_palette`.
  - `musicstreamer/ui_qt/toast.py` — replace hardcoded `setStyleSheet` with palette-driven `_rebuild_stylesheet()` helper + system-theme branch + `changeEvent` override.
  - `musicstreamer/ui_qt/theme_picker_dialog.py` — verify live-preview tile-click path covers new keys (likely automatic); optionally `app.setProperty("theme_name", ...)` for D-10 path b.
- **Possibly modified files (1):**
  - `musicstreamer/ui_qt/theme_editor_dialog.py` — should be no-op if it iterates `EDITABLE_ROLES`; if it has a hardcoded 9-element layout, update to 11.
- **Untouched files (must not regress):**
  - `musicstreamer/ui_qt/main_window.py` — `show_toast()` proxy + 28 call sites.
  - `musicstreamer/ui_qt/_theme.py` — `ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE` (Phase 66 D-03).
  - `musicstreamer/accent_utils.py` — accent layering (Phase 59 D-02).
  - `musicstreamer/ui_qt/accent_color_dialog.py` — accent picker.
  - `musicstreamer/ui_qt/station_list_peek_overlay.py` — z-order coupling with toast.
- **Test files (modified):**
  - `tests/test_toast_overlay.py` — line 143 assertion becomes system-theme-only; add palette-driven assertions + `changeEvent` retint assertion (D-13).
  - `tests/test_theme.py` — per-preset `ToolTipBase`/`ToolTipText` presence assertions (D-15).
  - `tests/test_theme_editor_dialog.py` — 11-row coverage for Save/Reset/Cancel (D-14).
- **Test files (must continue to pass):**
  - `tests/test_theme_picker_dialog.py` — verify live-preview retints toast with new ToolTipBase values when a preset tile is clicked.
  - `tests/test_accent_color_dialog.py`, `tests/test_accent_provider.py` — no Phase 75 changes; verify accent layering still works (toast independent of accent).

</code_context>

<specifics>
## Specific Ideas

- **The user-visible promise:** "I'm using Vaporwave (or any theme other than System default) and a toast pops up — it's not a generic dark grey blob anymore. The bg color is tinted to match the theme (a soft pinkish overlay for Vaporwave, near-black-magenta for Overrun, forest-green for GBS.FM, etc.) and the text picks up the theme's tooltip text color. When I switch themes via the picker, the next toast (and any visible one) repaints to the new theme instantly. If I'm on the default System theme, toasts look exactly like they do today — dark grey overlay, white text — no regression."
- **Phase 66 explicitly anticipated this work.** `66-RESEARCH.md` lines 1020-1023: "Should ToolTipBase / ToolTipText / BrightText / Mid be set per theme? RESOLVED: leave at Qt defaults for v1. If UAT surfaces unreadable tooltips on dark themes, add ToolTip roles in v1.1." Phase 75 is the v1.1 follow-up. The toast widget is one of the consumers that surfaces "unreadable on dark themes" because today it's hardcoded dark grey on dark themes, which is fine, but it's locked dark-grey on Vaporwave too, which clashes with the pastel aesthetic.
- **Stock palette roles, not new roles.** `QPalette.ColorRole` is a closed enum in Qt — we can't add a `ToastBg` member. ToolTipBase/ToolTipText are the *intended* roles for floaty notification widgets in Qt's design vocabulary. Reusing them is idiomatic, not a hack.
- **System-theme legacy preservation is intentional.** The user runs Linux Wayland + GNOME (per project memory). Qt on GNOME picks ToolTipBase from the GTK/Adwaita theme — typically a pale yellow tooltip color. That would be a visible regression vs today's dark grey overlay. Branching on `theme='system'` keeps the day-one experience pixel-identical.
- **Single-style retint is the right scope.** The 28 call sites cover info, success, and error semantics with one widget today. Splitting them is its own UX exercise (icon? color? text-prefix? typography?) and belongs in a future phase if daily use surfaces a need. Roadmap intent is "extend theme coloring", not "add severity tiers".
- **No SQLite migration.** `theme_custom` JSON dict is already a free-form `{role_name: hex}` blob; adding two more accepted keys is purely additive. Existing Custom-theme users get default Qt ToolTipBase/ToolTipText on their next launch; one trip through the editor + Save updates their Custom palette to include the new keys.

</specifics>

<deferred>
## Deferred Ideas

- **Severity tiers (info/success/error toast colors).** Considered, rejected for Phase 75. If daily use surfaces a need (e.g., error toasts get lost in the visual flow because they look identical to "Saved to favorites"), a future phase can add a `kind=` parameter to `show_toast()`, classify the 28 call sites, and grow the editor by 4 more rows (info-bg/text + error-bg/text). Single-tier retint preserves the smallest possible Phase 75 footprint.
- **Per-call-site toast tinting** (e.g., explicitly green for "Saved to favorites" regardless of theme). Rejected — that's a tier in disguise. Same future-phase landing as severity tiers.
- **Animated color transition on retint** (toast bg/text fades from old color to new over ~200ms when palette changes). Rejected — repaint-on-PaletteChange is sufficient. Animated transitions are cosmetic polish for a future phase if it surfaces.
- **Toast geometry/animation tunability via theme** (e.g., per-theme fade-in duration, per-theme corner-radius). Rejected — out of phase scope. Theme = colors only, not motion or geometry.
- **A separate "Toast" hamburger menu entry** for direct toast color editing without going through the theme editor. Rejected — toast colors live inside the Custom theme editor (D-05); promoting them to their own menu surface would break the "theme is the unit of palette" model.
- **`ERROR_COLOR_HEX` / `WARNING_COLOR_HEX` migration into theme system** (Phase 66 deferred-items.md item — "Theme tokens v2"). Phase 75 covers ONE half of that deferred item (toast bg). The other half (error/warning text tokens used in QSS strings at `gbs_search_dialog.py:_token_label` and elsewhere) remains deferred — those tokens are call-site-specific and not toast-related.
- **`STATION_ICON_SIZE` migration into theme system** (also Phase 66 deferred-items.md). Out of scope for Phase 75 — it's a sizing token, not a color token. Leave for a "Theme tokens v3" phase if size-tunability surfaces.
- **Auto-derived ToolTipBase/ToolTipText from Window/WindowText** for the Custom theme (so the editor doesn't grow rows). Rejected via D-05 — explicit rows give the user direct control, and the auto-derivation algorithm would need per-luminance tuning to avoid washed-out pastels. Phase 75 keeps the editor surface honest.
- **`BrightText` / `Mid` / `Dark` / `Shadow` palette role additions** to the theme editor. Phase 66 RESEARCH 1020-1023 mentioned `BrightText` / `Mid` as candidates for the same v1.1 review. None of those have a current MusicStreamer consumer that visibly clashes with the 7 presets. Add only if a future widget surfaces a "unreadable on theme X" complaint.
- **GTK/Adwaita color-scheme dynamic detection on Linux for theme='system'** (so toast picks up the live system tooltip color even under system theme). Rejected via D-09 — preserving the legacy dark-grey overlay is the explicit user choice. If a user wants their toast to track GNOME's tooltip color, the path is to switch off `theme='system'` and pick a non-system theme.

### Reviewed Todos (not folded)

None — `cross_reference_todos` step did not surface any pending todos for this phase number.

</deferred>

---

*Phase: 75-extend-theme-coloring-to-include-toast-colors-phase-66-intro*
*Context gathered: 2026-05-14*
