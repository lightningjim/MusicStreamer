---
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
plan: 01

subsystem: ui

tags:
  - pyside6
  - qpalette
  - theme
  - color
  - startup-wiring
  - defense-in-depth

# Dependency graph
requires:
  - phase: 19-accent-color-picker
    provides: "ACCENT-01 — accent_color SQLite key + apply_accent_palette"
  - phase: 40-accent-css-validator
    provides: "_is_valid_hex defense-in-depth + build_accent_qss"
  - phase: 59-visual-accent-color-picker
    provides: "ACCENT-02 — Phase 59 layering contract (Highlight override on top of theme baseline)"

provides:
  - "musicstreamer.theme module with THEME_PRESETS (7 presets), DISPLAY_NAMES (8 keys), DISPLAY_ORDER (8-tuple), EDITABLE_ROLES (9-tuple)"
  - "build_palette_from_dict() — defense-in-depth palette construction from {role_name: hex} dict"
  - "apply_theme_palette(app, repo) — startup palette application, branches on theme setting"
  - "Startup wiring in __main__._run_gui — db_connect hoisted; theme runs before MainWindow construction"
  - "THEME-01 requirement registered in REQUIREMENTS.md (Features + Traceability)"
  - "Wave 0 RED + GREEN test contract — 16 new tests in tests/test_theme.py"

affects:
  - "Plan 66-02 (theme picker dialog) — consumes THEME_PRESETS + DISPLAY_NAMES + DISPLAY_ORDER + apply_theme_palette"
  - "Plan 66-03 (custom theme editor) — consumes EDITABLE_ROLES + build_palette_from_dict"
  - "Plan 66-04 (hamburger menu wiring) — consumes apply_theme_palette for live preview"

# Tech tracking
tech-stack:
  added: []  # No new runtime dependencies (per CONTEXT.md D-24)
  patterns:
    - "QPalette-only theme application (no parallel QSS-on-disk file analogous to paths.accent_css_path())"
    - "Lazy import inside apply_theme_palette to avoid circular __main__ ↔ theme dependency"
    - "JSON load + try/except + isinstance(dict) defense-in-depth for tampered theme_custom"
    - "db_connect hoist in _run_gui — single repo instance reused for theme + MainWindow"

key-files:
  created:
    - "musicstreamer/theme.py — palette construction + apply helpers (231 LOC; mirrors accent_utils.py shape)"
  modified:
    - "musicstreamer/__main__.py — _run_gui hoist + theme.apply_theme_palette call insertion"
    - "tests/test_theme.py — augmented with 16 new Phase 66 tests (Phase 46 UI-token tests preserved at top of file)"
    - ".planning/REQUIREMENTS.md — THEME-01 added to Features + Traceability; coverage counts updated"

key-decisions:
  - "Append Phase 66 tests to existing tests/test_theme.py rather than overwrite — preserves 5 Phase 46 UI-token regression tests at the top of the file"
  - "GBS.FM hex preserved verbatim from CONTEXT.md D-05 (uppercase form) — comparison via dict equality against the locked dict, not normalized via .lower()"
  - "Vaporwave Link role uses #7b5fef (purple-blue) instead of cyan #5fefef per RESEARCH Q7 / A2 (cyan on near-white base = 1.4:1 contrast, fails WCAG)"
  - "_apply_windows_palette function definition preserved verbatim; now invoked only from inside theme.apply_theme_palette on the Windows system-default branch"
  - "db_connect hoist trade-off accepted: second-instance forwards now incur <5ms SQLite connect/close before exiting — clarity of single-source repo construction outweighs the tiny startup-path cost"

patterns-established:
  - "Theme module = pure helpers + one apply function (parallels accent_utils.py)"
  - "Locked-hex preservation: brand-sampled palettes preserve uppercase hex from source (vs Qt's lowercase .name() output) and compare via dict equality"
  - "Defense-in-depth chain at trust boundary: try/except JSONDecodeError → isinstance(dict) → _is_valid_hex per value → getattr(QPalette.ColorRole, name, None) for unknown role names"
  - "Lazy circular-import escape hatch: import inside function body (not module-level) for __main__-imports-theme-imports-__main__ chains"

