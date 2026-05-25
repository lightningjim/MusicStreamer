---
phase: 75
plan: 08
subsystem: tests
tags: [tests, theme-picker, toast, integration, live-preview, palette-change, wave-3]
dependency_graph:
  requires:
    - "Plan 75-01 (Wave 1) — THEME_PRESETS['vaporwave']['ToolTipBase'] = '#f9d6f0', and apply_theme_palette sets QApplication.property('theme_name')"
    - "Plan 75-03 (Wave 2) — ToastOverlay._rebuild_stylesheet reads QApplication.property('theme_name') lazily + changeEvent(QEvent.PaletteChange) override"
    - "Plan 75-04 (Wave 2) — _on_tile_clicked mirrors setProperty('theme_name', theme_id) before any setPalette() call"
  provides:
    - "Property-mirror regression lock for both preset and system branches of _on_tile_clicked"
    - "End-to-end retint integration coverage — vaporwave tile click rebuilds a live ToastOverlay's QSS to contain rgba(249, 214, 240, 220)"
    - "Headless test recipe for live-preview retint: QApplication.sendPostedEvents() between setPalette() and reading widget.styleSheet()"
  affects:
    - tests/test_theme_picker_dialog.py
tech_stack:
  added: []
  patterns:
    - "QApplication.sendPostedEvents() flush between picker tile click and toast.styleSheet() read in headless Qt 6.11 (per 75-03-SUMMARY §Issues Encountered)"
    - "Inline parent-widget construction in picker test (parent_widget fixture lives only in test_toast_overlay.py, not conftest)"
    - "Defense-in-depth pre-state reset: qapp.setProperty('theme_name', 'system') + qapp.setPalette(QPalette()) at integration test start to force a known starting state independent of test ordering"
key_files:
  created:
    - .planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-08-SUMMARY.md
    - .planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/deferred-items.md
  modified:
    - tests/test_theme_picker_dialog.py
decisions:
  - "Used QApplication.sendPostedEvents() (no arguments) to flush all posted events including PaletteChange — Qt 6.11 delivers PaletteChange via the posted-events queue in headless mode, so reading toast.styleSheet() before flushing returns the stale stylesheet. This recipe is documented in 75-03-SUMMARY §Issues Encountered as the proven test-environment pattern."
  - "Added defense-in-depth pre-state reset to test_tile_click_retints_toast_overlay (`qapp.setProperty('theme_name', 'system'); qapp.setPalette(QPalette())`) per the plan's optional clause — explicit starting state means the test cannot pass by virtue of a prior test leaving vaporwave in place, and the assertion is genuinely about post-click retint behavior."
  - "Hoisted ToastOverlay, QWidget, and QApplication imports to module-level rather than function-scoping them — matches the prevailing test-file idiom (Qt and dialog imports at top) and avoids per-test import overhead. QApplication is needed for sendPostedEvents()."
  - "Did NOT touch the existing test_tile_click_applies_palette test — palette-mutation coverage (Window color check) is orthogonal to property-mirror coverage (theme_name string check) and both should remain locked independently."
metrics:
  duration_seconds: 540
  tasks_completed: 2
  files_modified: 1
  completed_date: 2026-05-15
---

# Phase 75 Plan 08: picker → toast end-to-end retint test coverage Summary

**Added three tests to `tests/test_theme_picker_dialog.py`: two property-mirror locks for `QApplication.property('theme_name')` on vaporwave and system tile clicks (PLAN-04 mechanism), plus one end-to-end integration test that constructs a live `ToastOverlay` under a parent `QWidget`, clicks the vaporwave tile, flushes Qt's posted-events queue via `QApplication.sendPostedEvents()`, and asserts the toast's stylesheet contains `rgba(249, 214, 240, 220)` — locking the full Wave-1 + Wave-2 + Wave-3 retint chain (PLAN-01 `ToolTipBase` preset hex → PLAN-04 picker `setProperty` mirror → PLAN-03 toast `changeEvent(PaletteChange)` + `_rebuild_stylesheet`).**

## Objective

Lock the PLAN-04 `setProperty` mirror at `theme_picker_dialog._on_tile_clicked:265` for both the preset and system branches, and lock the end-to-end live-preview retint flow so that any future change to PLAN-01 / PLAN-03 / PLAN-04 that breaks the chain (e.g., removing the `setProperty` call, reverting `changeEvent` to a no-op, dropping the toast `ToolTipBase` preset hex) is caught by the picker test suite without requiring manual-UAT verification.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add property-mirror tests for vaporwave + system tile clicks (`test_tile_click_sets_theme_name_property`, `test_tile_click_system_sets_theme_name_property`) | `c639600` | `tests/test_theme_picker_dialog.py` |
| 2 | Add end-to-end integration test for live-preview toast retint (`test_tile_click_retints_toast_overlay`) — hoisted `ToastOverlay` + `QWidget` + `QApplication` imports to module scope | `49d95f9` | `tests/test_theme_picker_dialog.py` |

