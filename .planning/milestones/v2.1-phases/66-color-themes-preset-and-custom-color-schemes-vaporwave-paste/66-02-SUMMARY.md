---
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
plan: 02

subsystem: ui

tags:
  - pyside6
  - qpalette
  - theme
  - picker
  - dialog
  - tile-grid

# Dependency graph
requires:
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 01
    provides: "musicstreamer.theme module (THEME_PRESETS, DISPLAY_NAMES, DISPLAY_ORDER, build_palette_from_dict, apply_theme_palette)"
  - phase: 59-visual-accent-color-picker
    provides: "AccentColorDialog idiom (modal QDialog, snapshot/restore, bound-method connects); apply_accent_palette helper"
  - phase: 40-accent-css-validator
    provides: "_is_valid_hex defense-in-depth"

provides:
  - "musicstreamer.ui_qt.theme_picker_dialog.ThemePickerDialog — modal QDialog with 4x2 tile grid"
  - "musicstreamer.ui_qt.theme_picker_dialog._ThemeTile — QPushButton subclass with custom paintEvent (4-color stripe + name label + active 3px border + checkmark)"
  - "musicstreamer.ui_qt.theme_editor_dialog.ThemeEditorDialog — STUB (one-line `class ThemeEditorDialog: pass`); Plan 03 Task 2 OVERWRITES with full implementation"
  - "13 RED-then-GREEN tests in tests/test_theme_picker_dialog.py covering tile-grid + click = live preview + Apply persist + Cancel restore + accent preservation + Customize button"
  - "Snapshot/restore + accent re-impose contract for tile-click live preview (mirrors Phase 59 AccentColorDialog)"

affects:
  - "Plan 66-03 (custom theme editor) — overwrites musicstreamer/ui_qt/theme_editor_dialog.py with full ThemeEditorDialog; relies on parent picker's _save_committed / _active_tile_id / _selected_theme_id contract documented here"
  - "Plan 66-04 (hamburger menu wire-up) — main_window.py adds 'Theme' action which constructs ThemePickerDialog(self._repo, self).exec()"

# Tech tracking
tech-stack:
  added: []  # No new runtime dependencies
  patterns:
    - "Custom-paint QPushButton tile (Approach A from RESEARCH Q8): paintEvent draws 4-color stripe + name label + active checkmark over base button bg"
    - "functools.partial held as a tile attribute (tile._click_handler) to keep a strong reference (QA-05 — no self-capturing lambdas)"
    - "Lazy import of ThemeEditorDialog inside _on_customize to escape Plan 02/03 cross-plan dependency cycle"
    - "closeEvent override that calls reject() — robust WM-close contract regardless of dialog visible state"

key-files:
  created:
    - "musicstreamer/ui_qt/theme_picker_dialog.py — ThemePickerDialog + _ThemeTile (319 LOC)"
    - "musicstreamer/ui_qt/theme_editor_dialog.py — STUB (one-line class; Plan 03 OVERWRITES) (8 LOC)"
    - "tests/test_theme_picker_dialog.py — 13 picker tests (202 LOC)"
  modified: []

key-decisions:
  - "closeEvent override added to ThemePickerDialog — Qt's QDialog.closeEvent only calls reject() when isVisible() is True; the override makes the WM-close contract robust for tests that close an unshown dialog (test_wm_close_behaves_like_cancel) AND matches user-perceived 'X = Cancel' regardless of whether the dialog has been shown yet"
  - "Stub theme_editor_dialog.py created in this plan (Plan 02) so the lazy import in _on_customize succeeds at runtime; Plan 03 Task 2 will OVERWRITE the stub with the real implementation. This avoids a hard cross-plan ordering constraint where Plan 02 cannot land before Plan 03"
  - "QA-05 partial-binding pattern: each tile gets a per-instance `_click_handler = functools.partial(self._on_tile_clicked, theme_id)` stored as a tile attribute to prevent GC. Alternative (clicked → self.sender()._theme_id) was rejected for clarity"

patterns-established:
  - "Tile widget shape: QPushButton subclass + custom paintEvent (4-color stripe at top + name label below) — reusable for any future preset-grid pickers"
  - "Empty-state hint inside the tile body (italic 'Click Customize…' label, no stripe) for disabled-but-discoverable Custom slot"
  - "Modal-stack save-suppression flag: child dialog's _on_save sets parent._save_committed = True so parent's reject() short-circuits snapshot restore — Phase 66 specific but the pattern generalizes to any nested-modal save+cancel scenario"

