---
phase: 75
plan: 07
subsystem: theme
tags: [theme, editor, tests, wave-3]
dependency_graph:
  requires:
    - "75-01: EDITABLE_ROLES extended to 11 (ToolTipBase, ToolTipText appended)"
    - "75-05: ROLE_LABELS extended with Toast background / Toast text; _on_role_color_changed flips theme_name to 'custom'"
  provides:
    - "11-row editor coverage with explicit ToolTipBase/ToolTipText presence assertions"
    - "ROLE_LABELS Toast-string lock test (UI-SPEC §Copywriting Contract)"
    - "Save round-trip lock for ToolTipBase user-edit → theme_custom JSON"
    - "Reset lock for both new keys reverting to UI-SPEC vaporwave LOCKED hex pair"
    - "Cancel snapshot-restore lock for ToolTipBase role in QApplication.palette()"
  affects: []
tech_stack:
  added: []
  patterns:
    - "Additive test extension reusing existing FakeRepo + stub_color_dialog fixtures (D-14 invariant)"
    - "Direct slot invocation (dlg._on_role_color_changed) for palette assertion in Cancel test — faster than qtbot.mouseClick + QColorDialog stub"
key_files:
  created: []
  modified:
    - tests/test_theme_editor_dialog.py
decisions:
  - "Imported ROLE_LABELS alongside the existing ThemeEditorDialog import (single import statement edit) — minimal-diff over a separate import line."
  - "Placed test_reset_restores_toast_rows_to_source_preset BEFORE test_reset_does_not_close_dialog (adjacent to test_reset_reverts_to_source_preset) to keep all Reset-flavor tests clustered."
  - "Placed test_save_persists_toast_keys_when_user_edits_them BEFORE test_save_sets_theme_to_custom (adjacent to test_save_persists_theme_custom_json) to keep all Save-flavor tests clustered."
  - "Placed test_cancel_restores_toast_roles_in_palette BEFORE test_cancel_does_not_persist_theme_custom (adjacent to test_cancel_restores_snapshot) to keep all Cancel-flavor tests clustered."
  - "Cancel test uses dlg._on_role_color_changed('ToolTipBase', '#000000') directly (no QColorDialog stub) per PLAN.md Task 2 (c) — bypasses the stubbed dialog for a more direct palette assertion."
metrics:
  duration_seconds: 720
  tasks_completed: 2
  files_modified: 1
  completed_date: 2026-05-15
---

# Phase 75 Plan 07: tests/test_theme_editor_dialog.py 11-row + Save/Reset/Cancel toast coverage Summary

Extended `tests/test_theme_editor_dialog.py` with the 5 locked assertions UI-SPEC §Test surface (lines 310-313, 315) requires for PLAN-01's 9 → 11 EDITABLE_ROLES growth and PLAN-05's ROLE_LABELS extension: retrofit the 9-row count test to 11 with explicit ToolTipBase + ToolTipText presence assertions; lock ROLE_LABELS to the UI-SPEC strings `"Toast background"` / `"Toast text"`; lock Save round-trip persistence of an edited ToolTipBase row to `theme_custom` JSON; lock Reset reverting both new rows to UI-SPEC vaporwave LOCKED hex (`#f9d6f0` / `#3a2845`); lock Cancel snapshot-restore of the ToolTipBase role in `QApplication.palette()`.

## Objective

Two minimal additive edits to `tests/test_theme_editor_dialog.py`:
1. Retrofit `test_editor_shows_9_color_rows` → `test_editor_shows_11_color_rows` with explicit ToolTipBase + ToolTipText presence assertions, AND add `test_role_labels_include_toast_pair` to lock the UI-SPEC §Copywriting Contract strings.
2. Add three new tests (`test_save_persists_toast_keys_when_user_edits_them`, `test_reset_restores_toast_rows_to_source_preset`, `test_cancel_restores_toast_roles_in_palette`) placed adjacent to their existing analogs, reusing the established `FakeRepo` / `repo` / `stub_color_dialog` fixtures verbatim.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Retrofit 9-row test → 11 rows; add ROLE_LABELS Toast-string assertion | `5bc8823` | tests/test_theme_editor_dialog.py |
| 2 | Add Save / Reset / Cancel coverage for ToolTipBase + ToolTipText keys | `02e8543` | tests/test_theme_editor_dialog.py |