## Implementation Details

### Task 1 — property-mirror tests

Inserted two new tests between the existing `test_tile_click_applies_palette` (lines 75-80) and `test_tile_click_preserves_accent_setting` (now line 99):

- `test_tile_click_sets_theme_name_property(qtbot, repo, qapp)` — constructs the picker, clicks the `vaporwave` tile, and asserts `qapp.property("theme_name") == "vaporwave"`. Locks the PLAN-04 preset-branch path.
- `test_tile_click_system_sets_theme_name_property(qtbot, repo, qapp)` — same shape, clicks the `system` tile, asserts `qapp.property("theme_name") == "system"`. Locks the PLAN-04 system-branch path (the Linux+system early return is reachable via this exact tile click).

Reused the existing `FakeRepo`, `repo`, `qapp`, and `qtbot` fixtures verbatim — no new fixtures. The existing `test_tile_click_applies_palette` was not touched: palette-mutation coverage (`#efe5ff` Window color check) is orthogonal to property-mirror coverage (`"vaporwave"` string check) and both should remain locked independently.

### Task 2 — end-to-end integration test

Added `test_tile_click_retints_toast_overlay(qtbot, repo, qapp)` adjacent to the Task 1 tests:

1. **Defense-in-depth pre-state reset:** `qapp.setProperty("theme_name", "system")` + `qapp.setPalette(QPalette())` force a known starting state so the assertion is genuinely about the post-click retint, not a side effect of prior-test ordering.
2. **Parent widget construction:** Inline parent following the `tests/test_toast_overlay.py:19-26` pattern (`QWidget()`, `resize(800, 600)`, `qtbot.addWidget`, `show()`, `qtbot.waitExposed`). Did NOT depend on the `parent_widget` fixture — that fixture lives in `test_toast_overlay.py` and is not shared via `conftest.py`.
3. **Toast construction under parent:** `toast = ToastOverlay(parent)`. The toast's `__init__` calls `_rebuild_stylesheet()` once, which sees `theme_name == "system"` and applies the IMMUTABLE legacy QSS.
4. **Picker tile click:** `qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)`. The picker slot sets `QApplication.property("theme_name") = "vaporwave"` (PLAN-04), then `app.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))` (PLAN-01's vaporwave preset contains `ToolTipBase = "#f9d6f0"`).
5. **Headless event flush:** `QApplication.sendPostedEvents()`. In headless Qt 6.11, `PaletteChange` is delivered via the posted-events queue (not synchronously inside `setPalette`), and the toast's `changeEvent(PaletteChange)` only fires after this flush. Once it fires, `_rebuild_stylesheet` re-reads `app.property("theme_name") == "vaporwave"` and interpolates the toast palette's `ToolTipBase` rgb into the QSS.
6. **Assertion:** `assert "rgba(249, 214, 240, 220)" in toast.styleSheet()`. The rgb tuple `(249, 214, 240)` is `#f9d6f0` in decimal; `220` is the literal alpha preserved per Phase 75 D-02.

### Imports hoisted

`tests/test_theme_picker_dialog.py` line 13 was changed from `from PySide6.QtWidgets import QDialog` to `from PySide6.QtWidgets import QApplication, QDialog, QWidget`, and a new line was added: `from musicstreamer.ui_qt.toast import ToastOverlay`. Module-level imports match the prevailing idiom of the test file (Qt + dialog imports at top) and avoid per-test import overhead.

## Verification

- `pytest tests/test_theme_picker_dialog.py -x` returns 0 — **16 passed** (13 pre-existing + 3 new).
- `pytest tests/test_toast_overlay.py tests/test_theme.py tests/test_theme_editor_dialog.py tests/test_theme_picker_dialog.py --deselect tests/test_theme.py::test_gbs_preset_locked_hex_match --deselect tests/test_theme_editor_dialog.py::test_editor_shows_9_color_rows` returns 0 — **63 passed, 2 deselected** (the 2 deselected tests are pre-existing Plan-01-caused failures in files outside this plan's `<files_modified>` scope — see "Deferred Issues" below).
- Source grep gates (Task 1):
  - `grep -c 'test_tile_click_sets_theme_name_property' tests/test_theme_picker_dialog.py` → **1**.
  - `grep -c 'test_tile_click_system_sets_theme_name_property' tests/test_theme_picker_dialog.py` → **1**.
- Source grep gates (Task 2):
  - `grep -c 'test_tile_click_retints_toast_overlay' tests/test_theme_picker_dialog.py` → **1**.
  - `grep -c 'rgba(249, 214, 240, 220)' tests/test_theme_picker_dialog.py` → **2** (assertion + inline comment), satisfying the "at least 1" criterion.

## Deviations from Plan

### Added — `QApplication.sendPostedEvents()` flush in Task 2

- **Rule 3 — Auto-fix blocking issue.**
- **Found during:** First run of `test_tile_click_retints_toast_overlay` after Task 2 initial draft. The toast's stylesheet still contained `rgba(40, 40, 40, 220)` (the legacy system QSS) after the vaporwave tile click, contradicting the assertion.
- **Root cause:** In headless Qt 6.11 with `pytest-qt`'s offscreen platform, `PaletteChange` is delivered to widgets via the **posted-events queue** rather than synchronously inside `QApplication.setPalette()`. The picker tile click writes `setProperty("theme_name", "vaporwave")` and calls `setPalette(vaporwave_palette)` — both correct — but the `PaletteChange` event for `ToastOverlay` sits in the queue until the next event loop iteration. Reading `toast.styleSheet()` immediately after the tile click returns the pre-flip stylesheet.
- **Fix:** Inserted `QApplication.sendPostedEvents()` between `qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)` and `qss = toast.styleSheet()`. This is the proven test-environment recipe documented in `75-03-SUMMARY.md` §"Issues Encountered" — under a real running event loop the propagation happens naturally without this call, so this is purely a test-harness affordance, not a production-code issue.
- **Note on plan text:** The plan's action block stated "Qt dispatches `PaletteChange` synchronously inside `setPalette()`" — that assertion is true on some platforms (notably with a running event loop) but is invalidated by Qt 6.11's headless event-queue path. The fix preserves the plan's intent (assert post-click QSS contains the vaporwave rgb tuple) while making the test deterministic across headless and real-GUI environments.
- **Files modified:** `tests/test_theme_picker_dialog.py` only (no production code changed).

No other deviations.

## Deferred Issues

Pre-existing failures in files outside this plan's `<files_modified>` scope, logged to `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/deferred-items.md`:

1. **`tests/test_theme.py::test_gbs_preset_locked_hex_match`** — Caused by Plan 75-01's Wave-1 addition of `ToolTipBase` + `ToolTipText` to the `gbs` preset (Phase 75 D-08). The `_GBS_LOCKED` constant in `tests/test_theme.py` was not updated to include the two new keys, so the verbatim-D-05-snapshot equality assertion fails. Fix path: update `_GBS_LOCKED` to include the new keys. Belongs in a plan that owns `tests/test_theme.py`.
2. **`tests/test_theme_editor_dialog.py::test_editor_shows_9_color_rows`** — Caused by Plan 75-01's Wave-1 expansion of `EDITABLE_ROLES` from 9 → 11 (Phase 75 D-05). The test asserts `len(dialog._rows) == 9` but `_rows` now has 11 entries. Fix path: rename the test to `test_editor_shows_11_color_rows` and update the assertion. Belongs in the plan that owns `tests/test_theme_editor_dialog.py`.

Both failures pre-exist Plan 75-08 (verified by re-running the failing tests at commit `c639600` before any Task 2 changes were applied) and are caused by Wave-1 PLAN-01's intentional dict / tuple expansions, not by any code introduced in Plan 75-08. Per `<scope_boundary>` deviation rule, they are out of scope for this plan.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None — the implementation is test-only and matches Plan 75-08's threat model disposition exactly (T-75-10 accepted: tests are read-only consumers of the picker, toast, and theme contracts; test isolation handled via `FakeRepo` dict per-instance).

## Files Modified

- `tests/test_theme_picker_dialog.py` — +49 net insertions, −1 deletion across two commits:
  - +1 module-level `from PySide6.QtWidgets import QApplication, QDialog, QWidget` (replaced the prior `from PySide6.QtWidgets import QDialog`, net +1 token but counted as -1/+1 in the diff stats since the import line was edited).
  - +1 module-level `from musicstreamer.ui_qt.toast import ToastOverlay`.
  - +12 `test_tile_click_sets_theme_name_property` + `test_tile_click_system_sets_theme_name_property` (Task 1).
  - +31 `test_tile_click_retints_toast_overlay` (Task 2).

## Files Created

- `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-08-SUMMARY.md` (this file).
- `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/deferred-items.md` (log of pre-existing failures outside this plan's scope; not committed because `.planning/` is gitignored and `-f` adds are only used for SUMMARY/PLAN/CONTEXT artifacts per phase convention).

## Self-Check: PASSED

- File `tests/test_theme_picker_dialog.py` exists and contains all three new tests (verified by `grep -c`).
- File `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-08-SUMMARY.md` exists (this file).
- Commit `c639600` exists: `test(75-08): add property-mirror tests for tile-click theme_name setProperty`.
- Commit `49d95f9` exists: `test(75-08): add end-to-end live-preview retint integration test`.
- `pytest tests/test_theme_picker_dialog.py -x` returns 0 (16 passed).
- Phase 75 4-file suite passes for all 63 tests outside the 2 pre-existing PLAN-01-caused deferred failures.
