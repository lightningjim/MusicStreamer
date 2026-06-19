---
status: partial
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
source: [95-VERIFICATION.md]
started: 2026-06-18
updated: 2026-06-18
---

## Current Test

[awaiting human testing]

## Tests

### 1. YouTube URL edit → first-play audio (the bug under fix)
expected: Play a YouTube station, edit its stream URL to a different valid YouTube source, and save. New audio starts immediately on the FIRST play — no "stream exhausted" toast, and no need to press play a second time. (Verifies D-01 + D-03 end-to-end with real yt-dlp resolution + GStreamer audio.)
result: [pending]

### 2. Metadata-only edit does NOT interrupt (D-02)
expected: While a YouTube station is playing, edit only its label/quality/codec (leave the URL unchanged) and save. Audio continues uninterrupted — no restart, no gap.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