## Implementation Details

### Task 1 — Retrofit 11-row count + ROLE_LABELS Toast-string lock

- Renamed `test_editor_shows_9_color_rows` → `test_editor_shows_11_color_rows`; updated docstring to `"""dlg._rows has exactly 11 keys matching EDITABLE_ROLES (Phase 75 D-05)."""`.
- Changed `assert len(dialog._rows) == 9` → `assert len(dialog._rows) == 11`.
- Preserved `assert set(dialog._rows.keys()) == set(EDITABLE_ROLES)` and `assert "Highlight" not in dialog._rows` verbatim.
- Added two new presence assertions: `assert "ToolTipBase" in dialog._rows` and `assert "ToolTipText" in dialog._rows`.
- Added new test `test_role_labels_include_toast_pair()` (no fixtures — pure module-level dict assertion): `assert ROLE_LABELS["ToolTipBase"] == "Toast background"`, `assert ROLE_LABELS["ToolTipText"] == "Toast text"`.
- Updated existing import at line 18 from `from musicstreamer.ui_qt.theme_editor_dialog import ThemeEditorDialog` to `from musicstreamer.ui_qt.theme_editor_dialog import ROLE_LABELS, ThemeEditorDialog` (single-line import addition, minimal-diff).

### Task 2 — Save / Reset / Cancel coverage for new keys

- **`test_save_persists_toast_keys_when_user_edits_them(qtbot, repo, qapp, stub_color_dialog)`** — placed adjacent to `test_save_persists_theme_custom_json`. Sets `stub_color_dialog["color"] = QColor("#abc123")`, constructs editor with `source_preset="vaporwave"`, clicks `dlg._rows["ToolTipBase"]._swatch_btn` (fires `_on_role_color_changed`), calls `dlg._on_save()`, then asserts `json.loads(repo.get_setting("theme_custom", ""))["ToolTipBase"] == "#abc123"`.

- **`test_reset_restores_toast_rows_to_source_preset(qtbot, repo, qapp, stub_color_dialog)`** — placed adjacent to `test_reset_reverts_to_source_preset`. Mutates BOTH new rows to `#000000` via `qtbot.mouseClick` on each swatch, then calls `dlg._on_reset()` and asserts `dlg._role_hex_dict["ToolTipBase"] == "#f9d6f0"` AND `dlg._role_hex_dict["ToolTipText"] == "#3a2845"` (UI-SPEC vaporwave LOCKED pair).

- **`test_cancel_restores_toast_roles_in_palette(qtbot, repo, qapp)`** — placed adjacent to `test_cancel_restores_snapshot`. Captures original ToolTipBase palette role via `qapp.palette().color(QPalette.ColorRole.ToolTipBase)` BEFORE constructing the editor, then calls `dlg._on_role_color_changed("ToolTipBase", "#000000")` directly (bypassing stubbed `QColorDialog` per PLAN.md Task 2 (c)), asserts the palette mutated, then calls `dlg.reject()` and asserts the original ToolTipBase color restored. Reuses the already-imported `QPalette` from line 14 — no new import required.

All three new tests reuse the existing `FakeRepo`, `repo`, and `stub_color_dialog` fixtures verbatim (no new fixtures introduced); no existing test was deleted.

## Verification Results

All acceptance criteria from PLAN.md tasks 1 and 2 pass:

