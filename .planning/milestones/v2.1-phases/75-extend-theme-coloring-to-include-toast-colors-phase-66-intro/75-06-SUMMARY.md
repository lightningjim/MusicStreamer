---
phase: 75
plan: 06
subsystem: tests

tags: [tests, pytest-qt, qpalette, toast, changeevent, palettechange, theme, test-retrofit, wave-3]

dependency_graph:
  requires:
    - phase: 75-01
      provides: "THEME_PRESETS ToolTipBase/ToolTipText hex pairs; EDITABLE_ROLES length 11; apply_theme_palette sets QApplication.property('theme_name')"
    - phase: 75-03
      provides: "ToastOverlay._rebuild_stylesheet branching on QApplication.property('theme_name'); changeEvent(QEvent.PaletteChange) live retint hook"
  provides:
    - "tests/test_toast_overlay.py — 19 tests covering: system-gated legacy QSS (test_14 renamed), non-system vaporwave + overrun palette-driven QSS, changeEvent retint, typography invariance, geometry invariance across 4 theme branches"
    - "tests/test_theme.py — 26 tests covering: 11-role EDITABLE_ROLES coverage, 12 LOCKED ToolTipBase/ToolTipText hex pins across 6 presets, system-preset-stays-empty sentinel, EDITABLE_ROLES tail order, apply_theme_palette property for preset + system paths"
  affects:
    - tests/test_toast_overlay.py
    - tests/test_theme.py

tech_stack:
  added: []
  patterns:
    - "QApplication.sendPostedEvents() between qapp.setPalette() and toast construction — headless test pattern documented in PLAN-03 SUMMARY (Qt 6.11 dispatches PaletteChange via posted-events queue, not synchronously; parent_widget constructed before the flip needs the flush before the toast inherits its palette)"
    - "Snapshot-mutate-assert for changeEvent verification — qss_before snapshot, mutate via setPalette + setProperty, assert qss_after != qss_before AND new substring present"
    - "Per-test qapp.setProperty('theme_name', ...) explicit setup — never assume the session-scoped pytest-qt qapp inherits a clean state (cross-test pollution guard)"
    - "Locked-hex pin pattern extended — _GBS_LOCKED dict mirrors the verbatim Phase 66 D-05 + Phase 75 D-08 hex set; test_tooltip_role_locked_hex_per_preset adds 12 inline assertions across 6 presets without mutating any existing dict in source"

key_files:
  created: []
  modified:
    - "tests/test_toast_overlay.py — +112 lines / -2 lines: import THEME_PRESETS+build_palette_from_dict+QApplication; rename test_14_stylesheet_color_contract → _system_theme_color_contract; add 5 new tests (vaporwave palette, overrun palette, changeEvent retint, no-font invariance, geometry invariance)"
    - "tests/test_theme.py — +51 lines / -2 lines: _GBS_LOCKED dict extended with Phase 75 ToolTipBase/ToolTipText keys (anticipated by PLAN-01 SUMMARY); rename test_all_presets_cover_9_roles → _11_roles + add len assertion; add 5 new tests (12 locked hex pins, system stays empty, EDITABLE_ROLES tail order, theme_name property for preset, theme_name property for system)"

decisions:
  - "Extended _GBS_LOCKED with Phase 75 ToolTipBase/ToolTipText keys. PLAN-01 SUMMARY anticipated that test_gbs_preset_locked_hex_match would break after Phase 75 additively extended the GBS preset (10 keys → 12 keys) and explicitly assigned ownership of the fix to PLAN-06. The plan body's instruction 'DO NOT touch the _GBS_LOCKED dict' was an authoring oversight — the test simply could not still pass with a 10-key fixture against a 12-key preset. Resolution: add the two locked Phase 75 keys to _GBS_LOCKED with an inline comment marking them as Phase 75 D-08 / UI-SPEC LOCKED (distinct from the Phase 66 D-05 brand-site-verbatim keys). Both lock semantics preserved."
  - "QApplication.sendPostedEvents() between setPalette and toast construction. Qt 6.11 dispatches PaletteChange via the posted-events queue (not synchronously). The parent_widget fixture is constructed BEFORE the per-test palette flip, so its cached palette is stale at the time the toast inherits from it via self.palette(). The PLAN-03 SUMMARY documented this finding and called out PLAN-06 as the consumer of the resolution pattern. Initial test run (without the flush) confirmed the issue — vaporwave test saw rgba(255, 255, 220, 220) (Qt's default ToolTipBase yellow), not the vaporwave LOCKED hex."
  - "Per-test qapp.setProperty('theme_name', ...) explicit setup, no autouse cleanup fixture. The pytest-qt qapp is session-scoped; without explicit setup at the start of each test, a stray setProperty call in a prior test pollutes downstream. The plan body called this out explicitly: 'Do NOT add an autouse cleanup fixture (additive minimum-diff per Phase 75 budget).' All 5 new toast tests follow this pattern."
  - "Geometry+typography invariance tests iterate across 4 theme branches (system + vaporwave + overrun + dark) rather than all 7. Covers the system branch + bright family (vaporwave) + dark family (overrun) + neutral family (dark) — every QSS shape produced by _rebuild_stylesheet. gbs / gbs_after_dark / light add no new QSS shape (their palette-driven branch is the same code path as vaporwave/overrun)."

