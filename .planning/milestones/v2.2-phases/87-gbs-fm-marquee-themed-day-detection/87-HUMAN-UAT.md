---
status: complete
phase: 87-gbs-fm-marquee-themed-day-detection
source: [87-VERIFICATION.md]
started: 2026-06-15T00:00:00Z
updated: 2026-06-15T11:30:00Z
gap_closure_landed: [87-07, 87-REVIEW-gap follow-up]
---

## Current Test

[testing complete — all 3 pass after 87-07 gap closure]

## Tests

### 1. Live GBS.FM announcement banner
expected: Bind a GBS.FM station (with active Phase 76 cookies) and within ~60s the top-of-NowPlayingPanel banner shows the first pipe-segment of the marquee (or stays hidden if the marquee is empty). The × dismiss hides it and the same announcement does not re-appear until the marquee text changes. Re-binding to a non-GBS station hides the banner immediately; re-binding to GBS re-evaluates on the next poll.
result: pass

### 2. Themed-logo session override (LIVE WINDOW AVAILABLE NOW — Pride Month)
expected: When GBS.FM serves a themed logo, the `logo_label` slot in NowPlayingPanel shows the themed PNG for the session; `cover_label` is unchanged; no libnotify toast fires; the SQLite station record is unchanged after the session; the next app launch re-evaluates from scratch (no persistence).
result: pass
prior_result: "issue (major) — Fail, still shows default. Themed logo at https://img.gbs.fm/NIgE8/yucEqesu87.png/raw . Log: gbs.marquee.fetch_failed url=https://gbs.fm/ error=URLError"
fix_landed: "87-07 — correlator now resolves the dynamic #leftmenulogo URL from homepage CSS (handles imgur + img.gbs.fm/.../raw) instead of static logo_3.png; WR-01 gate fix makes it fire even when the marquee is empty; User-Agent header added for the URLError."
reverified: "2026-06-15 — user confirmed live Pride logo swaps in the logo slot after 87-07 fix"
note: Today (2026-06-15) is **Pride Month** — a live themed-day window. If gbs.fm is currently serving a Pride-themed logo, this can be verified live right now instead of waiting for Halloween 2026-10-31. The hash-drift fallback (D-12) should catch the Pride logo via SHA-256 drift even though "pride" may not be in GBS_THEMED_DAY_KEYWORDS, applying the themed logo and emitting a structured INFO log. Capturing the live Pride logo+marquee now would also satisfy the `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` baseline-accretion follow-up early.

### 3. CR-01 thread safety on macOS/Windows
expected: Run the app on a GBS.FM station through a themed-day detection on macOS or Windows (where the GUI paint backend is stricter than Linux/XCB offscreen). No QPixmap-on-non-GUI-thread crash, warning, or corrupted pixmap; the themed logo renders correctly.
result: pass
prior_result: "blocked — Windows ran without crash but the swap never fired (Test 2 gap), so the QPixmap path was never exercised."
fix_landed: "87-07 cleared CR-01 at the source: worker emits raw bytes, QPixmap is built on the main thread (QPixmap import removed from gbs_marquee.py)."
reverified: "2026-06-15 — user confirmed on Windows: themed logo renders cleanly during the live swap, no QPixmap thread warning/crash"
note: Code review CR-01 (BLOCKER) — `QPixmap()` + `pix.loadFromData()` run on the `GbsMarqueeWorker` QThread (gbs_marquee.py:469-472). Qt does not guarantee QPixmap is safe off the GUI thread; Linux offscreen testing masks this. Recommended fix before shipping to macOS/Windows: emit raw `bytes` from the worker and construct the QPixmap inside `set_themed_logo_override` on the main thread. Run `/gsd:code-review 87 --fix` to apply.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Binding GBS.FM during a live themed-day window swaps the Now Playing logo slot to the themed logo for the session (SC1 / GBS-THEME-01..05)"
  status: failed
  reason: "User reported: Fail, still shows default. Live themed logo is served at https://img.gbs.fm/NIgE8/yucEqesu87.png/raw (hashed img.gbs.fm CDN path, not a static logo_3.png). App log shows: gbs.marquee.fetch_failed url=https://gbs.fm/ error=URLError"
  severity: major
  test: 2
  root_cause: "Themed-day correlator hashes a HARDCODED STATIC logo URL (gbs_api.GBS_STATION_METADATA['logo_url'] = https://gbs.fm/images/logo_3.png) that never changes for themed days. The actual themed logo is referenced DYNAMICALLY in the homepage CSS as `#leftmenulogo {background-image:url(...)}` and the URL rotates per theme and even per host — Memorial Day harvest = https://i.imgur.com/l27hhaY.png, Pride 2026 = https://img.gbs.fm/NIgE8/yucEqesu87.png/raw. Because logo_3.png never drifts, compute_logo_theme never sees a non-baseline hash and the session override never fires. (Plan 87-01 actually CAPTURED the correct i.imgur URL in the homepage fixture, but Plan 87-04 ignored it and assumed a static logo_3.png.)"
  artifacts:
    - path: "musicstreamer/gbs_api.py:54"
      issue: "GBS_STATION_METADATA['logo_url'] hardcoded to /images/logo_3.png — not where the themed logo lives"
    - path: "musicstreamer/gbs_marquee.py:319-348 (_fetch_logo_bytes)"
      issue: "fetches the static logo_url instead of resolving the live #leftmenulogo background-image from the homepage HTML"
    - path: "musicstreamer/gbs_marquee.py:54-75 (GBS_LOGO_BASELINE_HASHES)"
      issue: "baseline hashes are moot while the wrong asset is fetched; needs the canonical (non-themed) #leftmenulogo hash"
  missing:
    - "Resolve the live themed-logo URL by parsing the homepage HTML for `#leftmenulogo {background-image:url('...')}` (reuse the homepage bytes already fetched for the marquee — single fetch), then fetch THAT URL, hash, and correlate"
    - "Handle arbitrary off-site logo hosts (i.imgur.com, img.gbs.fm, etc.) — do not assume a gbs.fm path"
    - "Re-baseline GBS_LOGO_BASELINE_HASHES with the canonical non-themed #leftmenulogo hash so non-themed days correctly suppress the override"
    - "(secondary) Investigate intermittent URLError on https://gbs.fm/ marquee fetch (gbs.marquee.fetch_failed at 10:20:18) — Test 1 passed so the path mostly works; confirm whether anonymous fallback needs a User-Agent/header or it is transient"
  debug_session: ""
  observed_clues:
    - "gbs.marquee.fetch_failed url=https://gbs.fm/ error=URLError — worker fetch to gbs.fm/ raises urllib URLError (quiet-fail path D-18 fired)"
    - "Actual themed logo URL is https://img.gbs.fm/NIgE8/yucEqesu87.png/raw (img.gbs.fm hashed path) — may differ from the logo URL the correlator fetches/baselines"
    - "Test 1 (announcement banner) PASSED, so some marquee data reached the UI earlier this session; the 10:20 fetch_failed indicates the fetch is at least intermittently erroring"
