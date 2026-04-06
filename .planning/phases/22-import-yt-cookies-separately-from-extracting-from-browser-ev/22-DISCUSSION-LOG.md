# Phase 22: Import YT Cookies - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 22-import-yt-cookies-separately-from-extracting-from-browser-ev
**Areas discussed:** Cookie input method, Cookie storage & lifecycle, Settings UI placement, yt-dlp/mpv integration

---

## Cookie Input Method

| Option | Description | Selected |
|--------|-------------|----------|
| File picker only | User exports cookies.txt via browser extension, picks file in-app | |
| File picker + paste | File picker plus text area for raw Netscape cookie format | |
| File picker + paste + Google login | All three methods: file, paste, and browser login flow | |

**User's choice:** File picker + paste + Google login (all three methods)
**Notes:** User wants all three input methods available

| Option | Description | Selected |
|--------|-------------|----------|
| Equal tabs | Three tabs: File, Paste, Login — no hierarchy | |
| Primary + fallback | File picker main, paste and login under 'Advanced' expander | ✓ |

**User's choice:** Primary + fallback — file picker prominent, others under expander
**Notes:** None

---

## Cookie Storage & Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| App data dir | ~/.local/share/musicstreamer/cookies.txt — alongside DB and assets | ✓ |
| yt-dlp config dir | ~/.config/yt-dlp/cookies.txt — shared with other yt-dlp uses | |
| User's choice | Store wherever user puts it, save path in SQLite settings | |

**User's choice:** App data dir
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only | User re-imports when things stop working. Show 'last imported' date. | ✓ |
| Detect + prompt | Prompt on auth errors to re-import cookies | |
| Both | Manual always available plus auto-detect auth failures | |

**User's choice:** Manual only
**Notes:** None

---

## Settings UI Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Header menu item | Hamburger menu with 'YouTube Cookies...' option opening a dialog | ✓ |
| Import dialog tab | Add 'Cookies' tab to existing ImportDialog | |
| Standalone dialog | New 'Cookie Manager' dialog from header bar | |
| Preferences window | Adw.PreferencesWindow with YouTube section | |

**User's choice:** Header menu item
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Expander for extras | File picker top, 'Other methods' expander with paste + login | ✓ |
| Tabs for each method | Three equal tabs: File, Paste, Login | |

**User's choice:** Expander for extras
**Notes:** None

---

## yt-dlp/mpv Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Always if available | Pass cookies to every yt-dlp/mpv call when file exists | ✓ |
| Only on failure | Try without first, retry with cookies on auth error | |

**User's choice:** Always if available
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, disable browser extraction | Pass --no-cookies-from-browser to prevent GNOME keyring issue | ✓ |
| No, leave default | Only pass --cookies when file exists, leave browser extraction as fallback | |

**User's choice:** Yes, disable browser extraction
**Notes:** None

---

## Claude's Discretion

- Exact Adw widget choices for dialog layout
- Google login implementation approach
- Cookie content validation
- Error handling for failed Google login

## Deferred Ideas

None
