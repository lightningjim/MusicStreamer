---
status: partial
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
source: [89-VERIFICATION.md]
started: 2026-06-16
updated: 2026-06-16
---

## Current Test

[awaiting human testing]

## Tests

### 1. Circular-crop visual quality (D-07, ART-AVATAR-06)
expected: For an ICY-disabled YouTube station with a stored avatar (e.g., Lofi Girl), the now-playing cover slot shows a clean circular-cropped avatar — antialiased edge, no border/ring, center-balanced, sized sensibly against adjacent square covers. Resize the panel through several tiers; the circle re-renders crisply at each size (no revert to thumbnail, no jaggies).
result: [pending]

### 2. Live avatar fetch roundtrip (ART-AVATAR-05)
expected: Paste a real YouTube channel/video URL into EditStationDialog. Within ~1s of the 500ms debounce settling, the inline preview shows the fetched avatar with a "Fetching avatar…" → "Avatar found" status. Click "Refresh avatar" — it re-fetches via the same async path. On a non-YouTube/bad URL, an inline "No avatar found" message shows and Save is still allowed (no block). (Automated tests mock the fetch; this exercises the real yt-dlp/YouTube CDN path.)
result: [pending]

### 3. Cached load persistence across dialog open/close (ART-AVATAR-08)
expected: After fetching an avatar and saving, close and reopen the app / re-bind the station. The cached avatar loads from the local PNG in well under 1s and displays as the circular cover for the ICY-disabled station, with no re-fetch. Deleting/corrupting the cached PNG cleanly falls back to the station thumbnail.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
