---
phase: 22-import-yt-cookies-separately-from-extracting-from-browser-ev
plan: 02
subsystem: ui
tags: [cookies, gtk4, dialog, hamburger-menu]
dependency_graph:
  requires: [22-01]
  provides: [cookies-dialog-ui, hamburger-menu]
  affects: [musicstreamer/ui/main_window.py, musicstreamer/ui/cookies_dialog.py]
tech_stack:
  added: []
  patterns: [Adw.Window dialog, Gtk.FileDialog, Gio.SimpleAction, Gio.Menu, Gtk.MenuButton]
key_files:
  created:
    - musicstreamer/ui/cookies_dialog.py
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "Gtk.Expander (not Adw.ExpanderRow) for Other methods — standalone, no ListBox parent required"
  - "Google login handler is a placeholder label only — full impl deferred to Plan 03 per spec"
metrics:
  duration: ~10min
  completed: 2026-04-06
  tasks_completed: 2
  tasks_total: 3
  files_changed: 2
---

# Phase 22 Plan 02: CookiesDialog UI and Hamburger Menu Summary

CookiesDialog with file picker, paste import, and status label; hamburger menu in header bar wired via Gio.SimpleAction.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create CookiesDialog | def8c21 | musicstreamer/ui/cookies_dialog.py (new, 248 lines) |
| 2 | Add hamburger menu to main window | 5ce45df | musicstreamer/ui/main_window.py (+19 lines) |
| 3 | Verify cookies dialog and hamburger menu | — | **checkpoint — awaiting human verification** |

## Task 3: Human-Verify Checkpoint

Task 3 is a `checkpoint:human-verify` gate. It was not executed — the orchestrator will present this to the user.

**What to verify:**
1. Launch app: `python3 -m musicstreamer`
2. Confirm hamburger icon (three lines) at far right of header bar
3. Click it — confirm "YouTube Cookies..." menu item appears
4. Click item — confirm CookiesDialog opens with title "YouTube Cookies"
5. Confirm layout: status label ("No cookies imported"), file picker row, "Other methods" expander, Clear Cookies (insensitive) + Import Cookies footer
6. Browse for a .txt file — confirm filename appears, Import becomes sensitive
7. Import — confirm status updates to "Last imported: {date}", Clear becomes sensitive
8. Expand "Other methods" — confirm paste textarea and Google button visible
9. Clear Cookies — confirm status resets, Clear becomes insensitive
10. Confirm `~/.local/share/musicstreamer/cookies.txt` lifecycle works

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `_on_google_login`: shows "Google login coming soon" label. This is the only intentional placeholder per plan spec (D-03 delivered in Plan 03).

## Threat Coverage

All mitigations from the threat register applied:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-22-03 | `_is_valid_cookies_txt()` validates before copy in `_import_from_file` | Applied |
| T-22-04 | `_is_valid_cookies_txt()` validates before write in `_import_from_paste` | Applied |
| T-22-05 | `os.chmod(COOKIES_PATH, 0o600)` after every write | Applied |
| T-22-06 | Large paste accepted — accepted per threat register | N/A |

## Self-Check: PASSED

- `musicstreamer/ui/cookies_dialog.py` exists: FOUND
- `musicstreamer/ui/main_window.py` modified: FOUND
- Commit def8c21: FOUND
- Commit 5ce45df: FOUND
- 193 tests passing: CONFIRMED
