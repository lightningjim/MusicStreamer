---
phase: 37-station-list-now-playing
reviewed: 2026-04-12T18:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/station_tree_model.py
  - musicstreamer/ui_qt/toast.py
  - tests/test_main_window_integration.py
  - tests/test_now_playing_panel.py
  - tests/test_station_list_panel.py
  - tests/test_station_tree_model.py
  - tests/test_ui_qt_scaffold.py
  - musicstreamer/ui_qt/icons.qrc
  - musicstreamer/ui_qt/icons_rc.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 37: Code Review Report

**Reviewed:** 2026-04-12T18:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 37 adds StationListPanel, NowPlayingPanel, ToastOverlay, and StationTreeModel to the Qt main window. The code is well-structured with consistent patterns: bound-method-only signal wiring (QA-05), PlainText lockdown on untrusted ICY metadata, QPixmapCache-backed icon loading, and proper Qt parent-ownership. Two warnings around race safety in the cover art path and a missing `last_played_at` field in a test factory. Three minor info items for code hygiene.

## Warnings

### WR-01: Cover art race -- stale token never checked on delivery

**File:** `musicstreamer/ui_qt/now_playing_panel.py:297-312`
**Issue:** `_fetch_cover_art_async` increments `_cover_fetch_token` but the token is never checked in `_on_cover_art_ready`. If two rapid title changes fire two fetches, the first (slower) fetch can overwrite the second (faster) fetch's cover art with a stale image. The token field exists but is unused.
**Fix:** Capture the token at dispatch time and compare on delivery:
```python
def _fetch_cover_art_async(self, icy_title: str) -> None:
    self._cover_fetch_token += 1
    token = self._cover_fetch_token
    emit = self.cover_art_ready.emit

    def _cb(path_or_none):
        emit(f"{token}:{path_or_none or ''}")

    fetch_cover_art(icy_title, _cb)

def _on_cover_art_ready(self, payload: str) -> None:
    token_str, _, path = payload.partition(":")
    if int(token_str) != self._cover_fetch_token:
        return  # stale response
    if not path:
        self._show_station_logo_in_cover_slot()
        return
    self._set_cover_pixmap(path)
```
Alternatively, use a separate Signal with `(int, str)` signature to avoid string packing.

### WR-02: Station model `last_played_at` missing from test factory in test_main_window_integration

**File:** `tests/test_main_window_integration.py:82-93`
**Issue:** The `_make_station` factory omits the `last_played_at` keyword, relying on the dataclass default (`None`). This works today but is fragile -- if the field ever loses its default or becomes required, all 11+ call sites break silently. The other test files (`test_station_list_panel.py`, `test_station_tree_model.py`) also omit it. Consistency with the `test_now_playing_panel.py` factory (which passes `streams=` explicitly) would be better.
**Fix:** Add `last_played_at=None` explicitly in the factory for clarity, or leave as-is if the team considers dataclass defaults sufficient. Low urgency.

## Info

### IN-01: Unused import `Optional` from `typing` in `station_tree_model.py`

**File:** `musicstreamer/ui_qt/station_tree_model.py:18`
**Issue:** `from typing import Optional` -- this module uses `Optional` in type hints on lines 32-33 and 56, so it is actually used. However, `from __future__ import annotations` is active, which means `Optional["_TreeNode"]` on line 32 could be written as `_TreeNode | None` using PEP 604 syntax. Not a bug, just inconsistent with the `| None` style used in `main_window.py` and `station_list_panel.py`.
**Fix:** Replace `Optional[X]` with `X | None` for consistency, or leave as-is.

### IN-02: Duplicate `_FALLBACK_ICON` constant across modules

**File:** `musicstreamer/ui_qt/station_list_panel.py:35` and `musicstreamer/ui_qt/station_tree_model.py:39`
**Issue:** Both modules define `_FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"` (private module constant) and `now_playing_panel.py:47` defines the same string. The station_list_panel also duplicates the icon-loading logic from station_tree_model. Consider extracting to a shared constant.
**Fix:** Move to a shared location (e.g., `musicstreamer/ui_qt/constants.py`) or accept the duplication as intentional encapsulation.

### IN-03: `_on_play_pause_clicked` does not update playing state after resume

**File:** `musicstreamer/ui_qt/now_playing_panel.py:280-284`
**Issue:** When `_on_play_pause_clicked` calls `self._player.pause()`, the panel does not update `_is_playing` to `False`. Similarly, calling `self._player.play(station)` does not set `_is_playing = True`. The panel relies on `MainWindow._on_station_activated` to call `on_playing_state_changed(True)`, but that path only runs on initial station selection -- not on play/pause toggle. If the Player emits a signal that MainWindow catches to update state, this is fine. If not, the play/pause button will get stuck after one toggle.
**Fix:** Either call `self.on_playing_state_changed(not self._is_playing)` after the player call, or confirm that Player emits a state-change signal that MainWindow relays back. This is likely a real bug if pause/resume is exercised outside of station activation.

---

_Reviewed: 2026-04-12T18:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
