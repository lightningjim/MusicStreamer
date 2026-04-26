---
phase: 41-platform-media-keys
fixed_at: 2026-04-15T00:00:00Z
review_path: .planning/phases/41-platform-media-keys/41-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 41: Code Review Fix Report

**Fixed at:** 2026-04-15
**Source review:** .planning/phases/41-platform-media-keys/41-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `file://` URL not encoded — spaces in art cache path will break MPRIS clients

**Files modified:** `musicstreamer/media_keys/mpris2.py`
**Commit:** 7a6d745
**Applied fix:** Added `from urllib.request import pathname2url` import and replaced `f"file://{path}"` with `"file://" + pathname2url(path)` so special characters (including spaces in home directory paths) are percent-encoded.

### WR-02: D-Bus service name collision on second instance — uninformative error

**Files modified:** `musicstreamer/media_keys/mpris2.py`
**Commit:** 7a6d745
**Applied fix:** Replaced the bare `bus.lastError().message()` fallback with `bus.lastError().message() or "name already taken or bus error"` and updated the error message format to include the service name. Added a TODO comment noting multi-instance unique-suffix support as future work.

Note: WR-01 and WR-02 both modify `mpris2.py` and were applied in the same file before committing; they share commit 7a6d745.

### WR-03: `_on_media_key_play_pause` reads `_is_playing` after calling `_on_play_pause_clicked` — race if slot chains signals synchronously

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** a2cfc2c
**Applied fix:** Captured `was_playing = self.now_playing._is_playing` before the toggle call, then derived `new_state` from the captured value. This makes intent explicit and is immune to any intermediate state mutations from signal chains.

---

_Fixed: 2026-04-15_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
