---
phase: 53-youtube-cookies-into-accounts-menu
plan: "02"
subsystem: main-window
tags: [pyside6, qt-mainwindow, hamburger-menu, ui-cleanup]
requirements: [BUG-04]

dependency_graph:
  requires:
    - 53-01 (AccountsDialog.toast_callback kwarg + YouTube QGroupBox)
  provides:
    - MainWindow hamburger menu trimmed to 9 entries (YouTube Cookies entry removed)
    - MainWindow._open_accounts_dialog forwards self.show_toast as toast_callback
    - _open_cookie_dialog slot removed
    - CookieImportDialog import removed from main_window.py
    - test_open_accounts_passes_toast verifying D-14 wiring
    - EXPECTED_ACTION_TEXTS updated 10 → 9 entries
  affects:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py

tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle (Wave 0 tests before implementation)
    - Namespace-patch idiom: monkeypatch.setattr("musicstreamer.ui_qt.main_window.AccountsDialog", ...) for testing bound imported symbols

key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py

decisions:
  - D-12: Three deletions applied — CookieImportDialog import (line 55), act_cookies menu action + connect (lines 148-149), _open_cookie_dialog method (lines 665-668)
  - D-13: EXPECTED_ACTION_TEXTS reduced from 10 to 9 entries; "YouTube Cookies" string absent; separator count 3 unchanged (Pitfall 3 verified)
  - D-14: _open_accounts_dialog now constructs AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)
  - D-10/D-11: cookie_import_dialog.py and test_cookie_import_dialog.py deliberately UNCHANGED (git diff confirmed empty)

metrics:
  duration_minutes: ~4
  completed: "2026-04-29"
  tasks_completed: 2
  files_modified: 2
---

# Phase 53 Plan 02: Trim MainWindow YouTube Cookies Surface Summary

Hamburger menu YouTube Cookies entry removed and _open_cookie_dialog slot deleted; _open_accounts_dialog updated to forward self.show_toast as toast_callback to AccountsDialog (D-14), closing the toast path for cookie-import success messages end-to-end from MainWindow through AccountsDialog to CookieImportDialog.

## What Was Built

### musicstreamer/ui_qt/main_window.py

Three deletions and one update:

- **Deleted import** (line 55): `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog` — no longer needed in main_window; AccountsDialog does its own in-slot import per Plan 01 D-12.
- **Deleted menu action** (lines 148-149): `act_cookies = self._menu.addAction("YouTube Cookies")` + `act_cookies.triggered.connect(self._open_cookie_dialog)`. Group 2 now has 3 entries (Accent Color, Accounts, Equalizer) with separator structure unchanged.
- **Deleted slot** (lines 665-668): `_open_cookie_dialog` method (4 lines). No callers remain.
- **Updated `_open_accounts_dialog`**: `AccountsDialog(self._repo, parent=self)` → `AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)`. Docstring extended with Phase 53 D-14 reference.

### tests/test_main_window_integration.py

Two changes:

- **`EXPECTED_ACTION_TEXTS` edited**: `"YouTube Cookies"` entry removed (length 10 → 9). The `"Accounts"` line now has a comment noting Phase 53 D-13 consolidation. `test_hamburger_menu_actions` assertion carries through automatically.
- **`test_open_accounts_passes_toast` added**: ~30-line test using the canonical namespace-patch idiom (`monkeypatch.setattr("musicstreamer.ui_qt.main_window.AccountsDialog", FakeAccountsDialog)`). Captures constructor kwargs and asserts `captured["toast_callback"] == window.show_toast`, `captured["parent"] is window`, and `captured["repo"] is window._repo`.

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| `tests/test_main_window_integration.py` (full) | 46 | all passed |
| `tests/test_accounts_dialog.py` | 37 | all passed |
| `tests/test_cookie_import_dialog.py` | 14 | all passed |
| Three-file cross-plan regression | 97 | all passed |
| Full suite (`pytest -q`) | 838 passed, 11 pre-existing failures | GREEN (11 failures pre-existing, unrelated to Phase 53) |

### Pre-existing Failures (Out of Scope)

Same 11 failures documented in Plan 01 SUMMARY: `test_media_keys_mpris2` (7), `test_media_keys_smtc` (1), `test_station_list_panel` (2), `test_twitch_auth` (1). All present before and after Plan 02 changes (verified with git stash).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Docstring CookieImportDialog ref] Removed CookieImportDialog name from _open_accounts_dialog docstring**
- **Found during:** Task 2 acceptance criteria check
- **Issue:** The plan's verbatim docstring included `(forwarded by AccountsDialog → CookieImportDialog)` which caused `grep -v '^#' main_window.py | grep -c "CookieImportDialog"` to return 1 instead of the required 0
- **Fix:** Shortened the docstring to `"so the YouTube cookie import flow can surface its success toast through the same overlay."` — same intent, no CookieImportDialog name
- **Files modified:** `musicstreamer/ui_qt/main_window.py`
- **Commit:** `004de5c`