- **Task 1 pytest:** `pytest tests/test_theme_editor_dialog.py::test_editor_shows_11_color_rows tests/test_theme_editor_dialog.py::test_role_labels_include_toast_pair -x -v` → 2/2 PASSED.
- **Task 1 grep gates:**
  - `grep -c 'test_editor_shows_9_color_rows' tests/test_theme_editor_dialog.py` → 0
  - `grep -c 'test_editor_shows_11_color_rows' tests/test_theme_editor_dialog.py` → 1
  - `grep -c '"Toast background"' tests/test_theme_editor_dialog.py` → 1
  - `grep -c '"Toast text"' tests/test_theme_editor_dialog.py` → 1
- **Task 2 pytest:** `pytest tests/test_theme_editor_dialog.py -x` → 18/18 PASSED.
- **Task 2 grep gates:**
  - `grep -c 'test_save_persists_toast_keys_when_user_edits_them' tests/test_theme_editor_dialog.py` → 1
  - `grep -c 'test_reset_restores_toast_rows_to_source_preset' tests/test_theme_editor_dialog.py` → 1
  - `grep -c 'test_cancel_restores_toast_roles_in_palette' tests/test_theme_editor_dialog.py` → 1
- **Plan-level smoke command:** `pytest tests/test_theme_editor_dialog.py -x` returns 0 (18 tests pass: 15 pre-existing/retrofitted + 3 new). The existing `test_save_persists_theme_custom_json` continues to pass (its `for role in EDITABLE_ROLES` loop auto-covers ToolTipBase + ToolTipText now that EDITABLE_ROLES has 11 entries — PLAN-01 defense-in-depth that Task 2 (a) adds to explicitly).

## Deviations from Plan

None — plan executed exactly as written. Tasks 1 and 2 each landed in a single atomic commit with no auto-fix activity, no checkpoint escalations, no authentication gates, and no architectural changes. The single import-statement consolidation in Task 1 (adding `ROLE_LABELS` to the existing `from musicstreamer.ui_qt.theme_editor_dialog import` line rather than a separate import line) is explicitly permitted by PLAN.md's "check existing imports first; if absent, add" instruction.

## Known Stubs

None. All new tests assert concrete behavior against locked values from the UI-SPEC and the PLAN.md task spec; no placeholder hex, no TODOs, no skipped tests, no `pytest.fail()` markers introduced.

## Threat Flags

None. The threat register entry `T-75-09` (Tampering — V5 N/A, Test files only) covers all edits: tests are read-only consumers of `EDITABLE_ROLES`, `ROLE_LABELS`, `ThemeEditorDialog`, and the JSON round-trip surface. No new trust-boundary surface introduced. The existing `_is_valid_hex` validator in `theme.py:179-186` (PLAN-01 threat-model coverage) continues to guard all hex flowing through `build_palette_from_dict` for both pre-existing and new ToolTipBase/ToolTipText keys.

## Self-Check: PASSED

- File `tests/test_theme_editor_dialog.py` modified at HEAD: FOUND
- Commit `5bc8823` (Task 1 — retrofit 9-row test → 11 rows + ROLE_LABELS toast lock): FOUND in `git log --oneline`
- Commit `02e8543` (Task 2 — Save/Reset/Cancel toast coverage): FOUND in `git log --oneline`
- Both commits live on branch `worktree-agent-a1069cc1b3114fd52` based on `bb74f7d` (Wave 2 merge).
- `test_editor_shows_11_color_rows` passes; `test_role_labels_include_toast_pair` passes.
- `test_save_persists_toast_keys_when_user_edits_them` passes (saved["ToolTipBase"] == "#abc123").
- `test_reset_restores_toast_rows_to_source_preset` passes (both new keys reverted to UI-SPEC vaporwave LOCKED #f9d6f0 / #3a2845).
- `test_cancel_restores_toast_roles_in_palette` passes (ToolTipBase palette role mutates to #000000 then restores to original via dlg.reject()).
- Full editor test suite: 18/18 PASSED.
- No pre-existing test deleted; one renamed (9_color → 11_color) per PLAN <verification>.
