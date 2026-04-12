---
phase: 37-station-list-now-playing
fixed_at: 2026-04-12T18:15:00Z
review_path: .planning/phases/37-station-list-now-playing/37-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 1
skipped: 1
status: partial
---

# Phase 37: Code Review Fix Report

**Fixed at:** 2026-04-12T18:15:00Z
**Source review:** .planning/phases/37-station-list-now-playing/37-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 1
- Skipped: 1

## Fixed Issues

### WR-01: Cover art race -- stale token never checked on delivery

**Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`, `tests/test_now_playing_panel.py`
**Commit:** 7143db0
**Applied fix:** Captured `_cover_fetch_token` at dispatch time in `_fetch_cover_art_async` and packed it into the signal payload as `"token:path"`. `_on_cover_art_ready` now unpacks and compares the token, discarding stale responses where a newer fetch is already in flight. Updated the test that calls `_on_cover_art_ready` directly to use the new `"token:path"` payload format.

## Skipped Issues

### WR-02: Station model `last_played_at` missing from test factory

**File:** `tests/test_main_window_integration.py:85-97`
**Reason:** Already fixed in current code -- `last_played_at=None` is explicitly present at line 96 of the factory function.
**Original issue:** The `_make_station` factory omits the `last_played_at` keyword, relying on the dataclass default. The reviewer suggested adding it explicitly for clarity.

---

_Fixed: 2026-04-12T18:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
