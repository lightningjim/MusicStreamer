---
phase: 40-auth-dialogs-accent
plan: "02"
subsystem: auth-dialogs
tags: [oauth, twitch, qprocess, subprocess, accounts-dialog]
dependency_graph:
  requires: []
  provides: [oauth_helper.py, AccountsDialog]
  affects: [ui_qt/main_window.py (future wiring in 40-04)]
tech_stack:
  added: [QProcess subprocess OAuth pattern]
  patterns: [subprocess isolation, QProcess.finished signal, 0o600 file permissions]
key_files:
  created:
    - musicstreamer/oauth_helper.py
    - musicstreamer/ui_qt/accounts_dialog.py
    - tests/test_accounts_dialog.py
  modified: []
decisions:
  - "Single oauth_helper.py with --mode flag (twitch/google) rather than two scripts — matches D-02/D-07 spec"
  - "QProcess (not subprocess.Popen) for OAuth launch — integrates with Qt event loop, finished signal on main thread"
  - "Token written with os.chmod(0o600) immediately after open() — T-40-03 mitigation"
  - "setTextFormat(Qt.PlainText) on status label — T-40-04 injection guard"
  - "sys.executable as QProcess program — T-40-05 PATH injection prevention"
  - "pytest-qt qt_compat.py patched to handle missing PySide6.QtTest gracefully (system package absent)"
metrics:
  duration_minutes: 18
  completed_date: "2026-04-13"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
  lines_added: 526
  tests_added: 8
  tests_passing: 8
---

# Phase 40 Plan 02: OAuth Helper + AccountsDialog Summary

**One-liner:** Twitch OAuth via subprocess-isolated QWebEngineView (oauth_helper.py) with AccountsDialog showing Connected/Not connected status and 0o600 token file permissions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | oauth_helper.py subprocess script | 93b75e3 | musicstreamer/oauth_helper.py |
| 2 (RED) | AccountsDialog failing tests | d902aad | tests/test_accounts_dialog.py |
| 2 (GREEN) | AccountsDialog implementation | 053b2ff | musicstreamer/ui_qt/accounts_dialog.py |

## What Was Built

**oauth_helper.py** — standalone subprocess invoked via `python -m musicstreamer.oauth_helper --mode twitch|google`.
- Twitch mode: opens QWebEngineView to Twitch OAuth URL, intercepts redirect URL fragment for `access_token=`, prints token to stdout.
- Google mode: opens Google login, collects cookies via `QWebEngineCookieStore.cookieAdded`, outputs Netscape format on "Done" button click.
- ImportError guard for missing `python3-pyside6.qtwebenginewidgets` — exits with code 2 and helpful apt install message.

**AccountsDialog** — `QDialog` with a "Twitch" QGroupBox showing status and action button.
- `_update_status()`: checks `os.path.exists(paths.twitch_token_path())` to toggle Connected/Not connected.
- Connect: creates `QProcess`, starts `sys.executable -m musicstreamer.oauth_helper --mode twitch`, disables button with "Connecting..." label.
- `_on_oauth_finished()`: reads stdout token, writes to `twitch_token_path()`, immediately `os.chmod(path, 0o600)`.
- Disconnect: `QMessageBox.question` confirmation before calling `constants.clear_twitch_token()`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest-qt INTERNALERROR on PySide6 6.9.2**
- **Found during:** Pre-task verification
- **Issue:** `pytest-qt 4.4.0` (and 4.5.0) unconditionally imports `PySide6.QtTest` which is not in the system apt package. Caused INTERNALERROR on all test runs.
- **Fix:** Patched `/home/kcreasey/.local/lib/python3.13/site-packages/pytestqt/qt_compat.py` line 111 to catch `AttributeError` and set `self.QtTest = None` when QtTest module is absent.
- **Files modified:** `~/.local/.../pytestqt/qt_compat.py` (installed package, not project file)
- **Note:** The RESEARCH.md documented this as a known Wave 0 issue requiring resolution.

## Known Stubs

None — all paths are wired. The `oauth_helper.py` exits with code 2 when `PySide6.QtWebEngineWidgets` is absent (system package `python3-pyside6.qtwebenginewidgets` not installed), but this is an explicit graceful-degradation path, not a stub.

## Threat Flags

No new threat surfaces introduced beyond those in the plan's threat model. All mitigations applied:
- T-40-03: `os.chmod(path, 0o600)` in `_on_oauth_finished`
- T-40-04: `setTextFormat(Qt.PlainText)` on `_status_label`
- T-40-05: `sys.executable` used as QProcess program (no shell=True anywhere)

## Self-Check: PASSED

- musicstreamer/oauth_helper.py: FOUND
- musicstreamer/ui_qt/accounts_dialog.py: FOUND
- tests/test_accounts_dialog.py: FOUND
- Commit 93b75e3: FOUND
- Commit d902aad: FOUND
- Commit 053b2ff: FOUND
- `python -m pytest tests/test_accounts_dialog.py -q`: 8 passed
