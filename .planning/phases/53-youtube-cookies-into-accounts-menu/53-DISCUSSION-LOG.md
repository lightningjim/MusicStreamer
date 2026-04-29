# Phase 53: YouTube Cookies into Accounts Menu - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 53-youtube-cookies-into-accounts-menu
**Areas discussed:** YouTube section shape, Clear/disconnect cookies, Group ordering, Standalone dialog fate, AA streamkey entry (deferred)

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| YouTube section shape | How does the YouTube row appear inside AccountsDialog? Three real choices: status+button (parity with Twitch/AA), action-button-only (minimal), or inline 3-tab UI embedded in the group. | ✓ |
| Clear/disconnect cookies | Should the YouTube section offer a 'Disconnect' / 'Clear cookies' button (parity with Twitch Disconnect + AA Clear)? | ✓ |
| Group ordering | Order of the three groups inside AccountsDialog. | ✓ |
| Standalone dialog fate | If the section opens the existing CookieImportDialog, do we keep it untouched, refactor it into a reusable widget, or revisit only if shape forces it? | ✓ |

**User's notes:** Kyle added a fifth concern during selection — "Also need a proper indication that there is a cookie saved for YT. Right now it just is assumed when saved it's there." Folded directly into the YouTube section shape area (status+button option addresses it).

---

## YouTube section shape

### Q1: How should the YouTube row appear inside AccountsDialog?

| Option | Description | Selected |
|--------|-------------|----------|
| Status + action button (Recommended) | Mirrors Twitch/AA: PlainText status label ('Connected' / 'Not connected') based on cookies.txt presence, plus an action button. Reuses existing CookieImportDialog as a child dialog. Adds ~15 lines. | ✓ |
| Action button only | Single button 'Import YouTube Cookies...' in the YouTube QGroupBox, no status label. Smallest diff but does NOT address the 'proper indication' concern. | |
| Inline 3-tab UI | Embed the 3-tab File/Paste/Google widget directly inside the YouTube QGroupBox. Most integrated, but risks SC #3 visual crowding. | |

**User's choice:** Status + action button (Recommended).
**Notes:** Directly addresses Kyle's "proper indication a cookie is saved" concern via file-existence check on `paths.cookies_path()`, mirroring how Twitch checks `twitch_token_path()`.

### Q2: What determines the 'Connected' / 'Not connected' label for YouTube?

| Option | Description | Selected |
|--------|-------------|----------|
| File-existence only (Recommended) | os.path.exists(paths.cookies_path()) — mirrors Twitch's check exactly. Phase 999.7's auto-clear-on-read provides corruption recovery. | ✓ |
| Existence + corruption check | Existence AND cookie_utils.is_cookie_file_corrupted() returns False. Slight latency but never lies about a known-bad file. | |
| Three explicit states | 'Connected' / 'Corrupted (will auto-clear)' / 'Not connected' — surfaces auto-clear as a permanent indicator. | |

**User's choice:** File-existence only (Recommended).
**Notes:** Simplest, consistent with Twitch precedent, and Phase 999.7's auto-clear-on-read remains the corruption recovery path (status display lying briefly is acceptable).

### Q3: What does the YouTube 'Disconnect' button actually do?

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm + delete cookies.txt (Recommended) | Mirrors Twitch's Disconnect. Yes/No confirm 'This will delete your saved YouTube cookies...' Then os.remove(paths.cookies_path()). | ✓ |
| Delete with no confirmation | Single click → immediate delete. Snappier but inconsistent with Twitch/AA. | |
| Defer Disconnect to a separate phase | Don't add a Disconnect button at all in Phase 53 — just status + Import. | |

