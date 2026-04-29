---
phase: 53-youtube-cookies-into-accounts-menu
plan: "01"
subsystem: accounts-dialog
tags: [pyside6, qt-dialog, accounts, youtube-cookies, ui-refactor]
requirements: [BUG-04]

dependency_graph:
  requires: []
  provides:
    - AccountsDialog.YouTube QGroupBox (status label + action button)
    - AccountsDialog._is_youtube_connected predicate
    - AccountsDialog._update_status YouTube branch
    - AccountsDialog._on_youtube_action_clicked slot
    - AccountsDialog.__init__ toast_callback defaulted kwarg
    - TestAccountsDialogYouTube class (14 unit tests)
  affects:
    - musicstreamer/ui_qt/accounts_dialog.py
    - tests/test_accounts_dialog.py

tech_stack:
  added:
    - typing.Callable (for toast_callback annotation)
  patterns:
    - QGroupBox + QVBoxLayout status label + QPushButton action button (third instance of Twitch/AA pattern)
    - Bound-method signal connection (QA-05: no self-capturing lambda)
    - setTextFormat(Qt.TextFormat.PlainText) on all status labels (T-40-04)
    - try/except FileNotFoundError around os.remove (T-53-01 race tolerance)
    - In-slot import of CookieImportDialog (D-05, D-12)
    - Defaulted keyword parameter for back-compat constructor extension

key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/accounts_dialog.py
    - tests/test_accounts_dialog.py

decisions:
  - D-06: toast_callback defaulted to None with no-op fallback preserves 24 existing AccountsDialog(fake_repo) test sites unchanged
  - D-09: YouTube group placed first in layout (YouTube → Twitch → AudioAddict → close button)
  - T-53-01: try/except FileNotFoundError around os.remove(paths.cookies_path()) protects against Phase 999.7 auto-clear race
  - T-53-02: _on_youtube_action_clicked strictly limited to cookies_path() removal + _update_status(); never touches twitch_token_path or audioaddict_listen_key
  - Test fix (Rule 1): test_import_launches_cookie_dialog used toasts.append twice with 'is' identity check — bound method objects are not singleton, fixed by saving reference to toast_cb before passing
  - Test fix (Rule 1): test_disconnect_file_already_gone originally deleted the file before calling the slot, causing the "not connected" branch to run and opening a real CookieImportDialog (blocking). Fixed by patching os.remove to raise FileNotFoundError (simulating the actual TOCTOU race) while keeping the file present for the _is_youtube_connected check

metrics:
  duration_minutes: ~97
  completed: "2026-04-29"
  tasks_completed: 2
  files_modified: 2
---

# Phase 53 Plan 01: YouTube QGroupBox in AccountsDialog Summary

YouTube cookie management consolidated into AccountsDialog via a new QGroupBox mirroring the Twitch/AA pattern: PlainText status label + state-toggling action button ("Import YouTube Cookies..." / "Disconnect"), with race-tolerant disconnect and isolated handler.

## What Was Built

### musicstreamer/ui_qt/accounts_dialog.py

- **Constructor signature** extended with `toast_callback: Callable[[str], None] | None = None` defaulted kwarg between `repo` and `parent`. Stored as `self._toast_callback = toast_callback or (lambda _msg: None)`.
- **YouTube QGroupBox** (`self._youtube_box`, titled "YouTube") constructed before Twitch/AA groups (D-09). Contains `self._youtube_status_label` (PlainText format, T-40-04) and `self._youtube_action_btn` (bound to `_on_youtube_action_clicked`, QA-05).
- **Layout reordering**: `self._youtube_box → twitch_box → aa_box → btn_box` (D-09).
- **`_is_youtube_connected()`**: `return os.path.exists(paths.cookies_path())` (D-02).
- **`_update_status()` YouTube branch** inserted at the top of the method: Connected → "Connected" + "Disconnect"; Not connected → "Not connected" + "Import YouTube Cookies..." (D-07, D-08).
- **`_on_youtube_action_clicked()`** slot: Connected → QMessageBox.question confirm ("Disconnect YouTube?") + try/except FileNotFoundError around os.remove + _update_status(); Not connected → in-slot CookieImportDialog import + dlg.exec() + unconditional _update_status() (D-03, D-05).
- **`from typing import Callable`** added at top of file.

### tests/test_accounts_dialog.py

