---
phase: 59-visual-accent-color-picker
plan: 01
subsystem: testing
tags: [pytest-qt, accent-color, dialog, tdd-red, wave-0, qcolordialog]

# Dependency graph
requires:
  - phase: 19-custom-accent-color
    provides: AccentColorDialog (Phase 19/40) — current implementation being replaced; FakeRepo + qtbot fixture pattern
  - phase: 40-modal-dialog-cleanup
    provides: snapshot-and-restore invariant (palette + QSS) preserved verbatim into Phase 59
provides:
  - "9-test TDD-RED contract for the new QColorDialog-based AccentColorDialog wrapper"
  - "T-59-A..T-59-H test coverage map per VALIDATION.md"
  - "Pitfall 3 corrupt-hex defensive test (no-black-flash guard)"
  - "Structural live-preview wiring lock (test_currentColorChanged_drives_live_preview_via_bound_method)"
  - "_accent_root fixture (paths._root_override monkeypatch under tmp_path)"
affects: [59-02-implementation, 59-03-uat]

# Tech tracking
tech-stack:
  added: []  # No new runtime/test deps — PySide6 6.11.0 + pytest-qt 4.5.0 already installed
  patterns:
    - "qtbot.waitSignal with check_params_cb for signal-payload assertion"
    - "process-static state neutralization (reset QColorDialog.setCustomColor slots before assertion to make tests order-independent)"
    - "_accent_root fixture mirrors _eq_root pattern (tests/test_equalizer_dialog.py:81-88) for paths._root_override redirection"

key-files:
  created: []
  modified:
    - "tests/test_accent_color_dialog.py — full rewrite, 107 → 218 LOC, 9 tests targeting self._inner / self._current_hex (Plan 02 contract)"

key-decisions:
  - "Test name convention: each test name matches VALIDATION.md T-59-A..T-59-H Automated Command suffix exactly so planner-injected pytest filters resolve without aliasing."
  - "Pitfall 1 mitigation in T-59-A: reset QColorDialog.setCustomColor(0..7, '#ffffff') BEFORE constructing the dialog so we are asserting that AccentColorDialog itself seeded the slots — not that an earlier test polluted process-static state."
  - "Pitfall 2 mitigation in T-59-B + structural lock test: pick a target color DIFFERENT from the initial blue (ACCENT_PRESETS[2] Green and #9141ac Purple respectively) so currentColorChanged fires — setCurrentColor to the same color is a no-op."
  - "Pitfall 3 defensive test (test_corrupt_saved_hex_falls_back_to_default): explicit assertion that QColor('not-a-hex') is NOT passed to setCurrentColor; defensive _is_valid_hex guard required in __init__."
  - "Pitfall 6 lock in T-59-H: assert dlg._current_hex == saved_hex AFTER construction, regardless of whether the wrapper wires currentColorChanged before or after setCurrentColor."

patterns-established:
  - "TDD-RED locked contract pattern: 9 tests target attributes (self._inner, self._current_hex) that DO NOT EXIST in the current implementation — Plan 02 reads the test file and writes whatever code makes them all pass, no interpretation of intent allowed."
  - "FakeRepo + qtbot.addWidget fixture preserved verbatim from the Phase 40 file (lines 19-43); only the test bodies change."
  - "_accent_root fixture: paths._root_override = str(tmp_path) — mirrors _eq_root in tests/test_equalizer_dialog.py:81-88 for hermetic file-system assertions in T-59-D."

requirements-completed: [ACCENT-02]  # Test contract for ACCENT-02; Plan 02 lands the implementation

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 59 Plan 01: Visual Accent Color Picker — Test Contract Rewrite Summary

**TDD-RED contract for the QColorDialog-based AccentColorDialog rewrite: 9 tests targeting self._inner + self._current_hex, all FAILING against today's implementation by design.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-04T00:48:00Z (approximate — Phase 59 execution kickoff)
- **Completed:** 2026-05-04T00:55:09Z
- **Tasks:** 1 / 1
- **Files modified:** 1 (`tests/test_accent_color_dialog.py`)

## Accomplishments

- Replaced 107-LOC Phase 40 test suite (referencing removed `_swatches` / `_hex_edit` attributes) with 218-LOC TDD-RED suite encoding the new wrapper contract.
- 8 of 9 tests map 1:1 to VALIDATION.md T-59-A..T-59-H Automated Command names — planner-injected pytest filters resolve without aliasing.
- 1 defensive test (`test_corrupt_saved_hex_falls_back_to_default`) locks the Pitfall 3 black-flash guard.
- 1 structural test (`test_currentColorChanged_drives_live_preview_via_bound_method`) locks the bound-method wiring against future refactor that drops the live-preview slot.
- D-19 verified: `tests/test_accent_provider.py` continues to pass unchanged (18/18 green).

## Task Commits

1. **Task 1: Rewrite tests/test_accent_color_dialog.py with 8 T-59 tests + corrupt-hex defensive test (TDD-RED)** — `fad8222` (test)

