---
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
verified: 2026-05-09T00:00:00Z
status: human_needed
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visual mood validation on Linux Wayland (DPR=1.0)"
    expected: "Each preset's tile + dialog retint feels right: Vaporwave = lavender/pink pastel, Overrun = dark neon magenta, GBS.FM = sage/kelly green matching brand site, GBS.FM After Dark = mint on near-black, Dark/Light = neutral utility"
    why_human: "Visual mood / brand fidelity cannot be measured programmatically without a vision LLM in the loop"
  - test: "Settings export/import ZIP round-trip carries theme + theme_custom"
    expected: "Export Settings ZIP, wipe `theme` + `theme_custom` keys, restart, Import the ZIP, restart, verify Custom theme is restored"
    why_human: "Requires real desktop session + filesystem ZIP round-trip; not exercised by the 75 automated tests"
  - test: "WR-01 (REVIEW.md warning) — Picker Cancel after editor-Save + tile-click drift"
    expected: "After editor Save → tile-click Light → Cancel: app SHOULD persist `theme=custom` while displaying Light until restart (documented behavior; review-level concern only). User to confirm if observed behavior is acceptable or if WR-01 fix should be scheduled"
    why_human: "Behavior is observable manually; documented as Warning in 66-REVIEW.md but not blocked"
  - test: "Hardcoded UI tokens (ERROR_COLOR_HEX, WARNING_COLOR_HEX, STATION_ICON_SIZE) survive across all 7 themes"
    expected: "Visually inspect each theme — error toasts stay red #c0392b, warning toasts stay amber #d4a017, station icons stay 32px regardless of theme"
    why_human: "Visual inspection across 7 themes; tokens are still defined verbatim in `_theme.py` (not modified) and 5 Phase 46 regression tests still pass, so technically locked, but cross-theme rendering proof is human"
---

# Phase 66: Color Themes Verification Report

**Phase Goal:** Add a "Theme" entry to the hamburger menu (immediately above "Accent Color") that opens a modal picker with 8 tiles: System default, Vaporwave (light pastel), Overrun (dark neon), GBS.FM (light, brand-sampled), GBS.FM After Dark (dark, brand-derived), Dark, Light, and a single user-editable Custom slot. Picking a theme retints the entire app palette (9 primary QPalette roles); the existing `accent_color` setting (Phase 59) continues to override Highlight on top whenever non-empty. Custom palette is duplicate-and-edit only via a "Customize…" button on the picker, persisted as JSON in a new `theme_custom` SQLite key. No new dependencies; pure PySide6 QPalette + QColorDialog. The hardcoded QSS tokens (`ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`) survive across all themes — they are theme-independent UI tokens.

