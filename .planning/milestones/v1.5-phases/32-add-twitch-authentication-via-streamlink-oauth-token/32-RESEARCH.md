# Phase 32: Add Twitch Authentication via Streamlink OAuth Token - Research

**Researched:** 2026-04-09
**Domain:** WebKit2 OAuth capture / streamlink auth / GTK4 tab UI
**Confidence:** HIGH

## Summary

This phase adds Twitch OAuth token capture via an embedded WebKit2 browser (the same GTK3 subprocess pattern already used for Google login), stores the token as a plain file, and threads it into the existing `_play_twitch()` streamlink invocation via `--twitch-api-header`. The UI work is a rename + tab addition on the existing `CookiesDialog`.

All locked decisions (D-01 through D-07) are well-supported by existing patterns in the codebase. No external services or new libraries are required. The primary research unknowns were (1) the Twitch cookie name holding the OAuth token, (2) the exact streamlink flag format, and (3) login completion detection — all three are now verified.

**Primary recommendation:** Follow the Google login subprocess pattern exactly. Cookie name is `auth-token`. Streamlink flag is `--twitch-api-header` with value `Authorization=OAuth <token>` as a separate list element.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use a WebKit2 WebView to open twitch.tv login page. User logs in normally (including 2FA if enabled). App captures the OAuth token from the session cookies after login completes.
- **D-02:** Pass the token to streamlink via `--twitch-api-header=Authorization=OAuth <token>` in the `_play_twitch()` subprocess call.
- **D-03:** Store the Twitch OAuth token as a plain text file at `~/.local/share/musicstreamer/twitch-token.txt` with `0o600` permissions. Matches the existing YouTube cookies pattern (`COOKIES_PATH`).
- **D-04:** Add `TWITCH_TOKEN_PATH` constant in `constants.py` alongside `COOKIES_PATH`.
- **D-05:** Rename the existing "YouTube Cookies" dialog to a general "Accounts" dialog. Rename the hamburger menu entry from "YouTube Cookies..." to "Accounts...".
- **D-06:** The Accounts dialog uses tabs — a "YouTube" tab (existing cookie UI, unchanged) and a "Twitch" tab with: "Log in to Twitch" button, login status display (logged in as X / not logged in), and "Log out" button.
- **D-07:** Rename `cookies_dialog.py` to `accounts_dialog.py` and `CookiesDialog` class to `AccountsDialog`.