**Plan metadata:** _pending — final commit pending below_

## Files Created/Modified

- `tests/test_accent_color_dialog.py` — Rewrite. 9 test functions encoding the locked contract for the new `AccentColorDialog(QDialog)` wrapper that embeds `QColorDialog` as `self._inner`. Removed every reference to `_swatches` and `_hex_edit` per D-18. Added `_accent_root` fixture (monkeypatches `paths._root_override` under `tmp_path`) for the QSS-write assertion in T-59-D.

## Test Map (VALIDATION.md ↔ test names)

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-59-A | `test_dialog_seeds_custom_colors_from_presets` | `QColorDialog.customColor(idx).name() == ACCENT_PRESETS[idx].lower()` for `idx in 0..7` after `__init__`. Slots reset to `#ffffff` before construction to neutralize process-static pollution. |
| T-59-B (subsumes T-59-C) | `test_setting_color_emits_signal_and_applies_palette` | `qtbot.waitSignal(dialog._inner.currentColorChanged, timeout=1000, check_params_cb=...)` around `setCurrentColor(target)`; asserts `dialog._current_hex` and `qapp.palette().color(QPalette.ColorRole.Highlight).name()` both updated. |
| T-59-D | `test_apply_persists_to_repo_and_writes_qss` | `_on_apply()` writes `repo.set_setting('accent_color', '#9141ac')` AND `os.path.isfile(paths.accent_css_path())`; uses `_accent_root` fixture. |
| T-59-E | `test_cancel_restores_palette_and_does_not_save` | Snapshot original Highlight role BEFORE dialog open; `dlg.reject()` restores it AND `repo.get_setting('accent_color', 'UNSET') == 'UNSET'`. |
| T-59-F | `test_reset_clears_setting_and_keeps_dialog_open` | `dlg._on_reset()` writes `''` to repo, zeros `_current_hex`, AND `dlg.result() == 0` (dialog has not been accepted/rejected — stays "open"). |
| T-59-G | `test_window_close_behaves_like_cancel` | `dlg.close()` does NOT mutate the `'UNSET-MARKER'` sentinel — Cancel does NOT touch repo. |
| T-59-H | `test_load_saved_accent_pre_selects_in_picker` | `repo.set_setting('accent_color', ACCENT_PRESETS[4])` then construct dialog: `dlg._inner.currentColor().name() == ACCENT_PRESETS[4].lower()` AND `dlg._current_hex == ACCENT_PRESETS[4]`. |
| (defensive) | `test_corrupt_saved_hex_falls_back_to_default` | `repo.set_setting('accent_color', 'not-a-hex')` then construct dialog: `dlg._inner.currentColor().name() == ACCENT_COLOR_DEFAULT.lower()` AND `dlg._current_hex == ACCENT_COLOR_DEFAULT`. |
| (structural) | `test_currentColorChanged_drives_live_preview_via_bound_method` | `qtbot.waitSignal(dialog._inner.currentColorChanged, timeout=1000)` around `setCurrentColor(QColor("#9141ac"))`; asserts `dialog._current_hex == "#9141ac"`. Locks the bound-method wiring against future refactor. |

## TDD-RED Confirmation (pytest output, last 11 lines)

```
=========================== short test summary info ============================
FAILED tests/test_accent_color_dialog.py::test_dialog_seeds_custom_colors_from_presets
FAILED tests/test_accent_color_dialog.py::test_setting_color_emits_signal_and_applies_palette
FAILED tests/test_accent_color_dialog.py::test_apply_persists_to_repo_and_writes_qss
FAILED tests/test_accent_color_dialog.py::test_cancel_restores_palette_and_does_not_save
FAILED tests/test_accent_color_dialog.py::test_reset_clears_setting_and_keeps_dialog_open
FAILED tests/test_accent_color_dialog.py::test_window_close_behaves_like_cancel
FAILED tests/test_accent_color_dialog.py::test_load_saved_accent_pre_selects_in_picker
FAILED tests/test_accent_color_dialog.py::test_corrupt_saved_hex_falls_back_to_default
FAILED tests/test_accent_color_dialog.py::test_currentColorChanged_drives_live_preview_via_bound_method
========================= 9 failed, 1 warning in 0.25s =========================
```

All 9 tests fail with `AttributeError: 'AccentColorDialog' object has no attribute '_inner'` — exactly the locked TDD-RED state. Plan 02 will introduce `self._inner = QColorDialog(self)` in `__init__` and the cascade of attribute/method existence will turn these tests GREEN one by one as the implementation lands.

## D-19 Verification (`tests/test_accent_provider.py` untouched, still passes)

```
======================== 18 passed, 1 warning in 0.19s =========================
```

