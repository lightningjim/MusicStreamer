---
status: superseded
phase: 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug
source: [78-VERIFICATION.md]
started: 2026-05-17T00:00:00Z
updated: 2026-05-25T00:00:00Z
superseded_by: "Phase 84 (BUG-09 Commit B shipped 2026-05-24; statistical closure gate WAIVED per 84-D-13 — 12 events/7 days insufficient sample; new 2-week ship+monitor window now lives in 84-VERIFICATION.md human_verification block)"
---

## Current Test

awaiting human testing — Commit A is the harvest-infrastructure half of a two-stage phase per CONTEXT.md D-01. The single open UAT item below is the ~1-week real-world A/B baseline accumulation that drives Commit B's planning pass.

## Tests

### 1. Harvest week — real-world A/B baseline accumulation
expected: After Commit A ships (this commit and below), launch MusicStreamer via the GNOME `.desktop` entry (NOT terminal — the whole point of Commit A is to capture data under daily-use launch context). Run normal daily-use sessions for approximately one week. Verify on inspection:
  - `~/.local/share/musicstreamer/buffer-events.log` accumulates `buffer_underrun ...` INFO lines whenever a buffer cycle closes (recovered / failover / stop / pause / shutdown).
  - The `Underruns: {N}` row in the hamburger-menu stats-for-nerds widget increments live during sessions (when the stats widget is toggled on).
  - File rotates correctly past 1MB without losing data: `ls ~/.local/share/musicstreamer/buffer-events.log*` will show at most `buffer-events.log`, `.log.1`, `.log.2`, `.log.3` (backupCount=3 cap).
  - The existing `Buffering…` toast still fires only on cycles exceeding the 1500ms dwell threshold (Phase 62 D-07 invariant preserved — Commit A added no UX changes).
  Sample count + dropout pattern observed during the week becomes the `<data-summary>` block inserted at the top of `78-CONTEXT.md` before Commit B's planning pass. SC #3 closure (demonstrable reduction in dropout count) remains gated on Commit B per CONTEXT D-01 — not on this UAT.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