**Verified:** 2026-05-09
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1 | 7 presets defined in `THEME_PRESETS` (system, vaporwave, overrun, gbs, gbs_after_dark, dark, light); 8th `custom` is runtime-loaded | ✓ VERIFIED | `theme.py:34-127`; Python check confirms `set(THEME_PRESETS.keys()) == {'system','vaporwave','overrun','gbs','gbs_after_dark','dark','light'}`; `DISPLAY_NAMES` and `DISPLAY_ORDER` add 'custom' as 8th entry |
| 2 | GBS.FM Light hex values LOCKED verbatim per CONTEXT.md D-05 | ✓ VERIFIED | `theme.py:71-82` exact match: `Window=#A1D29D, WindowText=#000000, Base=#D8E9D6, AlternateBase=#E7F1E6, Text=#000000, Button=#B1D07C, ButtonText=#000000, Highlight=#5AB253, HighlightedText=#FFFFFF, Link=#448F3F` (uppercase preserved); confirmed via `test_gbs_preset_locked_hex_match` |
| 3 | THEME-01 entry exists in REQUIREMENTS.md with reference to Phase 66 | ✓ VERIFIED | `.planning/REQUIREMENTS.md:42` (Features bullet) + `:103` (Traceability row `\| THEME-01 \| Phase 66 \| Pending \|`); coverage counts updated to 19 total / 17 pending |
| 4 | Hamburger menu Theme action positioned IMMEDIATELY ABOVE Accent Color | ✓ VERIFIED | `main_window.py:189` `act_theme = self._menu.addAction("Theme")` followed by `:190` `triggered.connect(self._open_theme_dialog)`; existing `act_accent` follows at `:192-193`. Order check: Theme(189) < Accent(192) |
| 5 | 8-tile grid in picker (4×2) covering all 8 entries in DISPLAY_ORDER | ✓ VERIFIED | `theme_picker_dialog.py:198-208` constructs `_ThemeTile` per `DISPLAY_ORDER` (8 entries, divmod 4 = 2 rows × 4 cols); `test_dialog_shows_8_tiles` passes |
| 6 | 9 editable QPalette roles in editor, Highlight EXCLUDED per D-08 | ✓ VERIFIED | `theme.py:154-164` `EDITABLE_ROLES` is 9-tuple without `Highlight`; `theme_editor_dialog.py:37-47` `ROLE_LABELS` has 9 keys, no Highlight; `test_editor_shows_9_color_rows` asserts `'Highlight' not in dialog._rows` |
| 7 | Layered Highlight contract preserved — `apply_accent_palette` re-imposed after every theme mutation; `accent_color` setting NEVER mutated | ✓ VERIFIED | `theme_picker_dialog.py:281-283` re-imposes accent in `_on_tile_clicked`; `theme_editor_dialog.py:265-267` re-imposes in `_on_role_color_changed`; `:304-306` re-imposes in `_on_reset`. Zero `set_setting.*accent_color` writes in any phase 66 file (grep confirmed). Verified by `test_tile_click_preserves_accent_setting`, `test_tile_click_reapplies_accent_override`, `test_color_change_re_imposes_accent`, `test_theme_then_accent_layering` |
| 8 | Two new SQLite keys (`theme` enum + `theme_custom` JSON dict), no schema migration | ✓ VERIFIED | `theme.py:206` reads `theme`; `:217` reads `theme_custom`; `theme_picker_dialog.py:289` writes `theme`; `theme_editor_dialog.py:272-273` writes `theme_custom` + `theme='custom'`. Additive string-keyed settings, no migration script. |
| 9 | Startup ordering — `apply_theme_palette` BEFORE MainWindow construction; existing accent restore runs AFTER (overrides Highlight on top) | ✓ VERIFIED | `__main__.py:185-201` constructs QApplication, hoists `db_connect/db_init/Repo`, calls `theme.apply_theme_palette(app, repo)` (line 201) — all BEFORE `MainWindow(player, repo, ...)` at line 222. Existing `_saved_accent` restore at `main_window.py:246-249` (called from MainWindow.__init__) runs AFTER theme baseline. |
| 10 | Windows path preserved — `theme='system'` on Windows runs `app.setStyle("Fusion") + _apply_windows_palette` verbatim | ✓ VERIFIED | `theme.py:208-214` system+win32 branch lazy-imports `_apply_windows_palette` and calls it after `setStyle("Fusion")`; `__main__.py:69-99` `_apply_windows_palette` body is byte-identical to pre-phase. The original `if sys.platform == "win32"` block in `_run_gui` was deleted — its behavior is now invoked from inside theme module. |
| 11 | 48/48 phase 66 tests pass + 27/27 phase 59 regression tests pass | ✓ VERIFIED | `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q` → **75 passed** (21 theme [16 phase 66 + 5 phase 46 UI tokens] + 13 picker + 14 editor + 13 accent dialog + 14 accent provider) |
| 12 | D-08 invariant: `_on_reset` does NOT mutate Highlight even when reverting all 9 EDITABLE_ROLES | ✓ VERIFIED | `theme_editor_dialog.py:284-307` only iterates `_source_preset_palette` (which is built from EDITABLE_ROLES, Highlight-free); test `test_reset_reverts_to_source_preset` (lines 142-181 of test file) explicitly asserts `qapp.palette().color(QPalette.ColorRole.Highlight)` unchanged across `_on_reset()` |
| 13 | No new runtime dependencies; `pyproject.toml` untouched since Phase 65 bump | ✓ VERIFIED | `git log --oneline 5be4ff2~..HEAD -- pyproject.toml` shows zero phase-66 commits modifying pyproject.toml. Last touch was `14ffb020` "bump to 2.1.65 for Phase 65 completion". `dependencies` array unchanged. |
| 14 | Hardcoded UI tokens preserved — `_theme.py` (ERROR_COLOR_HEX, WARNING_COLOR_HEX, STATION_ICON_SIZE) NOT modified | ✓ VERIFIED | `musicstreamer/ui_qt/_theme.py:43, 48, 52` retain the same hex/int values; 5 Phase 46 regression tests pass (`test_error_color_hex_is_string`, `test_error_color_qcolor_is_qcolor`, `test_station_icon_size_is_32`, `test_no_raw_error_hex_outside_theme`, `test_no_raw_icon_size_in_migrated_sites`). The new `theme.py` (palette construction) and `_theme.py` (UI tokens) are separate modules — phase 66 added a new top-level module without modifying the existing UI-tokens file. |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/theme.py` | Palette construction + apply helpers (≥80 LOC) | ✓ VERIFIED | 231 LOC; defines `THEME_PRESETS`, `DISPLAY_NAMES`, `DISPLAY_ORDER`, `EDITABLE_ROLES`, `build_palette_from_dict()`, `apply_theme_palette()`. Uses `_is_valid_hex` defense-in-depth and `getattr(QPalette.ColorRole, name, None)` for unknown roles. Zero `setStyleSheet` calls. |
| `musicstreamer/ui_qt/theme_picker_dialog.py` | Modal QDialog with 4×2 tile grid (≥150 LOC) | ✓ VERIFIED | 319 LOC; `ThemePickerDialog(QDialog)` + `_ThemeTile(QPushButton)` with custom paintEvent; snapshot/restore on Cancel; `_save_committed` flag; `_on_tile_clicked` re-imposes `apply_accent_palette`; `_on_customize` lazy-imports `ThemeEditorDialog` |
| `musicstreamer/ui_qt/theme_editor_dialog.py` | 9-row Custom palette editor (≥180 LOC) | ✓ VERIFIED | 314 LOC; `ROLE_LABELS` (9 keys), `_ColorRow(QWidget)` with QColorDialog (DontUseNativeDialog), `ThemeEditorDialog(QDialog)` with Save/Reset/Cancel; `_compute_source_palette` handles 5 source_preset cases; `_on_save` flips parent flags via stashed `_save_target_parent`; `_on_reset` excludes Highlight (D-08) |
| `musicstreamer/__main__.py` | Startup wiring with hoisted db_connect + theme.apply_theme_palette | ✓ VERIFIED | `_run_gui` at lines 197-201 constructs `con/db_init/repo` then calls `theme.apply_theme_palette(app, repo)` — all BEFORE `MainWindow` at line 222. AST parse OK. |
| `musicstreamer/ui_qt/main_window.py` | Theme menu action above Accent Color + `_open_theme_dialog` slot | ✓ VERIFIED | `:189-190` adds `act_theme = self._menu.addAction("Theme")` + bound triggered.connect; `:780-790` defines `_open_theme_dialog` with lazy import. AST parse OK. |
| `tests/test_theme.py` | 16 phase-66 tests + 5 phase-46 UI-token regression tests | ✓ VERIFIED | 21 tests (16 phase 66 palette construction + apply + 5 phase 46 _theme.py tokens). All pass. |
| `tests/test_theme_picker_dialog.py` | 13 picker tests | ✓ VERIFIED | 13 tests covering 8-tile grid, click=preview, accent preservation, Customize button, snapshot restore. All pass. |
| `tests/test_theme_editor_dialog.py` | 14 editor tests including D-08 Highlight invariant | ✓ VERIFIED | 14 tests covering 9-row layout, source_preset prefill (5 cases), Save persists JSON + parent flags, Reset preserves Highlight (D-08), Cancel restores. All pass. |
| `.planning/REQUIREMENTS.md` | THEME-01 in Features + Traceability | ✓ VERIFIED | Line 42 Features bullet present; line 103 Traceability row `\| THEME-01 \| Phase 66 \| Pending \|`; coverage counts updated to 19 total / 17 pending |
| `.planning/ROADMAP.md` | Phase 66 entry with concrete Goal + 4 plans | ✓ VERIFIED | Lines 529-540 contain concrete Goal text (no `[To be planned]` placeholder), `**Requirements**: THEME-01`, `**Plans:** 4/4 plans complete`, all 4 plans listed `[x]` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `__main__._run_gui` | `theme.apply_theme_palette` | import + call | ✓ WIRED | Line 200 `from musicstreamer import theme`; line 201 `theme.apply_theme_palette(app, repo)` |
| `theme.apply_theme_palette` | `repo.get_setting("theme")` + `("theme_custom")` | settings read | ✓ WIRED | theme.py:206 reads `theme`; :217 reads `theme_custom` |
| `theme.build_palette_from_dict` | `accent_utils._is_valid_hex` | per-value validation | ✓ WIRED | theme.py:26 imports; :180 calls `_is_valid_hex(hex_value)` |
| `MainWindow._open_theme_dialog` | `ThemePickerDialog` | lazy import + .exec() | ✓ WIRED | main_window.py:788 lazy import; :789-790 `dlg = ThemePickerDialog(self._repo, parent=self); dlg.exec()` |
| `ThemePickerDialog._on_tile_clicked` | `theme.build_palette_from_dict` | function call (live preview) | ✓ WIRED | theme_picker_dialog.py:276,278 call `build_palette_from_dict(...)`; `app.setPalette(...)` mutates QApplication |
| `ThemePickerDialog._on_tile_clicked` | `apply_accent_palette` | re-impose accent on every preview | ✓ WIRED | theme_picker_dialog.py:283 calls `apply_accent_palette(app, accent)` after every palette mutation |
| `ThemePickerDialog._on_apply` | `repo.set_setting("theme", ...)` | persist on Apply | ✓ WIRED | theme_picker_dialog.py:289 |
| `ThemePickerDialog._on_customize` | `ThemeEditorDialog` | lazy import + .exec() with parent=self | ✓ WIRED | theme_picker_dialog.py:295-297 |
| `ThemeEditorDialog._on_save` | `parent._save_committed = True` | cross-modal-stack flag mutation | ✓ WIRED | theme_editor_dialog.py:277-281 (uses stashed `_save_target_parent`); test `test_save_sets_parent_flag` confirms |
| `ThemeEditorDialog._on_role_color_changed` | `apply_accent_palette` | re-impose after every role change | ✓ WIRED | theme_editor_dialog.py:267 |
| `ThemeEditorDialog._on_reset` | iterates only `_source_preset_palette` (not Highlight) | D-08 invariant | ✓ WIRED | theme_editor_dialog.py:292 — never touches `QPalette.ColorRole.Highlight` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| All phase 66 + phase 59 tests pass | `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q` | 75 passed, 1 warning in 0.68s | ✓ PASS |
| AST parse all phase 66 modules | `python -c "ast.parse(...)"` for theme.py, picker, editor, main_window.py, __main__.py | AST_OK_ALL | ✓ PASS |
| Python module imports + GBS.FM lock + EDITABLE_ROLES count + Dark/Light Highlight | Inline Python check (THEME_PRESETS contents, DISPLAY_NAMES, DISPLAY_ORDER, EDITABLE_ROLES, GBS hex dict equality, Dark/Light = ACCENT_COLOR_DEFAULT) | All assertions PASS | ✓ PASS |
| ROLE_LABELS has 9 keys, Highlight excluded | `python -c "from musicstreamer.ui_qt.theme_editor_dialog import ROLE_LABELS"` + assertions | 9 keys, no Highlight | ✓ PASS |
| pyproject.toml unchanged in phase 66 | `git log --oneline 5be4ff2~..HEAD -- pyproject.toml` | (empty — no commits) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| THEME-01 | 66-01-PLAN, 66-02-PLAN, 66-03-PLAN, 66-04-PLAN | User can switch between 7 preset themes + 1 Custom slot via hamburger menu Theme action; accent_color overrides Highlight on top; theme_custom JSON in SQLite | ✓ SATISFIED | All 14 truths VERIFIED above; THEME-01 registered in REQUIREMENTS.md (Features + Traceability); 75/75 tests green; menu action wired at `main_window.py:189`; layered Highlight contract verified by 4 dedicated tests |

**Note:** REQUIREMENTS.md still shows THEME-01 as `[ ]` Pending (line 42) and Traceability row says `Pending` (line 103). Plan 04 SUMMARY claims `requirements-completed: ["THEME-01"]` but the checkbox flip was not performed. This is a doc-state cosmetic gap — the substantive contract (theme switching works end-to-end) is fully delivered. Per phase-66 convention (Plan 01 explicitly registers as `[ ]`, with full satisfaction across 01-04), the `[ ]` → `[x]` flip was never required by any plan's `<action>` block.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TODO/FIXME/XXX/HACK/PLACEHOLDER comments in any phase 66 source file | ℹ Info | Phase 66 source files are clean |
| theme_picker_dialog.py | 305 | `_save_committed` flag never re-armed after editor save (WR-01 in 66-REVIEW.md) | ⚠ Warning | Edge case: post-Save tile-click + Cancel keeps the live preview, contradicting persisted theme until next launch. Self-resolves on relaunch. Documented as Warning in 66-REVIEW.md, not a goal blocker. |
| theme_editor_dialog.py | 218-225 | `_compute_source_palette` Case D returns partial dict when preset omits a role (WR-02) | ⚠ Warning | Latent: every current preset defines all 9 EDITABLE_ROLES, so this is benign today. A future preset missing a role would silently drop it from `theme_custom` JSON on Save. Documented as Warning in 66-REVIEW.md. |
| theme_editor_dialog.py | 18-19 | Unused imports `QFont` and `Qt` (IN-01) | ℹ Info | Cosmetic; ruff/lint cleanup. No functional impact. |
| theme.py + picker + main_window.py | various | Stale line-number references in docstrings (`main_window.py:241-245` should be `:246-249`) (IN-02) | ℹ Info | Cosmetic doc drift; comments will rot further as main_window.py evolves. No functional impact. |

### Human Verification Required

The phase goal is fully satisfied at the contract level (75/75 automated tests pass, all 14 truths VERIFIED, all 11 key links WIRED, all 5 spot-checks PASS). However, four dimensions remain that cannot be confirmed without a human at a Linux Wayland (DPR=1.0) desktop:

#### 1. Visual mood validation per preset

**Test:** Run `python -m musicstreamer`, open hamburger → Theme. Click each tile in turn and confirm:
- Vaporwave feels lavender/pink/soft pastel
- Overrun feels dark neon / hot magenta / electric cyan
- GBS.FM matches https://gbs.fm visually (sage Window, kelly green Highlight, mint Base)
- GBS.FM After Dark feels like GBS.FM transposed to a dark surface (mint text on near-black)
- Dark feels neutral utility (gray Window, neutral blue Highlight)
- Light feels neutral utility (light gray Window, neutral blue Highlight)

**Expected:** Each preset matches the documented visual intent

**Why human:** Brand fidelity / mood feel are subjective and require eyeball inspection on a real Wayland desktop. The 75 automated tests verify the hex values and palette mutation, but not perceptual quality.

#### 2. Settings export/import ZIP round-trip

**Test:**
1. Open Theme picker → Customize… → set Window to a distinctive color → Save → Apply
2. Hamburger → Export Settings → save ZIP
3. `sqlite3 ~/.local/share/musicstreamer/musicstreamer.db "DELETE FROM settings WHERE key IN ('theme', 'theme_custom');"`
4. Restart app (System default applied)
5. Hamburger → Import Settings → pick the ZIP → confirm
6. Restart app

**Expected:** Custom theme is restored — Window is the distinctive color again

**Why human:** Requires real desktop session + SQLite + filesystem ZIP round-trip; not exercised by tests. Phase 66 added two additive string-keyed settings (`theme`, `theme_custom`) which `settings_export.py` (existing) carries by default, but only manual UAT proves the round-trip.

#### 3. WR-01 edge-case behavior acceptability (66-REVIEW.md Warning)

**Test:**
1. Open Theme picker (default `system`)
2. Click Customize → edit Window color → Save → editor closes
3. Click Light tile in picker (live preview applies)
4. Click Cancel

**Expected per code:** Database persists `theme=custom` + `theme_custom=<edits>`; live app palette displays Light. On next restart, app shows Custom.

**Expected per design intent:** User's "Cancel" should likely have reverted the Light preview to the saved Custom palette.

**Why human:** This is a documented Warning (WR-01) in 66-REVIEW.md, not a blocker. Need user decision: accept current behavior or schedule fix.

#### 4. Hardcoded UI tokens cross-theme rendering

**Test:** With each theme active in turn (especially dark themes), verify that:
- Error toasts still render in `#c0392b` red
- Warning toasts still render in `#d4a017` amber
- Station-row icons stay 32px