requirements-completed:
  - "THEME-01"   # Note: requirement is REGISTERED in this plan; full requirement is satisfied across Plans 66-01..66-04. Plan 66-01 ships the foundation layer; Plans 02/03/04 ship the picker / editor / menu wire-up.

# Metrics
duration: ~7min
completed: 2026-05-09
---

# Phase 66 Plan 01: theme palette foundation Summary

**`musicstreamer.theme` module with 7 presets (system / vaporwave / overrun / gbs / gbs_after_dark / dark / light), startup wiring in `_run_gui`, and THEME-01 requirement registered.**

## Performance

- **Duration:** ~7 min (commit-span: 82db2de → 1dc4608)
- **Completed:** 2026-05-09
- **Tasks:** 4 / 4
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `musicstreamer/theme.py` shipped with 7 palette presets + 4 public symbols (`THEME_PRESETS`, `DISPLAY_NAMES`, `DISPLAY_ORDER`, `EDITABLE_ROLES`) + 2 functions (`build_palette_from_dict`, `apply_theme_palette`)
- GBS.FM brand palette locked verbatim from CONTEXT.md D-05 (uppercase hex preserved)
- Defense-in-depth on the `theme_custom` JSON trust boundary: try/except JSONDecodeError, isinstance dict guard, per-value `_is_valid_hex` check, `getattr(QPalette.ColorRole, name, None)` for unknown role names — all four guards covered by tests
- Startup wiring in `__main__._run_gui` hoisted `db_connect/db_init/Repo` so theme palette is in place BEFORE MainWindow construction, with the existing `accent_color` restore in `main_window.py:241-245` continuing to layer on top of the theme's Highlight baseline (Phase 59 invariant preserved)
- 16 new tests in `tests/test_theme.py` cover preset hex, palette construction, defense-in-depth, Linux 'system' no-op contract, theme + accent layering, persistence round-trip — all green
- `THEME-01` requirement registered in `.planning/REQUIREMENTS.md` (Features bullet + Traceability row + coverage counts updated)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED test stubs in tests/test_theme.py** — `82db2de` (test) — RED gate confirmed: `ModuleNotFoundError: No module named 'musicstreamer.theme'` during collection
2. **Task 2: Implement musicstreamer/theme.py palette core** — `fc9cbb0` (feat) — GREEN gate: 21/21 pass on test_theme.py (16 new + 5 preserved Phase 46 UI-token tests)
3. **Task 3: Wire apply_theme_palette into __main__._run_gui (startup ordering hoist)** — `5be4ff2` (feat) — AST parse OK; Phase 59 + 66 contract suites all green
4. **Task 4: Add THEME-01 to REQUIREMENTS.md (Features + Traceability)** — `1dc4608` (docs)

_Note: Task 1 = RED, Task 2 = GREEN under the plan-level TDD gate. No REFACTOR commit needed — the GREEN implementation matches the plan's specified shape directly._

## Files Created/Modified

- `musicstreamer/theme.py` (created, 231 LOC) — palette construction + apply helpers; mirrors `musicstreamer/accent_utils.py` shape
- `musicstreamer/__main__.py` (modified, +13/-6) — `_run_gui` hoist for `db_connect/db_init/Repo` and `theme.apply_theme_palette(app, repo)` call insertion; deletes the original 3-line win32 setStyle block (now invoked from inside theme module)
- `tests/test_theme.py` (modified, +255/-6) — appended 16 Phase 66 tests; preserved 5 existing Phase 46 UI-token tests at the top of the file
- `.planning/REQUIREMENTS.md` (modified, +6/-4) — THEME-01 Features bullet + Traceability row; coverage counts 18→19 total / 16→17 pending; footer date 2026-05-09
- `.planning/phases/66-…/deferred-items.md` (created) — pre-existing full-suite Qt teardown crash logged as out-of-scope

## Decisions Made

