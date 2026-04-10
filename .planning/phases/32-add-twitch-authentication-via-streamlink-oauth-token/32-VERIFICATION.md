---
phase: 32-add-twitch-authentication-via-streamlink-oauth-token
verified: 2026-04-10T01:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open hamburger menu and click Accounts..."
    expected: "Dialog opens with YouTube and Twitch tabs; YouTube tab has full cookie UI unchanged"
    why_human: "Cannot verify GTK dialog rendering without a display"
  - test: "Click Log in to Twitch"
    expected: "WebKit2 subprocess opens browser window at twitch.tv/login; after login browser closes, status changes to Logged in, Log out button becomes active"
    why_human: "Requires interactive browser and real Twitch credentials"
  - test: "After login, close and reopen Accounts dialog"
    expected: "Twitch tab shows Logged in with active Log out button"
    why_human: "Persistent state test requires UI interaction"
  - test: "Click Log out"
    expected: "Status changes to Not logged in; twitch-token.txt is deleted"
    why_human: "Requires UI interaction"
  - test: "Play a Twitch stream with valid token"
    expected: "streamlink args include --twitch-api-header Authorization=OAuth <token>; stream plays without ad interruption"
    why_human: "Requires live Twitch channel and real token"
---

# Phase 32: Add Twitch Authentication via Streamlink OAuth Token Verification Report

**Phase Goal:** Twitch OAuth token captured via WebKit2 login flow, stored as plain text file, and passed to streamlink via --twitch-api-header; CookiesDialog renamed to AccountsDialog with YouTube and Twitch tabs
**Verified:** 2026-04-10T01:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TWITCH_TOKEN_PATH constant resolves to ~/.local/share/musicstreamer/twitch-token.txt | VERIFIED | `constants.py` line 8: `TWITCH_TOKEN_PATH = os.path.join(DATA_DIR, "twitch-token.txt")`; DATA_DIR = `~/.local/share/musicstreamer`; test `test_twitch_token_path_constant` passes |
| 2 | _play_twitch() includes --twitch-api-header Authorization=OAuth <token> when token file exists | VERIFIED | `player.py` lines 279-287: cmd built with `--twitch-api-header` and `f"Authorization=OAuth {token}"` inside OSError guard; tests `test_play_twitch_includes_auth_header`, `test_play_twitch_no_header_when_absent`, `test_play_twitch_no_header_when_empty` all pass |
| 3 | Hamburger menu shows "Accounts..." opening AccountsDialog with YouTube and Twitch tabs | VERIFIED (automated part) | `main_window.py` line 58: `"Accounts\u2026", "app.open-accounts"`; action `open-accounts` wired to `_open_accounts_dialog`; `AccountsDialog` has `Gtk.Notebook` with YouTube and Twitch tabs at lines 35, 132, 173 |
| 4 | Twitch tab has login status, "Log in to Twitch" button, and "Log out" button | VERIFIED | `accounts_dialog.py` lines 147-171: `_twitch_status` label, `_twitch_login_btn`, `_twitch_logout_btn`; status reads TWITCH_TOKEN_PATH at init; logout wired to `clear_twitch_token()` |
| 5 | WebKit2 subprocess captures auth-token cookie from .twitch.tv and stores raw token with 0o600 | VERIFIED | `_TWITCH_WEBKIT2_SUBPROCESS_SCRIPT` searches `.twitch.tv` domain for `auth-token` cookie name; `_on_twitch_token_ready` writes via `os.open(O_WRONLY\|O_CREAT\|O_TRUNC, 0o600)` + `os.fdopen` at lines 400-401 |
| 6 | Existing YouTube cookie functionality unchanged | VERIFIED | YouTube tab content is direct migration of CookiesDialog; all cookie methods (`_on_browse`, `_on_import`, `_on_clear`, `_on_google_login`, `_run_webkit_subprocess`, `_on_google_cookies_ready`, `_update_status`) present and unmodified; 261 tests pass with no regressions |

