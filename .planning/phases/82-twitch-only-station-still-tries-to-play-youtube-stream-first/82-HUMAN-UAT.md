---
status: partial
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
source: [82-VERIFICATION.md]
started: 2026-05-22T13:50:00Z
updated: 2026-05-22T13:50:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Real-world Lofi Girl repro
expected: Pick Twitch stream in dropdown, pause player, resume — Twitch plays (not YT). Restart app, re-pick Lofi Girl — Twitch still selected and plays.
why_human: Requires live YT-resolution-failure path + Twitch stream; cannot be exercised with mocked GStreamer pipeline.
result: [pending]

### 2. Dropdown survives station re-click
expected: After picking Twitch on Lofi Girl, click a different station then click Lofi Girl again — Twitch plays, not YT.
why_human: Visual confirmation that all `_on_station_activated` entry points (D-03) honor the sticky pick; requires a live DB state with a real `preferred_stream_id` persisted.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
