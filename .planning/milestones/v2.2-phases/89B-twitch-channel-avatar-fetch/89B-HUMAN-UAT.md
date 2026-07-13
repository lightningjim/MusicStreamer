---
status: resolved
phase: 89B-twitch-channel-avatar-fetch
source: [89B-VERIFICATION.md]
started: 2026-06-16
updated: 2026-06-17
---

## Current Test

[testing complete — 1 issue found on new-station-add path]

## Tests

### 1. Live avatar auto-fetch in EditStationDialog
expected: With a valid `twitch-token.txt` (logged into Twitch via Accounts), pasting/editing a `https://www.twitch.tv/<streamer>` URL in EditStationDialog triggers the debounced auto-fetch and shows the streamer's profile image, circular-cropped, in the avatar preview. The "Refresh avatar" button is enabled for the twitch.tv URL.
result: pass
note: Re-tested 2026-06-17 after GQL fix (commit ff027cf8). Avatar fetches and renders correctly.

### 2. ICY-disabled cover-slot rendering
expected: A bound Twitch station with ICY disabled and a stored avatar shows the circular-cropped streamer avatar in the now-playing **cover slot** (not the left logo slot); the left logo slot is unchanged, so the same image is never shown twice. Sibling Twitch stations of the same streamer reuse the one cached `{provider_id}.png`.
result: pass
note: Verified 2026-06-17 — cover slot shows circular avatar, left logo unchanged. Sibling-reuse sub-case N/A: Twitch is one live stream per channel by platform design (the multi-live-per-channel case is YouTube, covered by Phase 89.1 per-provider keying).

### 3. No-token / failure fallback UX
expected: With no `twitch-token.txt` (or an expired token → Helix 401, or a non-existent login → empty `data`), adding/editing a twitch.tv station shows a non-blocking inline message and **Save always succeeds**; the cover slot falls back to the station thumbnail (no crash, no blank). Optionally a hint points to the Accounts dialog to connect Twitch.
result: pass
note: Verified 2026-06-17 — non-blocking inline message, Save succeeds, cover slot falls back to station thumbnail. During this test the user observed a separate add-path defect (see Gaps, test: add-path).

## Summary

total: 3
passed: 3
issues: 1
pending: 0
skipped: 0
blocked: 0
note: 3/3 scripted tests pass. 1 issue discovered out-of-band on the new-station-add path (see Gaps, test: add-path).

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

- truth: "Adding a NEW Twitch station with a valid URL auto-fetches and shows the streamer avatar on first save (same as editing an existing station)"
  status: resolved
  resolved_by: "89B-03 (commit 29575e49) — synchronous _maybe_fetch_avatar_sync in _on_save + in-memory provider_id/name refresh. RED→GREEN TDD, 13 tests pass, 21-test regression sweep green. Verified 2026-06-17."
  reason: "User reported (2026-06-17 UAT): on new station add, the avatar fails to resolve for a valid station; re-opening the station in edit mode and saving again fetches it correctly."
  severity: major
  test: add-path
  root_cause: "On new-station add, self._station.provider_id is None (placeholder created by repo.create_station() with no provider) and is never updated in-memory. The debounced avatar fetch in _on_url_timer_timeout is gated on provider_id != None (Pitfall-7 guard, edit_station_dialog.py:1331), so it is skipped on the add path. _on_save derives+persists provider_id (line 1706) but never refreshes self._station.provider_id and never triggers a fetch before accept() — so first add never fetches. On re-edit, get_station() rehydrates provider_id from DB, the gate passes, and the fetch fires."
  artifacts:
    - path: "musicstreamer/ui_qt/edit_station_dialog.py"
      issue: "_on_save (~line 1699-1788) derives provider_id via repo.ensure_provider but never assigns self._station.provider_id / provider_name and never kicks the avatar fetch before accept(); guard at line 1331 then blocks add-path fetch since provider_id is None"
    - path: "musicstreamer/ui_qt/main_window.py"
      issue: "new station created via repo.create_station() (~line 1230) with provider_id NULL; edit path re-fetches via get_station() (~line 1254) which rehydrates provider_id (hence edit works)"
  missing:
    - "After provider_id = repo.ensure_provider(provider_name) in _on_save: assign self._station.provider_id = provider_id and self._station.provider_name = provider_name"
    - "Trigger the avatar fetch on the add path once provider_id is set, only when provider_avatar_path is empty (honor D-07 reuse gate + _force_avatar_refresh); ensure the fetch result is actually persisted before/independent of accept() teardown (worker QThread finished->_on_avatar_fetched slot delivery risk; prefer synchronous fetch-and-persist or fetch-before-accept)"
    - "Preserve D-04 blank-provider guard (line 1699) and Pitfall-7 single guard (line 1331 untouched)"
  debug_session: ".planning/debug/twitch-avatar-fails-on-new-add.md"