### Claude's Discretion
- WebKit2 cookie extraction specifics (which cookie name holds the OAuth token)
- How to detect login completion in the WebView (URL redirect, cookie presence check)
- Status label format for logged-in state
- Whether to validate token with a Twitch API call before storing

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core (all already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| WebKit2 (GTK3) | 4.1 | Embedded browser for Twitch login | Already used for Google login; must run in subprocess due to GTK3/GTK4 conflict |
| streamlink | system | Twitch HLS resolution + auth header | Already used in `_play_twitch()` (Phase 31) |
| Adw.ViewStack / Gtk.Notebook | GTK4/libadwaita | Tab switcher in Accounts dialog | Both available; Adw.ViewStack is already used in the project |

No new packages required. All dependencies already installed.

**Installation:** None needed.

## Architecture Patterns

### Recommended Project Structure (changes only)
```
musicstreamer/
├── constants.py              # add TWITCH_TOKEN_PATH, clear_twitch_token()
├── player.py                 # inject --twitch-api-header in _play_twitch()
└── ui/
    ├── accounts_dialog.py    # renamed from cookies_dialog.py; add Twitch tab
    └── main_window.py        # rename action "open-cookies" → "open-accounts"
```

### Pattern 1: WebKit2 Subprocess for Twitch Login

**What:** Spawn a GTK3 subprocess (same mechanism as Google login) that opens `https://www.twitch.tv/login`, waits for the user to land on `twitch.tv` (not the login page), then extracts the `auth-token` cookie value and writes it to a temp file.

**Twitch cookie name:** `auth-token` [VERIFIED: streamlink docs at streamlink.github.io/cli/plugins/twitch.html]

**Login completion detection:** On `WebKit2.LoadEvent.FINISHED`, check `uri.startswith("https://www.twitch.tv/")` and `"login" not in uri` and `"passport-logout" not in uri`. When true, call `get_all_cookies()` and look for `name == "auth-token"` in cookies for `.twitch.tv` domain. [ASSUMED: the exact URL pattern — the Google login analogue used `"youtube.com" in uri and "accounts.google" not in uri`]

**Example subprocess script pattern (mirrored from Google login):**
```python
# Source: musicstreamer/ui/cookies_dialog.py _WEBKIT2_SUBPROCESS_SCRIPT
def on_load_changed(webview, event):
    global _token_extracted
    if event != WebKit2.LoadEvent.FINISHED:
        return
    uri = webview.get_uri() or ""
    # Twitch redirects to twitch.tv/<username> after login
    if "twitch.tv" in uri and "login" not in uri and not _token_extracted:
        _token_extracted = True
        mgr = webview.get_website_data_manager().get_cookie_manager()
        mgr.get_all_cookies(None, on_got_cookies, None)

def on_got_cookies(mgr, res, user_data):
    cookies = mgr.get_all_cookies_finish(res)
    twitch_cookies = [c for c in (cookies or [])
                      if ".twitch.tv" in (c.get_domain() or "")]
    token = None
    for c in twitch_cookies:
        if c.get_name() == "auth-token":
            token = c.get_value()
            break
    if token:
        with open(OUTPUT_PATH, "w") as f:
            f.write(token)
        Gtk.main_quit()
        sys.exit(0)
    else:
        Gtk.main_quit()
        sys.exit(1)
```

### Pattern 2: Streamlink --twitch-api-header Injection

**What:** When `TWITCH_TOKEN_PATH` exists, read the token and add the header arg to the streamlink command list in `_play_twitch()`.

**Exact flag format:** Two separate list elements — `"--twitch-api-header"` and `"Authorization=OAuth <token>"`. Do NOT use `=` to join them (though that also works). [VERIFIED: streamlink docs + GitHub discussion #4400]

```python
# Source: streamlink docs / GitHub discussion #4400
cmd = ["streamlink", "--stream-url", url, "best"]
if os.path.exists(TWITCH_TOKEN_PATH):
    try:
        token = open(TWITCH_TOKEN_PATH).read().strip()
        if token:
            cmd = ["streamlink",
                   "--twitch-api-header", f"Authorization=OAuth {token}",
                   "--stream-url", url, "best"]
    except OSError:
        pass
```

Note: `--twitch-api-header` only affects GraphQL API calls to `gql.twitch.tv`, not the HLS stream itself. This is the correct mechanism for ad suppression for logged-in users. [VERIFIED: streamlink docs]

### Pattern 3: Tab UI in AccountsDialog

**What:** Wrap existing YouTube content and new Twitch content in `Adw.ViewStack` with `Adw.ViewSwitcherBar` or `Gtk.Notebook`. Given the dialog's small size (480×400), `Gtk.Notebook` is simpler and sufficient.

**Twitch tab content:**
- Status label: "Not logged in" or "Logged in" (token username not easily available without an API call — see Assumptions)
- "Log in to Twitch" button → spawns WebKit2 subprocess
- "Log out" button (destructive) → deletes token file, updates label

**Status label format (Claude's discretion):** "Logged in" when token file exists (simple), or "Not logged in". Avoid Twitch API validation call to keep it simple [ASSUMED].

### Pattern 4: Secure Token File Write

```python
# Source: musicstreamer/constants.py pattern (os.fdopen + 0o600)
import os
os.makedirs(os.path.dirname(TWITCH_TOKEN_PATH), exist_ok=True)
fd = os.open(TWITCH_TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(token)
```

### Anti-Patterns to Avoid
- **Subprocess with shell=True:** Never used in this project; `--twitch-api-header` works fine with list args.
- **Storing the full cookie jar:** Only the raw token string is needed, not Netscape format.
- **Calling Twitch API to validate token:** Adds network dependency, complexity, and a potential failure mode for no user benefit at this scope.
- **GTK4 WebKit2 import in main process:** WebKit2 requires GTK3; always use subprocess to avoid namespace conflict (exact same reason as Google login).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth token capture | Custom HTTP server / redirect flow | WebKit2 cookie extraction | Twitch doesn't expose an easy redirect URI for desktop apps; cookie extraction is the documented community approach |
| Token storage | Keyring / encrypted vault | Plain file at `0o600` | Matches project pattern (COOKIES_PATH); simple, no new dependencies |
| Ad suppression | HLS stream rewriting | `--twitch-api-header` | streamlink handles this natively for authenticated users |

## Common Pitfalls

### Pitfall 1: Wrong login completion detection URL
**What goes wrong:** `on_load_changed` fires too early (e.g., on the login page itself or intermediate redirects) and finds no `auth-token` cookie yet.
**Why it happens:** Twitch login has multiple redirect steps.
**How to avoid:** Check that `"login" not in uri` AND `"twitch.tv" in uri` together. Also gate on `_token_extracted` flag to prevent double-extraction.
**Warning signs:** Subprocess exits with code 1 immediately after window opens.

### Pitfall 2: auth-token cookie is HttpOnly
**What goes wrong:** `get_all_cookies()` returns the cookie but some implementations filter HttpOnly cookies.
**Why it happens:** WebKit2's `get_all_cookies()` via `WebsiteDataManager.get_cookie_manager()` actually does return HttpOnly cookies — this is the same mechanism used for Google login.
**How to avoid:** Use `get_website_data_manager().get_cookie_manager().get_all_cookies()` — NOT `WebKit2.CookieManager` obtained any other way. [ASSUMED: based on working Google pattern]

### Pitfall 3: Menu action name collision
**What goes wrong:** Renaming `app.open-cookies` to `app.open-accounts` without updating all references causes the menu item to silently do nothing.
**Why it happens:** `Gio.Menu.append` takes the action name as a string — no compile-time check.
**How to avoid:** Search for all occurrences of `"open-cookies"` in `main_window.py` — there are exactly two (`settings_section.append(...)` and `action = Gio.SimpleAction.new(...)`). Both must change.

### Pitfall 4: Token file read in _play_twitch runs on background thread
**What goes wrong:** Reading `TWITCH_TOKEN_PATH` inside the `_resolve` inner function (which runs on a daemon thread) is fine for file I/O, but any UI updates must use `GLib.idle_add`.
**Why it happens:** `_play_twitch` already runs resolution on a thread; token read can piggyback on the same thread.
**How to avoid:** Only read the token file in the thread; never touch GTK widgets from the thread.

## Code Examples

### Verified: _play_twitch token injection
```python
# Based on: musicstreamer/player.py _play_twitch() (lines 270-292)
def _play_twitch(self, url: str):
    self._pipeline.set_state(Gst.State.NULL)
    env = os.environ.copy()
    local_bin = os.path.expanduser("~/.local/bin")
    if local_bin not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")

    def _resolve():
        cmd = ["streamlink", "--stream-url", url, "best"]
        try:
            token = open(TWITCH_TOKEN_PATH).read().strip()
            if token:
                cmd = ["streamlink",
                       "--twitch-api-header", f"Authorization=OAuth {token}",
                       "--stream-url", url, "best"]
        except OSError:
            pass
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        # ... rest unchanged

    threading.Thread(target=_resolve, daemon=True).start()
```

### Verified: constants.py additions
```python
# Alongside existing COOKIES_PATH
TWITCH_TOKEN_PATH = os.path.join(DATA_DIR, "twitch-token.txt")

def clear_twitch_token() -> bool:
    """Delete twitch-token.txt if it exists. Returns True if removed."""
    if os.path.exists(TWITCH_TOKEN_PATH):
        os.remove(TWITCH_TOKEN_PATH)
        return True
    return False
```

### Verified: main_window.py rename
```python
# Before:
settings_section.append("YouTube Cookies\u2026", "app.open-cookies")
action = Gio.SimpleAction.new("open-cookies", None)
action.connect("activate", self._open_cookies_dialog)
# ...
def _open_cookies_dialog(self, action, param):
    dlg = CookiesDialog(...)

# After:
settings_section.append("Accounts\u2026", "app.open-accounts")
action = Gio.SimpleAction.new("open-accounts", None)
action.connect("activate", self._open_accounts_dialog)
# ...
def _open_accounts_dialog(self, action, param):
    dlg = AccountsDialog(...)
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Twitch login completion detected by `"twitch.tv" in uri and "login" not in uri` | Architecture Patterns P1 | Subprocess exits prematurely or never detects login; fixable during implementation |
| A2 | `get_website_data_manager().get_cookie_manager().get_all_cookies()` returns HttpOnly cookies including `auth-token` | Common Pitfalls P2 | Token extraction fails silently; fallback: inject JS to read `document.cookie` (though `auth-token` may be HttpOnly and not JS-accessible) |
| A3 | Status label shows "Logged in" / "Not logged in" without username (no API call) | Architecture Patterns P3 | Minor UX only — user may prefer username display |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| WebKit2 (GTK3) | Twitch login WebView | ✓ (already used for Google login) | 4.1 | — |
| streamlink | Twitch resolution | ✓ (Phase 31) | system | — |
| python3 | subprocess execution | ✓ | system | — |

No missing dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_twitch_auth.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| TWITCH_TOKEN_PATH constant resolves to DATA_DIR/twitch-token.txt | unit | `pytest tests/test_twitch_auth.py::test_twitch_token_path_constant -x` | ❌ Wave 0 |
| clear_twitch_token() deletes file and returns True | unit | `pytest tests/test_twitch_auth.py::test_clear_twitch_token_removes_file -x` | ❌ Wave 0 |
| clear_twitch_token() returns False when absent | unit | `pytest tests/test_twitch_auth.py::test_clear_twitch_token_returns_false_when_absent -x` | ❌ Wave 0 |
| _play_twitch() includes --twitch-api-header when token file exists | unit | `pytest tests/test_twitch_auth.py::test_play_twitch_includes_auth_header -x` | ❌ Wave 0 |
| _play_twitch() omits --twitch-api-header when token file absent | unit | `pytest tests/test_twitch_auth.py::test_play_twitch_no_header_when_absent -x` | ❌ Wave 0 |
| AccountsDialog opens (smoke — no WebKit subprocess) | unit | `pytest tests/test_twitch_auth.py::test_accounts_dialog_import -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_twitch_auth.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_twitch_auth.py` — covers all behaviors above
- [ ] Pattern mirrors `tests/test_cookies.py` for constants/player tests

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (token storage) | File permissions 0o600 — matches existing COOKIES_PATH pattern |
| V5 Input Validation | yes | Token read with `.strip()` before use; empty token skips header |
| V6 Cryptography | no | Plain file storage is the project decision (D-03) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token file readable by other users | Information Disclosure | 0o600 on write; `os.open()` with mode before write |
| Token logged to stderr/stdout | Information Disclosure | Do not log token value; log only "token found" or "token missing" |

## Sources

### Primary (HIGH confidence)
- [streamlink Twitch plugin docs](https://streamlink.github.io/cli/plugins/twitch.html) — confirmed `auth-token` cookie name, `--twitch-api-header Authorization=OAuth <token>` format
- `musicstreamer/ui/cookies_dialog.py` — Google WebKit2 subprocess pattern (direct code reference)
- `musicstreamer/player.py:270-292` — `_play_twitch()` implementation (direct code reference)
- `musicstreamer/constants.py` — `COOKIES_PATH` / `clear_cookies()` pattern (direct code reference)

### Secondary (MEDIUM confidence)
- [streamlink GitHub discussion #4400](https://github.com/streamlink/streamlink/discussions/4400) — subprocess list arg format for `--twitch-api-header`

## Metadata

**Confidence breakdown:**
- Streamlink flag format: HIGH — verified via official docs + GitHub discussion
- Twitch cookie name (`auth-token`): HIGH — verified via streamlink docs
- Login completion URL detection: MEDIUM — pattern inferred from Google login analogue; exact URLs need validation during implementation
- WebKit2 HttpOnly cookie access: MEDIUM — assumed based on working Google pattern

**Research date:** 2026-04-09
**Valid until:** 2026-07-09 (streamlink API is stable; Twitch cookie names rarely change)
