---
status: passed
phase: 90-somafm-preroll-instrumentation
source: [90-VERIFICATION.md]
started: 2026-06-18T00:00:00Z
updated: 2026-06-18T00:00:00Z
---

## Current Test

[complete]

## Tests

### 1. Manual all-stations SomaFM run-through (SOMA-PRE-04 verify-half)
expected: On a fresh launch, playing each SomaFM station plays a preroll where one is
available; preroll-events.log records the decision path + chosen URL per station; Boot
Liquor plays a preroll on bind; repeated binds show random rotation.
result: passed — User confirmed across several stations: Boot Liquor and others that
previously did NOT play a preroll now play one audibly, AND the random selection rotates
as intended. Conclusion: the missing-preroll symptom is resolved (incidentally fixed by
unrelated code changes between phase creation and execution). No station found truly
broken → Phase 90b not needed.

### 2. "Open preroll log" hamburger action (SOMA-PRE-02)
expected: Opens preroll-events.log in the OS viewer; toast when the file does not exist yet.
result: passed (automated) — `test_open_preroll_log_absent_shows_toast` + wiring grep-verified
green; live OS file-open spot-check not separately reported by user (non-blocking).

### 3. "Re-fetch SomaFM prerolls" hamburger action (SOMA-PRE-06)
expected: Re-fetches empty SomaFM stations, toasts the real updated count, double-click guard holds.
result: passed (automated) — 14/14 `test_main_window_soma.py` incl. WR-01/WR-02 regression
tests green; live toast/timing spot-check not separately reported by user (non-blocking).

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None — core acceptance (audible preroll on bind + random rotation) confirmed by user;
secondary UI levers covered by passing automated tests.