- `QGroupBox` added to the PySide6.QtWidgets import line.
- `TestAccountsDialogYouTube` class added with **14 unit tests** covering all VALIDATION.md invariants:
  - `test_youtube_group_present`, `test_status_not_connected`, `test_status_connected`, `test_button_label_not_connected`, `test_button_label_connected`
  - `test_import_launches_cookie_dialog`, `test_post_import_refreshes_status`, `test_post_cancel_status_unchanged`
  - `test_disconnect_removes_cookies`, `test_disconnect_cancel_keeps_cookies`, `test_disconnect_file_already_gone`, `test_disconnect_isolates_youtube`
  - `test_group_order`, `test_status_label_plain_text`

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| `tests/test_accounts_dialog.py::TestAccountsDialogYouTube` | 14 | 14 passed |
| `tests/test_accounts_dialog.py` (full file) | 37 | 37 passed |
| Quick suite (`tests/test_accounts_dialog.py tests/test_main_window_integration.py`) | 80 | 80 passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed bound method identity check in test_import_launches_cookie_dialog**
- **Found during:** Task 2 verification
- **Issue:** `assert captured["toast_cb"] is toasts.append` — accessing a bound method attribute twice creates two distinct objects; `is` identity check always fails
- **Fix:** `toast_cb = toasts.append; dlg = AccountsDialog(fake_repo, toast_callback=toast_cb); assert captured["toast_cb"] is toast_cb`
- **Files modified:** `tests/test_accounts_dialog.py`
- **Commit:** `bdbab33`

**2. [Rule 1 - Bug] Fixed test_disconnect_file_already_gone blocking on real CookieImportDialog**
- **Found during:** Task 2 verification (test suite hung at 33/37 in non-verbose mode)
- **Issue:** The plan's test code deleted the cookies file before triggering the click. With the file gone, `_is_youtube_connected()` returned False and the "not connected" branch ran — opening a real (non-mocked) CookieImportDialog that blocked the test runner
- **Fix:** Keep the file present (so `_is_youtube_connected()` returns True and enters the Disconnect branch), then patch `os.remove` to raise FileNotFoundError (simulating the actual TOCTOU race window) while also calling `os.unlink` to clean the file so `_update_status()` correctly sees "Not connected"
- **Files modified:** `tests/test_accounts_dialog.py`
- **Commit:** `bdbab33`

### Pre-existing Failures (Out of Scope)

The full `pytest -q` run shows 7 test module collection errors (test_cookies.py, test_player_*.py, test_twitch_*.py, test_windows_palette.py) and some player/SMTC test failures — all due to missing `gi` (GStreamer Python bindings) and MPRIS D-Bus session bus not being available in the test environment. These are pre-existing in the codebase and unrelated to Phase 53 changes.

## Open Work for Plan 02

Per the plan's output spec:
- **main_window.py:** Drop `act_cookies`, `_open_cookie_dialog` method, `CookieImportDialog` top-level import; pass `self.show_toast` as `toast_callback` to `AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)` in `_open_accounts_dialog` (D-12, D-14)
- **tests/test_main_window_integration.py:** Remove "YouTube Cookies" from `EXPECTED_ACTION_TEXTS` (length 10 → 9); add `test_open_accounts_passes_toast` test verifying D-14 wiring

## Commits

| Hash | Message |
|------|---------|
| `1a6727f` | test(53-01): add TestAccountsDialogYouTube class with 14 RED tests |
| `bdbab33` | feat(53-01): add YouTube QGroupBox + slot + status branch + toast_callback to AccountsDialog |

## Grep Gate Results (Post-Task-2)

| Gate | Expected | Actual | Pass |
|------|----------|--------|------|
| `setTextFormat(Qt.TextFormat.PlainText)` count | ≥ 3 | 5 | ✓ |
| `QGroupBox("YouTube"` count | == 1 | 1 | ✓ |
| `def _on_youtube_action_clicked` count | == 1 | 1 | ✓ |
| `def _is_youtube_connected` count | == 1 | 1 | ✓ |
| `toast_callback: Callable[[str], None] \| None = None` | == 1 | 1 | ✓ |
| `from typing import Callable` | == 1 | 1 | ✓ |
| `except FileNotFoundError` | ≥ 1 | 2 | ✓ |
| `"Disconnect YouTube?"` | == 1 | 1 | ✓ |
| `"Import YouTube Cookies..."` | == 1 | 1 | ✓ |
| `"Connected"` count | ≥ 2 | 2 | ✓ |
| `"Not connected"` count | ≥ 2 | 2 | ✓ |
| `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog` | == 1 | 1 | ✓ |
| `_youtube_action_btn.clicked.connect(lambda` | == 0 | 0 | ✓ |
| No `twitch_token_path`/`audioaddict_listen_key` in slot | == 0 | 0 | ✓ |

## Self-Check: PASSED

- 53-01-SUMMARY.md: FOUND
- musicstreamer/ui_qt/accounts_dialog.py: FOUND
- tests/test_accounts_dialog.py: FOUND
- Commit 1a6727f (RED tests): FOUND
- Commit bdbab33 (implementation): FOUND
- 37 tests passed in full test_accounts_dialog.py run
- 80 tests passed in quick suite (accounts_dialog + main_window_integration)
