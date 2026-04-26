---
phase: 42-settings-export-import
fixed_at: 2026-04-16T00:00:00Z
review_path: .planning/phases/42-settings-export-import/42-REVIEW.md
ui_review_path: .planning/phases/42-settings-export-import/42-UI-REVIEW.md
iteration: 2
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 42: Code + UI Review Fix Report

**Fixed at:** 2026-04-16
**Source reviews:** 42-REVIEW.md (Warnings + Info) + 42-UI-REVIEW.md (Top 3 + minor)
**Iteration:** 2 (consolidated report — includes iteration 1 fixes)

**Summary:**
- Findings in scope: 11 total across two iterations
  - Iteration 1: 3 code Warnings (WR-01..03) + 3 UI priority fixes (UI-01..03)
  - Iteration 2: 4 code Info findings (IN-01, IN-03, IN-04, IN-05) + 1 UI minor follow-up (error-row a11y / color token unification)
- Fixed: 11
- Skipped: 0
- IN-02: already addressed in iteration 1 as UI-03 (marked `already_fixed`, no new work)

## Fixed Issues — Iteration 1 (Code Warnings)

### WR-01: Filesystem logo writes are not rolled back on DB transaction failure

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** 7ab9796
**Applied fix:** Accumulate logo bytes in a `pending_logos` list inside the `with repo.con:` block (UPDATE on stations still happens inside the transaction, pointing at the eventual path). After the transaction commits successfully, iterate `pending_logos` and write the bytes to disk. If any SQL statement fails mid-loop, the list is discarded and no files are written — eliminating the orphaned-files failure mode.

### WR-02: `commit_import` does not re-validate ZIP members (TOCTOU)

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** 34f9825
**Applied fix:** Extracted the member-path validation into a module-level helper `_validate_zip_members(zf)` that rejects `/`-prefixed, `..`, or `\\` paths. Called from both `preview_import` (replacing the inline loop) and `commit_import` (new call immediately after `zipfile.ZipFile(preview.zip_path, ...)`). Backslash rejection added at the same time per reviewer suggestion.

### WR-03: Settings row uses `setting["key"]` / `setting["value"]` without `.get()`

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** a384d47
**Applied fix:** Replaced direct `setting["key"]` / `setting["value"]` access with `.get("key")` / `.get("value", "")`. Entries with a missing/empty key are skipped rather than aborting the whole import (consistent with how favorites and stations handle malformed rows).

## Fixed Issues — Iteration 1 (UI Review Top 3)

### UI-01: No progress feedback during export / import preview

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** d4ae77c
**Applied fix:** Added `_begin_busy` / `_end_busy` helpers that call `QApplication.setOverrideCursor(Qt.WaitCursor)` and disable both `_act_export` and `_act_import_settings` menu actions. `_begin_busy` fires in `_on_export_settings` and `_on_import_settings` after the user picks a path; `_end_busy` fires in every `_on_*_done` / `_on_*_error` / `_on_import_preview_ready` slot so the cursor and menu state are restored whether the worker succeeds, fails, or returns a preview. Added `QApplication` + `QCursor` to the imports.

### UI-02: Replace All modal deviates from UI-SPEC D-11 (inline-only pattern)

**Files modified:** `.planning/phases/42-settings-export-import/42-UI-SPEC.md`
**Commit:** 65eb29b
**Applied fix:** Per orchestrator guidance (recommend updating spec rather than removing the safety modal), rewrote the Destructive-Confirmation paragraph in 42-UI-SPEC.md to document the Replace All modal as an **approved deviation** from the otherwise-inline-only app convention. New text explains: (1) the inline warning label sets expectation, (2) the modal fires only on Replace All as an irreversible-action second-touch safeguard, (3) merge mode and other destructive actions elsewhere in the app remain inline-only.

### UI-03: `_ImportCommitWorker` error path marked `# pragma: no cover`

**Files modified:** `musicstreamer/ui_qt/settings_import_dialog.py`, `tests/test_settings_import_dialog.py`
**Commit:** ac60605
**Applied fix:** Removed the `# pragma: no cover` pragma on the worker's `except Exception`. Added `test_commit_error_shows_toast_and_reenables_button` which monkeypatches `musicstreamer.ui_qt.settings_import_dialog.commit_import` to raise `RuntimeError("disk full")`, invokes `_on_import` (merge mode: no modal), waits for the worker to finish via `QThread.wait`, and asserts both the "Import failed — disk full" toast appeared AND the Import button is re-enabled. Test passes cleanly alongside the 5 existing widget tests.

**Note:** This finding was re-filed as IN-02 in 42-REVIEW.md. It was already fixed in iteration 1; no duplicate work was performed in iteration 2.

## Fixed Issues — Iteration 2 (Code Info + UI Minor)

### IN-01: Error detail discarded in `_on_import_preview_error`

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** 4e86a48
**Applied fix:** Replaced the generic `"Invalid settings file"` toast with one that includes the underlying `ValueError` message truncated to 80 characters (with an ellipsis if longer). Users now see specific causes like `"Invalid settings file: Unsupported version: 99"` or `"Invalid settings file: Missing settings.json"` instead of a black-box failure.