- **GBS.FM uppercase hex preserved verbatim** — `THEME_PRESETS["gbs"]` matches the CONTEXT.md D-05 dict literal byte-for-byte (uppercase). Test compares via dict equality, not via lowercased `.name()` output. This locks the brand-sampled values against drift.
- **Vaporwave Link role → `#7b5fef`** (purple-blue, not cyan `#5fefef`) per RESEARCH Q7/A2: cyan on near-white base hits 1.4:1 contrast (WCAG AA fail). Purple-blue keeps the vaporwave aesthetic while passing AA.
- **_apply_windows_palette preserved verbatim** in `__main__.py` lines 69-99; now reachable only via `theme.apply_theme_palette` lazy-import on `theme=='system'` + Windows. No callers in `_run_gui` body.
- **db_connect hoist accepted** despite the cost on second-instance forwards — see plan Task 3 `<rationale>` block. Trade-off: <5ms SQLite open on second-instance forward in exchange for single-source repo construction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] tests/test_theme.py already existed (Phase 46 UI-token tests)**
- **Found during:** Task 1 (file creation)
- **Issue:** Plan instructed "Create `tests/test_theme.py`" as the RED Wave 0 contract, but the file already existed at HEAD with 5 Phase 46 tests covering `musicstreamer.ui_qt._theme` (UI tokens — `ERROR_COLOR_HEX`, `STATION_ICON_SIZE`). Overwriting would have deleted those regression tests; the existing file path collides with the plan's intent because both phases want the file `test_theme.py`.
- **Fix:** Augmented the existing file by appending the 16 new Phase 66 tests below a divider comment, after the existing Phase 46 tests. Combined imports at the top of the file. The file now houses both sets of tests cleanly.
- **Files modified:** tests/test_theme.py
- **Verification:** `pytest tests/test_theme.py -x -q` → 21/21 pass (16 new Phase 66 + 5 preserved Phase 46)
- **Committed in:** 82db2de (Task 1 commit)

**2. [Rule 1 - Bug] Plan Task 2 docstring contained literal `theme.css` substring violating its own grep gate**
- **Found during:** Task 2 (verify gate)
- **Issue:** The plan's Task 2 `<action>` block specified a docstring that says "no parallel `theme.css` file" — but Task 2's Done criterion `grep -c 'theme.css' musicstreamer/theme.py` outputs `0` flags ANY occurrence of `theme.css` in the file, including in negative-phrasing comments. Initial implementation literally followed the spec docstring, then grep returned 1.
- **Fix:** Rephrased the docstring to "no parallel QSS-on-disk file analogous to paths.accent_css_path()" — preserves the meaning (no `paths.theme_css_path()` analog created) without the trigger substring.
- **Files modified:** musicstreamer/theme.py
- **Verification:** `grep -c 'theme.css' musicstreamer/theme.py` → 0
- **Committed in:** fc9cbb0 (Task 2 commit, applied before commit so single commit)

**3. [Rule 1 - Bug] Plan Task 4 grep gate `grep -c 'THEME-01' = 2` is incompatible with its own Edit D footer text**
- **Found during:** Task 4 (verify gate)
- **Issue:** The plan's Edit D specifies an EXACT footer string: `*Last updated: 2026-05-09 — THEME-01 (preset + custom color themes via hamburger menu; accent_color layering preserved) added for Phase 66.*`. That text contains the substring `THEME-01`. Adding it brings the file's `grep -c 'THEME-01'` count to 3 (Features bullet + Traceability row + footer mention), not 2 as the Done criterion expects.
- **Fix:** Followed the plan's exact Edit D text. The substantive contract (Features bullet + Traceability row + counts updated + footer date) is met. The grep gate is internally inconsistent in the plan — recording the deviation here.
- **Files modified:** .planning/REQUIREMENTS.md
- **Verification:** Features bullet present (line 42); Traceability row present (line 102); v2.1 requirements: 19 total; Pending: 17; footer dated 2026-05-09 with Phase 66 mention.
- **Committed in:** 1dc4608 (Task 4 commit)

---

**Total deviations:** 3 auto-fixed (3× Rule 1 bugs in plan as-written)
**Impact on plan:** All three deviations are tweaks to plan-internal-inconsistencies (file collision, docstring vs grep gate, footer text vs grep count). No architectural change; full substantive contract delivered. No scope creep.

## Issues Encountered

