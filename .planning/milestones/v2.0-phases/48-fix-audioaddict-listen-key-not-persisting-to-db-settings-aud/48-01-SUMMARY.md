---
phase: 48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud
plan: 01
subsystem: ui_qt/accounts_dialog
tags: [pyside6, accounts-dialog, audioaddict, settings-persistence, phase-48]
dependency_graph:
  requires:
    - musicstreamer/repo.py::get_setting
    - musicstreamer/repo.py::set_setting
  provides:
    - AccountsDialog AA view/clear group
    - AccountsDialog._is_aa_key_saved
    - AccountsDialog._on_aa_clear_clicked
    - AccountsDialog constructor now requires `repo` positional arg
  affects:
    - musicstreamer/ui_qt/main_window.py::_open_accounts_dialog
    - tests/test_accounts_dialog.py (8 existing + 3 new AA tests)
tech_stack:
  added: []
  patterns:
    - Password-masked credential display via QLineEdit.EchoMode.Password (planner's D-08 — lives in plan 48-02, not this plan)
    - AA view/clear pattern mirroring Twitch group (GroupBox + Label + single Button + QMessageBox.question Yes/No)
    - FakeRepo fixture duplicated in-file (project convention — no shared conftest)
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/accounts_dialog.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_accounts_dialog.py
decisions:
  - "AccountsDialog constructor takes `repo` as first positional arg (per D-04 + research Pitfall 2); all 8 existing test call sites retrofitted to pass FakeRepo"
  - "_update_status extended with AA branch appended to bottom — Twitch logic untouched to preserve existing behavior + tests"
  - "FakeRepo fixture duplicated at top of test_accounts_dialog.py rather than extracted to conftest — matches existing convention in tests/test_accent_color_dialog.py"
  - "Module docstring updated to describe AA surface; class docstring lists D-04/D-05/D-06/D-07 for future readers"
metrics:
  duration_min: 8
  tasks_completed: 2
  files_modified: 3
  completed_date: "2026-04-19"
---

# Phase 48 Plan 01: AccountsDialog AudioAddict View/Clear Group Summary

Adds an AudioAddict view-and-clear surface to `AccountsDialog` (alongside the existing Twitch group) and threads `repo` through its constructor so the dialog can read `audioaddict_listen_key` from the settings table and clear it with a Yes/No confirm.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add repo param, AA group, and clear flow to AccountsDialog; update main_window caller | 4262737 | musicstreamer/ui_qt/accounts_dialog.py, musicstreamer/ui_qt/main_window.py |
| 2 | Retrofit existing accounts tests + add 2 AA widget tests (3 added; spec said "2 new" but D-06 requires both Yes and No cases — added both + the status-reflection test per plan action step 3) | 4343cb8 | tests/test_accounts_dialog.py |

## What Changed

### `musicstreamer/ui_qt/accounts_dialog.py`
- `__init__(self, parent=...)` → `__init__(self, repo, parent=...)`; stores `self._repo = repo`.
- New `QGroupBox("AudioAddict")` inserted between Twitch group and Close button.
  - `self._aa_status_label` — `Qt.TextFormat.PlainText`, same font as Twitch status label.
  - `self._aa_clear_btn` — wired to `_on_aa_clear_clicked`.
- New method `_is_aa_key_saved() -> bool` — returns `bool(repo.get_setting("audioaddict_listen_key", ""))`.
- `_update_status()` extended with an AA branch at the bottom; existing Twitch branches untouched.
- New slot `_on_aa_clear_clicked()` — `QMessageBox.question` Yes/No (default **No**); Yes → `repo.set_setting("audioaddict_listen_key", "")` + `_update_status()`.
- Module + class docstrings updated to describe the Phase 48 AA surface.

### `musicstreamer/ui_qt/main_window.py`
- `_open_accounts_dialog` now calls `AccountsDialog(self._repo, parent=self)` instead of `AccountsDialog(parent=self)`. Docstring updated with the D-04 reference. No other lines touched; the `ImportDialog(...)` call at line 510 is left for plan 48-02 to own.

### `tests/test_accounts_dialog.py`
- Added `FakeRepo` class at top + `fake_repo` fixture (mirrors `tests/test_accent_color_dialog.py`).
- Retrofitted all 8 existing `AccountsDialog()` calls to pass `fake_repo`, adding the fixture to each test signature.
- New `TestAccountsDialogAudioAddict` class with 3 tests:
  - `test_aa_group_reflects_saved_status` — asserts label + button state at open with empty vs. saved repo (both scenarios in one test, per plan's D-05 spec).
  - `test_clear_aa_key_requires_confirm_yes` — monkeypatches `QMessageBox.question` → Yes; asserts setting cleared and status flipped.
  - `test_clear_aa_key_requires_confirm_no` — monkeypatches `QMessageBox.question` → No; asserts setting unchanged.

## Test Results

```
pytest tests/test_accounts_dialog.py -x
============================== 11 passed in 0.12s ==============================
```

All 11 tests green (8 retrofitted + 3 new).

Broader suite: `pytest --ignore` of pre-existing gi/ModuleNotFoundError tests yields 550 passed / 17 failed — all 17 failures are pre-existing (missing `gi` Python binding in this worktree environment). **Zero regressions introduced by this plan.**

## Success Criteria

1. ✓ AccountsDialog has an AudioAddict group with status label and clear button.
2. ✓ Clear button state reflects saved/unsaved correctly at open and after clear.
3. ✓ Clear requires Yes confirmation; No is a no-op.
4. ✓ AccountsDialog constructor requires `repo` positional argument (verified via `inspect.signature`).
5. ✓ main_window.py `_open_accounts_dialog` passes `self._repo`.
6. ✓ All 11 tests in `tests/test_accounts_dialog.py` pass (8 retrofitted + 3 new AA).

## Deviations from Plan

### Task 2 added 3 new tests, not 2

The plan's `<success_criteria>` said "2 new AA widget tests" but the `<action>` section listed 3 distinct test methods (`test_aa_group_reflects_saved_status`, `test_clear_aa_key_requires_confirm_yes`, `test_clear_aa_key_requires_confirm_no`). D-06 explicitly requires testing both Yes and No confirm paths, so 3 tests were added as specified in the action step — matching the `grep -c "AccountsDialog(fake_repo"` acceptance criterion of "at least 11". Not a true deviation; the success-criteria summary was inconsistent with the action section, and I followed the more specific action spec.

### Initial edits applied to wrong directory

First three Edit calls targeted `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py` (the main repo) rather than the worktree path. Discovered when signature inspection showed the old signature even after edits reported success. Re-applied all edits to the worktree path explicitly. **Rule 3 auto-fix** — blocking issue, recovered in place.

Impact: The main repo's `accounts_dialog.py` at `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py` has been modified outside the worktree. This is outside the scope of what this agent commits (committed artifacts live in the worktree branch). The orchestrator's worktree merge will resolve the worktree branch into main; the accidental edits to the main-repo file will appear as local uncommitted changes if the main repo's working tree still holds them at merge time. Flagging for orchestrator awareness — consider `git -C /home/kcreasey/OneDrive/Projects/MusicStreamer/ checkout -- musicstreamer/ui_qt/accounts_dialog.py` before merge if that working tree shows unexpected modifications.

## Threat Flags

None — all Phase 48 threat register items (T-48-01..T-48-04) are fully mitigated in the committed code:
- T-48-01 (Tampering / accidental clear): `QMessageBox.StandardButton.No` default ✓
- T-48-02 (Repudiation): accepted per project convention (single-user desktop)
- T-48-03 (Information Disclosure): label shows only "Saved"/"Not saved" ✓
- T-48-04 (Rich-text injection): `Qt.TextFormat.PlainText` on `_aa_status_label` ✓

No new surface introduced beyond the threat model.

## Known Stubs

None. The AA view/clear surface is fully wired — `_update_status` reads live settings at open and after clear; no placeholder values.

## Follow-Up

- Plan 48-02 will add AA listen-key editing in `ImportDialog` (prefill, save on successful fetch, masked-by-default echoMode, Show toggle).
- Phase 42 UAT test 7 (round-trip) becomes unblocked once 48-02 lands; no action from 48-01 directly.

## Self-Check: PASSED

- ✓ `musicstreamer/ui_qt/accounts_dialog.py` modified (commit 4262737)
- ✓ `musicstreamer/ui_qt/main_window.py` modified (commit 4262737)
- ✓ `tests/test_accounts_dialog.py` modified (commit 4343cb8)
- ✓ Commit 4262737 exists in git log
- ✓ Commit 4343cb8 exists in git log
- ✓ 11/11 tests pass in `tests/test_accounts_dialog.py`
