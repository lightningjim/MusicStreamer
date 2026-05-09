---
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
plan: 03

subsystem: ui

tags:
  - pyside6
  - qpalette
  - theme
  - editor
  - dialog
  - tdd

# Dependency graph
requires:
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 01
    provides: "EDITABLE_ROLES, THEME_PRESETS"
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 02
    provides: "ThemePickerDialog._save_committed/_active_tile_id/_selected_theme_id contract; theme_editor_dialog.py stub site OVERWRITTEN by this plan"
  - phase: 59-visual-accent-color-picker
    provides: "AccentColorDialog snapshot/restore idiom; apply_accent_palette + _is_valid_hex"

provides:
  - "musicstreamer.ui_qt.theme_editor_dialog.ThemeEditorDialog — modal QDialog with 9-row single-column custom palette editor"
  - "musicstreamer.ui_qt.theme_editor_dialog._ColorRow — clickable swatch button + monospace hex display widget"
  - "musicstreamer.ui_qt.theme_editor_dialog.ROLE_LABELS — 9-key dict mapping QPalette role names to UI-SPEC §Copywriting labels"
  - "Per-role live-preview + accent re-imposition + snapshot-restore-on-Cancel + Reset-stays-open + Save-persist+flip-parent-flags+accept contract"
  - "14 RED-then-GREEN tests in tests/test_theme_editor_dialog.py covering 9-row layout, per-role preview, source-preset prefill (5 cases), Reset preserving Highlight (D-08 invariant), Save persisting + setting parent flags, Cancel restoring snapshot"

affects:
  - "Plan 66-04 (hamburger menu wire-up) — does not directly consume editor; menu opens picker which lazy-imports editor on Customize…"
  - "musicstreamer/ui_qt/theme_picker_dialog.py — picker's _on_customize already constructs ThemeEditorDialog(self._repo, source_preset=..., parent=self) per Plan 02; this plan honors that constructor signature"

# Tech tracking
tech-stack:
  added: []  # No new runtime dependencies
  patterns:
    - "Plan-level skeleton+core split (Task 2a + 2b) for ~190 LOC class — RED collection succeeds at 2a, GREEN reached at 2b"
    - "Static-modal QColorDialog idiom (per row): QColorDialog.getColor(initial, parent, title, DontUseNativeDialog) — different from Phase 59's embedded QColorDialog"
    - "Cross-modal-stack parent flag mutation via _save_target_parent stash: editor's parent arg is stored separately from Qt's super().__init__() parent, allowing non-QWidget callers (test stubs) to receive flag mutations while still satisfying Qt's QWidget|None signature"
    - "D-08 Highlight invariant: _on_reset iterates only the 9 EDITABLE_ROLES, never touching QPalette.ColorRole.Highlight"
    - "Defense-in-depth chain at trust boundary: try/except JSONDecodeError → isinstance(dict) → per-value _is_valid_hex → getattr(QPalette.ColorRole, name, None) for unknown role names"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/theme_editor_dialog.py — OVERWROTE Plan 02's 8-LOC stub with 314-LOC full implementation (ROLE_LABELS + _ColorRow + ThemeEditorDialog)"
    - "tests/test_theme_editor_dialog.py — NEW (239 LOC) — 14 tests for editor surface (RED → GREEN cycle)"

key-decisions:
  - "Stash caller's parent in self._save_target_parent (separate from Qt's parent()) — required so the test_save_sets_parent_flag scenario works with a plain Python _FakePicker stub instead of a real QWidget. Qt's QDialog.__init__(parent) requires QWidget|None; passing a plain Python object raises TypeError. The cross-modal-stack flag mutation is the load-bearing contract (Pitfall 1) — it must work whether the caller is the real ThemePickerDialog (a QDialog) or a stub mimicking only the three flag attributes (T-66-11 mitigation)"
  - "Module file OVERWROTE Plan 02's stub (the 8-LOC `class ThemeEditorDialog: pass` placeholder) — Plan 02's lazy import in ThemePickerDialog._on_customize already references this module path; the stub allowed Plan 02 to ship in isolation and Plan 03 lands the real implementation that reaches users"
  - "Reset deliberately does NOT call set_setting on theme_custom — persistence is Save-only per UI-SPEC §State Machine E-Reset (D-14). Reset reverts the running palette + working dict + visible row state, but the saved theme_custom JSON remains unchanged until Save"

