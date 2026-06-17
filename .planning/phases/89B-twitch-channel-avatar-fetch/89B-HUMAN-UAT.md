---
status: partial
phase: 89B-twitch-channel-avatar-fetch
source: [89B-VERIFICATION.md]
started: 2026-06-16
updated: 2026-06-16
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live avatar auto-fetch in EditStationDialog
expected: With a valid `twitch-token.txt` (logged into Twitch via Accounts), pasting/editing a `https://www.twitch.tv/<streamer>` URL in EditStationDialog triggers the debounced auto-fetch and shows the streamer's profile image, circular-cropped, in the avatar preview. The "Refresh avatar" button is enabled for the twitch.tv URL.
result: [pending]

### 2. ICY-disabled cover-slot rendering
expected: A bound Twitch station with ICY disabled and a stored avatar shows the circular-cropped streamer avatar in the now-playing **cover slot** (not the left logo slot); the left logo slot is unchanged, so the same image is never shown twice. Sibling Twitch stations of the same streamer reuse the one cached `{provider_id}.png`.
result: [pending]

### 3. No-token / failure fallback UX
expected: With no `twitch-token.txt` (or an expired token → Helix 401, or a non-existent login → empty `data`), adding/editing a twitch.tv station shows a non-blocking inline message and **Save always succeeds**; the cover slot falls back to the station thumbnail (no crash, no blank). Optionally a hint points to the Accounts dialog to connect Twitch.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
