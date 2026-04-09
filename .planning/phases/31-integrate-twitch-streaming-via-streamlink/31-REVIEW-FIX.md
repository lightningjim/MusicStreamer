---
phase: 31-integrate-twitch-streaming-via-streamlink
fixed_at: 2026-04-09T00:00:00Z
review_path: .planning/phases/31-integrate-twitch-streaming-via-streamlink/31-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 31: Code Review Fix Report

**Fixed at:** 2026-04-09
**Source review:** `.planning/phases/31-integrate-twitch-streaming-via-streamlink/31-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `time.sleep(2)` blocks the GLib main thread in `_play_youtube`

**Files modified:** `musicstreamer/player.py`
**Commit:** 4eed93e
**Applied fix:** Replaced the `time.sleep(2)` + inline poll block with a `GLib.timeout_add(2000, _check_cookie_retry)` one-shot callback. The nested `_check_cookie_retry` function captures `cmd` and `env` from the enclosing scope and returns `False` so it only fires once. The `import sys` that was inline is now inside the callback (still deferred; IN-01 was out of scope but the `import glob` top-level move was not applied as it is info-only).

### WR-02: Offline detection checks `result.stdout` only — misses `stderr`

**Files modified:** `musicstreamer/player.py`
**Commit:** 4eed93e (same commit as WR-01 — both edits were in player.py)
**Applied fix:** Added `output = result.stdout + result.stderr` in the `_resolve` thread and changed the offline branch condition to `"No playable streams found" in output`, ensuring the check catches the error regardless of which stream streamlink writes it to.

### WR-03: `_on_twitch_offline` does not stop the pipeline or clear `_on_title`

**Files modified:** `musicstreamer/ui/main_window.py`
**Commit:** 43e0c95
**Applied fix:** Added `self.player.stop()` before `self._pause_timer()` in `_on_twitch_offline`. `Player.stop()` already clears `_on_title`, `_on_failover`, the streams queue, the yt proc, and sets the pipeline to NULL — exactly the cleanup needed.

---

_Fixed: 2026-04-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