**2. [Rule 2 - Comment quoting] Removed quoted YouTube Cookies from EXPECTED_ACTION_TEXTS comment**
- **Found during:** Task 1 acceptance criteria check
- **Issue:** The plan's verbatim comment `# Phase 53 D-13: "YouTube Cookies" entry removed` contained the grep target string `"YouTube Cookies"` inside a comment, causing `grep -c '"YouTube Cookies"' tests/test_main_window_integration.py` to return 1 instead of 0
- **Fix:** Removed quotes from the comment: `# Phase 53 D-13: YouTube Cookies entry removed; cookie management consolidated into Accounts dialog`
- **Files modified:** `tests/test_main_window_integration.py`
- **Commit:** `0d3f9e5`

## Invariant Verification

### D-10/D-11 Enforcement
`git diff HEAD~2 -- musicstreamer/ui_qt/cookie_import_dialog.py tests/test_cookie_import_dialog.py` → empty (no changes). Both files are untouched across Plan 02.

### Grep Gates (all pass)

| Gate | Expected | Actual |
|------|----------|--------|
| `grep -c "from musicstreamer.ui_qt.cookie_import_dialog" main_window.py` | 0 | 0 |
| `grep -v '^#' main_window.py \| grep -c "CookieImportDialog"` | 0 | 0 |
| `grep -c "act_cookies" main_window.py` | 0 | 0 |
| `grep -c '"YouTube Cookies"' main_window.py` | 0 | 0 |
| `grep -c "_open_cookie_dialog" main_window.py` | 0 | 0 |
| `grep -c "AccountsDialog(self._repo, toast_callback=self.show_toast" main_window.py` | 1 | 1 |
| `grep -c '"YouTube Cookies"' tests/test_main_window_integration.py` | 0 | 0 |

## Manual UAT Checklist (for `/gsd-verify-phase`)

1. Launch the app: `uv run python -m musicstreamer`
2. Open hamburger menu — confirm 9 entries (no "YouTube Cookies" entry); confirm 3 group separators
3. Click "Accounts" → confirm dialog opens with three groups in order: YouTube, Twitch, AudioAddict
4. (If cookies.txt is absent) confirm YouTube row reads "Not connected" + "Import YouTube Cookies..."
5. Click "Import YouTube Cookies..." → CookieImportDialog opens (3 tabs: File / Paste / Google login)
6. Choose Google login → complete flow → on success, toast "YouTube cookies imported." appears
7. AccountsDialog YouTube row flips to "Connected" + "Disconnect"
8. Click "Disconnect" → confirm dialog "Disconnect YouTube?" appears with Yes/No (default No)
9. Click Yes → cookies.txt deleted, row flips back to "Not connected" + "Import YouTube Cookies..."
10. Verify: visual layout has no group title overlap, no scrollbar required, all text legible

## BUG-04 Closure Status

| SC | Description | Status |
|----|-------------|--------|
| SC-1 | Hamburger menu has no standalone YouTube Cookies entry | CLOSED — `test_hamburger_menu_actions` GREEN, grep gate passes |
| SC-2 | YouTube cookie import reachable from Accounts with toast forwarded end-to-end | CLOSED — Plan 01 `test_import_launches_cookie_dialog` + Plan 02 `test_open_accounts_passes_toast` GREEN |
| SC-3 | Twitch + YouTube cookies coexist cleanly in Accounts | CLOSED — Plan 01 `test_group_order` GREEN; manual UAT visual check pending |

## Commits

| Hash | Message |
|------|---------|
| `0d3f9e5` | test(53-02): update EXPECTED_ACTION_TEXTS (9 entries) and add RED test_open_accounts_passes_toast |
| `004de5c` | feat(53-02): trim main_window.py — remove YouTube Cookies menu entry, slot, import; wire toast_callback |

## Self-Check: PASSED

- 53-02-SUMMARY.md: FOUND (this file)
- musicstreamer/ui_qt/main_window.py: FOUND
- tests/test_main_window_integration.py: FOUND
- Commit 0d3f9e5 (RED tests): FOUND
- Commit 004de5c (implementation): FOUND
- 97 tests passed in three-file cross-plan regression
- D-10/D-11: git diff empty on cookie_import_dialog files