**Pre-existing full-suite Qt teardown crash** (out of scope): running `pytest tests/ -q` (full suite, no `-x`) triggers a fatal Qt-internal abort in C-stack teardown. Verified by `git stash --include-untracked` then re-running on the stashed (pre-Task-3) tree — same crash repros, so this is **not caused by Plan 66-01**. Logged in `.planning/phases/66-…/deferred-items.md` for a future test-infrastructure phase. Plan-defined targeted verification commands (`pytest tests/test_theme.py -x -q`, `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q`, `pytest tests/test_main_run_gui_ordering.py -q`) all pass cleanly.

## User Setup Required

None — no external service configuration required. The new SQLite settings keys (`theme`, `theme_custom`) are additive and have safe defaults (`'system'` and empty string). Existing accent_color users see identical app behavior on first launch (theme defaults to `system` → Linux: Qt default palette unchanged; Windows: existing `_apply_windows_palette` path unchanged via the system-on-Windows branch in `theme.apply_theme_palette`).

## Threat Compliance

All four threats from the plan's `<threat_model>` (T-66-01 through T-66-04) are mitigated:

| Threat | Component | Mitigation | Verified by |
|--------|-----------|------------|-------------|
| T-66-01 | `theme.apply_theme_palette` JSON load + `build_palette_from_dict` role lookup | try/except JSONDecodeError + isinstance(dict) + `_is_valid_hex` per value + `getattr(QPalette.ColorRole, name, None)` | `test_apply_theme_palette_corrupt_json_safe`, `test_apply_theme_palette_non_dict_json_safe`, `test_build_palette_from_dict_skips_malformed_hex`, `test_build_palette_from_dict_skips_unknown_role` |
| T-66-02 | startup DoS | All exceptions silently caught; falls back to default palette | `test_apply_theme_palette_corrupt_json_safe` |
| T-66-03 | unknown theme name | `THEME_PRESETS.get(name, {})` returns empty dict → default palette | `test_apply_theme_palette_unknown_theme_safe` |
| T-66-04 | hex-into-QSS interpolation | NEVER interpolates hex into QSS (theme module has 0 `setStyleSheet` calls) | grep gate: `grep -v '^#' musicstreamer/theme.py \| grep -c 'setStyleSheet'` → 0 |

## Next Phase Readiness

- **Plan 66-02 (theme picker dialog)** can begin: `THEME_PRESETS`, `DISPLAY_NAMES`, `DISPLAY_ORDER`, `apply_theme_palette` are all live and tested. Picker dialog will instantiate tile widgets per `DISPLAY_ORDER`, label them per `DISPLAY_NAMES`, and call `apply_theme_palette` on click for live preview.
- **Plan 66-03 (custom theme editor)** can begin: `EDITABLE_ROLES` (9-tuple) and `build_palette_from_dict` provide the editor's role list and palette construction primitive.
- **Plan 66-04 (hamburger menu wire-up)** can begin: `apply_theme_palette(app, repo)` is the entry point the menu's "Theme" action will invoke after the user picks a tile in the picker.
- **Phase 59 / ACCENT-02 layering invariant intact**: `tests/test_accent_color_dialog.py` and `tests/test_accent_provider.py` continue to pass; `test_theme_then_accent_layering` confirms theme baseline survives accent override.

## Self-Check: PASSED

Verified at completion:
- ✓ `tests/test_theme.py` exists and `pytest tests/test_theme.py -x -q` reports 21 passed (16 Phase 66 + 5 Phase 46)
- ✓ `musicstreamer/theme.py` exists, 231 LOC (>= plan's `min_lines: 80`)
- ✓ `musicstreamer/__main__.py` AST parses OK; `theme.apply_theme_palette` called once in `_run_gui`; `app.setStyle("Fusion")` removed from `_run_gui` body
- ✓ `.planning/REQUIREMENTS.md` Features bullet + Traceability row + coverage counts present
- ✓ Commits found in git log: 82db2de, fc9cbb0, 5be4ff2, 1dc4608

## TDD Gate Compliance

This plan does NOT have plan-level `type: tdd` (PLAN frontmatter line 4 reads `type: execute`); per-task TDD gates handled inline. Task 1 = RED (test commit `82db2de`), Task 2 = GREEN (feat commit `fc9cbb0`) — gate sequence honored at the per-task level even though the plan-level gate isn't set. No REFACTOR commit needed — implementation matched plan-specified shape directly.

---
*Phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste, Plan 01*
*Completed: 2026-05-09*
