---
status: testing
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
source: [89-VERIFICATION.md]
started: 2026-06-16
updated: 2026-06-16
---

## Current Test

number: 2
name: Live avatar fetch roundtrip (ART-AVATAR-05)
expected: |
  Paste a real YouTube channel/video URL into EditStationDialog. Within ~1s of the
  500ms debounce settling, the inline preview shows the fetched avatar with a
  "Fetching avatar…" → "Avatar found" status. (Re-test after the playlist_items="0"
  fix — fetch should now return in ~1-2s instead of hanging.)
awaiting: user response

## Tests

### 1. Circular-crop visual quality (D-07, ART-AVATAR-06)
expected: For an ICY-disabled YouTube station with a stored avatar (e.g., Lofi Girl), the now-playing cover slot shows a clean circular-cropped avatar — antialiased edge, no border/ring, center-balanced, sized sensibly against adjacent square covers. Resize the panel through several tiers; the circle re-renders crisply at each size (no revert to thumbnail, no jaggies).
result: [pending]

### 2. Live avatar fetch roundtrip (ART-AVATAR-05)
expected: Paste a real YouTube channel/video URL into EditStationDialog. Within ~1s of the 500ms debounce settling, the inline preview shows the fetched avatar with a "Fetching avatar…" → "Avatar found" status. Click "Refresh avatar" — it re-fetches via the same async path. On a non-YouTube/bad URL, an inline "No avatar found" message shows and Save is still allowed (no block). (Automated tests mock the fetch; this exercises the real yt-dlp/YouTube CDN path.)
result: issue
reported: "I'm stuck at 'Fetching avatar...', I have no stations with any stored avatar yet"
severity: blocker
root_cause: "fetch_channel_avatar (yt_import.py:181) built yt-dlp opts with no playlist bound and no extract_flat. For a channel URL, yt-dlp then recursively extracts full metadata for every video in the channel (e.g. all of Lofi Girl), which never returns and is not bounded by the 10s urllib download timeout. The worker thread never emits finished, so the status stays on 'Fetching avatar…' forever and no avatar is ever stored (also blocking Tests 1 and 3)."
fix: "Added playlist_items='0' to the avatar fetch opts — bounds extraction to channel/playlist metadata only. Verified against @LofiGirl: 0 video entries extracted, avatar_uncropped thumbnail still present, returns in ~1-2s. Regression test: tests/test_yt_import_library.py::test_avatar_opts_bound_playlist_items_to_zero."
status_after_fix: needs-retest

### 3. Cached load persistence across dialog open/close (ART-AVATAR-08)
expected: After fetching an avatar and saving, close and reopen the app / re-bind the station. The cached avatar loads from the local PNG in well under 1s and displays as the circular cover for the ICY-disabled station, with no re-fetch. Deleting/corrupting the cached PNG cleanly falls back to the station thumbnail.
result: [pending]

## Summary

total: 3
passed: 0
issues: 1
pending: 2
skipped: 0
blocked: 0

## Gaps

- truth: "Live avatar fetch returns and shows the avatar (ART-AVATAR-05)"
  status: fixed-needs-retest
  reason: "User reported: stuck at 'Fetching avatar...' indefinitely; no avatar ever stored"
  severity: blocker
  test: 2
  root_cause: "fetch_channel_avatar opts omitted any playlist bound; channel URL triggered full per-video recursive extraction (unbounded by the 10s urllib timeout) so the worker never emitted finished"
  fix: "playlist_items='0' added to opts (yt_import.py); regression test test_avatar_opts_bound_playlist_items_to_zero"
  artifacts:
    - path: "musicstreamer/yt_import.py"
      issue: "avatar fetch opts had no playlist_items bound"
  missing: []
