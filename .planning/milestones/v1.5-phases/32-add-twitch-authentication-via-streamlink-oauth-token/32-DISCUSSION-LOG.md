# Phase 32: Add Twitch authentication via streamlink OAuth token - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 32-add-twitch-authentication-via-streamlink-oauth-token
**Areas discussed:** Auth method, Token storage, UI entry point

---

## Auth Method

| Option | Description | Selected |
|--------|-------------|----------|
| Paste token directly | User gets OAuth token manually and pastes it | |
| Browser cookie extraction | Extract Twitch auth token from browser cookies automatically | |
| Twitch login WebView | WebKit WebView to twitch.tv login, capture OAuth token from session | ✓ |

**User's choice:** Twitch login WebView
**Notes:** Familiar login flow, no manual steps. WebKit2 dependency already exists for YouTube Google login.

---

## Token Storage

| Option | Description | Selected |
|--------|-------------|----------|
| File in data dir | Plain text file at ~/.local/share/musicstreamer/twitch-token.txt with 0o600 | ✓ |
| SQLite settings table | Store via get_setting/set_setting in existing settings table | |

**User's choice:** File in data dir
**Notes:** Matches existing YouTube cookies pattern. Easy to inspect/delete independently.

---

## UI Entry Point

| Option | Description | Selected |
|--------|-------------|----------|
| Rename CookiesDialog to Auth dialog | General "Accounts" dialog with YouTube and Twitch tabs | ✓ |
| Separate Twitch dialog | New hamburger menu entry for independent Twitch dialog | |
| Add tab to existing CookiesDialog | Add Twitch tab without renaming | |

**User's choice:** Rename CookiesDialog to Accounts dialog
**Notes:** One menu entry covers both. Tabs for YouTube and Twitch. Hamburger entry renamed to "Accounts...".

---

## Claude's Discretion

- WebKit2 cookie extraction specifics
- Login completion detection mechanism
- Status label format
- Token validation approach

## Deferred Ideas

None — discussion stayed within phase scope