requirements-completed: []  # THEME-01 was REGISTERED in Plan 01; full satisfaction is across Plans 01-04

# Metrics
duration: ~3min
completed: 2026-05-09
---

# Phase 66 Plan 02: theme picker dialog Summary

**ThemePickerDialog ships as a modal QDialog with a 4x2 tile grid (8 tiles in DISPLAY_ORDER), tile-click live preview, Apply-persist, Cancel-restore-snapshot, and a Customize... button that lazy-imports the (stubbed) Plan 03 editor.**

## Performance

- **Duration:** ~3 min (commit-span: d3dd9c4 → b61ce11)
- **Completed:** 2026-05-09
- **Tasks:** 3 / 3 (Task 3 = UAT checkpoint, auto-approved under --chain)
- **Files created:** 3 (theme_picker_dialog.py, theme_editor_dialog.py stub, tests/test_theme_picker_dialog.py)
- **Files modified:** 0
- **Tests added:** 13

## Accomplishments

- `musicstreamer/ui_qt/theme_picker_dialog.py` shipped (319 LOC): ThemePickerDialog modal QDialog wrapping a 4-column-by-2-row QGridLayout of `_ThemeTile` widgets, each tile rendering a 4-swatch stripe (Window/Base/Text/Highlight-or-fallback) above the theme display name; active tile gets a 3px Highlight border + SP_DialogApplyButton checkmark; disabled Custom tile gets an italic "Click Customize…" hint label inside the tile body
- Tile click = live preview: `_on_tile_clicked` sets the QApplication palette and re-imposes `apply_accent_palette` so the user's accent_color override stays in effect on top of the theme baseline (Phase 59 D-02 layering — T-66-07 mitigated)
- Apply persists `theme = self._selected_theme_id` and accepts; Cancel restores the snapshot palette + styleSheet UNLESS `_save_committed` is True (Pitfall 1 — editor saved during picker session)
- Custom tile is `setEnabled(False)` when `theme_custom` is missing/empty/corrupt-JSON/non-dict-JSON (T-66-06); JSON parse wrapped in `try/except json.JSONDecodeError` + `isinstance(dict)` check (T-66-05). Defense-in-depth: `build_palette_from_dict` from Plan 01 already applies `_is_valid_hex` per value
- Customize... button lazy-imports `ThemeEditorDialog` from `musicstreamer.ui_qt.theme_editor_dialog` and constructs with `source_preset = self._selected_theme_id` (D-18); after editor closes, picker calls `_refresh_custom_tile_enabled()` and `_refresh_active_tile()` to pick up any new Custom palette state
- `closeEvent` overridden to call `reject()` — makes the WM-close contract robust for tests AND for the case where the dialog is shown then dismissed via the WM X button before any palette mutation
- Stub `musicstreamer/ui_qt/theme_editor_dialog.py` created (one-line `class ThemeEditorDialog: pass`) so the lazy import succeeds at runtime; Plan 03 Task 2 will OVERWRITE this file with the full editor implementation
- 13/13 picker tests pass (`pytest tests/test_theme_picker_dialog.py -x -q`); Phase 59 + Plan 01 regression suites green (48/48: 21 theme + 13 accent_color_dialog + 14 accent_provider)
- All UI-SPEC §"Audit Hooks" grep gates pass: `setContentsMargins(8, 8, 8, 8) = 1`, `setFixedSize(120, 100) = 1`, `setWindowTitle("Theme") = 1`, `setDefault(True) = 1`, `connect(lambda) = 0` (QA-05), `apply_accent_palette = 2`, `_save_committed = 4`, `keyPressEvent = 0`, `theme.css = 0`

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED test stubs in tests/test_theme_picker_dialog.py** — `d3dd9c4` (test) — RED gate confirmed: `ModuleNotFoundError: No module named 'musicstreamer.ui_qt.theme_picker_dialog'` during collection
2. **Task 2: Implement ThemePickerDialog + editor stub** — `b61ce11` (feat) — GREEN gate: 13/13 picker tests pass; Phase 59 + Plan 01 regression suite green; all audit grep gates satisfied
3. **Task 3 (CHECKPOINT): UAT — visually verify the Theme picker** — auto-approved under `--auto/--chain` (see "UAT Checkpoint" section below)