patterns-established:
  - "Skeleton-then-core 2-task split for medium-sized classes (Task 2a writes module top + helper classes; Task 2b appends the dialog class) — produces atomic intermediate commit (`2df1ed3`) that lets future bisects isolate \"helper changed\" vs \"dialog logic changed\""
  - "Cross-modal flag mutation via stashed-parent-arg: pattern usable for any nested-dialog Save+Cancel scenario where the inner dialog needs to communicate \"committed\" up to the outer dialog without coupling test stubs to the Qt class hierarchy"
  - "monkeypatch QColorDialog.getColor with a closure-controlled holder — lets pytest-qt drive QColorDialog flows without ever opening a modal in the test event loop. Pattern reusable for any future per-row picker-launching dialog (e.g. font picker, image picker)"

requirements-completed: []  # THEME-01 was REGISTERED in Plan 01; final satisfaction in Plan 04 (menu wire-up)

# Metrics
duration: ~6min
completed: 2026-05-09
---

# Phase 66 Plan 03: theme editor dialog Summary

**ThemeEditorDialog ships as a modal QDialog with 9 single-column color rows (one per editable QPalette role; Highlight excluded per D-08), per-row QColorDialog launchers, live-preview + accent re-imposition, snapshot-restore-on-Cancel, Reset-stays-open with source-preset reversion, and Save-persists-theme_custom-JSON + flips parent picker flags + accepts. Plan 02's 8-LOC stub at `musicstreamer/ui_qt/theme_editor_dialog.py` has been OVERWRITTEN with the 314-LOC full implementation.**

## Performance

- **Duration:** ~6 min (commit-span: ed7cfc4 → c016404)
- **Completed:** 2026-05-09
- **Tasks:** 3 / 3
- **Files created:** 1 (tests/test_theme_editor_dialog.py)
- **Files modified:** 1 (musicstreamer/ui_qt/theme_editor_dialog.py — overwrote stub)
- **Tests added:** 14

## Accomplishments

- `musicstreamer/ui_qt/theme_editor_dialog.py` shipped (314 LOC) — Plan 02's 8-LOC `class ThemeEditorDialog: pass` stub fully overwritten with the production implementation
- `_ColorRow(QWidget)` widget — label / clickable swatch button (48×24) / monospace hex display (FixedFont so digits align across rows). Click on swatch opens modal `QColorDialog.getColor(initial, self, "Choose {Role label} color", DontUseNativeDialog)`. Defense-in-depth `_is_valid_hex` at three write sites (`__init__`, `refresh`, `_on_swatch_clicked`)
- `ThemeEditorDialog(QDialog)` — `__init__(repo, source_preset, parent=None)` matches Plan 02 picker's constructor invocation; snapshots palette + styleSheet at open; constructs 9 rows in `EDITABLE_ROLES` order; button row Save (Accept, default) | Reset (ResetRole) | Cancel (RejectRole) per UI-SPEC §Editor button row
- `_compute_source_palette` handles all 5 source-preset cases per UI-SPEC §Pre-population: (A) `custom` with valid theme_custom JSON, (B) `custom` with corrupt/empty JSON → falls back to active app palette per role (T-66-10 — no black flash), (C) `system` → fresh `QPalette()` Qt-default, (D) named preset → `THEME_PRESETS` lookup, (E) unknown name → active app palette fallback
- `_on_role_color_changed` performs per-role live preview + re-imposes `apply_accent_palette` if `accent_color` is non-empty (Phase 59 D-02 layering — Pitfall 2)
- `_on_save` persists `theme_custom` JSON + sets `theme='custom'` + flips parent's `_save_committed`/`_active_tile_id`/`_selected_theme_id` (when parent has those attributes per `hasattr` guard) + `self.accept()`
- `_on_reset` reverts all 9 rows to source preset (single batched `setPalette` pass) + re-imposes accent override; **dialog stays open** (`result() == 0` — D-14). **D-08 invariant locked**: only iterates `EDITABLE_ROLES`, never touches `QPalette.ColorRole.Highlight`
- `reject()` restores the independent snapshot palette + styleSheet (RESEARCH Q10) — independent of picker's snapshot, so Cancel-from-editor reverts only what the editor previewed
- 14/14 editor tests pass (`pytest tests/test_theme_editor_dialog.py -x -q`)
- 61/61 regression suite green (`pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py tests/test_theme_picker_dialog.py -x -q` → 21 + 13 + 14 + 13 = 61)
- All UI-SPEC §"Audit Hooks" grep gates pass: `setContentsMargins(8, 8, 8, 8)=1`, `setWindowTitle("Customize Theme")=1`, `addButton("Save"/"Reset"/"Cancel")=1` each, `DontUseNativeDialog=3`, `setDefault(True)=1`, `connect(lambda)=0` (QA-05), `apply_accent_palette=3` (≥2), `parent._save_committed = True=1`, `class ThemeEditorDialog=1`, `getattr(QPalette.ColorRole=3` (≥2), `FixedFont|monospace=1`, `keyPressEvent=0`

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED test stubs in tests/test_theme_editor_dialog.py** — `ed7cfc4` (test) — RED gate confirmed: `TypeError: ThemeEditorDialog() takes no arguments` (Plan 02 stub class has no `__init__`)
2. **Task 2a: Skeleton — ROLE_LABELS + _ColorRow + module imports (no ThemeEditorDialog yet)** — `2df1ed3` (feat) — module imports + 9-key `ROLE_LABELS` + `_ColorRow(QWidget)` class + trailing `# Task 2b lands ThemeEditorDialog here.` placeholder. Tests still RED (ImportError on `ThemeEditorDialog` symbol — expected; Task 2b lands the class)
3. **Task 2b: Implement ThemeEditorDialog class — reach GREEN (14/14 tests pass)** — `c016404` (feat) — `ThemeEditorDialog(QDialog)` body appended; 14/14 GREEN; full regression suite green; all audit grep gates pass

