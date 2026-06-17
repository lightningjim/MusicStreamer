---
status: partial
phase: 89B-twitch-channel-avatar-fetch
source: [89B-VERIFICATION.md]
started: 2026-06-16
updated: 2026-06-16
---

## Current Test

number: 1
name: Live avatar auto-fetch in EditStationDialog
result: fix applied (commit ff027cf8) — re-testing in app
awaiting: user re-test (restart the app to load the GQL fix)

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

- truth: "twitch.tv URL in EditStationDialog fetches and shows the streamer avatar"
  status: fixed
  reason: "User reported 'No avatar found' despite a real channel avatar."
  severity: blocker
  test: 1
  root_cause: "The web auth-token cookie (client-id kimne78..., legacy v5 scopes) has no Helix REST access — api.twitch.tv/helix/users returns HTTP 404. CONTEXT D-06 / RESEARCH #1 wrongly assumed Bearer-framed Helix would work."
  fix: "Rewrote twitch_helix.fetch_channel_avatar to query gql.twitch.tv/gql user(login).profileImageURL with Authorization: OAuth + Client-Id (the streamlink credential). Commit ff027cf8. Verified live (twitchdev + lightningjim2 → valid PNGs) and via 40 unit tests."
  artifacts:
    - path: "musicstreamer/twitch_helix.py"
      issue: "Used Helix /users (no access for this token) → 404 → empty emit → 'No avatar found'"
  missing: []