`tests/test_accent_provider.py` was not touched. 18/18 tests pass — confirms `accent_utils.py` (`_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette`) is unaffected. Plan 02 reuses these helpers as-is.

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `python3 -c "import ast; ast.parse(...)"` exits 0 | OK — file parses |
| `grep -v '^#' \| grep -cE '_swatches\|_hex_edit'` returns 0 | OK — no legacy refs (line-anchored grep returned 0) |
| `grep -cE '^def test_'` returns 9 | OK — 9 test functions at left margin |
| Each T-59-A..T-59-H name matches exactly | OK — all 8 names + 1 defensive + 1 structural verified individually |
| `grep -cE 'qtbot\.waitSignal\(dialog\._inner\.currentColorChanged'` returns ≥1 | OK — 1 hit (T-59-B uses `dialog._inner`; structural test also waitSignals on it but on a different fixture line) |
| `grep -cE 'paths\._root_override'` returns ≥1 | OK — 1 hit in `_accent_root` fixture |
| `grep -cE 'class FakeRepo'` returns 1 | OK — preserved verbatim |
| `pytest --collect-only -q \| grep -cE '^tests/test_accent_color_dialog\.py::test_'` returns 9 | OK — 9 tests collected |

## Decisions Made

- **Test name fidelity to VALIDATION.md:** every T-59 test name matches its row's "Automated Command" suffix string exactly. This is load-bearing — the planner's injected pytest filters resolve via exact match, not substring search.
- **Process-static state neutralization in T-59-A:** reset `QColorDialog.setCustomColor(idx, QColor("#ffffff"))` for `idx in 0..7` BEFORE constructing the dialog. This makes T-59-A order-independent — without it, a prior test that seeded slot 3 with green would leak into T-59-A and the assertion would still pass for the wrong reason. The neutralization captures Pitfall 1's intent (assert that this dialog seeds slots, not that some previous dialog did).
- **Pick `ACCENT_PRESETS[2]` (Green, `#3a944a`) and `#9141ac` (Purple) as targets for the two `qtbot.waitSignal` tests:** both are guaranteed different from the initial `ACCENT_COLOR_DEFAULT` blue, so the no-op-on-same-color short-circuit (Pitfall 2) does not suppress the emission.
- **Use `dlg.result() == 0` to verify "dialog stays open" in T-59-F:** `QDialog.result()` returns `0` (Rejected sentinel value) before either `accept()` or `reject()` is called. Asserting `result() == 0` directly probes that neither finisher fired during `_on_reset()`. The plan's suggested `dialog.isVisible() is False` from PATTERNS.md (line 387) was rejected — the dialog was never `show()`n in tests so `isVisible()` is always False, which makes that assertion a tautology rather than a contract test.
- **Use `dialog.close()` (not `_inner.close()`) in T-59-G:** for a modal `QDialog`, calling `close()` on the wrapper is the canonical Qt path that routes through `reject()`. Calling `close()` on the inner `QColorDialog` widget would be a different thing entirely (it would close the embedded widget, not the wrapper).

## Deviations from Plan

None — plan executed exactly as written. The plan called for "8 T-59-A..T-59-H tests + 1 defensive corrupt-hex test" in the action body but the acceptance criteria + the `<must_haves>` truths called for 9 test functions including the structural live-preview lock; both are accounted for in the rewrite. Test count: 9, exactly as the acceptance criteria require.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Self-Check: PASSED

- [x] `tests/test_accent_color_dialog.py` exists and parses (218 LOC)
- [x] Commit `fad8222` exists in `git log` (verified: `git rev-parse --short HEAD` → `fad8222`)
- [x] All 9 tests collect via pytest
- [x] All 9 tests FAIL at runtime (TDD-RED — Plan 02 turns GREEN)
- [x] `tests/test_accent_provider.py` still passes (18/18, D-19 invariant)
- [x] No `_swatches` / `_hex_edit` references in test file (D-18 cleanup verified via grep)

## Next Phase Readiness

- **Plan 02 contract is locked.** The next agent reads `tests/test_accent_color_dialog.py` and writes whatever code in `musicstreamer/ui_qt/accent_color_dialog.py` makes all 9 tests pass — no interpretation of intent allowed.
- **No blockers.** Wave 0 complete. The rewritten dialog must:
  - Construct `self._inner = QColorDialog(self)` with `NoButtons | DontUseNativeDialog` options
  - Seed `QColorDialog.setCustomColor(idx, QColor(ACCENT_PRESETS[idx]))` for `idx in 0..7` BEFORE inner construction
  - Wire `self._inner.currentColorChanged` to a bound `_on_color_changed(self, color)` slot that writes `self._current_hex = color.name()` AND calls `apply_accent_palette(QApplication.instance(), self._current_hex)`
  - `_is_valid_hex`-guard the saved hex from repo before passing to `setCurrentColor` (Pitfall 3 black-flash defense)
  - Set `self._current_hex = initial` in `__init__` regardless of wiring order (Pitfall 6 invariant)
  - `_on_apply` persists hex + writes QSS file via `paths.accent_css_path()` + calls `self.accept()`
  - `_on_reset` clears repo setting + restores snapshot + sets `_current_hex = ""` + dialog stays open
  - `reject()` restores snapshot palette + QSS

---
*Phase: 59-visual-accent-color-picker*
*Plan: 01*
*Completed: 2026-05-04*