**Expected:** Tokens visible regardless of theme palette

**Why human:** `_theme.py` is byte-identical to pre-phase (zero modifications, 5 regression tests still pass), so the contract is provably locked. But cross-theme rendering proof requires triggering toasts under each theme — which is a manual UI flow.

### Gaps Summary

**No gaps blocking goal achievement.** All 14 must-haves are VERIFIED, all 11 key links are WIRED, all 5 spot-checks PASS. 75/75 automated tests green (48 phase 66 + 27 phase 59).

Two warnings documented in 66-REVIEW.md (WR-01: snapshot re-arm on editor-save; WR-02: partial-dict in `_compute_source_palette` Case D) are latent fragilities, not active defects — both have been triaged at code review time as non-blocking.

One doc-state cosmetic note: REQUIREMENTS.md still shows THEME-01 as `[ ]` Pending. Plan 04 SUMMARY's `requirements-completed: ["THEME-01"]` claim was not realized in the markdown — but no plan's `<action>` block instructed flipping the box, and the substantive contract is fully delivered.

The phase goal is achieved. Status is `human_needed` because four manual-only verification items (visual mood, export/import round-trip, WR-01 edge-case acceptance, cross-theme token rendering) cannot be programmatically confirmed without a vision-LLM or real Wayland desktop session.

---

_Verified: 2026-05-09_
_Verifier: Claude (gsd-verifier)_
