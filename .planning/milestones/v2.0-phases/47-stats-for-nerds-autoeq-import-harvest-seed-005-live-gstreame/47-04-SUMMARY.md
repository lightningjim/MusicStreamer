---
phase: 47-stream-bitrate-quality-ordering
plan: "04"
subsystem: ui_qt/edit_station_dialog
tags: [gap-closure, uat-gap-1, qt-delegate, bitrate, regression-test]
gap_closure: true
requires: []
provides:
  - "_BitrateDelegate.setModelData — deterministic empty-text persistence to Qt.EditRole"
  - "test_bitrate_delegate_persists_empty_string_on_commit — full delegate-cycle regression"
affects:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_edit_station_dialog.py
tech_stack:
  added: []
  patterns:
    - "QStyledItemDelegate.setModelData override that writes editor.text() to Qt.EditRole"
key_files:
  created: []
  modified:
    - path: musicstreamer/ui_qt/edit_station_dialog.py
      change: "Added setModelData override on _BitrateDelegate (13 lines)"
    - path: tests/test_edit_station_dialog.py
      change: "Appended test_bitrate_delegate_persists_empty_string_on_commit (39 lines)"
decisions:
  - "Explicit model.setData(index, editor.text(), Qt.EditRole) instead of relying on default USER-property write — makes empty-string persistence Qt-version independent"
  - "Test committed as GREEN rather than RED — the default delegate path already handles empty string correctly on Qt 6.9.2 Linux, so the test cannot be made to fail by the plan-specified edit cycle in this environment. Override still added as defensive codification per plan intent."
metrics:
  duration_seconds: 98
  tasks_completed: 2
  files_modified: 2
  completed: 2026-04-18
commits:
  - hash: 2dae666
    type: test
    message: "test(47-04): add delegate-path regression for _BitrateDelegate empty-cell commit"
  - hash: 1c6e133
    type: fix
    message: "fix(47-04): _BitrateDelegate.setModelData persists empty editor text"
---

# Phase 47 Plan 04: Stream Bitrate Quality Ordering (Gap Closure 1) Summary

Adds an explicit `_BitrateDelegate.setModelData` override and a delegate-path regression test to close UAT gap 1 (clearing a Bitrate cell reverted to the prior value on Enter/Tab commit).

## What Shipped

1. **`_BitrateDelegate.setModelData` override** in `musicstreamer/ui_qt/edit_station_dialog.py` (lines 170-181). Unconditionally writes `editor.text()` (including `""`) to `Qt.EditRole` via `model.setData(...)`. This makes empty-string persistence deterministic across Qt versions/platforms rather than relying on the QLineEdit USER-property default path.
2. **New regression test** `test_bitrate_delegate_persists_empty_string_on_commit` in `tests/test_edit_station_dialog.py`. Drives the full delegate edit cycle: `createEditor` → `editor.setText("")` → `setModelData` → assert item text is `""` → `_on_save()` → assert `update_stream(..., bitrate_kbps=0)`.

The save path (`int(bitrate_text or "0")` at line 717, D-14) was already in place from plan 47-03 and was not modified.

## Root Cause

The user's UAT gap 1 report: clearing a Bitrate cell and pressing Enter/Tab caused the cell to revert to its prior value instead of saving as 0.

The plan's diagnosis: `_BitrateDelegate` previously defined only `createEditor`. It inherited `QStyledItemDelegate.setModelData`, whose default path writes the editor's USER property (for QLineEdit, `text`). Empty-string behavior through that path is Qt platform/version dependent.

Fix: make the write explicit and unconditional to `Qt.EditRole`.

## Deviations from Plan

### [Rule 1 - Bug / RED-gate anomaly] Test passed against unmodified code

- **Found during:** Task 1 (RED phase)
- **Issue:** The delegate-path regression test, run against the ORIGINAL `_BitrateDelegate` (no `setModelData` override), **passed** — the core assertion `item(0, _COL_BITRATE).text() == ""` held, and the save path produced `bitrate_kbps=0`. The TDD RED gate was therefore not reproducible in this environment (Qt 6.9.2 / PySide6 / Linux).
- **Diagnosis:** The default `QStyledItemDelegate.setModelData` path on Qt 6.9.2 DOES persist an empty QLineEdit text via the USER property in this environment. The user's UAT-observed reversion is likely a Qt platform/version quirk (different OS, different Qt patch level, or caused by a focus-out / closeEditor interaction the isolated test doesn't model).
- **Decision:** Continued per plan. Added the explicit `setModelData` override as defensive codification — it guarantees the contract regardless of the underlying Qt default behavior, removing the environment-dependence from the UAT gap. Test committed as permanent coverage.
- **Files modified:** tests/test_edit_station_dialog.py, musicstreamer/ui_qt/edit_station_dialog.py
- **Commits:** 2dae666 (test), 1c6e133 (fix)

### [Rule 3 - Blocker triage, out-of-scope] Pre-existing QtTest environment failures

- **Found during:** Task 2 verification
- **Issue:** 4 tests in `test_edit_station_dialog.py` fail with `AttributeError: 'NoneType' object has no attribute 'QTest'`:
  - `test_add_tag_creates_chip`
  - `test_stream_table_populated_and_add`
  - `test_remove_stream_removes_row`
  - `test_move_up_down_reorder`
- **Verification:** Reproduced on the pre-plan baseline (git stash showed same 4 failures on HEAD prior to any 47-04 changes). Failures come from pytestqt calling `qt_api.QtTest.QTest.mouseClick` when `QtTest` is `None` in this environment — a missing Python binding, not a code defect.
- **Action:** Logged here; not fixed (out of scope — pre-existing environment issue unrelated to 47-04).
- **Impact on this plan:** None. All 4 bitrate tests (PB-16, PB-17, PB-17b, new regression) pass. `test_empty_bitrate_saves_as_zero` and `test_populated_bitrate_saves_as_int` — the pre-existing tests that MUST stay green per plan — both pass.

## Verification

| Check | Result |
|-------|--------|
| `grep "def setModelData" edit_station_dialog.py` | 1 match (line 170, inside `_BitrateDelegate`) |
| `grep "model.setData(index, editor.text(), Qt.EditRole)"` | 1 match |
| `pytest tests/test_edit_station_dialog.py -k "bitrate or delegate"` | 4 passed (PB-16, PB-17, PB-17b, new regression) |
| `pytest tests/test_edit_station_dialog.py` | 20 passed, 4 pre-existing env failures (QtTest binding missing) |
| `Qt` import present in file | Already imported at line 23 (`from PySide6.QtCore import Qt, ...`) |

## UAT Gap Closure

UAT gap 1 (severity: major) is closed at the code level: the `_BitrateDelegate` now has a deterministic, explicit setModelData path that cannot depend on the Qt default's empty-string handling. Manual smoke test on the app is recommended as a follow-up confirmation of the user-observed flow.

## Self-Check: PASSED

- [x] `musicstreamer/ui_qt/edit_station_dialog.py` exists and contains `setModelData` override inside `_BitrateDelegate`
- [x] `tests/test_edit_station_dialog.py` contains `test_bitrate_delegate_persists_empty_string_on_commit`
- [x] Commit `2dae666` exists (`git log --all | grep 2dae666`)
- [x] Commit `1c6e133` exists (`git log --all | grep 1c6e133`)
- [x] Bitrate regression tests (PB-16, PB-17, PB-17b) all still pass
- [x] New delegate-path test passes