**Score:** 6/6 truths verified (automated checks)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/constants.py` | TWITCH_TOKEN_PATH constant and clear_twitch_token() | VERIFIED | Both present at lines 8 and 19-24 |
| `musicstreamer/player.py` | Token injection in _play_twitch() | VERIFIED | Auth header injection at lines 279-287; imports TWITCH_TOKEN_PATH from constants |
| `tests/test_twitch_auth.py` | Unit tests for constants and player auth injection | VERIFIED | 6 tests; all pass |
| `musicstreamer/ui/accounts_dialog.py` | AccountsDialog with YouTube and Twitch tabs | VERIFIED | 664 lines; class present; Gtk.Notebook with both tabs; WebKit2 subprocess script included |
| `musicstreamer/ui/main_window.py` | Hamburger menu wiring to AccountsDialog | VERIFIED | Import, menu label, action, and method handler all updated |
| `musicstreamer/ui/cookies_dialog.py` | Deleted (renamed to accounts_dialog.py) | VERIFIED | File does not exist |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/player.py` | `musicstreamer/constants.py` | `import TWITCH_TOKEN_PATH` | WIRED | Line 11: `from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES, COOKIES_PATH, TWITCH_TOKEN_PATH` |
| `musicstreamer/ui/main_window.py` | `musicstreamer/ui/accounts_dialog.py` | `import AccountsDialog` | WIRED | Line 18: `from musicstreamer.ui.accounts_dialog import AccountsDialog`; used at line 1169 |
| `musicstreamer/ui/accounts_dialog.py` | `musicstreamer/constants.py` | `import TWITCH_TOKEN_PATH, clear_twitch_token` | WIRED | Line 11: `from musicstreamer.constants import COOKIES_PATH, clear_cookies, TWITCH_TOKEN_PATH, clear_twitch_token` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `player.py _play_twitch()` | `token` / `cmd` | `open(TWITCH_TOKEN_PATH).read().strip()` from disk | Yes — reads actual file content; empty/absent guards in place | FLOWING |
| `accounts_dialog.py Twitch tab` | `_twitch_status` text | `os.path.exists(TWITCH_TOKEN_PATH)` at init and in `_update_twitch_status()` | Yes — reads real filesystem state | FLOWING |
| `accounts_dialog.py _on_twitch_token_ready` | `token` | Written to `TWITCH_TOKEN_PATH` via `os.open(0o600)` | Yes — secure write with correct permissions | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 6 twitch auth unit tests pass | `pytest tests/test_twitch_auth.py -x -q` | 6 passed in 0.04s | PASS |
| Full test suite passes (261 tests) | `pytest tests/ -x -q` | 261 passed in 1.93s | PASS |
| AccountsDialog imports cleanly | `python3 -c "from musicstreamer.ui.accounts_dialog import AccountsDialog, _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT; assert 'auth-token' in _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT; assert 'twitch.tv/login' in _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT; print('OK')"` | OK | PASS |
| cookies_dialog.py deleted | `test -f musicstreamer/ui/cookies_dialog.py` | DELETED | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TAUTH-01 | 32-01-PLAN | TWITCH_TOKEN_PATH in constants.py resolves to DATA_DIR/twitch-token.txt | SATISFIED | constants.py line 8; test_twitch_token_path_constant passes |
| TAUTH-02 | 32-01-PLAN | clear_twitch_token() deletes file and returns True; returns False when absent | SATISFIED | constants.py lines 19-24; test_clear_twitch_token_* tests pass |
| TAUTH-03 | 32-01-PLAN | _play_twitch() includes --twitch-api-header when token exists; omits when absent/empty | SATISFIED | player.py lines 279-287; 3 injection tests pass |
| TAUTH-04 | 32-02-PLAN | CookiesDialog renamed to AccountsDialog; hamburger shows "Accounts..." | SATISFIED | accounts_dialog.py has `class AccountsDialog`; main_window.py shows "Accounts\u2026" with `app.open-accounts` |
| TAUTH-05 | 32-02-PLAN | AccountsDialog uses Gtk.Notebook with YouTube and Twitch tabs | SATISFIED | accounts_dialog.py lines 35, 132, 173: Gtk.Notebook with both tab pages |
| TAUTH-06 | 32-02-PLAN | Twitch tab: status label, Log in button (WebKit2 subprocess), Log out button | SATISFIED | accounts_dialog.py lines 147-171; `_on_twitch_login` spawns daemon thread with `_run_twitch_webkit_subprocess` |
| TAUTH-07 | 32-02-PLAN | WebKit2 subprocess captures auth-token cookie from .twitch.tv, writes token with 0o600 | SATISFIED | `_TWITCH_WEBKIT2_SUBPROCESS_SCRIPT` filters `.twitch.tv` cookies, extracts `auth-token`; `_on_twitch_token_ready` uses `os.open(..., 0o600)` |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `accounts_dialog.py` line 462 | `class _GoogleLoginWindow: ... pass` stub body | Info | Intentional stub for import compatibility — real implementation in subprocess script; documented in comment |

No blockers found. The `_GoogleLoginWindow` stub is documented as intentional and was carried over from CookiesDialog.

### Human Verification Required

All automated checks pass. The following behaviors require human testing because they involve an interactive GTK UI, a real browser session, and live Twitch credentials.

#### 1. Accounts dialog opens correctly

**Test:** Launch app, open hamburger menu, click "Accounts..."
**Expected:** Dialog title "Accounts" with two tabs labeled "YouTube" and "Twitch"
**Why human:** GTK rendering cannot be verified without a display

#### 2. YouTube tab is fully functional

**Test:** Click YouTube tab in Accounts dialog; verify cookie import (file browse + paste), Google login button, Clear Cookies button, status label all work
**Expected:** Identical behavior to the old CookiesDialog — no regressions
**Why human:** Requires display and user interaction

#### 3. Twitch login flow end-to-end

**Test:** Click Twitch tab; click "Log in to Twitch"; complete Twitch login in the WebKit2 browser window (including 2FA if applicable)
**Expected:** Browser closes automatically; status changes to "Logged in"; "Log out" button becomes active
**Why human:** Requires interactive browser and real Twitch credentials; WebKit2 cookie capture cannot be tested headlessly

#### 4. Twitch login state persists across dialog reopens

**Test:** After login succeeds, close Accounts dialog and reopen it
**Expected:** Twitch tab still shows "Logged in" with active Log out button
**Why human:** Requires prior UI login step

#### 5. Twitch logout works

**Test:** Click "Log out" in Twitch tab
**Expected:** Status changes to "Not logged in"; Log out button grays out; twitch-token.txt deleted from disk
**Why human:** Requires prior login and UI interaction

#### 6. Token injected into streamlink when playing Twitch stream

**Test:** With valid token saved, play a live Twitch channel
**Expected:** Stream plays; if streamlink verbose output is available, confirm --twitch-api-header is present
**Why human:** Requires live Twitch channel, real token, and running GStreamer pipeline

### Gaps Summary

No gaps found. All 7 requirements implemented correctly. All 6 roadmap success criteria satisfied via automated checks. Human verification is required for the interactive UI/browser flow — this is inherent to WebKit2 login testing and not a code deficiency.

---

_Verified: 2026-04-10T01:00:00Z_
_Verifier: Claude (gsd-verifier)_
