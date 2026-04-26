---
phase: 37-station-list-now-playing
reviewed: 2026-04-12T18:45:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/station_tree_model.py
  - musicstreamer/ui_qt/toast.py
  - musicstreamer/ui_qt/icons.qrc
  - musicstreamer/ui_qt/icons_rc.py
  - tests/test_main_window_integration.py
  - tests/test_now_playing_panel.py
  - tests/test_station_list_panel.py
  - tests/test_station_tree_model.py
  - tests/test_toast_overlay.py
  - tests/test_ui_qt_scaffold.py
  - musicstreamer/__main__.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 37: Code Review Report (Re-review)

**Reviewed:** 2026-04-12T18:45:00Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Re-review after prior round fixes. The cover art race condition (prior WR-01) is correctly fixed -- `_fetch_cover_art_async` now packs the token into the signal payload and `_on_cover_art_ready` compares it against `_cover_fetch_token` to discard stale responses. The `__main__.py` fix passing `player` and `repo` to `MainWindow(player, repo)` is correct and matches the constructor signature `__init__(self, player, repo, parent=None)`.

Prior IN-03 (play/pause state not updating on toggle) is promoted to a Warning -- it is a user-facing bug, not just a style issue.

## Warnings

### WR-01: Play/pause button click does not update playing state or icon

**File:** `musicstreamer/ui_qt/now_playing_panel.py:280-284`
**Issue:** `_on_play_pause_clicked` calls `self._player.pause()` or `self._player.play(self._station)` but never calls `self.on_playing_state_changed()` to update the button icon and `_is_playing` flag. After clicking pause, the button still shows the pause icon (tooltip "Pause") and `_is_playing` remains `True`, so the next click calls `pause()` again instead of toggling back. The only callers of `on_playing_state_changed` are `MainWindow._on_station_activated` (initial play), `_on_failover(None)`, and `_on_offline` -- none of which fire on a simple pause/resume cycle. This means the play/pause toggle is broken after first use.
**Fix:**
```python
def _on_play_pause_clicked(self) -> None:
    if self._is_playing:
        self._player.pause()
        self.on_playing_state_changed(False)
    elif self._station is not None:
        self._player.play(self._station)
        self.on_playing_state_changed(True)
```

## Info

### IN-01: Duplicate `_FALLBACK_ICON` constant across three modules

**File:** `musicstreamer/ui_qt/station_list_panel.py:35`, `musicstreamer/ui_qt/station_tree_model.py:39`, `musicstreamer/ui_qt/now_playing_panel.py:47`
**Issue:** All three modules define the same fallback icon path string. Consider extracting to a shared constant if more modules adopt it.
**Fix:** Move to a shared location or accept as intentional encapsulation.

### IN-02: Inconsistent `Optional[X]` vs `X | None` style in station_tree_model.py

**File:** `musicstreamer/ui_qt/station_tree_model.py:18,32-33,56`
**Issue:** Uses `from typing import Optional` and `Optional["_TreeNode"]` while peer modules (`main_window.py`, `station_list_panel.py`) use PEP 604 `X | None` style. Both are valid with `from __future__ import annotations`.
**Fix:** Align to `X | None` for consistency, or leave as-is.

---

_Reviewed: 2026-04-12T18:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
