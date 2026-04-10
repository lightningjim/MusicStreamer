---
phase: 32-add-twitch-authentication-via-streamlink-oauth-token
plan: "02"
subsystem: ui
tags: [accounts, twitch, webkit2, oauth, gtk]
dependency_graph:
  requires: []
  provides: [AccountsDialog, TwitchWebKit2Login]
  affects: [musicstreamer/ui/main_window.py, musicstreamer/constants.py]
tech_stack:
  added: []
  patterns: [WebKit2-subprocess-login, Gtk.Notebook-tabs, os.open-secure-write]
key_files:
  created: [musicstreamer/ui/accounts_dialog.py]
  modified: [musicstreamer/ui/main_window.py, musicstreamer/constants.py]
decisions:
  - "TWITCH_TOKEN_PATH and clear_twitch_token added to constants.py in this plan (parallel plan 01 adds them too — both plans define identical symbols, no conflict)"
  - "Task 2 implemented in same file write as Task 1 — no separate commit needed"
metrics:
  duration: "~10 min"
  completed: "2026-04-10T00:23:22Z"
  tasks_completed: 3
  files_modified: 3
---

# Phase 32 Plan 02: Accounts Dialog with Twitch Login Summary

AccountsDialog replaces CookiesDialog with tabbed UI: YouTube tab preserves all existing cookie functionality, Twitch tab adds WebKit2 login flow that captures auth-token cookie and stores it at 0o600 permissions.

## What Was Built

- `musicstreamer/ui/accounts_dialog.py` — `AccountsDialog` class (renamed from `CookiesDialog`) with `Gtk.Notebook` containing YouTube and Twitch tabs
- YouTube tab: identical to old `CookiesDialog` — status, file picker, paste, Google login, clear
- Twitch tab: "Not logged in"/"Logged in" status, Log in button, destructive Log out button
- `_TWITCH_WEBKIT2_SUBPROCESS_SCRIPT` — GTK3/WebKit2 subprocess that navigates to `twitch.tv/login`, detects post-login URL, extracts `auth-token` cookie from `.twitch.tv` domain, writes raw token to temp file
- `_on_twitch_login` → `_run_twitch_webkit_subprocess` → `_on_twitch_token_ready` flow with daemon thread + `GLib.idle_add`
- Token written via `os.open(O_WRONLY|O_CREAT|O_TRUNC, 0o600)` + `os.fdopen` (secure write pattern)
- `musicstreamer/ui/main_window.py` — hamburger menu updated: "YouTube Cookies..." → "Accounts...", action `open-cookies` → `open-accounts`, import and method renamed
- `musicstreamer/constants.py` — `TWITCH_TOKEN_PATH` and `clear_twitch_token()` added (Rule 3 deviation: parallel plan dependency)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1+2 | d9be96a | feat(32-02): rename CookiesDialog to AccountsDialog with YouTube/Twitch tabs |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added TWITCH_TOKEN_PATH and clear_twitch_token to constants.py**
- **Found during:** Task 1
- **Issue:** accounts_dialog.py imports `TWITCH_TOKEN_PATH` and `clear_twitch_token` from `musicstreamer.constants`, but these are defined by plan 01 which runs in parallel. Import would fail if plan 01 hasn't committed yet.
- **Fix:** Added `TWITCH_TOKEN_PATH = os.path.join(DATA_DIR, "twitch-token.txt")` and `clear_twitch_token()` to constants.py directly in this worktree.
- **Files modified:** musicstreamer/constants.py
- **Commit:** d9be96a

**2. Task 2 implemented in same commit as Task 1**
- Both tasks modify only `accounts_dialog.py`. Since the full file was written in one operation covering both tasks, the implementation is in a single commit. All Task 2 acceptance criteria verified independently.

## Verification

- `python -c "from musicstreamer.ui.accounts_dialog import AccountsDialog, _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT; assert 'auth-token' in _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT"` — PASS
- All grep acceptance criteria — PASS
- `pytest tests/ -x` — 255 passed

## Self-Check: PASSED

- `musicstreamer/ui/accounts_dialog.py` — FOUND
- `musicstreamer/ui/main_window.py` — modified, FOUND
- `musicstreamer/constants.py` — modified, FOUND
- Commit `d9be96a` — FOUND
- `cookies_dialog.py` deleted — CONFIRMED
