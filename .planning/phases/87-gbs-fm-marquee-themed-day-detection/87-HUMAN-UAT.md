---
status: partial
phase: 87-gbs-fm-marquee-themed-day-detection
source: [87-VERIFICATION.md]
started: 2026-06-15T00:00:00Z
updated: 2026-06-15T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live GBS.FM announcement banner
expected: Bind a GBS.FM station (with active Phase 76 cookies) and within ~60s the top-of-NowPlayingPanel banner shows the first pipe-segment of the marquee (or stays hidden if the marquee is empty). The × dismiss hides it and the same announcement does not re-appear until the marquee text changes. Re-binding to a non-GBS station hides the banner immediately; re-binding to GBS re-evaluates on the next poll.
result: [pending]

### 2. Themed-logo session override (LIVE WINDOW AVAILABLE NOW — Pride Month)
expected: When GBS.FM serves a themed logo, the `logo_label` slot in NowPlayingPanel shows the themed PNG for the session; `cover_label` is unchanged; no libnotify toast fires; the SQLite station record is unchanged after the session; the next app launch re-evaluates from scratch (no persistence).
result: [pending]
note: Today (2026-06-15) is **Pride Month** — a live themed-day window. If gbs.fm is currently serving a Pride-themed logo, this can be verified live right now instead of waiting for Halloween 2026-10-31. The hash-drift fallback (D-12) should catch the Pride logo via SHA-256 drift even though "pride" may not be in GBS_THEMED_DAY_KEYWORDS, applying the themed logo and emitting a structured INFO log. Capturing the live Pride logo+marquee now would also satisfy the `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` baseline-accretion follow-up early.

### 3. CR-01 thread safety on macOS/Windows
expected: Run the app on a GBS.FM station through a themed-day detection on macOS or Windows (where the GUI paint backend is stricter than Linux/XCB offscreen). No QPixmap-on-non-GUI-thread crash, warning, or corrupted pixmap; the themed logo renders correctly.
result: [pending]
note: Code review CR-01 (BLOCKER) — `QPixmap()` + `pix.loadFromData()` run on the `GbsMarqueeWorker` QThread (gbs_marquee.py:469-472). Qt does not guarantee QPixmap is safe off the GUI thread; Linux offscreen testing masks this. Recommended fix before shipping to macOS/Windows: emit raw `bytes` from the worker and construct the QPixmap inside `set_themed_logo_override` on the main thread. Run `/gsd:code-review 87 --fix` to apply.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