_Plan-level TDD gate: Task 1 = RED (test commit `d3dd9c4`), Task 2 = GREEN (feat commit `b61ce11`). No REFACTOR commit needed — implementation matched plan-specified shape directly._

## Files Created/Modified

- `musicstreamer/ui_qt/theme_picker_dialog.py` (created, 319 LOC) — ThemePickerDialog (QDialog) + _ThemeTile (QPushButton with custom paintEvent)
- `musicstreamer/ui_qt/theme_editor_dialog.py` (created, 8 LOC) — STUB; Plan 03 Task 2 OVERWRITES with full editor implementation
- `tests/test_theme_picker_dialog.py` (created, 202 LOC) — 13 picker tests covering tile-grid + click = live preview + Apply persist + Cancel restore + accent preservation + Customize button

## Decisions Made

- **`closeEvent` override added** — Qt's `QDialog.closeEvent` only calls `reject()` when `isVisible()` is True; tests close an unshown dialog so the override makes the WM-close contract robust regardless of visible state. The grep-gated ban on `keyPressEvent` is preserved (Esc still routes through Qt default RejectRole) — `closeEvent` is a different method and not banned by UI-SPEC §A11y.
- **Stub theme_editor_dialog.py created in this plan** — the plan explicitly specifies the stub contents (one-line `class ThemeEditorDialog: pass`) so the lazy import in `_on_customize` succeeds at runtime. Plan 03 Task 2 OVERWRITES this stub. This decouples Plan 02/03 ordering — Plan 02 ships standalone and Plan 03's overwrite is what reaches users.
- **functools.partial as the tile-click binding** — each tile gets `tile._click_handler = functools.partial(self._on_tile_clicked, theme_id)` stored as an attribute so the partial keeps a strong reference (Qt does not auto-hold). This satisfies QA-05 (no self-capturing lambdas) AND keeps the dispatch explicit (each tile has its own bound theme_id; no `self.sender()._theme_id` reflection).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `dlg.close()` does not auto-route through `reject()` for unshown dialogs**

- **Found during:** Task 2 verify (`pytest tests/test_theme_picker_dialog.py -x -q`)
- **Issue:** `test_wm_close_behaves_like_cancel` calls `dlg.close()` on a `qtbot.addWidget(dlg)`-managed dialog that has not been `.show()`-ed. Qt's `QDialog.closeEvent(event)` source code only calls `self.reject()` when `isVisible()` is True; on an unshown dialog `close()` returns True but neither `closeEvent` nor `reject` fire, so the snapshot restore never runs and the test failed (`AssertionError: '#0a0408' != '#efe5ff'`).
- **Fix:** Added a `closeEvent(self, event)` override on `ThemePickerDialog` that calls `self.reject()` then `event.accept()`. This makes the WM-close contract robust regardless of visible state. The override does not touch the Esc key contract — Esc still routes through Qt's default RejectRole binding (the `keyPressEvent = 0` grep gate is preserved at 0).
- **Files modified:** `musicstreamer/ui_qt/theme_picker_dialog.py`
- **Verification:** `pytest tests/test_theme_picker_dialog.py -x -q` → 13/13 pass; `grep -c 'keyPressEvent' musicstreamer/ui_qt/theme_picker_dialog.py` → 0 (UI-SPEC §A11y ban preserved)
- **Committed in:** b61ce11 (Task 2 commit, applied before commit so single feat commit)

---

**Total deviations:** 1 auto-fixed (1× Rule 1 bug — Qt API behavior the plan as-written did not anticipate)
**Impact on plan:** Cosmetic — adds a small (~6 LOC) `closeEvent` method to satisfy the plan's existing `test_wm_close_behaves_like_cancel` assertion. No architectural change; full substantive contract delivered.

## UAT Checkpoint (Task 3 — auto-approved under `--chain`)

**Auto-approved under --auto/--chain — visual verification deferred to user post-merge.**

The plan's Task 3 is a `checkpoint:human-verify` UAT for visual verification of the dialog in a live Qt session on Linux Wayland (DPR=1.0). Under `--auto/--chain` the orchestrator auto-approves human-verify checkpoints — this section documents what the user should verify manually post-merge:

