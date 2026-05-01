---
status: testing
phase: 64-audioaddict-siblings-on-now-playing
source: [64-VERIFICATION.md, 64-VALIDATION.md]
started: 2026-05-01T00:00:00Z
updated: 2026-05-01T00:00:00Z
---

## Current Test

number: 1
name: Click-switches-playback UX feel
expected: |
  Launch the app. Play an AudioAddict station that you know has at least one cross-network sibling — for example, DI.fm "Ambient" with a ZenRadio "Ambient" station also in your library. Confirm the line "Also on: ZenRadio" appears below the station name on the Now Playing panel.
  Click "ZenRadio".
  After the click: the panel re-binds to ZenRadio's "Ambient" — name and logo update, the audio transitions to the ZenRadio stream, the "Connecting…" toast fires, Recently Played updates, and the OS media-keys metadata reflects the new station. The transition should feel intentional and clean — no audible glitch beyond the normal Connecting flow, no UI flicker, no orphaned state from the previous station.
awaiting: user response

## Tests

### 1. Click-switches-playback UX feel
expected: |
  Launch the app. Play an AudioAddict station that you know has at least one cross-network sibling — for example, DI.fm "Ambient" with a ZenRadio "Ambient" station also in your library. Confirm the line "Also on: ZenRadio" appears below the station name on the Now Playing panel.
  Click "ZenRadio".
  After the click: the panel re-binds to ZenRadio's "Ambient" — name and logo update, the audio transitions to the ZenRadio stream, the "Connecting…" toast fires, Recently Played updates, and the OS media-keys metadata reflects the new station. The transition should feel intentional and clean — no audible glitch beyond the normal Connecting flow, no UI flicker, no orphaned state from the previous station.
result: [pending]

### 2. Hidden-for-non-AA layout cleanliness
expected: |
  Play a non-AA station — for example, a YouTube stream or a Radio-Browser station. Confirm there is no "Also on:" line, and the station name + ICY title sit cleanly with no visual gap or stale spacing where the line would otherwise be.
  Then switch to an AA station that has siblings. Confirm the "Also on:" line appears with no layout pop — the rest of the panel doesn't shift unexpectedly.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
