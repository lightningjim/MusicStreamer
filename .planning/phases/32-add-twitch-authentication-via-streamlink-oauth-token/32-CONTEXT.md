# Phase 32: Add Twitch authentication via streamlink OAuth token - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add Twitch authentication so streamlink passes an OAuth token when resolving Twitch URLs, eliminating pre-stream ads/promos for logged-in users. Includes a WebKit login flow, token storage, and a renamed "Accounts" dialog with YouTube and Twitch tabs.

</domain>

<decisions>
## Implementation Decisions

### Auth Method
- **D-01:** Use a WebKit2 WebView to open twitch.tv login page. User logs in normally (including 2FA if enabled). App captures the OAuth token from the session cookies after login completes.
- **D-02:** Pass the token to streamlink via `--twitch-api-header=Authorization=OAuth <token>` in the `_play_twitch()` subprocess call.

### Token Storage
- **D-03:** Store the Twitch OAuth token as a plain text file at `~/.local/share/musicstreamer/twitch-token.txt` with `0o600` permissions. Matches the existing YouTube cookies pattern (`COOKIES_PATH`).
- **D-04:** Add `TWITCH_TOKEN_PATH` constant in `constants.py` alongside `COOKIES_PATH`.

### UI Entry Point
- **D-05:** Rename the existing "YouTube Cookies" dialog to a general "Accounts" dialog. Rename the hamburger menu entry from "YouTube Cookies..." to "Accounts...".
- **D-06:** The Accounts dialog uses tabs — a "YouTube" tab (existing cookie UI, unchanged) and a "Twitch" tab with: "Log in to Twitch" button, login status display (logged in as X / not logged in), and "Log out" button.
- **D-07:** Rename `cookies_dialog.py` to `accounts_dialog.py` and `CookiesDialog` class to `AccountsDialog`.

### Claude's Discretion
- WebKit2 cookie extraction specifics (which cookie name holds the OAuth token)
- How to detect login completion in the WebView (URL redirect, cookie presence check)
- Status label format for logged-in state
- Whether to validate token with a Twitch API call before storing

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Auth Infrastructure
- `musicstreamer/ui/cookies_dialog.py` — Current YouTube cookies dialog (to be renamed to accounts_dialog.py). Has file picker, paste, and Google WebView login patterns.
- `musicstreamer/constants.py` — `COOKIES_PATH`, `clear_cookies()` — pattern for token file storage and cleanup.

### Player Integration
- `musicstreamer/player.py:270-292` — `_play_twitch()` method — needs `--twitch-api-header` argument when token exists.
- `musicstreamer/player.py:218-263` — `_play_youtube()` — reference for cookie file handling pattern with temp copy and cleanup.

### UI
- `musicstreamer/ui/main_window.py` — Hamburger menu wiring (currently opens CookiesDialog, needs to open AccountsDialog).

### Phase 31 Context
- `.planning/phases/31-integrate-twitch-streaming-via-streamlink/31-CONTEXT.md` — Twitch playback decisions this phase builds on.

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CookiesDialog` WebKit2 Google login flow — direct reference for Twitch WebView login
- `COOKIES_PATH` / `clear_cookies()` pattern — reuse for `TWITCH_TOKEN_PATH` / `clear_twitch_token()`
- `Adw.ViewStack` or tab patterns — for YouTube/Twitch tab switcher in Accounts dialog

### Established Patterns
- `os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600))` for secure file writes
- `GLib.idle_add` for cross-thread UI updates from WebView callbacks
- Hamburger menu action wiring in `main_window.py`

### Integration Points
- `_play_twitch()` subprocess call — add `--twitch-api-header` when token file exists
- Hamburger menu action — rename cookies action to accounts
- `constants.py` — add `TWITCH_TOKEN_PATH` and `clear_twitch_token()`

</code_context>

<specifics>
## Specific Ideas

- The YouTube cookies dialog already has a WebKit2 Google login flow — the Twitch login follows the same pattern but captures a different cookie
- streamlink's `--twitch-api-header` flag is the official way to pass auth; no need to write cookies to a file for streamlink
- The token file only needs to store the raw token string — no Netscape cookie format needed
- "Log out" just deletes the token file and updates the status label

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 32-add-twitch-authentication-via-streamlink-oauth-token*
*Context gathered: 2026-04-09*