1. **Tile grid layout:** 4 columns × 2 rows = 8 tiles
2. **Tile order (left→right, top→bottom):** System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light, Custom
3. **Active state:** "System default" tile shows 3px Highlight border + checkmark in top-right (default theme since no setting saved)
4. **Custom tile:** disabled, italic "Click Customize…" label inside the tile body, no 4-color stripe (theme_custom unset)
5. **Tile stripes:** each enabled tile shows 4 horizontal swatches in the upper region (Window / Base / Text / Highlight-or-fallback)
6. **Window title:** "Theme"
7. **Button row:** Customize… (left-aligned), Apply (right, bold/default), Cancel (right)
8. **Apply button has a focus ring / bold border by default** (Qt's setDefault(True) styling)
9. **Click Vaporwave:** dialog itself retints to lavender background + deep purple text (live preview applied to QApplication); Vaporwave tile gains active 3px border + checkmark; System default loses active styling
10. **Click Overrun:** dark near-black retint with hot magenta highlight
11. **Cancel/X:** dialog closes; main app palette is restored to the pre-open snapshot
12. **With accent_color = #e62d42 + click Vaporwave:** Highlight role stays #e62d42 (red accent), NOT #ff77ff (vaporwave's pink baseline) — proves the layered Highlight contract
13. **With theme_custom = '{"Window":"#abcdef","Base":"#fedcba","Text":"#000000"}':** Custom tile is enabled, shows a stripe with light blue/peach swatches; clicking it retints the dialog

**Snippet for ad-hoc UAT (Linux Wayland DPR=1.0, parented to dialog itself; no MainWindow needed):**

```bash
cd /home/kcreasey/OneDrive/Projects/MusicStreamer
python -c "
import sqlite3, sys
from PySide6.QtWidgets import QApplication
from musicstreamer.repo import Repo, db_init
from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog
app = QApplication(sys.argv)
con = sqlite3.connect(':memory:'); con.row_factory = sqlite3.Row; db_init(con)
repo = Repo(con)
dlg = ThemePickerDialog(repo)
dlg.show()
app.exec()
"
```

The picker is parented to itself (no MainWindow needed) so this snippet is sufficient. Plan 04 will wire the actual hamburger-menu entry point.

The underlying contract is locked by the 13/13 automated tests in `tests/test_theme_picker_dialog.py` (palette construction + tile click = live preview + Cancel restore + Apply persist + accent preservation + Customize button → editor recorder). The UAT only adds the human-eye Wayland DPR=1.0 rendering check.

## Threat Compliance

All four threats from the plan's `<threat_model>` (T-66-05 through T-66-08) are mitigated:

| Threat | Component | Mitigation | Verified by |
|--------|-----------|------------|-------------|
| T-66-05 | `_on_tile_clicked` Custom branch JSON load + `_refresh_custom_tile_enabled` JSON parse + `_ThemeTile._stripe_colors` Custom branch | Three independent JSON-parse sites all wrapped in `try/except json.JSONDecodeError` + `isinstance(role_hex, dict)` check; `build_palette_from_dict` applies `_is_valid_hex` per value (Plan 01); corrupt JSON → empty dict → default palette (no exception, no flash) | `test_corrupt_theme_custom_disables_tile`, `test_populated_custom_tile_enabled` |
| T-66-06 | Empty/corrupt theme_custom on dialog open → user clicks disabled Custom tile | `setEnabled(False)` set in `_refresh_custom_tile_enabled`; Qt ignores QPushButton click on disabled widgets; NO `mousePressEvent` override anywhere in `_ThemeTile` (verified by grep gate); tooltip steers user to Customize… button | `test_empty_custom_tile_disabled`, `test_corrupt_theme_custom_disables_tile` |
| T-66-07 | accent_color preservation across theme switch | `_on_tile_clicked` only READS accent_color (never writes); `apply_accent_palette` re-imposed after every tile click so Highlight stays user's accent on top of theme baseline (Phase 59 D-02) | `test_tile_click_preserves_accent_setting`, `test_tile_click_reapplies_accent_override` |
| T-66-08 | snapshot-restore semantics in conjunction with editor save | `_save_committed` flag flipped by editor's `_on_save` (Plan 03 contract); `reject()` short-circuits restore when flag is True; this prevents picker Cancel from undoing a valid Save (Pitfall 1) | Test for this branch lives in Plan 03 (`test_parent_save_flag_set`); the flag itself is initialized in `__init__` and consulted in `reject()` (verified by `_save_committed` grep gate = 4 occurrences in picker module) |

## Issues Encountered

None beyond the single Rule-1 deviation documented above.

The pre-existing full-suite Qt teardown crash (logged in deferred-items.md by Plan 01) was not exercised — Plan 02's targeted verification commands (`pytest tests/test_theme_picker_dialog.py -x -q`, `pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q`) all pass cleanly.

## User Setup Required

None — no external service configuration required. The picker is constructed standalone in the worktree (no menu wiring yet — Plan 04 owns that). To preview the dialog:

```bash
cd /home/kcreasey/OneDrive/Projects/MusicStreamer
python -c "
import sqlite3, sys
from PySide6.QtWidgets import QApplication
from musicstreamer.repo import Repo, db_init
from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog
app = QApplication(sys.argv)
con = sqlite3.connect(':memory:'); con.row_factory = sqlite3.Row; db_init(con)
repo = Repo(con)
dlg = ThemePickerDialog(repo)
dlg.show()
app.exec()
"
```

## Next Phase Readiness

- **Plan 66-03 (custom theme editor)** can begin: the stub `musicstreamer/ui_qt/theme_editor_dialog.py` exists with `class ThemeEditorDialog: pass`; Plan 03 Task 2 will OVERWRITE the file with the full implementation. The picker's `_on_customize` already constructs `ThemeEditorDialog(self._repo, source_preset=self._selected_theme_id, parent=self)` and calls `.exec()` — Plan 03 needs only to honor that constructor signature and (per the locked contract) set `parent._save_committed = True` + `parent._active_tile_id = "custom"` + `parent._selected_theme_id = "custom"` from the editor's `_on_save`.
- **Plan 66-04 (hamburger menu wire-up)** can begin: `ThemePickerDialog(repo, parent).exec()` is the single-line entry point the menu's "Theme" action will invoke. Place it immediately above the existing "Accent Color" action at `main_window.py:188` per CONTEXT.md D-15.
- **Phase 59 / ACCENT-02 layering invariant intact**: tests/test_accent_color_dialog.py (13 tests) and tests/test_accent_provider.py (14 tests) still pass; tile click preserves accent_color setting AND re-imposes apply_accent_palette to maintain the Highlight override (T-66-07).

## Self-Check: PASSED

Verified at completion:
- ✓ `tests/test_theme_picker_dialog.py` exists; `pytest tests/test_theme_picker_dialog.py -x -q` reports 13 passed
- ✓ `musicstreamer/ui_qt/theme_picker_dialog.py` exists, 319 LOC (>= plan's `min_lines: 150`)
- ✓ `musicstreamer/ui_qt/theme_editor_dialog.py` exists with the one-line stub; `python -c "from musicstreamer.ui_qt.theme_editor_dialog import ThemeEditorDialog"` exits 0
- ✓ `pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q` reports 48 passed (Phase 59 + Plan 01 regression intact)
- ✓ Audit grep gates all satisfied: setContentsMargins(8, 8, 8, 8)=1, setFixedSize(120, 100)=1, setDefault(True)=1, setWindowTitle("Theme")=1, addButton("Apply"=1, addButton("Cancel"=1, addButton("Customize…"=1, _save_committed=4 (>=2), connect(lambda)=0, apply_accent_palette=2 (>=1), keyPressEvent=0, theme.css=0
- ✓ Commits found in git log: d3dd9c4 (test), b61ce11 (feat)

## TDD Gate Compliance

Task 1 = RED (test commit `d3dd9c4`), Task 2 = GREEN (feat commit `b61ce11`). The PLAN frontmatter has `type: execute` (not plan-level `type: tdd`); per-task TDD gates are honored at the per-task level via `tdd="true"` on Tasks 1 and 2. No REFACTOR commit needed — implementation matched plan-specified shape directly with one Rule-1 auto-fix (`closeEvent` override) applied before the GREEN commit.

---
*Phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste, Plan 02*
*Completed: 2026-05-09*
