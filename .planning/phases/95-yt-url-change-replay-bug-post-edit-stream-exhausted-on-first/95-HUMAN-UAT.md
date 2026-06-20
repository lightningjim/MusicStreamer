---
status: partial
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
source: [95-VERIFICATION.md]
started: 2026-06-20
updated: 2026-06-20
---

## Current Test

[awaiting human testing]

## Tests

### 1. D-01 primary repro — YouTube URL edit, no spurious toast
expected: Play a YouTube station, edit its stream URL to a DIFFERENT working YouTube URL and save while playing. The new stream plays and NO "Stream exhausted" toast flashes (not even briefly) before it starts.
why_human: End-to-end depends on real yt-dlp resolution and the GStreamer bus-thread timing of the old stream's EOS error during the async resolve window — observable only with a live pipeline.
result: [pending]

### 2. CR-01 leak — edit YouTube → direct (non-YouTube) URL mid-resolve
expected: Play a YouTube station, then edit its URL to a direct/non-YouTube stream URL and save while the resolve is still in flight. The direct stream plays, AND a later genuine all-streams-failed exhaustion in the SAME session still surfaces a "Stream exhausted" toast (the in-flight gate did not leak / get stuck suppressed for the rest of the session).
why_human: The permanent-leak path requires a real resolve in flight and a real non-YouTube restart funnel; the regression is "no toast ever again," only observable across a live session.
result: [pending]

### 3. CR-01 spurious exhaustion — rapid YouTube A→B switch
expected: Rapidly switch from playing YouTube station A to YouTube station B (plain station change, no edit). No spurious "Stream exhausted" toast appears while B is still resolving.
why_human: Depends on the relative timing of A's late resolve failure vs B's resolve spawn on a real pipeline.
result: [pending]

### 4. D-03 genuine exhaustion still toasts exactly once
expected: Play a station whose streams are all broken/unreachable. A single "Stream exhausted" toast fires exactly once (legitimate exhaustion is not over-suppressed by the in-flight gate).
why_human: Confirms the gate does not over-correct; needs a real all-streams-failed station.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