_Plan-level TDD gate: Task 1 = RED (test commit `ed7cfc4`), Task 2b = GREEN (feat commit `c016404`). The PLAN frontmatter has `type: execute` (not plan-level `type: tdd`); per-task TDD gates are honored at the per-task level via `tdd="true"` on Tasks 1, 2a, 2b. No REFACTOR commit — implementation matched plan-specified shape after one Rule-1 auto-fix (parent-arg type handling) applied before the GREEN commit._

## Files Created/Modified

- `tests/test_theme_editor_dialog.py` (created, 239 LOC) — 14 tests covering editor surface; uses `_FakePicker` stub for parent-flag test (independent of Plan 02 import); `monkeypatch` of `QColorDialog.getColor` for hermetic per-row click flows
- `musicstreamer/ui_qt/theme_editor_dialog.py` (modified, +307/-7 = 314 LOC final) — OVERWROTE Plan 02's 8-LOC stub. New module: docstring + imports + `ROLE_LABELS` (9 entries, UI-SPEC §Copywriting locked) + `_ColorRow(QWidget)` + `ThemeEditorDialog(QDialog)` with `__init__`, `_compute_source_palette`, `_read_app_palette_role_dict`, `_read_app_palette_role`, `_role_hex_from_palette`, `_on_role_color_changed`, `_on_save`, `_on_reset`, `reject`

## Decisions Made

- **Caller's parent stashed separately from Qt's parent()** (`self._save_target_parent`) — Qt's `QDialog.__init__(parent)` rejects non-QWidget arguments with `TypeError`. The cross-modal-stack flag mutation contract (T-66-11) requires the editor to mutate `parent._save_committed` for any caller exposing that attribute, including the `_FakePicker` test stub which is a plain Python object. Stashing the original parent arg separately + only forwarding QWidget instances to `super().__init__()` resolves both constraints. The real `ThemePickerDialog` (a `QDialog` ⊂ `QWidget`) flows through both paths — stashed AND forwarded to Qt — so the picker's modal-stack semantics work as before.
- **Skeleton + core 2-task split (2a + 2b)** — produced an atomic intermediate commit (`2df1ed3`) at end of 2a where module imports + `ROLE_LABELS` + `_ColorRow` exist but `ThemeEditorDialog` is intentionally absent. Tests stay RED (ImportError) at that point, then turn GREEN at 2b's commit. Bisect-friendly: future regressions can isolate "helper changed" vs "dialog logic changed".
- **`reject()` restores independent snapshot, NOT picker's snapshot** — RESEARCH Q10 contract. The editor's snapshot is what `app.palette()` looked like *at editor open*, which may already include picker-driven live previews. This is correct: cancelling the editor reverts only the per-row edits the user just made, not the picker's prior tile selection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan-specified `super().__init__(parent)` rejects non-QWidget parents (test stub)**

