---
status: partial
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
source: [95-VERIFICATION.md]
started: 2026-06-19
updated: 2026-06-19
---

## Current Test

[awaiting human testing]

## Tests

### 1. YouTube URL edit → first-play audio, NO spurious toast (95-02 gap closure)
expected: Play a YouTube station, edit its URL to a different valid YouTube source, save. New audio starts immediately on the first play — and NO "Stream exhausted" toast appears at any point during the transition (this is the residual flash you reported, now fixed by the _recovery_seq guard). Control check: a station whose every stream genuinely fails should STILL show "Stream exhausted" exactly once — the fix must not over-suppress legitimate exhaustion.
why_human: End-to-end depends on real yt-dlp resolution, the GStreamer bus-thread timing of the old stream's EOS error, and live playbin3 audio output. The spurious-toast race is a QueuedConnection timing issue observable only with a real pipeline.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