### IN-02: `_on_commit_error` path uncovered / marked `# pragma: no cover`

**Status:** already_fixed (iteration 1, UI-03)
**Applied fix:** See UI-03 above. The pragma was removed and `test_commit_error_shows_toast_and_reenables_button` was added in commit ac60605. No additional work needed in iteration 2.

### IN-03: Import-click / replace_all confirm / import_complete emission not tested

**Files modified:** `tests/test_settings_import_dialog.py`
**Commit:** 0b23550
**Applied fix:** Added four new widget tests:
- `test_import_click_merge_emits_import_complete` — monkeypatches `commit_import`, `Repo`, `db_connect` to no-ops so the worker can run without a real DB; asserts the `import_complete` signal fires and the "Import complete" toast is emitted.
- `test_replace_all_confirm_cancel_does_not_start_worker` — monkeypatches `QMessageBox.warning` to return `Cancel` and a guard-raising `commit_import`; asserts `_commit_worker` is still `None` and the Import button remains enabled.
- `test_replace_all_confirm_yes_starts_worker` — same pattern, but `QMessageBox.warning` returns `Yes`; asserts the worker runs to completion and the success toast fires.
- `test_import_button_disabled_during_commit` — blocks a fake `commit_import` on a `threading.Event` so the test can observe the mid-flight state: asserts the Import button is disabled while the worker is running, then releases the event for clean teardown.

Phase 42 widget test count went from 6 to 10 (all passing).

### IN-04: Weak path-traversal check rejects legitimate names

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** ce0c689
**Applied fix:** Tightened `_validate_zip_members` to use `posixpath.normpath` for the `..` detection. Absolute paths (`/`-prefixed) and backslashes are still rejected unconditionally (backslash rejection was added in WR-02 iteration 1 and is retained). For `..`, the new logic rejects only when the normalized path IS `..`, starts with `../`, or normalizes to an absolute path. Names like `logos/foo..bar.jpg` now pass correctly; true traversal members (`../evil.txt`, `logos/../evil.txt`) are still rejected. Added `import posixpath` to the module.

### IN-05: `_sanitize` can return `"."` or `".."` for pathological station names

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** 503fb04
**Applied fix:** After the length truncation in `_sanitize`, added an explicit check that returns the `"station"` fallback when the result is empty, `"."`, or `".."`. This prevents an export from producing archive members like `logos/..jpg` that its own `_validate_zip_members` would later reject — i.e. eliminates the self-inconsistency where an exported archive could fail its own re-import validation. Existing tests (including `test_sanitize_filename`) all still pass.

### UI follow-up: Error-row color token + a11y warning icon

**Files modified:** `musicstreamer/ui_qt/settings_import_dialog.py`
**Commit:** a6ce100
**Applied fix:** Two related changes:
1. **Color token unification** — replaced `Qt.red` on error-row foreground with `QColor("#c0392b")` so all red-state UI in the dialog (Replace All warning label + error rows) uses the same palette entry. Defined a module-level `_ERROR_COLOR = QColor("#c0392b")` constant.
2. **A11y warning glyph** — added `item.setIcon(0, QStyle.SP_MessageBoxWarning)` on error rows so users with color-vision deficiency still get an unambiguous status indicator independent of the red foreground. Uses the system standard icon so it matches the native theme.

Added `QColor` and `QStyle` to the imports. All 27 phase-42 tests (10 dialog + 17 export) still pass.

## Skipped Issues

None — all 11 in-scope findings across both iterations were fixed.

## Verification

**Iteration 1:**
- Tier 1 (re-read) completed for each edit.
- Tier 2 (Python syntax via `ast.parse`) passed for every modified `.py` file.
- Full phase-42 test suite: 23/23 passing (17 export + 6 dialog tests, including the new error-path test).

**Iteration 2:**
- Tier 1 (re-read) completed for each edit.
- Tier 2 (Python syntax via `ast.parse`) passed for every modified `.py` file.
- Full phase-42 test suite: 27/27 passing (17 export + 10 dialog tests, including the 4 new IN-03 tests).
- Pre-existing env issue (`yt_dlp` missing) prevents running `test_main_window_integration.py`, but the failure chain is unrelated to the edited code — imports fail in `yt_import.py` before reaching `main_window.py`.

## Commit Trail

| Iteration | Finding | Commit  |
|-----------|---------|---------|
| 1 | WR-01   | 7ab9796 |
| 1 | WR-02   | 34f9825 |
| 1 | WR-03   | a384d47 |
| 1 | UI-01   | d4ae77c |
| 1 | UI-02   | 65eb29b |
| 1 | UI-03 / IN-02 | ac60605 |
| 2 | IN-01   | 4e86a48 |
| 2 | IN-04   | ce0c689 |
| 2 | IN-05   | 503fb04 |
| 2 | IN-03   | 0b23550 |
| 2 | UI minor (a11y + color token) | a6ce100 |

---

_Fixed: 2026-04-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2 (consolidated)_