- **Found during:** Task 2b verify (`pytest tests/test_theme_editor_dialog.py -x -q`)
- **Issue:** Plan-specified body for `ThemeEditorDialog.__init__` calls `super().__init__(parent)` directly. The plan also specifies `test_save_sets_parent_flag` constructs the editor with `parent = _FakePicker()` (a plain Python object, not a QWidget). Qt's `QDialog.__init__` rejects this with `TypeError: 'PySide6.QtWidgets.QDialog.__init__' called with wrong argument types: PySide6.QtWidgets.QDialog.__init__(_FakePicker) | Supported signatures: PySide6.QtWidgets.QDialog.__init__(parent: PySide6.QtWidgets.QWidget | None = None, ...)`. Test was failing at editor construction time before any `_on_save` logic could execute.
- **Fix:** Stash caller's parent in `self._save_target_parent` (used in `_on_save` for the `hasattr(parent, '_save_committed')` mutation contract); pass `parent if isinstance(parent, QWidget) else None` to `super().__init__()`. Both real `ThemePickerDialog` (QDialog ⊂ QWidget) and `_FakePicker` (plain Python) callers now construct cleanly. The `parent._save_committed = True` literal grep gate is preserved (`grep -c 'parent._save_committed = True' = 1`) because the local variable in `_on_save` is also named `parent`. The threat-model T-66-11 mitigation — `hasattr(parent, '_save_committed')` guard — is preserved verbatim.
- **Files modified:** `musicstreamer/ui_qt/theme_editor_dialog.py`
- **Verification:** `pytest tests/test_theme_editor_dialog.py::test_save_sets_parent_flag -x -q` → 1 passed; full editor suite 14/14 pass; all audit grep gates pass; regression suite (61 tests across theme + accent_color_dialog + accent_provider + theme_picker_dialog) still green
- **Committed in:** `c016404` (Task 2b commit, applied before commit so single feat commit)

---

**Total deviations:** 1 auto-fixed (1× Rule 1 bug — plan as-written had a Qt-API-vs-test-stub-type incompatibility)
**Impact on plan:** Cosmetic — adds 5 LOC to `__init__` (stash arg + isinstance check) and changes `self.parent()` → `self._save_target_parent` in `_on_save` (1 line). No architectural change; full substantive contract delivered. The `parent._save_committed = True` grep gate is preserved at count=1 because the local variable name in `_on_save` is still `parent`.

## Threat Compliance

All four threats from the plan's `<threat_model>` (T-66-09 through T-66-12) are mitigated:

| Threat | Component | Mitigation | Verified by |
|--------|-----------|------------|-------------|
| T-66-09 | `_ColorRow._on_swatch_clicked` QColor.name() output flowing into palette | `_is_valid_hex` guard at three write sites: `_ColorRow.__init__`, `_ColorRow.refresh`, `_ColorRow._on_swatch_clicked` (post-`QColorDialog.getColor`); also in `_on_role_color_changed` before `palette.setColor`; `getattr(QPalette.ColorRole, role_name, None)` for unknown role names | `test_color_change_applies_palette` exercises full flow; `_is_valid_hex` returns early for invalid hex (no test attempts to inject a bad hex through QColorDialog because Qt's QColor.name() always returns lowercase #rrggbb — defense-in-depth check is structural, not behavioral) |
| T-66-10 | `_compute_source_palette` source_preset='custom' branch with corrupt theme_custom JSON | `try/except json.JSONDecodeError` + `isinstance(parsed, dict)` check + per-value `_is_valid_hex` + fallback to active app palette role per `_read_app_palette_role` (NOT black `QColor()`) | `test_editor_prefills_from_custom_uses_saved_json` (happy path); the corrupt-JSON branch is exercised structurally by the same code path on case (B) — fallback-to-active-app-palette branch — and has no separate test (RESEARCH Pitfall 3 — no black flash invariant) |
| T-66-11 | Editor mutates parent picker's `_save_committed` + `_active_tile_id` + `_selected_theme_id` | `hasattr(parent, "_save_committed")` guard so non-picker parents (None or plain widget) don't AttributeError; `_save_target_parent` stash makes the mutation work for both real QDialog parents and test stubs | `test_save_sets_parent_flag` (uses `_FakePicker` stub) proves cross-mutation; `test_save_persists_theme_custom_json` (no parent) proves no-parent path also works |
| T-66-12 | Swatch button's `setStyleSheet(f"background-color: {hex}")` interpolation | `_current_hex` is validated by `_is_valid_hex` at every write site (`_ColorRow.__init__`, `refresh`, `_on_swatch_clicked` post-getColor); the QSS interpolation is therefore safe at consumption time — same defense-in-depth pattern as Phase 59's `build_accent_qss` (validated hex → interpolated into QSS). Note: this site is QSS interpolation of *validated* hex, not unvalidated foreign data | Structural: every assignment to `self._current_hex` is preceded by `_is_valid_hex(...)` short-circuit; verified by manual code review |

## Issues Encountered

None beyond the single Rule-1 deviation documented above.

The pre-existing full-suite Qt teardown crash (logged in `deferred-items.md` by Plan 01) was not exercised — Plan 03's targeted verification commands (`pytest tests/test_theme_editor_dialog.py -x -q`, `pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py tests/test_theme_picker_dialog.py -x -q`) all pass cleanly.

## User Setup Required

None — no external service configuration required. The editor is reachable only through the picker's "Customize…" button (Plan 02). Once Plan 04 wires the "Theme" hamburger-menu action, the user's flow will be:

1. Hamburger → Theme → Picker opens
2. Click any preset tile (or Custom if previously saved) → live preview applies
3. Click "Customize…" → editor opens, prefilled with selected preset's hex per role
4. Click any swatch → modal QColorDialog → pick → row's swatch + hex label update + palette previews live + accent re-imposed if user has one
5. Save → theme_custom JSON persisted, theme='custom', editor closes, picker shows Custom as active
6. (or) Reset → all 9 rows revert to source preset, dialog stays open
7. (or) Cancel → snapshot restored, dialog closes; picker still showing whatever was active before Customize

## Next Phase Readiness

- **Plan 66-04 (hamburger menu wire-up)** can begin: the editor is fully implemented and integrated with Plan 02's picker. Plan 04's only remaining task is wiring `act_theme.triggered.connect(self._open_theme_dialog)` in `main_window.py` (where `_open_theme_dialog` lazy-imports `ThemePickerDialog`).
- **Phase 59 / ACCENT-02 layering invariant intact**: `tests/test_accent_color_dialog.py` (13 tests) and `tests/test_accent_provider.py` (14 tests) still pass; per-row color change re-imposes `apply_accent_palette` to maintain Highlight override (T-66-09 + Pitfall 2).
- **D-08 invariant locked**: `test_reset_reverts_to_source_preset` proves that after `_on_reset()`, `qapp.palette().color(QPalette.ColorRole.Highlight)` is unchanged — Highlight is owned by the accent layering path, NOT the theme editor's reversion sweep. Future refactors that drop the `EDITABLE_ROLES`-only iteration in `_on_reset` will break this test.

## Self-Check: PASSED

Verified at completion:
- ✓ `tests/test_theme_editor_dialog.py` exists; `pytest tests/test_theme_editor_dialog.py -x -q` reports 14 passed
- ✓ `musicstreamer/ui_qt/theme_editor_dialog.py` exists, 314 LOC (≥ plan's `min_lines: 180`); `class ThemeEditorDialog` defined; `class _ColorRow` defined; `ROLE_LABELS` has 9 entries
- ✓ `pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py tests/test_theme_picker_dialog.py -x -q` reports 61 passed (Phase 59 + Plan 01 + Plan 02 regression intact)
- ✓ Audit grep gates all satisfied: setContentsMargins(8, 8, 8, 8)=1, setWindowTitle("Customize Theme")=1, addButton("Save"=1, addButton("Reset"=1, addButton("Cancel"=1, DontUseNativeDialog=3, setDefault(True)=1, connect(lambda)=0, apply_accent_palette=3, parent._save_committed = True=1, class ThemeEditorDialog=1, getattr(QPalette.ColorRole=3, FixedFont|monospace=1, keyPressEvent=0
- ✓ Commits found in git log: ed7cfc4 (test), 2df1ed3 (feat — skeleton), c016404 (feat — GREEN)

## TDD Gate Compliance

Task 1 = RED (test commit `ed7cfc4`), Task 2b = GREEN (feat commit `c016404`). Task 2a is an intermediate skeleton commit (`2df1ed3`) that does not change the RED/GREEN status — tests remain RED at end of 2a (ImportError on `ThemeEditorDialog` symbol because the class is intentionally not yet defined) and turn GREEN at 2b. The PLAN frontmatter has `type: execute` (not plan-level `type: tdd`); per-task TDD gates are honored at the per-task level via `tdd="true"` on Tasks 1, 2a, 2b. No REFACTOR commit — the GREEN implementation matched plan-specified shape after the Rule-1 auto-fix (parent-arg type handling).

---
*Phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste, Plan 03*
*Completed: 2026-05-09*