**User's choice:** Confirm + delete cookies.txt (Recommended).
**Notes:** Default button = No (consistent with Twitch's `QMessageBox.StandardButton.No` default).

### Q4: After a successful import in CookieImportDialog, what happens?

| Option | Description | Selected |
|--------|-------------|----------|
| Dialog closes, AccountsDialog refreshes + toast (Recommended) | CookieImportDialog auto-closes (already does via self.accept()), AccountsDialog re-runs _update_status(), toast fires through MainWindow.show_toast. AccountsDialog gains a toast_callback param. | ✓ |
| Dialog closes, no auto-refresh | CookieImportDialog closes but AccountsDialog status stays stale until reopened. | |
| AccountsDialog also closes after import | Both dialogs dismiss after successful import. | |

**User's choice:** Dialog closes, AccountsDialog refreshes + toast (Recommended).
**Notes:** Drives the AccountsDialog signature change (toast_callback param) — primary integration decision.

### Q5: Button label when 'Not connected'?

| Option | Description | Selected |
|--------|-------------|----------|
| Import YouTube Cookies... (Recommended) | Matches existing CookieImportDialog window title verb. Trailing ellipsis = Qt convention for 'opens another dialog'. | ✓ |
| Connect YouTube | Mirrors Twitch's 'Connect Twitch' verb. Cleaner parallel, but cookie-import isn't really 'connecting'. | |
| Set up YouTube... | Generic verb, sidesteps the import-vs-connect tension. Less informative. | |

**User's choice:** Import YouTube Cookies... (Recommended).

---

## Clear/disconnect cookies

Resolved by YouTube section shape Q3 — Disconnect button with `QMessageBox.question` Yes/No confirm + `os.remove(paths.cookies_path())`. No separate questions asked.

---

## Group ordering

### Q1: After adding YouTube, what order should the three QGroupBoxes appear?

| Option | Description | Selected |
|--------|-------------|----------|
| Twitch → YouTube → AudioAddict (initial recommendation) | Both video/cookie-based providers stay together at the top; AudioAddict (key-only) below. | |
| Twitch → AudioAddict → YouTube | Append-only: existing order preserved, YouTube tacked on at the bottom. | |
| Alphabetical: AudioAddict → Twitch → YouTube | Sorted by display name. | |
| YouTube → Twitch → AudioAddict (user override via free-text) | User-specified ordering — YouTube first, Twitch second, AudioAddict third. | ✓ |

**User's choice:** YouTube → Twitch → AudioAddict.
**Notes:** First-pass question was rejected. User clarified intent: place YouTube first to match its newly-elevated position in the user's mental model, Twitch second to preserve it as the established account surface, AudioAddict third.

### Q2: AA streamkey entry from AccountsDialog (raised by user)

User asked: "Also is there a way we can include the ability to set the AA streamkey from here? Not just the import?" Phase 48 D-04 explicitly carved AccountsDialog as read-only for AA — reversing it is a legitimate symmetric polish but a new write capability outside Phase 53's scope.

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to follow-up phase (Recommended) | Capture in Phase 53 deferred ideas. Run /gsd-add-phase after Phase 53 ships. | ✓ |
| Fold into Phase 53 anyway | Expand scope, amend ROADMAP SCs, broaden risk. | |
| Skip / don't pursue | Keep Phase 48 D-04 as-is permanently. | |

**User's choice:** Defer to follow-up phase (Recommended).

---

## Standalone dialog fate

Resolved by YouTube section shape Q1 — keeping `CookieImportDialog` unchanged and reused as a child dialog launched from inside `AccountsDialog`. No separate questions asked.

---

## Claude's Discretion

- Slot/handler attribute names (`_on_youtube_action_clicked`, `_youtube_status_label`, `_youtube_action_btn`, `_youtube_box`).
- Whether the YouTube `QGroupBox` body uses the same `status_font` instance as Twitch (sharing is fine — read-only after `setPointSize`).
- Whether the Disconnect confirm message wording exactly matches the draft or is reworded for tone consistency.
- Whether `AccountsDialog._toast_callback` is stored as `self._toast` (matching `CookieImportDialog`) or as `self._toast_callback`.
- Whether `os.remove(paths.cookies_path())` is wrapped in try/except `FileNotFoundError` (recommendation: yes, matches Twitch precedent).
- Whether `_update_status()` runs unconditionally after `dlg.exec()` returns or only on `QDialog.DialogCode.Accepted` (recommendation: unconditional — idempotent).
- Whether the new YouTube group is built via a private builder method or inline in `__init__` (existing groups are inline; staying inline is consistent).

---

## Deferred Ideas

- **Set/update AudioAddict listen key from AccountsDialog** — symmetric polish reversing Phase 48 D-04. Captured for a follow-up phase via `/gsd-add-phase`.
- **Surfacing YouTube "Connected" status outside AccountsDialog** (Now Playing badge, startup toast, tree indicator) — not requested.
- **Three explicit cookie-status states** — considered and rejected in favor of two-state parity with Twitch/AA.
- **Refactoring CookieImportDialog into a reusable embeddable widget** — only relevant if a future phase needs the import flow inline (non-modal).
- **Generalized "any cookie-auth provider" abstraction** — three providers isn't enough to abstract; revisit if a fourth cookie-auth provider lands.