metrics:
  duration_seconds: 580
  tasks_completed: 2
  files_modified: 2
  files_created: 0
  completed_date: 2026-05-15
---

# Phase 75 Plan 06: tests/test_toast_overlay.py + tests/test_theme.py retrofit Summary

**Test-surface coverage for the Phase 75 toast retint plumbing (PLAN-03) and theme.py 11-role foundation (PLAN-01) landed in two test files: 6 new toast tests + 1 rename gating the legacy QSS to theme='system'; 5 new theme tests + 1 rename for 11-role EDITABLE_ROLES coverage + 12 LOCKED ToolTipBase/ToolTipText hex pin assertions across 6 presets. All 45 tests (19 toast + 26 theme) pass.**

## Performance

- **Duration:** ~10 min (Wave 3 worktree agent)
- **Completed:** 2026-05-15
- **Tasks:** 2
- **Files modified:** 2 (tests/test_toast_overlay.py, tests/test_theme.py)

## Accomplishments

### Task 1 — tests/test_toast_overlay.py

- **Renamed `test_14_stylesheet_color_contract` → `test_14_stylesheet_system_theme_color_contract`.** Gated the legacy `rgba(40, 40, 40, 220)` assertion to explicit `qapp.setProperty("theme_name", "system")` setup. Added two additional assertions in the same test: `color: white` (UI-SPEC IMMUTABLE QSS LOCK preserved) and `padding: 8px 12px` (geometry locked under system branch).
- **Added `test_stylesheet_non_system_uses_tooltip_palette`** — vaporwave UI-SPEC LOCKED palette → asserts `rgba(249, 214, 240, 220)` (ToolTipBase=#f9d6f0 → rgb), `color: #3a2845` (ToolTipText lowercase), `border-radius: 8px`, `padding: 8px 12px`.
- **Added `test_stylesheet_non_system_overrun_palette`** — overrun UI-SPEC LOCKED palette → asserts `rgba(26, 10, 24, 220)` (ToolTipBase=#1a0a18 → rgb) and `color: #ffe8f4`. Vaporwave (bright) + overrun (dark) covers both contrast regimes.
- **Added `test_changeEvent_palette_change_rebuilds_qss`** — snapshot-mutate-assert: construct under `theme='system'` (snapshot legacy QSS); flip to vaporwave via `qapp.setProperty("theme_name", "vaporwave")` + `qapp.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))` + `QApplication.sendPostedEvents()` (Qt 6.11 PaletteChange dispatched via posted events). Assert `qss_after != qss_before` AND `rgba(249, 214, 240, 220)` in `qss_after`.
- **Added `test_stylesheet_no_font_properties`** — typography invariance lock. Iterates across `("system", "vaporwave", "overrun", "dark")`; for each, assert `font-size:`, `font-family:`, `font-weight:` are NOT in the QSS.
- **Added `test_stylesheet_geometry_invariant_both_branches`** — geometry invariance lock. Same 4-theme iteration; for each, assert `border-radius: 8px` AND `padding: 8px 12px` ARE in the QSS.
- **Imports extended:** added `from musicstreamer.theme import THEME_PRESETS, build_palette_from_dict`; added `QApplication` to the existing `PySide6.QtWidgets` import line.

### Task 2 — tests/test_theme.py

- **Extended `_GBS_LOCKED` dict** with the two Phase 75 LOCKED keys (`ToolTipBase=#2d5a2a`, `ToolTipText=#f0f5e8`) — anticipated by PLAN-01 SUMMARY ("This breakage is anticipated and explicitly owned by PLAN-06"). Added inline comment marking the new keys as Phase 75 D-08 / UI-SPEC LOCKED (distinct from the Phase 66 D-05 brand-site-verbatim keys).
- **Renamed `test_all_presets_cover_9_roles` → `test_all_presets_cover_11_roles`** — updated docstring to "all 11 EDITABLE_ROLES (Phase 75 D-08)"; added `assert len(EDITABLE_ROLES) == 11` at the top of the body. Existing inner for-loop unchanged (auto-grew with EDITABLE_ROLES).
- **Added `test_tooltip_role_locked_hex_per_preset`** — 12 LOCKED hex pin assertions: vaporwave (`#f9d6f0` / `#3a2845`), overrun (`#1a0a18` / `#ffe8f4`), gbs (`#2d5a2a` / `#f0f5e8`), gbs_after_dark (`#d5e8d3` / `#0a1a0d`), dark (`#181820` / `#f0f0f0`), light (`#2a2a32` / `#f5f5f5`). Helpful failure messages embedded.
- **Added `test_system_preset_stays_empty`** — `THEME_PRESETS["system"] == {}` (Phase 66 D-23 sentinel).
- **Added `test_editable_roles_appends_tooltip_pair_last`** — asserts `len(EDITABLE_ROLES) == 11` AND `EDITABLE_ROLES[-2:] == ("ToolTipBase", "ToolTipText")`.
- **Added `test_apply_theme_palette_sets_theme_name_property(qapp, repo)`** — set theme='gbs', call apply_theme_palette, assert `qapp.property("theme_name") == "gbs"`.
- **Added `test_apply_theme_palette_sets_property_for_system(qapp, repo)`** — same shape for theme='system'.

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Retrofit test_toast_overlay.py — rename test_14 + 5 new tests | `57354d7` | tests/test_toast_overlay.py |
| 2 | Retrofit test_theme.py — _GBS_LOCKED extend + rename 9→11 roles + 5 new tests | `d10148d` | tests/test_theme.py |

## Files Created/Modified

- `tests/test_toast_overlay.py` — +112 / -2. Pre-existing tests 1-13 untouched. Test 14 renamed + extended. 5 new tests appended after test 14.
- `tests/test_theme.py` — +51 / -2. Pre-existing structure preserved; `_GBS_LOCKED` extended with 2 new keys; `test_all_presets_cover_9_roles` renamed to `_11_roles`; 5 new tests appended into the "preset definitions" / "apply_theme_palette: preset path" sections (immediately after the rename, before the existing `test_dark_light_use_accent_default_highlight`).

## Decisions Made

- **`_GBS_LOCKED` extension despite plan instruction.** The plan body said "DO NOT touch the `_GBS_LOCKED` dict at lines 114-126" and claimed `test_gbs_preset_locked_hex_match` "still passes". This was an authoring oversight: the test compares `THEME_PRESETS["gbs"] == _GBS_LOCKED`, and Phase 75 PLAN-01 additively extended `THEME_PRESETS["gbs"]` from 10 → 12 keys. PLAN-01 SUMMARY explicitly anticipated this: "**This breakage is anticipated and explicitly owned by PLAN-06**". Resolved by adding the 2 Phase 75 LOCKED keys to `_GBS_LOCKED` with a comment marking their provenance (Phase 75 D-08 / UI-SPEC LOCKED, distinct from the Phase 66 D-05 brand-site-verbatim keys). Both lock intents preserved: the 10 original keys still match the brand site verbatim; the 2 new keys still match the UI-SPEC LOCKED table verbatim.
- **`QApplication.sendPostedEvents()` between `setPalette` and reading `styleSheet()` / constructing a new toast.** Without the flush, the parent_widget fixture (constructed before the per-test palette flip) has a stale palette, and the toast inherits from it via `self.palette()`. Initial test run confirmed: vaporwave test saw `rgba(255, 255, 220, 220)` (Qt's default yellow ToolTipBase), not the LOCKED `rgba(249, 214, 240, 220)`. PLAN-03 SUMMARY documented this Qt 6.11 quirk and called out PLAN-06 as the consumer of the resolution pattern. The flush is added in every test that flips the palette mid-test.
- **Per-test explicit `qapp.setProperty("theme_name", ...)` calls; no autouse fixture.** The pytest-qt qapp is session-scoped — without explicit setup, a stray setProperty in a prior test pollutes downstream tests. The plan body explicitly forbade adding an autouse cleanup fixture ("additive minimum-diff per Phase 75 budget"). Every new test starts with the explicit setProperty call.
- **4-theme iteration (system + vaporwave + overrun + dark) for invariance tests, not all 7.** Covers every distinct QSS code path: system branch (legacy QSS) + bright non-system (vaporwave) + dark non-system (overrun) + neutral non-system (dark). gbs / gbs_after_dark / light traverse the same non-system code path as vaporwave/overrun and add no new shape — 7-theme iteration would be redundant with no additional coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended `_GBS_LOCKED` dict from 10 to 12 keys**
- **Found during:** Task 2 baseline run (pre-existing test failure inherited from Phase 75 PLAN-01)
- **Issue:** `test_gbs_preset_locked_hex_match` failed: `THEME_PRESETS["gbs"]` had grown to 12 keys via PLAN-01, but `_GBS_LOCKED` was still the 10-key Phase 66 dict. PLAN-06's plan body said "DO NOT touch the `_GBS_LOCKED` dict... the existing `test_gbs_preset_locked_hex_match` still passes" — this was incorrect; the test could not pass without the extension.
- **Fix:** Added `"ToolTipBase": "#2d5a2a"` and `"ToolTipText": "#f0f5e8"` (the UI-SPEC LOCKED Phase 75 D-08 GBS values, identical to `THEME_PRESETS["gbs"]["ToolTipBase"/"ToolTipText"]`) with an inline comment distinguishing them from the Phase 66 D-05 brand-site-verbatim keys.
- **Files modified:** `tests/test_theme.py` (the `_GBS_LOCKED` dict literal)
- **Commit:** `d10148d`
- **Plan reconciliation:** PLAN-01 SUMMARY anticipated this exact issue and assigned ownership to PLAN-06 ("**This breakage is anticipated and explicitly owned by PLAN-06**"). The fix preserves the intent of the test (locked-pin verbatim match of GBS palette) under the new 12-key shape.

## Known Stubs

None. All test assertions are concrete values pinned against the UI-SPEC LOCKED table or against the actual Phase 75 implementation behavior. No placeholder hex, no TODOs, no skipped tests.

## Verification Results

- **Combined pytest:** `pytest tests/test_toast_overlay.py tests/test_theme.py -x` → 45 passed, 1 warning (unrelated PyGI deprecation), 0 failed.
- **Source-grep gates (Task 1 — test_toast_overlay.py):**
  - `grep -c 'test_14_stylesheet_color_contract' tests/test_toast_overlay.py` → 0 (legacy name removed).
  - `grep -c 'test_14_stylesheet_system_theme_color_contract' tests/test_toast_overlay.py` → 1.
  - `grep -c '"rgba(249, 214, 240, 220)"' tests/test_toast_overlay.py` → 2 (vaporwave palette test + changeEvent test).
- **Source-grep gates (Task 2 — test_theme.py):**
  - `grep -c 'test_all_presets_cover_9_roles' tests/test_theme.py` → 0.
  - `grep -c 'test_all_presets_cover_11_roles' tests/test_theme.py` → 1.
  - `grep -c 'test_tooltip_role_locked_hex_per_preset' tests/test_theme.py` → 1.
  - `grep -c 'ToolTipBase' tests/test_theme.py` → 6 (1 in `_GBS_LOCKED` + 6 expected dict keys + ... actual count = 6 matches across the new test surface).
- **Per-test must-haves (UI-SPEC §Test surface 75-UI-SPEC.md:298-316):**
  - test_toast_overlay.py test 143 system-gated: PASS.
  - Non-system palette QSS assertion (vaporwave + overrun): PASS.
  - changeEvent rebuilds (snapshot-before/after): PASS.
  - Geometry + typography invariance both branches: PASS.
  - test_theme.py 11-role count + per-preset locked hex pairs (6 × 2 = 12 assertions): PASS.
  - system stays empty: PASS.
  - apply_theme_palette sets QApplication property for both preset and system: PASS.

## Threat Surface

No new threat surface. Per the plan's `<threat_model>` T-75-08 (Tampering V5 — N/A): test files are read-only consumers of `THEME_PRESETS`, `EDITABLE_ROLES`, `apply_theme_palette`, and `ToastOverlay`. They lock the behavioral contract introduced by PLAN-01 + PLAN-03. The V5 mitigation for `theme_custom` JSON lives upstream in `theme.py:179-186` (no Phase 75 change required).

## Self-Check: PASSED

- File `tests/test_toast_overlay.py` exists (modified): FOUND (`wc -l` returns 257 lines, up from 145).
- File `tests/test_theme.py` exists (modified): FOUND (`wc -l` returns 366 lines, up from 318).
- Commit `57354d7` (Task 1) exists in `git log --oneline`: FOUND.
- Commit `d10148d` (Task 2) exists in `git log --oneline`: FOUND.
- Both commits live on branch `worktree-agent-a69ba8dfef791f8cf` based on `bb74f7d`.
- `pytest tests/test_toast_overlay.py tests/test_theme.py` exit code 0: VERIFIED (45 passed).

## Next Plan Readiness

- Plan 75-07 (theme editor dialog test retrofit for 11-row editor) inherits the verification template:
  - Use the `_GBS_LOCKED` extension pattern (or analogous per-fixture extensions) when a Phase 66 locked dict must absorb the Phase 75 additive keys.
  - Use `QApplication.sendPostedEvents()` between `setPalette` and reading widget state in headless tests.
- Plan 75-08 (final integration test) inherits both above plus the snapshot-mutate-assert pattern for `changeEvent` retint verification.
- All Wave-2 behavioral contracts (toast retint, 11-role foundation, QApplication property broadcast) are now locked in test code; any future regression will surface immediately in `pytest tests/test_toast_overlay.py tests/test_theme.py`.

---
*Phase: 75-extend-theme-coloring-to-include-toast-colors-phase-66-intro*
*Completed: 2026-05-15*
