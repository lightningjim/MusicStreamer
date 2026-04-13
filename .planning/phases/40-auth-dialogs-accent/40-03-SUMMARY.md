---
phase: 40-auth-dialogs-accent
plan: "03"
subsystem: ui_qt
tags: [cookie-import, dialog, youtube, oauth, file-picker, paste, subprocess]
dependency_graph:
  requires: [musicstreamer/paths.py, musicstreamer/oauth_helper.py]
  provides: [musicstreamer/ui_qt/cookie_import_dialog.py]
  affects: [musicstreamer/ui_qt/main_window.py]
tech_stack:
  added: []
  patterns: [QProcess subprocess isolation, QTabWidget three-tab dialog, os.chmod 0o600, _validate_youtube_cookies]
key_files:
  created:
    - musicstreamer/ui_qt/cookie_import_dialog.py
    - tests/test_cookie_import_dialog.py
  modified: []
decisions:
  - "isHidden() used in tests instead of isVisible() — isVisible() returns False for unshown parent widgets in headless test context"
  - "QProcess(self) — dialog as parent ensures process lifetime is scoped to dialog"
metrics:
  duration: "~10 min"
  completed: "2026-04-13"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 40 Plan 03: CookieImportDialog Summary

**One-liner:** QDialog with File/Paste/Google Login tabs for YouTube cookie import; validates Netscape format, writes with 0o600 permissions, launches oauth_helper subprocess.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for CookieImportDialog | e9fdbb6 | tests/test_cookie_import_dialog.py |
| 1 (GREEN) | CookieImportDialog implementation | 56729ae | musicstreamer/ui_qt/cookie_import_dialog.py, tests/test_cookie_import_dialog.py |

## What Was Built

`CookieImportDialog(QDialog)` with three import paths:

- **File tab** — `QFileDialog.getOpenFileName` → read file → validate → write. Shows "Import" button only after a file is chosen. 40-char truncated filename display.
- **Paste tab** — `QTextEdit` with `textChanged` enabling Import button when non-empty. Validates before writing.
- **Google Login tab** — `QProcess(self)` with `sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "google"]`. Disables button + shows "Logging in..." while running. Reads stdout on exit code 0, validates, writes.

Shared helpers:
- `_validate_youtube_cookies(text)` — module-level, checks for `≥1` `.youtube.com` tab-separated Netscape line.
- `_write_cookies(text)` — writes to `paths.cookies_path()` with immediate `os.chmod(0o600)`, fires toast, calls `accept()`.
- `_show_error` / `_hide_error` — inline `QLabel` below tabs, `#c0392b`, 9pt, hidden by default.

## Threat Mitigations Applied

| ID | Mitigation |
|----|-----------|
| T-40-07 | `_validate_youtube_cookies` rejects non-Netscape/non-.youtube.com input |
| T-40-08 | `os.chmod(0o600)` immediately after write |
| T-40-09 | `sys.executable` as QProcess program — no PATH injection |
| T-40-10 | `setTextFormat(Qt.PlainText)` on all QLabel instances |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test used isVisible() which fails headless**
- **Found during:** Task 1 GREEN
- **Issue:** `isVisible()` returns False for widgets whose parent dialog has not been `.show()`n — Qt propagates parent visibility to children. In headless offscreen tests the dialog is never shown.
- **Fix:** Changed two test assertions to `not dlg._error_label.isHidden()` which checks the widget's own explicit visibility flag regardless of parent state.
- **Files modified:** tests/test_cookie_import_dialog.py
- **Commit:** 56729ae

## Test Results

```
15 passed in 0.11s
```

## Known Stubs

None — all three import paths are fully wired. `oauth_helper.py` (Plan 02) is referenced but mocked in tests; it is created by the parallel Plan 02 agent.

## Self-Check

- [x] musicstreamer/ui_qt/cookie_import_dialog.py exists
- [x] tests/test_cookie_import_dialog.py exists
- [x] Commit e9fdbb6 (RED tests) exists
- [x] Commit 56729ae (GREEN implementation) exists
- [x] All 15 tests pass

## Self-Check: PASSED
