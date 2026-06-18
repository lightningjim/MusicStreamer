---
status: partial
phase: 90-somafm-preroll-instrumentation
source: [90-VERIFICATION.md]
started: 2026-06-18T00:00:00Z
updated: 2026-06-18T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Manual all-stations SomaFM run-through (SOMA-PRE-04 verify-half)
expected: On a fresh launch, playing each SomaFM station plays a preroll where one is
available. `~/.local/share/musicstreamer/preroll-events.log` records, per station, the
decision path (`preroll_start` with the randomly-chosen URL, `preroll_skipped_throttle`,
`preroll_skipped_empty`, `preroll_handoff_complete`, or `preroll_error`). Boot Liquor in
particular plays a preroll on bind (the previously-reported miss is resolved). Repeated
binds of the same station show URL rotation (random.choice), confirming all preroll files
are reachable. No station with upstream prerolls is silently stuck.
result: [pending]

### 2. "Open preroll log" hamburger action (SOMA-PRE-02)
expected: The hamburger menu's "Open preroll log" entry opens
`~/.local/share/musicstreamer/preroll-events.log` in the OS default viewer. When the log
file does not yet exist, a toast explains it will appear after the first SomaFM bind
(no crash, no empty-file creation surprise).
result: [pending]

### 3. "Re-fetch SomaFM prerolls" hamburger action (SOMA-PRE-06)
expected: The hamburger menu's "Re-fetch SomaFM prerolls" entry re-fetches prerolls for
SomaFM stations with no local prerolls, shows a success toast reflecting the real number
of stations updated (0 if none needed / all rejected — no false success), and the
double-click guard prevents a second concurrent run while one is in flight. The app stays
responsive (work runs off the main thread).

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
