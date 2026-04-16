---
phase: 42-settings-export-import
fixed_at: 2026-04-16T00:00:00Z
review_path: .planning/phases/42-settings-export-import/42-REVIEW.md
ui_review_path: .planning/phases/42-settings-export-import/42-UI-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 42: Code + UI Review Fix Report

**Fixed at:** 2026-04-16
**Source reviews:** 42-REVIEW.md (Warnings) + 42-UI-REVIEW.md (Top 3)
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (3 code Warnings + 3 UI priority fixes)
- Fixed: 6
- Skipped: 0

## Fixed Issues — Code Review

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

## Fixed Issues — UI Review

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

## Skipped Issues

None — all 6 in-scope findings were fixed.

## Verification

- Tier 1 (re-read) completed for each edit.
- Tier 2 (Python syntax via `ast.parse`) passed for every modified `.py` file.
- Full phase-42 test suite: 23/23 passing (17 export + 6 dialog tests, including the new error-path test).
- Pre-existing env issue (`yt_dlp` missing) prevents running `test_main_window_integration.py`, but the failure chain is unrelated to the edited code — imports fail in `yt_import.py` before reaching `main_window.py`.

## Out of Scope (Info findings — not addressed this iteration)

- IN-01: `_on_import_preview_error` discards error detail (main_window.py:438-439)
- IN-03: `test_settings_import_dialog.py` does not exercise Import-button click / replace_all cancel flow
- IN-04: `_validate_zip_members` still uses substring `".." in fname` (could reject `foo..bar.jpg`) — partially touched by WR-02 (added `\\` rejection) but a proper `posixpath.normpath` normalization is a separate follow-up.
- IN-05: `_sanitize` can return `"."` or `".."` for pathological station names.

---

_Fixed: 2026-04-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
