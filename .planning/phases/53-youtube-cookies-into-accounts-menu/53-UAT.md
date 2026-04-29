---
status: complete
phase: 53-youtube-cookies-into-accounts-menu
source:
  - 53-01-SUMMARY.md
  - 53-02-SUMMARY.md
  - 53-VERIFICATION.md
started: 2026-04-29T03:00:00Z
updated: 2026-04-29T03:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Hamburger menu — YouTube Cookies removed
expected: Open the app's hamburger menu (≡ icon, top-left of menu bar). The menu shows exactly 9 entries in this order: New Station, Discover Stations, Import Stations, Accent Color, Accounts, Equalizer, Stats for Nerds, Export Settings, Import Settings. There is NO standalone "YouTube Cookies" entry — that surface is gone.
result: pass

### 2. Accounts dialog — YouTube group + group order
expected: From the hamburger menu, click "Accounts". The dialog shows three sections stacked top-to-bottom in this exact order: YouTube, Twitch, AudioAddict. Each section is a labeled GroupBox with a status label and one button. The dialog renders cleanly — no scrollbars, no group title overlap, all text legible at default font size.
result: pass

### 3. Initial status — no cookies → Not connected
expected: In the Accounts dialog, the YouTube section status reads "Not connected" (assuming no cookies file present yet — if you already have ~/.local/share/musicstreamer/cookies.txt, this test should be run after the Disconnect flow in test 5). The button below reads "Import YouTube Cookies..." (with three trailing dots).
result: pass

### 4. Import cookies — full flow with toast + status flip
expected: In the Accounts dialog YouTube section, click "Import YouTube Cookies...". A new dialog opens titled "YouTube Cookies" with three tabs: File, Paste, Google Login. Use any tab to import valid YouTube cookies (Google Login is the most realistic — log in to a Google account that has watched a YouTube video recently). On success, the import dialog closes, a toast "YouTube cookies imported." appears on the main window, and the AccountsDialog YouTube section now shows "Connected" with button "Disconnect". (Cancel/close the import dialog first if you want to skip the actual import — toast won't fire.)
result: pass

### 5. Disconnect — confirm flow + status flip
expected: With YouTube showing "Connected" (from test 4), click "Disconnect" in the YouTube section. A confirmation dialog appears titled "Disconnect YouTube?" with message "This will delete your saved YouTube cookies. You will need to re-import to play cookie-protected YouTube streams." The default highlighted button is "No". Click "Yes". The cookies file at ~/.local/share/musicstreamer/cookies.txt is deleted, and the AccountsDialog YouTube section now reads "Not connected" with button "Import YouTube Cookies...".
result: pass

### 6. Twitch + AudioAddict groups unaffected (regression check)
expected: In the Accounts dialog, the Twitch group still shows its existing status ("Connected" or "Not connected") and Connect/Disconnect button — Phase 53 did not break Twitch flow. The AudioAddict group still shows "Saved" or "Not saved" with the Clear button. The Disconnect-YouTube action you ran in test 5 did NOT touch Twitch or AA state.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
